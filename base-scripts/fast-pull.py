import socket
import os
import struct
import time

def pull_folder_zerocopy(target_ip, output_dir, port=5001):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8388608)
        s.connect((target_ip, port))
        print("Connected, receiving...")

        start_time = time.time()
        total_bytes = 0

        # big recv buffer
        sock_file = s.makefile('rb', buffering=8388608)

        while True:
            path_len_data = sock_file.read(2)
            if not path_len_data: break
            path_len = struct.unpack('!H', path_len_data)[0]
            if path_len == 0: break

            rel_path = sock_file.read(path_len).decode('utf-8')
            filesize = struct.unpack('!Q', sock_file.read(8))[0]

            full_path = os.path.join(output_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            bytes_received = 0
            buffer_size = 1024 * 1024  # 1MB chunks

            with open(full_path, 'wb') as f:
                while bytes_received < filesize:
                    to_read = min(buffer_size, filesize - bytes_received)
                    chunk = sock_file.read(to_read)
                    if not chunk: break
                    f.write(chunk)
                    bytes_received += len(chunk)

            total_bytes += filesize
            print(f"  {rel_path} ({filesize / (1024*1024):.2f} MB)")

        sock_file.close()
        end_time = time.time()
        speed = (total_bytes / (1024 * 1024)) / (end_time - start_time)
        print(f"\nDone - {speed:.2f} MB/s")

if __name__ == "__main__":
    phone_hotspot_ip = "10.113.91.72"
    destination_path = "./transferred_files_fast"
    pull_folder_zerocopy(phone_hotspot_ip, destination_path)