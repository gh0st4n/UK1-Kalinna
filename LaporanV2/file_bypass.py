#!/usr/bin/env python3
import requests
import base64
import os

URL = input("Masukkan URL Target : ").strip()
COOKIE_VALUE = input("Masukkan Cookie : ").strip().replace('PHPSESSID=', '').strip()
IMAGE_PATH   = input("Masukkan File JPEG : ").strip().strip('"').strip("'")
IMAGE_PATH   = os.path.expanduser(os.path.expandvars(IMAGE_PATH))

if not URL:
    print("[ERROR] URL kosong.")
    raise SystemExit(1)

if not URL.startswith(('http://', 'https://')):
    URL = 'http://' + URL
    print(f"[!] URL tanpa skema, di-prefix: {URL}")

if not COOKIE_VALUE:
    print("[ERROR] Cookie kosong.")
    raise SystemExit(1)

if not IMAGE_PATH:
    print("[ERROR] Path gambar kosong.")
    raise SystemExit(1)

if not os.path.isfile(IMAGE_PATH):
    print(f"[ERROR] File tidak ditemukan: {IMAGE_PATH}")
    raise SystemExit(1)

try:
    with open(IMAGE_PATH, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
except Exception as e:
    print(f"[ERROR] Gagal membaca file: {e}")
    raise SystemExit(1)

files = {
    'jenis_absen': (None, 'Hadir'),
    'image':       (None, f'data:image/jpeg;base64,{img_b64}'),
    'latitude':    (None, '-6.200000'),
    'longitude':   (None, '106.816666'),
}
cookies = {'PHPSESSID': COOKIE_VALUE}

print(f"[*] Target : {URL}")
print(f"[*] Image  : {IMAGE_PATH}")
print(f"[*] Cookie : {COOKIE_VALUE[:16]}...")
print("[*] Mengirim POST...")

try:
    r = requests.post(URL, files=files, cookies=cookies, timeout=15)
    print(f"\n[OKE] Status: {r.status_code}")
    print(r.text[:500])
except requests.exceptions.Timeout:
    print("[ERROR] Request timeout — server tidak merespons.")
except requests.exceptions.ConnectionError:
    print("[ERROR] Gagal terhubung ke server — cek IP/port.")
except Exception as e:
    print(f"[ERROR] {e}")