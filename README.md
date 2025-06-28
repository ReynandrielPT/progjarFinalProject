# Dots and Boxes Multiplayer Game

Project ini adalah implementasi permainan **Dots and Boxes** untuk dua pemain secara **real-time multiplayer** menggunakan arsitektur socket dan protokol HTTP sederhana. 

---

## Anggota Kelompok

| Nama Lengkap                   | NIM          |
|-------------------------------|--------------|
| Theresa Dwiputri Aruan        | 5025231039   |
| Adelia Rahmatus Sa’dia        | 5025231054   |
| Reynandriel Pramas Thandya    | 5025231113   |
| Miskiyah                      | 5025231119   |
| Basten Andika Salim           | 5025231132   |
---
## Fitur

### Fitur Game

* Multiplayer 2 pemain (Player 1 & Player 2)
* Sistem READY/UNREADY sebelum game dimulai
* Countdown sebelum mulai dan saat resume
* Giliran bergantian dan validasi move
* Deteksi kotak dan penilaian skor
* Penentuan pemenang dan auto-reset ke lobby

### Fitur Jaringan

* Load balancer dengan sticky session per IP
* Server HTTP berbasis thread pool
* Game State Server terpisah untuk sinkronisasi data
* Manajemen sesi berdasarkan cookie
* Auto-cleanup session yang tidak aktif
* Polling client untuk real-time game state sync

### Fitur Client

* UI menggunakan **Pygame**
* Visualisasi board, garis, box, skor, giliran
* Event handling keyboard dan mouse
* Countdown & overlay pause/resume
* Komunikasi ke server menggunakan HTTP socket manual

---

## Deskripsi file

| File                         | Deskripsi                                                                    |
| ---------------------------- | ---------------------------------------------------------------------------- |
| `client.py`                  | Aplikasi client berbasis Pygame                                              |
| `http.py`                    | Server HTTP yang menangani request client                                    |
| `server_thread_pool_http.py` | Worker HTTP server menggunakan thread pool                                   |
| `game_state_server.py`       | Menyimpan dan memproses logika permainan                                     |
| `game_state_client.py`       | Client yang digunakan oleh HTTP server untuk komunikasi ke game state server |
| `load_balancer.py`           | Sticky load balancer berbasis IP                                             |
| `dots_logic.py`              | Logika permainan Dots and Boxes                                              |

---

## Menjalankan program
**Server**

Keseluruhan server dapat dijalankan dalam terminal environment Jupyter.
* Pertama, jalankan load balancer dengan perintah python load_balancer.py atau python3 load_balancer.py.
* Kedua, jalankan server HTTP pertama dengan perintah python server_thread_pool_http.py 8001 atau python3 server_thread_pool_http.py 8001.
* Ketiga, jalankan server HTTP kedua dengan perintah python server_thread_pool_http.py 8002 atau python3 server_thread_pool_http.py 8002.
* Keempat, jalankan server game state dengan perintah python game_state_server.py atau python3 game_state_server.py.

**Client**

Client hanya dapat dijalan dalam lxterminal environment noVNC. Perintah yang digunakan adalah python client.py atau python3 client.py.
