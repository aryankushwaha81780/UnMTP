import socket
import tarfile
import time
import os

def pull_folder(target_ip, output_directory, port=5001):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print(f"Connecting to {target_ip}:{port}...")
        s.connect((target_ip, port))
        print("Connected, pulling folder...")

        start_time = time.time()

        sock_file = s.makefile('rb')

        # stream mode, no seek
        with tarfile.open(fileobj=sock_file, mode='r|') as tar:
            tar.extractall(path=output_directory)

        sock_file.close()
        end_time = time.time()
        print(f"Extracted to: {output_directory}")
        print(f"Took {end_time - start_time:.2f}s")

if __name__ == "__main__":
    phone_hotspot_ip = "10.113.91.72"
    destination_path = "./transferred_files"
    pull_folder(phone_hotspot_ip, destination_path)