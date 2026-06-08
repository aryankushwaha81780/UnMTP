import socket
import os
import struct
import time

def send_folder_zerocopy(folder_path, port=5001):
    base_dir = os.path.normpath(folder_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8388608)
        s.bind(('0.0.0.0', port))
        s.listen(1)
        print(f"Hosting: {base_dir} on port {port}")
        conn, addr = s.accept()
        print(f"Connected: {addr}")
        start_time = time.time()
        total_bytes = 0

        for root, _, files in os.walk(base_dir):
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, os.path.dirname(base_dir))
                filesize = os.path.getsize(filepath)

                # header: path len (2B) + path + file size (8B)
                rel_path_encoded = rel_path.encode('utf-8')
                header = struct.pack(f'!H{len(rel_path_encoded)}sQ', len(rel_path_encoded), rel_path_encoded, filesize)
                conn.sendall(header)

                # sendfile = zero-copy
                with open(filepath, 'rb') as f:
                    conn.sendfile(f)
                total_bytes += filesize
                print(f"  {rel_path} ({filesize / (1024*1024):.2f} MB)")

        # empty header = done
        conn.sendall(struct.pack('!H', 0))
        end_time = time.time()
        speed = (total_bytes / (1024 * 1024)) / (end_time - start_time)
        print(f"\nDone - {speed:.2f} MB/s")

if __name__ == "__main__":
    target_folder = "/data/data/com.termux/files/home/storage/downloads/forza"
    send_folder_zerocopy(target_folder)
