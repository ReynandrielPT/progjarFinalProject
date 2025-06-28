from socket import *
import socket
import time
import sys
import logging
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from http import HttpServer

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
            if b"GET" in rcv_bytes and rcv_bytes.endswith(b"\r\n\r\n"):
                break
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
    while True:
        time.sleep(2)
        try:
            httpserver.cleanup_sessions()
        except Exception as e:
            logging.error(f"Error cleaning up sessions: {e}")

def Server(port=8001):
    the_clients = []
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    logging.info(f"Worker Server berjalan di port {port}")
    logging.info("Terhubung ke Game State Server")
    my_socket.bind(('0.0.0.0', port))
    my_socket.listen(10)


    threading.Thread(target=purge_stale_sessions_thread, daemon=True).start()

    with ThreadPoolExecutor(20) as executor:
        while True:
            try:
                connection, client_address = my_socket.accept()
                p = executor.submit(ProcessTheClient, connection, client_address)
                the_clients.append(p)
                
                #menampilkan jumlah process yang sedang aktif
                jumlah = ['x' for i in the_clients if i.running()==True]
                print(len(jumlah))
                
            except Exception as e:
                logging.error(f"Error menerima koneksi: {e}")

def main():
    try:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    except (IndexError, ValueError):
        port = 8001
    
    try:
        Server(port)
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__=="__main__":
    main()
