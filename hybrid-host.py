import socket
import os
import struct
import time
import tarfile
import sys

# anything above this goes through sendfile() instead of tar
BIG_FILE_THRESHOLD = 5 * 1024 * 1024 * 1024 

def get_valid_target_folder():
    # pick the right default based on OS
    if os.name == 'nt':
        default_dir = os.path.abspath(os.getcwd())
        print(f"Windows detected. Default directory set to: {default_dir}")
    else:
        default_dir = "/data/data/com.termux/files/home/storage/"
        print(f"Android/Termux detected. Default directory set to: {default_dir}")
    while True:
        try:
            folder_input = input(f"Enter target folder path to host [Default: {default_dir}]: ").strip()
            if not folder_input:
                folder_input = default_dir

            # try resolving relative to default_dir first, then cwd
            if not os.path.isabs(folder_input):
                path_relative_to_default = os.path.normpath(os.path.join(default_dir, folder_input))
                path_relative_to_cwd = os.path.abspath(folder_input)
                
                if os.path.exists(path_relative_to_default):
                    abs_path = path_relative_to_default
                elif os.path.exists(path_relative_to_cwd):
                    abs_path = path_relative_to_cwd
                else:
                    abs_path = path_relative_to_default
            else:
                abs_path = os.path.abspath(folder_input)

            if not os.path.exists(abs_path):
                print(f"Error: '{abs_path}' doesn't exist.")
                continue
            if not os.path.isdir(abs_path):
                print(f"Error: '{abs_path}' is not a directory.")
                continue

            # make sure we can actually read it
            try:
                os.listdir(abs_path)
            except (OSError, PermissionError) as e:
                print(f"Can't read '{abs_path}' — permission denied. {e}")
                continue

            return abs_path
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)
        except Exception as e:
            print(f"Something went wrong: {e}")

def hybrid_host(folder_path, port=5001):
    base_dir = os.path.normpath(folder_path)
    if not os.path.isdir(base_dir):
        print(f"Error: {base_dir} is not a folder.")
        return

    # find the big ones first
    big_files = []
    for root, _, files in os.walk(base_dir):
        for file in files:
            fp = os.path.join(root, file)
            try:
                if os.path.getsize(fp) >= BIG_FILE_THRESHOLD:
                    big_files.append(fp)
            except OSError:
                pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8388608)
        try:
            s.bind(('0.0.0.0', port))
            s.listen(1)
        except OSError as e:
            print(f"Can't bind to port {port}: {e}")
            return

        print(f"Server ready. {len(big_files)} file(s) above the sendfile threshold.")
        print("Waiting for connection...")
        
        try:
            conn, addr = s.accept()
            print(f"Connected: {addr}")
            start_time = time.time()
            speed_samples = []  # MB/s snapshots for stats
        except KeyboardInterrupt:
            print("\nStopped.")
            return

        try:
            # phase 1 — blast big files with sendfile()
            for filepath in big_files:
                rel_path = os.path.relpath(filepath, os.path.dirname(base_dir))
                filesize = os.path.getsize(filepath)
                
                conn.sendall(b'\x01')
                
                rel_path_encoded = rel_path.encode('utf-8')
                header = struct.pack(f'!H{len(rel_path_encoded)}sQ', len(rel_path_encoded), rel_path_encoded, filesize)
                conn.sendall(header)

                print(f"  [phase 1] sending: {rel_path} ({filesize / (1024*1024*1024):.2f} GB)")
                file_start = time.time()
                with open(filepath, 'rb') as f:
                    conn.sendfile(f)
                file_elapsed = time.time() - file_start
                if file_elapsed > 0 and filesize > 0:
                    speed_samples.append(filesize / (1024 * 1024) / file_elapsed)

            # phase 2 — tar the rest
            print("\nPhase 1 done. Tar-streaming remaining files...")
            
            conn.sendall(b'\x02')
            
            # skip big files, already sent those
            def tar_filter(tarinfo):
                full_path = os.path.join(os.path.dirname(base_dir), tarinfo.name)
                try:
                    if os.path.isfile(full_path) and os.path.getsize(full_path) >= BIG_FILE_THRESHOLD:
                        return None
                except OSError:
                    pass
                return tarinfo

            # measure tar phase size by summing small files
            tar_total = 0
            for root, _, files in os.walk(base_dir):
                for file in files:
                    fp = os.path.join(root, file)
                    try:
                        sz = os.path.getsize(fp)
                        if sz < BIG_FILE_THRESHOLD:
                            tar_total += sz
                    except OSError:
                        pass

            sock_file = conn.makefile('wb')
            base_name = os.path.basename(base_dir)
            
            tar_start = time.time()
            with tarfile.open(fileobj=sock_file, mode='w|') as tar:
                tar.add(base_dir, arcname=base_name, filter=tar_filter)
                
            sock_file.close()
            tar_elapsed = time.time() - tar_start
            if tar_elapsed > 0 and tar_total > 0:
                speed_samples.append(tar_total / (1024 * 1024) / tar_elapsed)

            end_time = time.time()
            print(f"\nDone! total transfer time: {end_time - start_time:.2f}s")
            
            if speed_samples:
                peak = max(speed_samples)
                lowest = min(speed_samples)
                avg = sum(speed_samples) / len(speed_samples)
                print(f"  Peak: {peak:.2f} MB/s | Lowest: {lowest:.2f} MB/s | Avg: {avg:.2f} MB/s")
        except (socket.timeout, ConnectionResetError, ConnectionAbortedError) as e:
            print(f"\nConnection lost: {e}")
        except Exception as e:
            print(f"\nSomething broke: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    target_folder = get_valid_target_folder()
    hybrid_host(target_folder)