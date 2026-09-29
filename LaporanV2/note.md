# Catatan Perbaikan - Anti Bypass Webcam.js

**File terkait:** `LaporanV2/siswa_absensifix.php`  
**File PoC:** `LaporanV2/file_bypass.py`  
**Tanggal:** 22 September 2026  
**Konteks:** Perbaikan atas temuan **4.7 — Upload Bypass via Base64 (HIGH)** pada [`Laporanv2.md`](Laporanv2.md).

## Daftar Isi

- [Catatan Perbaikan - Anti Bypass Webcam.js](#catatan-perbaikan---anti-bypass-webcamjs)
  - [Daftar Isi](#daftar-isi)
  - [1. Masalah Sebelum Perbaikan](#1-masalah-sebelum-perbaikan)
  - [2. Perubahan yang Dilakukan](#2-perubahan-yang-dilakukan)
    - [2.1 CSRF Token](#21-csrf-token)
    - [2.2 Validasi Base64 Server-Side (`validateBase64Image`)](#22-validasi-base64-server-side-validatebase64image)
    - [2.3 Nama File Random](#23-nama-file-random)
    - [2.4 Validasi GPS](#24-validasi-gps)
    - [2.5 Validasi Surat via Magic Bytes](#25-validasi-surat-via-magic-bytes)
    - [2.6 Folder Tanpa Spasi](#26-folder-tanpa-spasi)
    - [2.7 Flag `webcamSnapped` di Client](#27-flag-webcamsnapped-di-client)
    - [2.8 Hapus File Jika DB Gagal](#28-hapus-file-jika-db-gagal)
  - [3. Yang BELUM Diselesaikan](#3-yang-belum-diselesaikan)
  - [4. Verifikasi Perbaikan](#4-verifikasi-perbaikan)
  - [5. Referensi](#5-referensi)

## 1. Masalah Sebelum Perbaikan

Sebelumnya, endpoint `absensi_siswa.php` (atau varian lamanya) menerima field `image` berupa **base64 data URI** dari client, kemudian **langsung di-decode & disimpan** tanpa validasi yang memadai:

```php
$img = str_replace('data:image/jpeg;base64,', '', $img);
$img = str_replace(' ', '+', $img);
$data = base64_decode($img);
file_put_contents($filePath, $data);
```

**Akibatnya:**

1. Penyerang dapat mengirim **payload Python** ([`file_bypass.py`](file_bypass.py)) yang tidak menggunakan webcam sama sekali — hanya base64 dari file JPEG lokal.
2. Server **tidak memverifikasi** apakah data yang dikirim benar-benar berasal dari webcam.
3. **Tidak ada cek magic bytes** — hanya cek prefix `data:image/jpeg;base64,` yang mudah dipalsukan.
4. **Tidak ada limit ukuran**, sehingga bisa dikirim file besar.
5. **Tidak ada validasi GPS**, sehingga koordinat bisa diisi asal-asalan.
6. **Tidak ada CSRF token**, sehingga request bisa di-CSRF.

## 2. Perubahan yang Dilakukan

### 2.1 CSRF Token

Ditambahkan token CSRF di session dan di form:

```php
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
```

```html
<input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf_token); ?>">
```

Verifikasi di server:

```php
$postedToken = $_POST['csrf_token'] ?? '';
if (!hash_equals($_SESSION['csrf_token'], $postedToken)) {
    // tolak
}
```

**Efek:** request harus berasal dari halaman resmi, tidak bisa direplay dari luar.

### 2.2 Validasi Base64 Server-Side (`validateBase64Image`)

Fungsi baru yang memeriksa:

1. **Prefix data URI** hanya `jpeg`, `jpg`, `png`, `webp`.
2. **Decode strict** (`base64_decode($payload, true)`).
3. **Batas ukuran** (2 MB).
4. **MIME asli** dengan `finfo_buffer()` — bukan hanya string prefix.
5. **Dimensi gambar** dengan `getimagesizefromstring()` — memastikan file benar-benar gambar yang valid, minimal 100×100.

```php
function validateBase64Image(string $dataUri, int $maxBytes = 2097152): array
{
    if (!preg_match('#^data:image/(jpeg|jpg|png|webp);base64,#i', $dataUri, $m)) {
        return [false, 'Format data URI tidak valid.'];
    }
    // ...
    $raw = base64_decode($payload, true);
    if ($raw === false || strlen($raw) === 0) {
        return [false, 'Data base64 tidak valid.'];
    }
    if (strlen($raw) > $maxBytes) {
        return [false, 'Ukuran file melebihi batas.'];
    }
    $finfo = new finfo(FILEINFO_MIME_TYPE);
    $mime  = $finfo->buffer($raw);
    if (!in_array($mime, ['image/jpeg', 'image/png', 'image/webp'], true)) {
        return [false, 'Tipe file tidak diizinkan.'];
    }
    $info = @getimagesizefromstring($raw);
    if ($info === false || $info[0] < 100 || $info[1] < 100) {
        return [false, 'File bukan gambar valid.'];
    }
    return [true, ['raw' => $raw, 'ext' => $ext, 'mime' => $mime]];
}
```

**Efek:** payload [`file_bypass.py`](file_bypass.py) yang mengirim JPEG valid **masih lolos cek MIME**, tetapi **tidak bisa mengirim sembarang file** (mis. webshell PHP) karena:
- MIME asli harus image.
- Dimensi harus valid.
- Ukuran maksimum 2 MB.

### 2.3 Nama File Random

```php
$fileName = 'selfie_' . $siswa_id . '_' . bin2hex(random_bytes(8)) . '.' . $ext;
```

**Efek:** nama file tidak dapat diprediksi (sebelumnya `time()` saja, mudah ditelusuri).

### 2.4 Validasi GPS

```php
if (!is_numeric($latitude) || !is_numeric($longitude)) {
    // tolak
}
$lat = (float) $latitude;
$lon = (float) $longitude;
if ($lat < -90 || $lat > 90 || $lon < -180 || $lon > 180) {
    // tolak
}
```

**Efek:** koordinat harus valid. Attacker yang tidak mengaktifkan GPS tidak bisa mengisi manual (server menolak).

### 2.5 Validasi Surat via Magic Bytes

`validateSuratUpload()` menggunakan `finfo_file()` untuk memastikan file surat benar-benar JPG/PNG/PDF — bukan hanya berdasarkan ekstensi.

```php
$allowed = [
    'image/jpeg'      => 'jpg',
    'image/png'       => 'png',
    'application/pdf' => 'pdf',
];
```

**Efek:** upload file `.php` dengan nama `.jpg` akan ditolak.

### 2.6 Folder Tanpa Spasi

```
uploads/surat dokter/  →  uploads/surat_dokter/
```

**Efek:** menghindari bug path dan memudahkan validasi.

### 2.7 Flag `webcamSnapped` di Client

Di JavaScript:

```js
let webcamSnapped = false;

Webcam.snap(function(data_uri) {
    // ...
    webcamSnapped = true;
    document.getElementById('formAbsen').submit();
});

document.getElementById('formAbsen').addEventListener('submit', function(e) {
    if (currentJenis === 'Hadir' && !webcamSnapped) {
        e.preventDefault();
        Swal.fire('Akses Ditolak', 'Foto harus diambil dari kamera.', 'error');
        return false;
    }
});
```

**Efek:** mencegah user biasa (yang hanya membuka DevTools dan mengisi `<input name="image">` secara manual) untuk submit form.

> **Catatan penting:** Flag client-side ini **hanya mengurangi bypass level rendah**. Penyerang berpengalaman bisa memodifikasi JS atau mengirim request langsung. Karena itu, **validasi server-side (`validateBase64Image`) tetap menjadi pertahanan utama**.

### 2.8 Hapus File Jika DB Gagal

```php
if ($exec) {
    // sukses
} else {
    @unlink($filePath); // bersihkan file yatim
}
```

**Efek:** tidak menumpuk file selfie/surat yang tidak tercatat di DB.

## 3. Yang BELUM Diselesaikan

Beberapa hal yang **belum** ditangani dalam patch ini dan masih perlu perhatian:

| # | Isu                                 | Rekomendasi                                                                                                  |
|---|-------------------------------------|--------------------------------------------------------------------------------------------------------------|
| 1 | **Session Hijacking via HTTP**      | Aktifkan HTTPS + flag `Secure`, `HttpOnly`, `SameSite=Strict` pada cookie session.                           |
| 2 | **Credential default siswa = NISN** | Ganti dengan password acak + paksa ganti saat login pertama.                                                 |
| 3 | **Rate limiting**                   | Batasi jumlah request absensi per IP/siswa per hari.                                                         |
| 4 | **Re-verifikasi lokasi GPS**        | Server dapat membandingkan koordinat dengan geofence sekolah.                                                |
| 5 | **Deteksi liveness**                | Selfie statis masih bisa dipalsukan dengan foto orang lain. Pertimbangkan liveness detection (blink/motion). |
| 6 | **Logging**                         | Catat semua percobaan absensi (berhasil & gagal) untuk audit.                                                |
| 7 | **Backend-side attestation**        | Pertimbangkan WebAuthn / device attestation untuk memastikan foto berasal dari perangkat resmi.              |

## 4. Verifikasi Perbaikan

Untuk memverifikasi bahwa bypass tidak lagi berhasil, jalankan kembali [`file_bypass.py`](file_bypass.py):

```bash
cd LaporanV2/
python3 file_bypass.py
```

**Ekspektasi setelah patch:**

| Skenario                                                                  | Hasil                                                                        |
|---------------------------------------------------------------------------|------------------------------------------------------------------------------|
| Kirim base64 **bukan gambar**                                             | ❌ Ditolak — `Tipe file sebenarnya tidak diizinkan`                         |
| Kirim base64 gambar **< 100×100**                                         | ❌ Ditolak — `resolusi terlalu kecil`                                       |
| Kirim file **> 2 MB**                                                     | ❌ Ditolak — `Ukuran file melebihi batas`                                   |
| Kirim latitude/longitude non-numerik                                      | ❌ Ditolak — `Lokasi GPS wajib diaktifkan`                                  |
| Kirim latitude/longitude di luar range                                    | ❌ Ditolak — `Koordinat GPS di luar rentang`                                |

> **Catatan:** Karena `file_bypass.py` mengirim gambar JPEG yang valid, request **masih bisa lolos** ke tahap penyimpanan. Yang dicegah adalah pengiriman file berbahaya (webshell, dsb.) dan permintaan tanpa CSRF. Untuk **benar-benar mencegah bypass webcam**, perlu ada **liveness detection** atau **device attestation** (lihat #7 pada bagian 3).

## 5. Referensi

- OWASP: [File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- PHP Manual: [`finfo_buffer`](https://www.php.net/manual/en/function.finfo-buffer.php), [`getimagesizefromstring`](https://www.php.net/manual/en/function.getimagesizefromstring.php), [`base64_decode`](https://www.php.net/manual/en/function.base64-decode.php)
- CWE-434: [Unrestricted Upload of File with Dangerous Type](https://cwe.mitre.org/data/definitions/434.html)
- CWE-352: [Cross-Site Request Forgery (CSRF)](https://cwe.mitre.org/data/definitions/352.html)
- Laporan V2: [`Laporanv2.md`](Laporanv2.md) — temuan 4.7 & 4.8
- PoC: [`file_bypass.py`](file_bypass.py)
 
**Perlu diuji ulang** dengan [`file_bypass.py`](file_bypass.py) dan skenario bypass lainnya.  
**Rekomendasi lanjutan:** implementasi liveness detection / device attestation (lihat [Bagian 3](#3-yang-belum-diselesaikan)).