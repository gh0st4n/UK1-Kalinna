# LAPORAN PENTEST — Aplikasi Management Data Siswa

- **Target:** `http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/`
- **Setup Lab:** Aplikasi berjalan di **Windows (Laragon)**, Attacker di **Kali Linux**
- **Tanggal:** 21–22 September 2026
- **Tester:** gh0st4n
- **Metodologi:** Black-box → White-box (setelah recovery source code via `.git`)

## Daftar Isi

- [LAPORAN PENTEST - Aplikasi Management Data Siswa](#laporan-pentest--aplikasi-management-data-siswa)
  - [Daftar Isi](#daftar-isi)
  - [1. Ringkasan Eksekutif](#1-ringkasan-eksekutif)
  - [2. Lingkup \& Setup Lab](#2-lingkup--setup-lab)
  - [3. Metodologi \& Reconnaissance](#3-metodologi--reconnaissance)
    - [Tools](#tools)
    - [Reconnaissance](#reconnaissance)
  - [4. Temuan](#4-temuan)
    - [4.1 Git Repository Exposure (CRITICAL)](#41-git-repository-exposure-critical)
    - [4.2 Credential Leak di Git History (CRITICAL)](#42-credential-leak-di-git-history-critical)
    - [4.3 Database Dump Ke-commit (HIGH)](#43-database-dump-ke-commit-high)
    - [4.4 Directory Listing Aktif (MEDIUM)](#44-directory-listing-aktif-medium)
    - [4.5 Session Hijacking via HTTP (MEDIUM)](#45-session-hijacking-via-http-medium)
    - [4.6 Business Logic - Validasi NISN (LOW)](#46-business-logic--validasi-nisn-low)
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
    - [8.4 Pre-commit Hook - Cegah Commit Credential](#84-pre-commit-hook--cegah-commit-credential)
    - [8.5 Kalau Sudah Terlanjur Commit - Bersihkan History](#85-kalau-sudah-terlanjur-commit--bersihkan-history)
    - [8.6 Gunakan GitHub Secrets untuk CI/CD](#86-gunakan-github-secrets-untuk-cicd)
    - [8.7 Checklist Sebelum Push](#87-checklist-sebelum-push)
    - [8.8 Alur Push yang Benar](#88-alur-push-yang-benar)
    - [8.9 Emergency Response - Kalau Credential Bocor](#89-emergency-response--kalau-credential-bocor)
  - [9. Lampiran](#9-lampiran)
    - [A. Command yang Digunakan](#a-command-yang-digunakan)
    - [B. Timeline](#b-timeline)
    - [C. Struktur File yang Ter-recover](#c-struktur-file-yang-ter-recover)
    - [D. Referensi](#d-referensi)

## 1. Ringkasan Eksekutif

Aplikasi **Management Data Siswa** memiliki **2 temuan Critical**, **1 High**, **2 Medium**, dan **1 Low**. Temuan paling berdampak adalah **eksposur folder `.git`** yang memungkinkan penyerang mengambil **seluruh source code** dan **credential admin** dari **git history**.

Dengan credential yang didapat, penyerang bisa **login sebagai admin** dan mengakses seluruh fungsi aplikasi. Meskipun aplikasi sudah menerapkan **prepared statement**, **CSRF token**, **role-based access control**, dan **whitelist ekstensi upload** dengan baik, **kebocoran source code & credential** membuat pertahanan tersebut menjadi tidak relevan.

**Catatan penting:** Setup lab ini **sengaja** dibuat rentan untuk keperluan pembelajaran. Di lingkungan production, konfigurasi seperti ini **tidak boleh** terjadi.

**Prioritas perbaikan:**

1. Blokir akses ke `.git` di web server (Production)
2. Rotasi seluruh password
3. Hapus git history yang mengandung credential (Production)
4. Nonaktifkan directory listing
5. Gunakan HTTPS + flag `Secure`/`HttpOnly` pada cookie
6. Terapkan praktik aman push ke GitHub (lihat [Bagian 8](#8-panduan-aman-push-ke-github))

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

- `feroxbuster` - directory brute-force
- `git-dumper` - recovery `.git`
- `exiftool` - analisis file
- `Wireshark` - sniffing cookie
- `curl` / browser - manual testing

### Reconnaissance

```bash
feroxbuster -u http://192.168.100.247/UK-PKL_Banjar/UK1-Kalina \
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
$passUser  = password_hash('user99887711', PASSWORD_BCRYPT);
echo "<p>Password Admin: <b>kalinadmin08</b></p>";
echo "<p>Password User: <b>user99887711</b></p>";
```

**Credential yang Didapat:**

| Role  | Username | Password       | Status         |
| ----- | -------- | -------------- | -------------- |
| Admin | `admin`  | `kalinadmin08` | Login berhasil |
| User  | `user`   | `user99887711` | Valid          |

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
File `db_management_data_siswa.sql` ikut ter-commit ke repository, berisi struktur DB + data siswa + hash password.

**Proof of Concept:**

```bash
cat db_management_data_siswa.sql
```

**Isi:**

- Data guru (5 record)
- Data kelas (9 record)
- Data siswa (22 record: NISN, nama, alamat, foto)
- Data user (username + hash password)

**Hash Password:**

```
admin : d7caed25e5bf33da4e752d774afed033
user  : f0bdd8a9ebdae53c6a61907a4333c9e9
```

_Catatan: hash MD5 ini kemungkinan sudah tidak valid (diganti bcrypt via `fix.php`)._

**Dampak:**

- Data pribadi siswa bocor (nama, NISN, alamat, foto)
- Struktur DB terekspos

**Severity:** 🟠 **HIGH** (CVSS 7.5)

**Remediasi:**

- Hapus file `.sql` dari repository
- Tambahkan `*.sql` ke `.gitignore`
- Rotasi hash password

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

**Severity:** 🟢 **LOW** (CVSS 3.1)

**Remediasi:**

```php
if (!preg_match('/^[0-9]{10}$/', $nisn)) {
    $error = "NISN harus 10 digit angka.";
}
```

## 5. Vektor yang Diuji & Aman

| Vektor                          | Status       | Bukti                                                                          |
| ------------------------------- | ------------ | ------------------------------------------------------------------------------ |
| **SQL Injection**               | ✅ Aman      | Semua query pakai `prepare()` + `bindParam()`                                  |
| **XSS**                         | ✅ Aman      | Output di-escape `htmlspecialchars()`                                          |
| **CSRF**                        | ✅ Aman      | Token + `hash_equals()` di semua form                                          |
| **BAC (Broken Access Control)** | ✅ Aman      | Role check di semua file (`$user_role !== 'admin'`)                            |
| **Command Injection**           | ✅ Aman      | Tidak ada `exec()`, `system()`, `shell_exec()`                                 |
| **LFI / RFI**                   | ✅ Aman      | Semua `include` statis                                                         |
| **File Upload → RCE**           | ✅ Aman      | Whitelist ekstensi (`jpg`, `jpeg`, `png`, `webp`, `pdf`) + nama file di-random |
| **`fix.php` Backdoor**          | ✅ Tidak ada | Sudah dihapus dari server                                                      |
| **IDOR**                        | ✅ Tidak ada | `siswa_detail.php` bukan IDOR - semua user boleh lihat data siswa              |

## 6. Matriks Risiko

| #   | Temuan                         | Severity    | CVSS | Status                     |
| --- | ------------------------------ | ----------- | ---- | -------------------------- |
| 4.1 | Git Repository Exposure        | 🔴 Critical | 9.1  | Confirmed                  |
| 4.2 | Credential Leak di Git History | 🔴 Critical | 9.8  | Confirmed (login berhasil) |
| 4.3 | Database Dump Ke-commit        | 🟠 High     | 7.5  | Confirmed                  |
| 4.4 | Directory Listing Aktif        | 🟡 Medium   | 5.3  | Confirmed                  |
| 4.5 | Session Hijacking via HTTP     | 🟡 Medium   | 5.9  | Confirmed                  |
| 4.6 | Business Logic - Validasi NISN | 🟢 Low      | 3.1  | Confirmed                  |

**Total:** 2 Critical, 1 High, 2 Medium, 1 Low

## 7. Rekomendasi Perbaikan

### Prioritas 1 (Immediate)

1. **Blokir akses `.git`** di web server config (Apache/Nginx)
2. **Rotasi seluruh password** (admin, user, DB)
3. **Hapus git history** yang mengandung credential:
   ```bash
   git filter-repo --path fix.php --invert-paths
   git filter-repo --path db_management_data_siswa.sql --invert-paths
   ```
4. **Hapus `.sql` dari repo** + tambahkan ke `.gitignore`

### Prioritas 2 (Short-term)

5. **Nonaktifkan directory listing** (`Options -Indexes`)
6. **Aktifkan HTTPS** (TLS/SSL)
7. **Set cookie flag**: `Secure`, `HttpOnly`, `SameSite=Strict`
8. **Regenerasi session ID** setelah login

### Prioritas 3 (Long-term)

9. **Validasi input NISN** (hanya angka, 10 digit)
10. **Gunakan environment variable** untuk credential (`.env`)
11. **Aktifkan logging & monitoring** untuk akses `.git`
12. **Security awareness training** untuk developer
13. **Gunakan `.gitignore`** yang proper sebelum commit (lihat [Bagian 8](#8-panduan-aman-push-ke-github))

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
  --exclude-dir=vendor
```

### 8.4 Pre-commit Hook — Cegah Commit Credential

Buat file `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook: cegah commit credential

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

**Pakai `git-filter-repo` (recommended):**

```bash
pip install git-filter-repo

# Hapus file dari seluruh history
git filter-repo --path fix.php --invert-paths
git filter-repo --path db_management_data_siswa.sql --invert-paths
git filter-repo --path config/database.php --invert-paths

# Force push
git push origin --force --all
git push origin --force --tags
```

**Atau pakai BFG Repo-Cleaner:**

```bash
wget https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar
java -jar bfg-1.14.0.jar --delete-files fix.php
java -jar bfg-1.14.0.jar --delete-files "*.sql"

git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
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
[ ] Credential di source code pakai environment variable
[ ] Pre-commit hook sudah dipasang
[ ] Scan credential pakai TruffleHog / Gitleaks
[ ] git status bersih dari file sensitif
[ ] git diff --cached sudah direview
[ ] Repo GitHub di-set private (kalau perlu)
[ ] GitHub Secrets dipakai untuk CI/CD
[ ] 2FA aktif di akun GitHub
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
grep -rniE "password|secret|api_key" . --exclude-dir=.git

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
3. Hapus file dari repo + history
4. Force push ke remote

**Short-term (1-24 jam):** 5. Cek log akses — apakah ada login mencurigakan? 6. Notifikasi tim — kasih tau kalau ada insiden 7. Monitor akun / sistem terkait

**Long-term (1-7 hari):** 8. Audit semua repo untuk credential lain 9. Update `.gitignore` di semua repo 10. Training developer soal security

## 9. Lampiran

### A. Command yang Digunakan

```bash
# Reconnaissance
feroxbuster -u http://192.168.100.247/UK-PKL_Banjar/UK1-Kalina -w /usr/share/wordlists/dirb/common.txt

# Git dump
git-dumper http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/.git/ ./hasil-git

# Credential search
git log -p --all | grep -iE "password|secret|api_key|token"

# Directory listing check
curl http://192.168.100.247/UK-PKL_Banjar/UK1/UK1-Kalinna2/uploads/
```

### B. Timeline

| Tanggal     | Aktivitas                                         |
| ----------- | ------------------------------------------------- |
| 21 Sep 2026 | Reconnaissance + git-dumper                       |
| 21 Sep 2026 | Analisis source code + credential leak            |
| 22 Sep 2026 | Login admin + testing vektor lain                 |
| 22 Sep 2026 | Session hijacking test (Wireshark)                |
| 22 Sep 2026 | Testing upload webshell (gagal — whitelist ketat) |

### C. Struktur File yang Ter-recover

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
├── db_management_data_siswa.sql   ← DB dump
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

### D. Referensi

- OWASP Top 10 2021: A01 (Broken Access Control), A02 (Cryptographic Failures), A05 (Security Misconfiguration)
- CWE-538: File and Directory Information Exposure
- CWE-798: Use of Hard-coded Credentials
- CWE-548: Exposure of Information Through Directory Listing
- CWE-614: Sensitive Cookie in HTTPS Session Without 'Secure' Attribute
- GitHub Docs: Removing sensitive data from a repository

---

**— END OF REPORT —**

_Laporan ini dibuat untuk keperluan pembelajaran / authorized pentest. Penggunaan tanpa izin adalah ilegal._
