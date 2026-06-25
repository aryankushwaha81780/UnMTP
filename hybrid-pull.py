import socket
import os
import struct
import tarfile
import time
import subprocess
import re
import sys
import os

def get_default_gateway_windows():
    # try powershell first, it's faster
    try:
        cmd = ["powershell", "-Command", "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object -ExpandProperty NextHop"]
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore', timeout=3.0, check=True)
        for line in result.stdout.splitlines():
            ip = line.strip()
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) and ip != '0.0.0.0':
                return ip
    except Exception:
        pass

    # fallback: parse ipconfig
    try:
        result = subprocess.run(['ipconfig'], capture_output=True, text=True, errors='ignore', timeout=3.0, check=True)
        output = result.stdout
        
        lines = output.splitlines()
        current_adapter = None
        adapter_data = {}
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if line.endswith(':'):
                current_adapter = stripped[:-1]
                adapter_data[current_adapter] = []
            elif current_adapter:
                adapter_data[current_adapter].append(stripped)
                
        # look for wifi adapter first
        wifi_section_lines = None
        for adapter, section_lines in adapter_data.items():
            if "wi-fi" in adapter.lower():
                wifi_section_lines = section_lines
                break
                
        gateway_candidates = []
        if wifi_section_lines:
            gateway_idx = -1
            for i, line in enumerate(wifi_section_lines):
                if "default gateway" in line.lower():
                    gateway_idx = i
                    break
            if gateway_idx != -1:
                parts = wifi_section_lines[gateway_idx].split(':', 1)
                if len(parts) > 1:
                    raw_val = parts[1].strip()
                    if raw_val:
                        gateway_candidates.append(raw_val)
                # sometimes gateway has extra lines below it (ipv6 etc)
                for j in range(gateway_idx + 1, len(wifi_section_lines)):
                    next_line = wifi_section_lines[j]
                    if ':' in next_line:
                        break
                    if next_line.strip():
                        gateway_candidates.append(next_line.strip())
                        
        # no wifi? try any adapter that has an ipv4 address
        if not gateway_candidates:
            for adapter, section_lines in adapter_data.items():
                has_ipv4 = any("ipv4 address" in line.lower() for line in section_lines)
                if not has_ipv4:
                    continue
                for i, line in enumerate(section_lines):
                    if "default gateway" in line.lower():
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            raw_val = parts[1].strip()
                            if raw_val:
                                gateway_candidates.append(raw_val)
                        for j in range(i + 1, len(section_lines)):
                            next_line = section_lines[j]
                            if ':' in next_line:
                                break
                            if next_line.strip():
                                gateway_candidates.append(next_line.strip())
                        break
                if gateway_candidates:
                    break
                    
        for cand in gateway_candidates:
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', cand) and cand != '0.0.0.0':
                return cand
    except Exception:
        pass
        
    return None

def get_valid_destination_path():
    default_dir = "./transferred_files_hybrid"
    while True:
        try:
            path_input = input(f"Enter destination path [Default: {default_dir}]: ").strip()
            if not path_input:
                path_input = default_dir
            
            abs_path = os.path.abspath(path_input)
            
            try:
                os.makedirs(abs_path, exist_ok=True)
            except (OSError, PermissionError) as e:
                print(f"Can't create '{path_input}': {e}")
                continue
                
            # quick write test
            test_file = os.path.join(abs_path, '.write_test_temp')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except (OSError, PermissionError) as e:
                print(f"'{path_input}' isn't writeable: {e}")
                continue
                
            return abs_path
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)
        except Exception as e:
            print(f"Bad path or permission issue: {e}")

