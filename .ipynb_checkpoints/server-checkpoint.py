# Nama file: server_dots_http.py
import socket
import sys
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http_handler import HttpServer

httpserver = HttpServer()
logging.basicConfig(level=logging.INFO, format='SERVER - %(levelname)s: %(message)s')

def ProcessTheClient(connection, address):
    try:
        rcv_bytes = b""
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            rcv_bytes += chunk
            # Jika request adalah GET, header adalah request lengkap
            if b"GET" in rcv_bytes and rcv_bytes.endswith(b"\r\n\r\n"):
                break
            # Jika POST, periksa Content-Length
            if b"POST" in rcv_bytes and b"\r\n\r\n" in rcv_bytes:
                header_end = rcv_bytes.find(b"\r\n\r\n")
                header_str = rcv_bytes[:header_end].decode()
                content_length = 0
                for line in header_str.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())
                        break
                
                body_received = len(rcv_bytes) - (header_end + 4)
                if body_received >= content_length:
                    break
        
        if not rcv_bytes:
            return

        rcv_str = rcv_bytes.decode('utf-8', 'ignore')
        print("="*30)
        print(f"REQUEST DARI {address}:")
        print(rcv_str.strip())
        print("="*30)
        
        hasil = httpserver.proses(rcv_str)
        
        try:
            header_part, body_part = hasil.split(b'\r\n\r\n', 1)
            print(f"RESPONSE KE {address}:")
            print(header_part.decode().strip())
            print(f"[Body: {len(body_part)} bytes]")
            print("-"*30 + "\n")
        except Exception:
            print(f"RESPONSE KE {address}:\n{hasil.decode().strip()}")
            print("-"*30 + "\n")

        connection.sendall(hasil)

    except Exception as e:
        logging.error(f"Error memproses klien {address}: {e}")
    finally:
        connection.close()

def purge_stale_sessions_thread():
    """Thread untuk membersihkan session yang sudah expired"""
    while True:
        time.sleep(2)
        try:
            httpserver.cleanup_sessions()
        except Exception as e:
            logging.error(f"Error cleaning up sessions: {e}")

def Server(port=8001):
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    my_socket.bind(('0.0.0.0', port))
    my_socket.listen(10)
    logging.info(f"Worker Server berjalan di port {port}")
    logging.info("Terhubung ke Game State Server")

    # Start session cleanup thread
    threading.Thread(target=purge_stale_sessions_thread, daemon=True).start()

    with ThreadPoolExecutor(20) as executor:
        while True:
            try:
                connection, client_address = my_socket.accept()
                executor.submit(ProcessTheClient, connection, client_address)
            except Exception as e:
                logging.error(f"Error menerima koneksi: {e}")

if __name__ == "__main__":
    try:
        port = int(sys.argv[1])
    except (IndexError, ValueError):
        port = 8001
    
    try:
        Server(port)
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)