# Nama file: load_balancer.py
import socket
import threading
import itertools
import time
import logging

# --- Konfigurasi ---
LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 8000

# Daftar alamat server game (worker) di backend
BACKEND_SERVERS = [
    ('127.0.0.1', 8001),
    ('127.0.0.1', 8002),
]

logging.basicConfig(level=logging.INFO, format='LOAD_BALANCER - %(levelname)s: %(message)s')

class StickyLoadBalancer:
    def __init__(self):
        # Kamus untuk menyimpan pemetaan: client_ip -> backend_server
        self.ip_to_backend = {}
        # Untuk memilih server baru secara bergiliran
        self.backend_cycler = itertools.cycle(BACKEND_SERVERS)
        # Lock untuk memastikan kamus ip_to_backend aman untuk thread
        self.lock = threading.Lock()

    def select_backend(self, client_ip):
        """
        Memilih backend server. Jika klien sudah pernah terhubung,
        kembalikan server yang sama. Jika baru, pilih yang berikutnya.
        """
        with self.lock:
            if client_ip not in self.ip_to_backend:
                # Klien baru, pilih worker berikutnya dan simpan
                backend = next(self.backend_cycler)
                self.ip_to_backend[client_ip] = backend
                logging.info(f"Klien baru {client_ip}, diarahkan ke worker {backend}")
            # Kembalikan worker yang sudah ditugaskan
            return self.ip_to_backend[client_ip]

    def forward_data(self, source, destination, direction=""):
        """
        Membaca data dari source dan meneruskannya ke destination
        hingga koneksi ditutup.
        """
        try:
            while True:
                data = source.recv(4096)
                if not data:
                    break
                destination.sendall(data)
        except (ConnectionResetError, BrokenPipeError, OSError):
            # Ini normal terjadi saat salah satu sisi menutup koneksi
            pass
        except Exception as e:
            logging.error(f"Error saat meneruskan data {direction}: {e}")
        finally:
            # Pastikan kedua koneksi ditutup untuk membersihkan sumber daya
            self.safe_close_socket(source)
            self.safe_close_socket(destination)

    def safe_close_socket(self, sock):
        """Safely close a socket"""
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def handle_client(self, client_socket, client_address):
        """Menangani setiap koneksi klien yang masuk."""
        client_ip = client_address[0]
        
        backend_host, backend_port = self.select_backend(client_ip)
        backend_socket = None

        try:
            # Buka koneksi ke worker yang telah dipilih
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.settimeout(10.0)  # Set timeout untuk connection
            backend_socket.connect((backend_host, backend_port))
            logging.info(f"Klien {client_ip} terhubung ke worker {backend_host}:{backend_port}")

            # Set socket ke non-blocking mode setelah connect
            client_socket.settimeout(None)
            backend_socket.settimeout(None)

            # Buat dua thread untuk meneruskan data dua arah secara simultan
            client_to_backend = threading.Thread(
                target=self.forward_data, 
                args=(client_socket, backend_socket, "client->backend"), 
                daemon=True
            )
            backend_to_client = threading.Thread(
                target=self.forward_data, 
                args=(backend_socket, client_socket, "backend->client"), 
                daemon=True
            )
            
            client_to_backend.start()
            backend_to_client.start()
            
            # Wait for either thread to finish (connection closed)
            client_to_backend.join(timeout=1)
            backend_to_client.join(timeout=1)

        except socket.timeout:
            logging.error(f"Timeout connecting to worker {backend_host}:{backend_port}")
        except ConnectionRefusedError:
            logging.error(f"Worker {backend_host}:{backend_port} is not available")
            # Remove this backend from client mapping if it's down
            with self.lock:
                if self.ip_to_backend.get(client_ip) == (backend_host, backend_port):
                    del self.ip_to_backend[client_ip]
        except Exception as e:
            logging.error(f"Error connecting to worker {backend_host}:{backend_port} - {e}")
            with self.lock:
                if self.ip_to_backend.get(client_ip) == (backend_host, backend_port):
                    del self.ip_to_backend[client_ip]
        finally:
            self.safe_close_socket(client_socket)
            if backend_socket:
                self.safe_close_socket(backend_socket)

    def start(self):
        """Memulai load balancer."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((LISTEN_HOST, LISTEN_PORT))
        server_socket.listen(10)
        logging.info(f"Load Balancer (Sticky Session) berjalan di {LISTEN_HOST}:{LISTEN_PORT}")
        logging.info(f"Meneruskan ke workers: {BACKEND_SERVERS}")

        while True:
            try:
                client_socket, client_address = server_socket.accept()
                # Buat thread baru untuk setiap koneksi klien yang masuk
                threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket, client_address), 
                    daemon=True
                ).start()
            except Exception as e:
                logging.error(f"Error accepting client connection: {e}")

if __name__ == "__main__":
    balancer = StickyLoadBalancer()
    try:
        balancer.start()
    except KeyboardInterrupt:
        logging.info("Shutting down Load Balancer...")
    except Exception as e:
        logging.error(f"Load Balancer error: {e}")