def hybrid_pull(target_ip, output_dir, port=5001):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8388608)
        s.settimeout(60.0)
        s.connect((target_ip, port))
        print("Connected! reading stream...")
        
        start_time = time.time()
        speed_samples = []  # MB/s snapshots for stats
        sock_file = s.makefile('rb', buffering=8388608)

        while True:
            flag = sock_file.read(1)
            if not flag:
                break
            
            if flag == b'\x01':
                # phase 1: big file incoming
                path_len_data = sock_file.read(2)
                if not path_len_data:
                    break
                path_len = struct.unpack('!H', path_len_data)[0]
                
                rel_path_data = sock_file.read(path_len)
                if not rel_path_data:
                    break
                rel_path = rel_path_data.decode('utf-8')
                
                filesize_data = sock_file.read(8)
                if not filesize_data:
                    break
                filesize = struct.unpack('!Q', filesize_data)[0]

                full_path = os.path.join(output_dir, rel_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                print(f"  [phase 1] {rel_path} ({filesize / (1024*1024*1024):.2f} GB)")
                
                bytes_received = 0
                buffer_size = 1024 * 1024  # 1MB chunks
                chunk_bytes_for_speed = 0
                chunk_time_start = time.time()
                
                try:
                    with open(full_path, 'wb') as f:
                        while bytes_received < filesize:
                            to_read = min(buffer_size, filesize - bytes_received)
                            chunk = sock_file.read(to_read)
                            if not chunk:
                                raise ConnectionAbortedError("stream ended early")
                            f.write(chunk)
                            bytes_received += len(chunk)
                            chunk_bytes_for_speed += len(chunk)
                            
                            # sample speed every ~8MB
                            if chunk_bytes_for_speed >= 8 * 1024 * 1024:
                                elapsed = time.time() - chunk_time_start
                                if elapsed > 0:
                                    speed_samples.append(chunk_bytes_for_speed / (1024 * 1024) / elapsed)
                                chunk_bytes_for_speed = 0
                                chunk_time_start = time.time()
                    
                    # catch leftover bytes that didn't hit the 8MB mark
                    elapsed = time.time() - chunk_time_start
                    if chunk_bytes_for_speed > 0 and elapsed > 0:
                        speed_samples.append(chunk_bytes_for_speed / (1024 * 1024) / elapsed)
                except (OSError, PermissionError) as e:
                    print(f"Can't write to {full_path}: {e}")
                    raise

            elif flag == b'\x02':
                # phase 2: tar stream for everything else
                print("  [phase 2] extracting remaining files...")
                tar_start = time.time()
                tar_start_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(output_dir) for f in fns)
                try:
                    with tarfile.open(fileobj=sock_file, mode='r|') as tar:
                        tar.extractall(path=output_dir)
                except Exception as e:
                    print(f"Tar extraction failed: {e}")
                    raise
                tar_elapsed = time.time() - tar_start
                tar_end_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(output_dir) for f in fns)
                tar_bytes = tar_end_size - tar_start_size
                if tar_elapsed > 0 and tar_bytes > 0:
                    speed_samples.append(tar_bytes / (1024 * 1024) / tar_elapsed)
                break

        sock_file.close()
        end_time = time.time()
        print(f"\nDone! took {end_time - start_time:.2f}s")
        
        if speed_samples:
            peak = max(speed_samples)
            lowest = min(speed_samples)
            avg = sum(speed_samples) / len(speed_samples)
            print(f"  Peak: {peak:.2f} MB/s | Lowest: {lowest:.2f} MB/s | Avg: {avg:.2f} MB/s")

if __name__ == "__main__":
    print("\n--- UnMTP Hybrid Pull Client ---")
    
    # 1. OS-Aware Gateway Detection
    if os.name == 'nt':
        print("Windows detected. Attempting to auto-detect Hotspot gateway...")
        target_ip = get_default_gateway_windows()
        if target_ip:
            print(f"Auto-detected Gateway IP: {target_ip}")
    else:
        print("Android/Linux detected. Skipping Windows network auto-detection.")
        target_ip = None  # Forcing this to None triggers your existing manual input prompt

    destination_path = get_valid_destination_path()

    port = 5001
    target_ip = detected_ip
    first_attempt = True
    
    while True:
        try:
            if not target_ip:
                target_ip = input("Server IP: ").strip()
                if not target_ip:
                    print("IP can't be empty.")
                    continue
            elif not first_attempt:
                user_ip = input(f"Server IP [Default: {target_ip}]: ").strip()
                if user_ip:
                    target_ip = user_ip
            
            first_attempt = False
            print(f"Connecting to {target_ip}:{port}...")
            hybrid_pull(target_ip, destination_path, port)
            break
            
        except (ConnectionRefusedError, socket.timeout) as e:
            print(f"\nCouldn't connect to {target_ip}:{port} — {e}")
            print("Is the server running?")
            target_ip = None
        except (ConnectionResetError, ConnectionAbortedError) as e:
            print(f"\nConnection dropped: {e}")
            retry = input("Retry? (y/n): ").strip().lower()
            if retry != 'y':
                print("Bye.")
                break
        except KeyboardInterrupt:
            print("\nCancelled.")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            break