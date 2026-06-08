import socket
import tarfile
import os
import time

def host_folder(folder_path, port=5001):
    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a valid directory.")
        return

    base_name = os.path.basename(os.path.normpath(folder_path))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', port))
        s.listen(1)
        print(f"Hosting folder: {base_name}")
        print("Waiting for connection...")

        conn, addr = s.accept()
        print(f"Connected: {addr} - streaming...")

        start_time = time.time()

        sock_file = conn.makefile('wb')

        # stream-only tar, no seeking
        with tarfile.open(fileobj=sock_file, mode='w|') as tar:
            tar.add(folder_path, arcname=base_name)

        sock_file.close()
        end_time = time.time()
        print(f"Done in {end_time - start_time:.2f}s")

if __name__ == "__main__":
    target_folder = "/data/data/com.termux/files/home/storage/downloads/forza"
    host_folder(target_folder)
