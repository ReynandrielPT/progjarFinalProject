from socket import *
import socket
import time
import sys
import logging
import multiprocessing
import threading
import itertools
from concurrent.futures import ThreadPoolExecutor

LISTEN_HOST = '0.0.0.0'
LISTEN_PORT = 8000

BACKEND_SERVERS = [
    ('127.0.0.1', 8001),
    ('127.0.0.1', 8002),
]

logging.basicConfig(level=logging.INFO, format='LB - %(levelname)s: %(message)s')

class StickyLoadBalancer:
    def __init__(self):
        self.ip_to_backend = {}
        self.backend_cycler = itertools.cycle(BACKEND_SERVERS)
        self.lock = threading.Lock()

    def select_backend(self, client_ip):
        with self.lock:
            if client_ip not in self.ip_to_backend:
                backend = next(self.backend_cycler)
                self.ip_to_backend[client_ip] = backend
                logging.info(f"Client baru {client_ip}, diarahkan ke worker {backend}")
            return self.ip_to_backend[client_ip]

def forward_data(source, destination, direction="", client_ip="", backend_info=""):
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break
            
            if direction == "client->backend" and data.strip():
                logging.info(f"Client {client_ip} REQUEST ke worker {backend_info}")
            elif direction == "backend->client" and data.strip():
                logging.info(f"Client {client_ip} RESPONSE dari worker {backend_info}")
            
            destination.sendall(data)
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    except Exception as e:
        logging.error(f"Error saat meneruskan data {direction}: {e}")
    finally:
        safe_close_socket(source)
        safe_close_socket(destination)

def safe_close_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass

def handle_client(client_socket, client_address, balancer):
    client_ip = client_address[0]
    backend_host, backend_port = balancer.select_backend(client_ip)
    backend_info = f"{backend_host}:{backend_port}"
    backend_socket = None

    try:
        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_socket.settimeout(10.0)
        backend_socket.connect((backend_host, backend_port))

        client_socket.settimeout(None)
        backend_socket.settimeout(None)

        client_to_backend = threading.Thread(
            target=forward_data, 
            args=(client_socket, backend_socket, "client->backend", client_ip, backend_info), 
            daemon=True
        )
        backend_to_client = threading.Thread(
            target=forward_data, 
            args=(backend_socket, client_socket, "backend->client", client_ip, backend_info), 
            daemon=True
        )
        
        client_to_backend.start()
        backend_to_client.start()
        
        client_to_backend.join()
        backend_to_client.join()

    except socket.timeout:
        logging.error(f"Timeout connecting to worker {backend_info}")
    except ConnectionRefusedError:
        logging.error(f"Worker {backend_info} is not available")
        with balancer.lock:
            if balancer.ip_to_backend.get(client_ip) == (backend_host, backend_port):
                del balancer.ip_to_backend[client_ip]
    except Exception as e:
        logging.error(f"Error connecting to worker {backend_info} - {e}")
        with balancer.lock:
            if balancer.ip_to_backend.get(client_ip) == (backend_host, backend_port):
                del balancer.ip_to_backend[client_ip]
    finally:
        safe_close_socket(client_socket)
        if backend_socket:
            safe_close_socket(backend_socket)

def Server():
    the_clients = []
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    balancer = StickyLoadBalancer()

    my_socket.bind((LISTEN_HOST, LISTEN_PORT))
    my_socket.listen(10)
    logging.info(f"Load Balancer (Sticky Session) berjalan di {LISTEN_HOST}:{LISTEN_PORT}")
    logging.info(f"Meneruskan ke workers: {BACKEND_SERVERS}")

    while True:
        try:
            connection, client_address = my_socket.accept()
            threading.Thread(
                target=handle_client, 
                args=(connection, client_address, balancer), 
                daemon=True
            ).start()
        except Exception as e:
            logging.error(f"Error accepting client connection: {e}")

def main():
    try:
        Server()
    except KeyboardInterrupt:
        logging.info("Shutting down Load Balancer...")
    except Exception as e:
        logging.error(f"Load Balancer error: {e}")

if __name__ == "__main__":
    main()
