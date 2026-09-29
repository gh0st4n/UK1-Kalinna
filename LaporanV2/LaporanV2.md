# LAPORAN PENTEST V2 — Aplikasi Management Data Siswa

- **Target:** `http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/`
- **Setup Lab:** Aplikasi berjalan di **Windows (Laragon)**, Attacker di **Kali Linux**
- **Tanggal:** 21–22 September 2026 (patch: 23 September 2026)
- **Tester:** gh05t4n
- **Metodologi:** Black-box → White-box (setelah recovery source code via `.git`)

## Daftar Isi

- [LAPORAN PENTEST V2 — Aplikasi Management Data Siswa](#laporan-pentest-v2--aplikasi-management-data-siswa)
  - [Daftar Isi](#daftar-isi)
  - [1. Ringkasan Eksekutif](#1-ringkasan-eksekutif)
  - [2. Lingkup \& Setup Lab](#2-lingkup--setup-lab)
  - [3. Metodologi \& Reconnaissance](#3-metodologi--reconnaissance)
    - [Tools](#tools)
    - [Struktur Folder](#struktur-folder)
    - [Reconnaissance](#reconnaissance)
  - [4. Temuan](#4-temuan)
    - [4.1 Git Repository Exposure (CRITICAL)](#41-git-repository-exposure-critical)
    - [4.2 Credential Leak di Git History (CRITICAL)](#42-credential-leak-di-git-history-critical)
    - [4.3 Database Dump Ke-commit (HIGH)](#43-database-dump-ke-commit-high)
    - [4.4 Directory Listing Aktif (MEDIUM)](#44-directory-listing-aktif-medium)
    - [4.5 Session Hijacking via HTTP (MEDIUM)](#45-session-hijacking-via-http-medium)
    - [4.6 Business Logic — Validasi NISN (LOW)](#46-business-logic--validasi-nisn-low)
    - [4.7 Upload Bypass via Base64 (HIGH)](#47-upload-bypass-via-base64-high)
    - [4.8 Kredensial Siswa Default = NISN (CRITICAL)](#48-kredensial-siswa-default--nisn-critical)
  - [5. Vektor yang Diuji \& Aman](#5-vektor-yang-diuji--aman)
  - [6. Matriks Risiko](#6-matriks-risiko)
  - [7. Rekomendasi Perbaikan](#7-rekomendasi-perbaikan)
    - [Prioritas 1 (Immediate)](#prioritas-1-immediate)
    - [Prioritas 2 (Short-term)](#prioritas-2-short-term)
    - [Prioritas 3 (Long-term)](#prioritas-3-long-term)
  - [8. Panduan Aman Push ke GitHub](#8-panduan-aman-push-ke-github)
    - [8.1 Buat `.gitignore` yang Proper](#81-buat-gitignore-yang-proper)
    - [8.2 Gunakan Environment Variable](#82-gunakan-environment-variable)
    - [8.3 Scan Credential Sebelum Push](#83-scan-credential-sebelum-push)
    - [8.4 Pre-commit Hook — Cegah Commit Credential](#84-pre-commit-hook--cegah-commit-credential)
    - [8.5 Kalau Sudah Terlanjur Commit — Bersihkan History](#85-kalau-sudah-terlanjur-commit--bersihkan-history)
    - [8.6 Gunakan GitHub Secrets untuk CI/CD](#86-gunakan-github-secrets-untuk-cicd)
    - [8.7 Checklist Sebelum Push](#87-checklist-sebelum-push)
    - [8.8 Alur Push yang Benar](#88-alur-push-yang-benar)
    - [8.9 Emergency Response — Kalau Credential Bocor](#89-emergency-response--kalau-credential-bocor)
  - [9. Lampiran](#9-lampiran)
    - [A. Struktur Folder](#a-struktur-folder)
    - [B. Command yang Digunakan](#b-command-yang-digunakan)
    - [C. Timeline](#c-timeline)
    - [D. Struktur File yang Ter-recover](#d-struktur-file-yang-ter-recover)
    - [E. Referensi](#e-referensi)

## 1. Ringkasan Eksekutif

Aplikasi **Management Data Siswa** memiliki **4 temuan Critical**, **2 High**, **2 Medium**, dan **1 Low**. Temuan paling berdampak adalah **eksposur folder `.git`** yang memungkinkan penyerang mengambil **seluruh source code** dan **credential admin** dari **git history**.

Selain itu, ditemukan **kelemahan kritis pada manajemen kredensial siswa**: username dan password default untuk akun siswa menggunakan **NISN** (Nomor Induk Siswa Nasional). NISN bersifat **semi-publik** (tertera di kartu pelajar, rapor, formulir pendaftaran, dan sering dibagikan dalam konteks administratif), sehingga kombinasi NISN + NISN sebagai kredensial login membuat akun siswa **sangat rentan diambil alih**.

Dengan credential yang didapat dari git history maupun dari NISN, penyerang bisa **login sebagai admin maupun siswa** dan mengakses seluruh fungsi aplikasi. Meskipun aplikasi sudah menerapkan **prepared statement**, **CSRF token**, **role-based access control**, dan **whitelist ekstensi upload**, masih ditemukan **celah upload bypass via base64** pada endpoint `absensi_siswa.php` — dieksploitasi menggunakan script Python `LaporanV2/file_bypass.py`.

> **Status perbaikan (23 Sep 2026):** Temuan **4.7** telah **dipatch** melalui `LaporanV2/siswa_absensifix.php` (v1.1 → v1.2). Detail lihat [Remediasi Terapan](#remediasi-terapan-v11--v12) dan [`note.md`](note.md). Temuan **4.8** (kredensial siswa = NISN) **belum dipatch** — masih butuh perubahan di level manajemen akun.

**Catatan penting:** Setup lab ini **sengaja** dibuat rentan untuk keperluan pembelajaran. Di lingkungan production, konfigurasi seperti ini **tidak boleh** terjadi.

**Prioritas perbaikan:**

1. Blokir akses ke `.git` di web server (Production)
2. Rotasi seluruh password (admin, user, DB, siswa)
3. Hapus git history yang mengandung credential (Production)
4. Nonaktifkan directory listing
5. Gunakan HTTPS + flag `Secure`/`HttpOnly` pada cookie
6. **Hentikan penggunaan NISN sebagai username/password default siswa**
7. Terapkan praktik aman push ke GitHub (lihat [Bagian 8](#8-panduan-aman-push-ke-github))

## 2. Lingkup & Setup Lab

| Komponen       | Detail                                                   |
| -------------- | -------------------------------------------------------- |
| **Aplikasi**   | Management Data Siswa (PHP + MySQL)                      |
| **Web Server** | Laragon (Windows)                                        |
| **Target IP**  | `192.168.100.247`                                        |
| **Attacker**   | Kali Linux (VM)                                          |
| **Jaringan**   | Bridged / Host-Only (satu subnet `192.168.100.x`)        |
| **Scope**      | `http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/` |

**Catatan:** Karena attacker & victim berada di **satu jaringan**, sniffing HTTP (tanpa TLS) menjadi **realistis** dan **valid** untuk diuji.

## 3. Metodologi & Reconnaissance

### Tools

- `feroxbuster` — directory brute-force
- `git-dumper` — recovery `.git`
- `exiftool` — analisis file
- `Wireshark` — sniffing cookie
- `curl` / browser — manual testing
- **`LaporanV2/file_bypass.py`** — script Python untuk eksploitasi upload bypass via base64

### Struktur Folder

```
LaporanV2/
├── Laporanv2.md          ← dokumen ini
├── file_bypass.py        ← PoC upload bypass base64
├── me.jpeg               ← sample image untuk PoC
└── note.md               ← catatan perbaikan (v1.1 & v1.2)
```

### Reconnaissance

```bash
feroxbuster -u http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2 \
  -w /usr/share/wordlists/dirb/common.txt
```

**Hasil menarik:**

```
200  .git/HEAD                          → Git exposed
200  config/database.php                → Config DB
200  note/note.md                       → Catatan dev
200  classes/auth.php                   → Logika auth
200  classes/siswa.php
200  classes/guru.php
200  classes/kelas.php
301  uploads/                           → Directory listing
301  config/                            → Directory listing
301  note/                              → Directory listing
301  classes/                           → Directory listing
301  views/                             → Directory listing
```

## 4. Temuan

### 4.1 Git Repository Exposure (CRITICAL)

**Deskripsi:**
Folder `.git` dapat diakses publik via HTTP, memungkinkan recovery source code lengkap. Laragon (default) tidak memblokir akses ke `.git`.

**URL:** `http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/.git/`

**Proof of Concept:**

```bash
git-dumper http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/.git/ ./hasil-git

[-] Testing http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/.git/HEAD [200]
[-] Fetching .git recursively
...
[-] Running git checkout .
Updated 65 paths from the index
```

**Hasil:**

- **65 file** source code ter-recover
- Termasuk `config/database.php`, `classes/auth.php`, `db_management_data_siswa.sql`

**Dampak:**

- Source code lengkap terekspos → memudahkan analisis kerentanan
- Git history bisa dibaca → credential yang dihapus masih ada
- File SQL dump ikut terekspos

**Severity:** 🔴 **CRITICAL** (CVSS 9.1)

**Remediasi:**

```apache
# Laragon / Apache .htaccess
RedirectMatch 404 /\.git
```

Atau di Nginx:

```nginx
location ~ /\.git { deny all; }
```

### 4.2 Credential Leak di Git History (CRITICAL)

**Deskripsi:**
File `fix.php` dihapus di commit `54cffb3` ("Hapus file skrip pemulihan fix.php demi keamanan"), tapi **plaintext password masih tersimpan di git history**.

**Proof of Concept:**

```bash
git log -p --all | grep -iE "password|secret"
```

**Output:**

```php
$passAdmin = password_hash('kalinadmin08', PASSWORD_BCRYPT);
$passUser  = password_hash('user123', PASSWORD_BCRYPT);
echo "<p>Password Admin: <b>kalinadmin08</b></p>";
echo "<p>Password User: <b>user123</b></p>";
```

**Credential yang Didapat:**

| Role  | Username | Password       | Status         |
| ----- | -------- | -------------- | -------------- |
| Admin | `admin`  | `kalinadmin08` | Login berhasil |
| User  | `user`   | `user123`      | Valid          |

> **Update:** Credential `user` sebelumnya `user99887711`, sekarang dikonfirmasi menjadi `user123`. Credential `admin` tetap `kalinadmin08`.

**Eksploitasi:**

```
URL: http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/login.php
Username: admin
Password: kalinadmin08
```

→ **Login berhasil sebagai admin** ✅

**Dampak:**

- Full access ke aplikasi sebagai admin
- CRUD data siswa, guru, kelas, absensi
- Upload file

**Severity:** 🔴 **CRITICAL** (CVSS 9.8)

**Remediasi:**

- Rotasi seluruh password (admin, user, DB)
- Hapus git history:
  ```bash
  git filter-repo --path fix.php --invert-paths
  ```
- Jangan pernah commit credential ke repository

### 4.3 Database Dump Ke-commit (HIGH)

**Deskripsi:**
File `db_management_data_siswa.sql` **sudah dihapus dari branch aktif repository**, namun **file tersebut masih dapat diakses melalui riwayat commit (git history)**. Siapa pun yang memiliki akses ke repository (atau yang berhasil men-dump `.git`) dapat melakukan checkout ke commit lama dan mengambil file `.sql` tersebut. File ini berisi struktur DB + data siswa + hash password.

**Bukti:**

- File `db_management_data_siswa.sql` **tidak ada lagi** di branch `main`/`master` (sudah dihapus).
- Namun masih tersimpan di commit `59ae5cdaf520ad971e798b09ce21d9...`.
- Dapat diakses via:
  ```bash
  git log --all --full-history -- "db_management_data_siswa.sql"
  git show <commit_hash>:db_management_data_siswa.sql
  ```
- Atau via GitHub UI: `https://github.com/kalinarnizkiriyah/uk1_management_data_siswa/commit/59ae5cdaf520ad971e798b09ce21d9...`

**Isi file (dari screenshot commit):**

```sql
--
-- Indeks untuk tabel `absensi`
--
ALTER TABLE `absensi`
  ADD PRIMARY KEY (`id_absensi`),
  ADD KEY `fk_absensi_siswa` (`id_siswa`);

--
-- Indeks untuk tabel `guru`
--
ALTER TABLE `guru`
  ADD PRIMARY KEY (`id`);

--
-- Indeks untuk tabel `kelas`
--
ALTER TABLE `kelas`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_kelas_guru` (`guru_id`);

--
-- Indeks untuk tabel `siswa`
--
ALTER TABLE `siswa`
  ADD PRIMARY KEY (`id`),
  ...
```

**Isi lengkap:**

- Data guru (5 record)
- Data kelas (9 record)
- Data siswa (22 record: NISN, nama, alamat, foto)
- Data user (username + hash password)

**Hash Password:**

```
admin : $2y$10$FBF7ta/BH1cnAVc8vN4TPuSq0JGUYpJU9WSDa6AVOu48TCcNUGSNK
user  : $2y$10$YUbQwlMuDAnDWlZCbXUC3ub1mSzS.rwUrX51GQPLPZCj1Q6VDLMDm
```

**Dampak:**

- Data pribadi siswa bocor (nama, NISN, alamat, foto)
- Struktur DB terekspos
- **Kombinasi dengan temuan 4.8**: NISN yang bocor langsung menjadi daftar kredensial valid (username = password = NISN)
- **Kombinasi dengan temuan 4.1**: `.git` yang terekspos memungkinkan recovery file ini tanpa akses repository

**Severity:** 🟠 **HIGH** (CVSS 7.5)

**Remediasi:**

- **Hapus file `.sql` dari seluruh git history** (bukan hanya dari branch aktif):
  ```bash
  git filter-repo --path db_management_data_siswa.sql --invert-paths
  git push origin --force --all
  git push origin --force --tags
  ```
- Tambahkan `*.sql` ke `.gitignore`
- Rotasi hash password
- **Catatan penting:** Menghapus file dari commit terakhir **TIDAK CUKUP** — file masih ada di history. Harus pakai `git filter-repo` atau BFG Repo-Cleaner.

### 4.4 Directory Listing Aktif (MEDIUM)

**Deskripsi:**
Beberapa direktori mengaktifkan directory listing, memungkinkan enumerasi file.

**URL:**

```
http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/uploads/
http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/config/
http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/classes/
http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/note/
http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/views/
```

**Dampak:**

- Enumerasi file yang pernah di-upload
- Akses file sensitif (foto siswa, surat dokter)
- Reconnaissance struktur aplikasi

**Severity:** 🟡 **MEDIUM** (CVSS 5.3)

**Remediasi:**

```apache
Options -Indexes
```

### 4.5 Session Hijacking via HTTP (MEDIUM)

**Deskripsi:**
Cookie `PHPSESSID` dikirim dalam bentuk **plaintext** (karena tidak ada HTTPS). Attacker di jaringan yang sama bisa sniff traffic dan mengambil cookie untuk hijack session.

**Proof of Concept:**

```
Cookie yang ditangkap via Wireshark:
PHPSESSID=6ridmd343lph1ec08qmghn5ua6
```

**Eksploitasi:**

1. Sniff traffic HTTP di jaringan lokal (Wireshark / tcpdump)
2. Ambil cookie `PHPSESSID` milik victim
3. Inject cookie ke browser (Cookie Editor)
4. Akses aplikasi **tanpa login**

**Dampak:**

- Akses tanpa credential
- Jika session admin yang di-hijack → **full access**

**Severity:** 🟡 **MEDIUM** (CVSS 5.9)

**Remediasi:**

- **Aktifkan HTTPS** (TLS/SSL)
- Set cookie flag:
  ```php
  session_set_cookie_params([
      'secure' => true,
      'httponly' => true,
      'samesite' => 'Strict'
  ]);
  ```
- Regenerasi session ID setelah login (`session_regenerate_id(true)`)
- Implementasi session timeout

### 4.6 Business Logic — Validasi NISN (LOW)

**Deskripsi:**
NISN tidak divalidasi format numerik — bisa diinput karakter apa saja.

**Proof of Concept:**
Input `<script>alert(1)</script>` pada field NISN → **tersimpan di DB** (tapi tidak XSS karena output di-escape `htmlspecialchars()`).

Dari screenshot `siswa_list.php`:

```
NISN: 010101101010
Nama: <script>alert(1)</script>   ← muncul sebagai teks, bukan alert
```

**Dampak:**

- Data tidak akurat
- Memperlambat maintenance
- Potensi data integrity issue
- **Memperparah temuan 4.8**: NISN yang tidak tervalidasi dapat berisi karakter aneh, namun tetap dipakai sebagai username/password

**Severity:** 🟢 **LOW** (CVSS 3.1)

**Remediasi:**

```php
if (!preg_match('/^[0-9]{10}$/', $nisn)) {
    $error = "NISN harus 10 digit angka.";
}
```

### 4.7 Upload Bypass via Base64 (HIGH)

**Deskripsi:**
Endpoint `absensi_siswa.php` menerima input `image` dalam bentuk **base64 data URI** melalui parameter POST. Meskipun upload file langsung sudah di-whitelist ekstensinya, mekanisme base64 ini **tidak divalidasi dengan ketat** — penyerang dapat mengirim gambar JPEG (atau file lain) yang di-encode base64 tanpa melalui validasi ekstensi file konvensional.

**URL:** `http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/absensi_siswa.php`

**Script Exploit:** [LaporanV2/file_bypass.py](file_bypass.py) untuk script yang lebih mudah digunakan, tanpa harus bongkar kode.


**Proof of Concept (`LaporanV2/file_bypass.py`):**

```python
import requests, base64

# Baca gambar & encode ke base64
with open("me.jpeg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

# Field form-data
files = {
    'jenis_absen': (None, 'Hadir'),
    'image': (None, f'data:image/jpeg;base64,{img_b64}'),
    'latitude': (None, '-6.200000'),
    'longitude': (None, '106.816666'),
}

# Session cookie (hasil hijack / login)
cookies = {'PHPSESSID': 'mc99rsr99gaectrbrislcqb9l8'}

# Kirim request
r = requests.post(
    'http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/absensi_siswa.php',
    files=files,
    cookies=cookies,
)

print(r.status_code)
print(r.text[:500])
```

**Cara Menjalankan:**

```bash
cd LaporanV2/
python3 file_bypass.py
```

**Penjelasan Script:**

| Baris                              | Fungsi                                                                     |
|------------------------------------|----------------------------------------------------------------------------|
| `base64.b64encode(...)`            | Encode file `me.jpeg` ke base64                                            |
| `data:image/jpeg;base64,{img_b64}` | Bentuk data URI yang dikirim sebagai field `image`                         |
| `files={...}`                      | Multipart form-data dengan `jenis_absen`, `image`, `latitude`, `longitude` |
| `cookies={'PHPSESSID': ...}`       | Session valid (hasil hijack / login) — bypass autentikasi                  |
| `requests.post(...)`               | Kirim POST ke endpoint absensi                                             |

**Hasil (sebelum patch):**

- Request berhasil dikirim (HTTP 200)
- Gambar base64 tersimpan/diproses oleh server
- Cookie session valid digunakan tanpa login ulang

**Dampak:**

- Bypass validasi ekstensi file upload konvensional
- Potensi upload file berbahaya jika server menyimpan base64 tanpa validasi MIME type
- Data absensi dapat dimanipulasi (jenis absen, koordinat GPS)
- Jika cookie session dicuri, absensi dapat dipalsukan dari jarak jauh

**Severity:** 🟠 **HIGH** (CVSS 7.3) → setelah patch: 🟡 **MEDIUM** (CVSS 5.3)

**Remediasi (rencana awal):**

- Validasi **MIME type** dan **magic bytes** file yang di-decode dari base64
- Batasi ukuran file base64 (misal maks 2MB)
- Simpan file dengan nama random + ekstensi yang sudah ditentukan server
- Jangan percaya `data:image/jpeg;base64,` prefix — verifikasi konten sebenarnya
- Terapkan rate limiting pada endpoint absensi
- Wajibkan autentikasi ulang (re-auth) untuk absensi dengan perubahan lokasi mencurigakan

### 4.8 Kredensial Siswa Default = NISN (CRITICAL)

**Deskripsi:**
Akun siswa menggunakan **NISN sebagai username sekaligus password**. Artinya, siapa pun yang mengetahui NISN seorang siswa dapat login sebagai siswa tersebut. NISN **bukan data rahasia** — tertera di kartu pelajar, rapor, formulir pendaftaran, pengumuman sekolah, dan sering dibagikan dalam konteks administratif. Kombinasi **username = password = NISN** melanggar prinsip dasar autentikasi dan menciptakan **kerentanan account takeover massal**.

**Bukti (dari `temuan.txt`):**

```
admin:kalinadmin08(Administrator)
user:user123(Akun Dummy)
NISN:NISN
```

Interpretasi: akun siswa dibuat dengan pola **username = NISN** dan **password = NISN**. Credential default `admin` dan `user` dikonfirmasi menggunakan password `kalinadmin08` dan `user123`.

**Contoh skenario eksploitasi:**

1. Penyerang memperoleh daftar NISN siswa (dari file `.sql` yang bocor via git history, dari directory listing `uploads/`, atau dari dokumen sekolah yang beredar).
2. Untuk setiap NISN, penyerang mencoba login dengan `username = NISN` dan `password = NISN`.
3. Karena tidak ada mekanisme **rate limiting** maupun **CAPTCHA**, penyerang dapat melakukan **credential stuffing / brute-force** secara efisien.
4. Setelah berhasil login, penyerang dapat:
   - Melihat data pribadi siswa
   - Mengubah absensi (hadir tanpa hadir fisik)
   - Memalsukan lokasi GPS absensi
   - Mengunggah file berbahaya via endpoint absensi menggunakan `LaporanV2/file_bypass.py` (lihat 4.7)

**Proof of Concept (konseptual):**

```
URL: http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/login.php
Username: 010101101010   ← NISN
Password: 010101101010   ← NISN yang sama
```

→ **Login berhasil sebagai siswa** ✅

Karena NISN bersifat sekuensial/terpola, penyerang dapat **mengenumerasi** akun dengan mencoba NISN berurutan.

**Dampak:**

- **Account takeover massal** — semua akun siswa dapat diambil alih jika daftar NISN bocor
- **Impersonasi siswa** — absensi, nilai, dan data dapat dimanipulasi
- **Pelanggaran privasi** — data pribadi siswa (alamat, foto, data orang tua) terekspos
- **Eskalasi ke temuan 4.7** — session siswa yang valid dapat dipakai untuk upload base64 via `LaporanV2/file_bypass.py`
- **Kombinasi dengan 4.3** — DB dump yang bocor berisi NISN → langsung menjadi daftar kredensial valid

**Severity:** 🔴 **CRITICAL** (CVSS 9.4)

**Remediasi:**

- **Jangan pernah** menggunakan NISN sebagai username, apalagi password
- Generate **password acak** saat pembuatan akun siswa (mis. 12+ karakter campuran huruf, angka, simbol)
- Paksa **ganti password saat login pertama** (`must_change_password = 1`)
- Gunakan **username terpisah** dari NISN (mis. `siswa_<id>` atau email)
- Terapkan **kebijakan password kuat** (min 12 karakter, tidak boleh sama dengan username/NISN)
- Tambahkan **rate limiting** dan **CAPTCHA** pada form login
- Aktifkan **logging** percobaan login gagal + alert jika ada pola enumerasi
- Implementasi **2FA** untuk akun dengan hak akses sensitif
- Jika NISN tetap dipakai sebagai identifier, jadikan **hanya sebagai username**, bukan password

**Contoh implementasi aman:**

```php
// Saat membuat akun siswa
$nisn = $data['nisn'];
$username = 'siswa_' . $nisn;  // username terpisah
$password = bin2hex(random_bytes(8));  // 16 char random
$hash = password_hash($password, PASSWORD_BCRYPT);
$must_change = 1;

// Kirim password sementara ke siswa via channel aman (email/WA)
// Paksa ganti saat login pertama
```

**Verifikasi format NISN (kombinasi dengan 4.6):**

```php
if (!preg_match('/^[0-9]{10}$/', $nisn)) {
    $error = "NISN harus 10 digit angka.";
}
```

## 5. Vektor yang Diuji & Aman

| Vektor                          | Status       | Bukti                                                                                                         |
| ------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------- |
| **SQL Injection**               | ✅ Aman      | Semua query pakai `prepare()` + `bindParam()`                                                                 |
| **XSS**                         | ✅ Aman      | Output di-escape `htmlspecialchars()`                                                                         |
| **CSRF**                        | ✅ Aman      | Token + `hash_equals()` di semua form                                                                         |
| **BAC (Broken Access Control)** | ✅ Aman      | Role check di semua file (`$user_role !== 'admin'`)                                                           |
| **Command Injection**           | ✅ Aman      | Tidak ada `exec()`, `system()`, `shell_exec()`                                                                |
| **LFI / RFI**                   | ✅ Aman      | Semua `include` statis                                                                                        |
| **File Upload → RCE**           | ✅ Aman      | Whitelist ekstensi + validasi magic bytes + re-encode GD + nonce liveness (setelah patch v1.2)                |
| **`fix.php` Backdoor**          | ✅ Tidak ada | Sudah dihapus dari server                                                                                     |
| **IDOR**                        | ✅ Tidak ada | `siswa_detail.php` bukan IDOR — semua user boleh lihat data siswa                                             |

## 6. Matriks Risiko

| #   | Temuan                          | Severity    | CVSS | Status                                                    |
| --- | ------------------------------- | ----------- | ---- | --------------------------------------------------------- |
| 4.1 | Git Repository Exposure         | 🔴 Critical | 9.1  | Confirmed                                                 |
| 4.2 | Credential Leak di Git History  | 🔴 Critical | 9.8  | Confirmed (login berhasil)                                |
| 4.3 | Database Dump Ke-commit         | 🟠 High     | 7.5  | Confirmed (masih ada di commit)                           |
| 4.4 | Directory Listing Aktif         | 🟡 Medium   | 5.3  | Confirmed                                                 |
| 4.5 | Session Hijacking via HTTP      | 🟡 Medium   | 5.9  | Confirmed                                                 |
| 4.6 | Business Logic — Validasi NISN  | 🟢 Low      | 3.1  | Confirmed                                                 |
| 4.7 | Upload Bypass via Base64        | 🟠 High     | 7.3  | ✅ Patched (v1.2) — turun ke 🟡 Medium (5.3)              |
| 4.8 | Kredensial Siswa Default = NISN | 🔴 Critical | 9.4  | Confirmed — belum dipatch                                 |

**Total:** 4 Critical, 2 High, 2 Medium, 1 Low → setelah patch 4.7: **4 Critical, 1 High, 3 Medium, 1 Low**

## 7. Rekomendasi Perbaikan

### Prioritas 1 (Immediate)

1. **Blokir akses `.git`** di web server config (Apache/Nginx)
2. **Rotasi seluruh password** (admin, user, DB, siswa)
3. **Hapus git history** yang mengandung credential dan file sensitif:
   ```bash
   git filter-repo --path fix.php --invert-paths
   git filter-repo --path db_management_data_siswa.sql --invert-paths
   ```
   > **Catatan:** Menghapus file dari branch aktif **TIDAK CUKUP**. File masih bisa diakses via commit history. Wajib pakai `git filter-repo` atau BFG.
4. **Hapus `.sql` dari repo** + tambahkan ke `.gitignore`
5. ~~Perbaiki validasi upload base64 di `absensi_siswa.php`~~ — ✅ **DONE** (lihat remediasi 4.7)
6. **Hentikan penggunaan NISN sebagai username/password siswa** — generate password acak, paksa ganti saat login pertama

### Prioritas 2 (Short-term)

7. **Nonaktifkan directory listing** (`Options -Indexes`)
8. **Aktifkan HTTPS** (TLS/SSL)
9. **Set cookie flag**: `Secure`, `HttpOnly`, `SameSite=Strict`
10. **Regenerasi session ID** setelah login
11. **Rate limiting** pada endpoint login dan absensi
12. **CAPTCHA** pada form login

### Prioritas 3 (Long-term)

13. **Validasi input NISN** (hanya angka, 10 digit)
14. **Gunakan environment variable** untuk credential (`.env`)
15. **Aktifkan logging & monitoring** untuk akses `.git`, login gagal, dan upload mencurigakan
16. **Implementasi 2FA** untuk akun admin
17. **Security awareness training** untuk developer
18. **Gunakan `.gitignore`** yang proper sebelum commit (lihat [Bagian 8](#8-panduan-aman-push-ke-github))

## 8. Panduan Aman Push ke GitHub

> **Prinsip:** Jangan pernah commit apapun yang kamu nggak mau dilihat publik. GitHub itu public by default, dan history tersimpan selamanya.

### 8.1 Buat `.gitignore` yang Proper

```gitignore
# ===== CREDENTIAL & SECRET =====
.env
.env.*
!.env.example
*.key
*.pem
*.p12
*.pfx
secrets.json
credentials.json

# ===== DATABASE =====
*.sql
*.sqlite
*.db
*.dump
db_*.sql

# ===== CONFIG =====
config/database.php
config/config.php
config/settings.php

# ===== BACKDOOR / FIX SCRIPTS =====
fix.php
fix_*.php
reset_*.php
test_*.php
*_backup.php

# ===== PAYLOAD / EXPLOIT SCRIPT =====
payload/
exploit*.py
*_bypass.py

# ===== BACKUP & LOG =====
*.bak
*.backup
*.old
*.log
logs/
error_log

# ===== IDE & OS =====
.vscode/
.idea/
*.swp
.DS_Store
Thumbs.db

# ===== DEPENDENCIES =====
node_modules/
vendor/
__pycache__/
*.pyc

# ===== BUILD =====
dist/
build/
*.min.js
*.min.css

# ===== UPLOAD =====
uploads/*
!uploads/.gitkeep
```

> **Catatan:** Folder `payload/` yang berisi script exploit (`file_bypass.py`) **tidak boleh** ikut ter-commit ke repository publik. Ini adalah alat bantu pentest yang sensitif.

### 8.2 Gunakan Environment Variable

Jangan hardcode credential di source code. Pakai `.env`:

**Install:**

```bash
composer require vlucas/phpdotenv
```

**Buat `.env` (JANGAN di-commit):**

```env
DB_HOST=localhost
DB_NAME=db_management_data_siswa
DB_USER=root
DB_PASS=your_secure_password
```

**Buat `.env.example` (INI yang di-commit):**

```env
DB_HOST=localhost
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASS=your_db_password
```

**Update `config/database.php`:**

```php
<?php
require_once __DIR__ . '/../vendor/autoload.php';

$dotenv = Dotenv\Dotenv::createImmutable(__DIR__ . '/..');
$dotenv->load();

class Database {
    private $host;
    private $db_name;
    private $username;
    private $password;

    public function __construct() {
        $this->host     = $_ENV['DB_HOST'];
        $this->db_name  = $_ENV['DB_NAME'];
        $this->username = $_ENV['DB_USER'];
        $this->password = $_ENV['DB_PASS'];
    }
    // ...
}
```

### 8.3 Scan Credential Sebelum Push

**TruffleHog:**

```bash
pip install trufflehog
trufflehog git file://. --only-verified
```

**Gitleaks:**

```bash
docker run -v $(pwd):/path zricethezav/gitleaks:latest detect \
  --source="/path" --verbose
```

**Manual grep:**

```bash
grep -rniE "password|passwd|secret|api_key|token|private_key" . \
  --exclude-dir=.git \
  --exclude-dir=node_modules \
  --exclude-dir=vendor \
  --exclude-dir=payload
```

### 8.4 Pre-commit Hook — Cegah Commit Credential

Buat file `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook: cegah commit credential & payload

PATTERNS=(
    "password\s*=\s*['\"][^'\"]+['\"]"
    "passwd\s*=\s*['\"][^'\"]+['\"]"
    "secret\s*=\s*['\"][^'\"]+['\"]"
    "api_key\s*=\s*['\"][^'\"]+['\"]"
    "token\s*=\s*['\"][^'\"]+['\"]"
    "BEGIN RSA PRIVATE KEY"
    "BEGIN OPENSSH PRIVATE KEY"
)

FILES=$(git diff --cached --name-only --diff-filter=ACM)

# Blokir file di folder payload/
for file in $FILES; do
    if [[ "$file" == payload/* ]]; then
        echo "❌ COMMIT DITOLAK: File '$file' berada di folder payload/ (sensitif)"
        exit 1
    fi
done

for file in $FILES; do
    for pattern in "${PATTERNS[@]}"; do
        if grep -qiE "$pattern" "$file" 2>/dev/null; then
            echo "❌ COMMIT DITOLAK: Potensi credential di file '$file'"
            echo "   Pattern: $pattern"
            exit 1
        fi
    done
done

echo "✅ Pre-commit check passed"
exit 0
```

Beri permission:

```bash
chmod +x .git/hooks/pre-commit
```

**Atau pakai `pre-commit` framework:**

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: detect-private-key
      - id: check-added-large-files
```

Install:

```bash
pip install pre-commit
pre-commit install
```

### 8.5 Kalau Sudah Terlanjur Commit — Bersihkan History

> **Studi kasus:** File `db_management_data_siswa.sql` sudah dihapus dari branch aktif, tapi **masih ada di commit history**. Ini adalah kesalahan umum — banyak developer mengira cukup `git rm` saja, padahal file masih bisa diakses via `git show <commit>:<file>`.

**Pakai `git-filter-repo` (recommended):**

```bash
pip install git-filter-repo

# Hapus file dari seluruh history
git filter-repo --path fix.php --invert-paths
git filter-repo --path db_management_data_siswa.sql --invert-paths
git filter-repo --path config/database.php --invert-paths
git filter-repo --path payload/ --invert-paths

# Force push
git push origin --force --all
git push origin --force --tags
```

**Atau pakai BFG Repo-Cleaner:**

```bash
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
java -jar bfg-1.14.0.jar --delete-files fix.php
java -jar bfg-1.14.0.jar --delete-files "*.sql"
java -jar bfg-1.14.0.jar --delete-folders payload

git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
```

**Verifikasi file sudah hilang dari history:**

```bash
git log --all --full-history -- "db_management_data_siswa.sql"
# Output harus kosong
```

> ⚠️ **Peringatan:** Force push menimpa history remote. Koordinasi dengan tim dulu.
> **Wajib:** Rotasi semua password yang bocor — history GitHub mungkin sudah di-cache / di-fork orang lain.

### 8.6 Gunakan GitHub Secrets untuk CI/CD

Jangan taruh credential di workflow file. Set di:

```
Repo → Settings → Secrets and variables → Actions → New repository secret
```

Pakai di workflow:

```yaml
- name: Deploy
  env:
    DB_HOST: ${{ secrets.DB_HOST }}
    DB_USER: ${{ secrets.DB_USER }}
    DB_PASS: ${{ secrets.DB_PASS }}
  run: |
    echo "Deploying..."
```

### 8.7 Checklist Sebelum Push

```
[ ] .gitignore sudah dibuat & proper
[ ] File .env TIDAK di-commit (hanya .env.example)
[ ] File config/database.php TIDAK di-commit
[ ] File *.sql TIDAK di-commit
[ ] File fix.php / reset_*.php TIDAK di-commit
[ ] Folder payload/ TIDAK di-commit (berisi script exploit)
[ ] Credential di source code pakai environment variable
[ ] Pre-commit hook sudah dipasang
[ ] Scan credential pakai TruffleHog / Gitleaks
[ ] git status bersih dari file sensitif
[ ] git diff --cached sudah direview
[ ] Repo GitHub di-set private (kalau perlu)
[ ] GitHub Secrets dipakai untuk CI/CD
[ ] 2FA aktif di akun GitHub
[ ] File sensitif yang sudah dihapus dari branch JUGA dihapus dari history
```

### 8.8 Alur Push yang Benar

```bash
# 1. Inisialisasi git
git init

# 2. Buat .gitignore DULU sebelum apapun
cat > .gitignore << 'EOF'
.env
.env.*
!.env.example
*.sql
*.log
config/database.php
fix.php
payload/
EOF

# 3. Tambahkan file yang aman
git add .gitignore
git add README.md
git add src/
git add config/database.example.php

# 4. Cek apa yang akan di-commit
git status
git diff --cached

# 5. Scan credential
grep -rniE "password|secret|api_key" . --exclude-dir=.git --exclude-dir=payload

# 6. Commit
git commit -m "Initial commit"

# 7. Push ke GitHub
git remote add origin https://github.com/username/repo.git
git branch -M main
git push -u origin main
```

### 8.9 Emergency Response — Kalau Credential Bocor

**Immediate (0-1 jam):**

1. Rotasi semua password yang bocor
2. Revoke API key / token yang bocor
3. Hapus file dari repo + **history** (bukan hanya branch)
4. Force push ke remote

**Short-term (1-24 jam):**

5. Cek log akses — apakah ada login mencurigakan?
6. Notifikasi tim — kasih tau kalau ada insiden
7. Monitor akun / sistem terkait

**Long-term (1-7 hari):**

8. Audit semua repo untuk credential lain
9. Update `.gitignore` di semua repo
10. Training developer soal security

## 9. Lampiran

### A. Struktur Folder

Folder `LaporanV2/` berisi dokumen, PoC, dan source code yang dipatch:

```
LaporanV2/
├── Laporanv2.md          ← dokumen ini
├── file_bypass.py        ← PoC upload bypass base64
├── me.jpeg               ← sample image untuk PoC
├── note.md               ← catatan perbaikan (v1.1 & v1.2)
└── siswa_absensifix.php  ← source code yang sudah dipatch
```

**`LaporanV2/file_bypass.py`:**

```python
import requests, base64

# Baca gambar & encode ke base64
with open("me.jpeg", "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

# Field form-data
files = {
    'jenis_absen': (None, 'Hadir'),
    'image': (None, f'data:image/jpeg;base64,{img_b64}'),
    'latitude': (None, '-6.200000'),
    'longitude': (None, '106.816666'),
}

# Session cookie (hasil hijack / login)
cookies = {'PHPSESSID': 'mc99rsr99gaectrbrislcqb9l8'}

# Kirim request
r = requests.post(
    'http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/absensi_siswa.php',
    files=files,
    cookies=cookies,
)

print(r.status_code)
print(r.text[:500])
```

**Cara menjalankan:**

```bash
cd LaporanV2/
python3 file_bypass.py
```

**Dependensi:**

```bash
pip install requests
```

### B. Command yang Digunakan

```bash
# Reconnaissance
feroxbuster -u http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2 -w /usr/share/wordlists/dirb/common.txt

# Git dump
git-dumper http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/.git/ ./hasil-git

# Credential search
git log -p --all | grep -iE "password|secret|api_key|token"

# Cari file yang sudah dihapus dari branch tapi masih di history
git log --all --full-history -- "db_management_data_siswa.sql"
git show <commit_hash>:db_management_data_siswa.sql

# Directory listing check
curl http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/uploads/

# Upload bypass base64 (via LaporanV2/file_bypass.py)
cd LaporanV2/
python3 file_bypass.py

# Login siswa dengan NISN (konseptual)
# Username: <NISN>  Password: <NISN>
```

### C. Timeline

| Tanggal     | Aktivitas                                                              |
| ----------- | ---------------------------------------------------------------------- |
| 21 Sep 2026 | Reconnaissance + git-dumper                                            |
| 21 Sep 2026 | Analisis source code + credential leak                                 |
| 22 Sep 2026 | Login admin + testing vektor lain                                      |
| 22 Sep 2026 | Session hijacking test (Wireshark)                                     |
| 22 Sep 2026 | Testing upload webshell (gagal — whitelist ketat)                      |
| 22 Sep 2026 | Upload bypass via base64 (`LaporanV2/file_bypass.py`)                  |
| 22 Sep 2026 | Identifikasi kredensial siswa default = NISN                           |
| 22 Sep 2026 | Konfirmasi file `.sql` masih ada di commit history                     |
| 22 Sep 2026 | Konfirmasi credential `admin:kalinadmin08` & `user:user123`            |
| 23 Sep 2026 | Patch v1.1: CSRF, validasi base64, MIME, GPS, nama file random         |
| 23 Sep 2026 | Patch v1.2: liveness nonce, rate limit, re-encode GD, logging          |
| 23 Sep 2026 | Verifikasi patch dengan `file_bypass.py` (sebagian besar ditolak)      |

### D. Struktur File yang Ter-recover

```
hasil-git/
├── absensi.php
├── absensi_rekap.php
├── classes/
│   ├── auth.php
│   ├── database.php
│   ├── guru.php
│   ├── kelas.php
│   └── siswa.php
├── config/
│   └── database.php
├── db_management_data_siswa.sql   ← DB dump (masih ada di commit history)
├── guru_edit.php / guru_hapus.php / guru_list.php / guru_tambah.php
├── index.php
├── kelas_edit.php / kelas_hapus.php / kelas_list.php / kelas_tambah.php
├── laporan.php
├── login.php / logout.php
├── siswa_detail.php / siswa_edit.php / siswa_hapus.php / siswa_list.php / siswa_tambah.php
├── uploads/
└── views/
    ├── footer.php
    └── header.php
```

### E. Referensi

- OWASP Top 10 2021: A01 (Broken Access Control), A02 (Cryptographic Failures), A04 (Insecure Design), A05 (Security Misconfiguration), A07 (Identification and Authentication Failures)
- OWASP File Upload Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- CWE-538: File and Directory Information Exposure
- CWE-798: Use of Hard-coded Credentials
- CWE-548: Exposure of Information Through Directory Listing
- CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
- CWE-434: Unrestricted Upload of File with Dangerous Type
- CWE-521: Weak Password Requirements
- CWE-262: Not Using Password Aging
- CWE-352: Cross-Site Request Forgery (CSRF)
- NIST SP 800-63B: Digital Identity Guidelines (Authentication)
- PHP Manual: [`finfo_buffer`](https://www.php.net/manual/en/function.finfo-buffer.php), [`getimagesizefromstring`](https://www.php.net/manual/en/function.getimagesizefromstring.php), [`base64_decode`](https://www.php.net/manual/en/function.base64-decode.php)
- GitHub Docs: Removing sensitive data from a repository
- Git Docs: `git filter-repo` — https://github.com/newren/git-filter-repo

---

**— END OF REPORT —**

_Laporan ini dibuat untuk keperluan pembelajaran / authorized pentest. Penggunaan tanpa izin adalah ilegal._