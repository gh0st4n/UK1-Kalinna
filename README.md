# 🔐 Laporan Pentest — Aplikasi Management Data Siswa

Repositori ini berisi laporan hasil **Penetration Testing** terhadap aplikasi **UK1 Management Data Siswa Kalinna Rizki Riah** yang berjalan di lingkungan lab. Terdapat **dua versi laporan**:

- **Laporan V1** — temuan awal (6 temuan, tanpa upload bypass & NISN default).
- **Laporan V2** — laporan terbaru, dengan **2 temuan tambahan Critical/High** (upload bypass base64 & kredensial siswa default = NISN).

## 📂 Struktur Repositori

```
.
├── README.md
├── Laporan/
│   └── Laporan.md          ← Laporan V1 (versi awal)
└── LaporanV2/
    ├── Laporanv2.md        ← Laporan V2 (versi terbaru)
    ├── file_bypass.py      ← PoC upload bypass base64
    ├── me.jpeg             ← Sample image untuk PoC
    └── note.md             ← Catatan perbaikan (anti-bypass webcam.js)
```

## 📋 Pilihan Laporan

| Versi  | Lokasi                                             | Jumlah Temuan     | Fokus                                                                                     |
|--------|----------------------------------------------------|-------------------|-------------------------------------------------------------------------------------------|
| **V1** | [`Laporan/Laporan.md`](Laporan/Laporan.md)         | 2C / 1H / 2M / 1L | Recon, git exposure, credential leak, directory listing, session hijacking, validasi NISN |
| **V2** | [`LaporanV2/LaporanV2.md`](LaporanV2/LaporanV2.md) | 4C / 2H / 2M / 1L | Semua V1 + **upload bypass base64** + **kredensial siswa default = NISN**                 |

## 🆚 Perbedaan Laporan V1 vs V2

### Ringkasan Perubahan

| Aspek              | Laporan V1        | Laporan V2              |
|--------------------|-------------------|-------------------------|
| **Critical**       | 2                 | **4** (+2)              |
| **Jumlah temuan**  | 6                 | 8                       |
| **High**           | 1                 | **2** (+1)              |
| **Medium**         | 2                 | 2                       |
| **Low**            | 1                 | 1                       |
| **CVSS tertinggi** | 9.8               | 9.8                     |
| **Scope**          | `.../UK1-Kalina/` | `.../UK1/UK1-Kalinna2/` |

### Temuan Baru di V2

| #       | Temuan                              | Severity          | Deskripsi Singkat                                                                                                 |
|---------|-------------------------------------|-------------------|-------------------------------------------------------------------------------------------------------------------|
| **4.7** | **Upload Bypass via Base64**        | 🟠 High (7.3)     | Endpoint `absensi_siswa.php` menerima `image` base64 tanpa validasi MIME/dimensi. PoC: `LaporanV2/file_bypass.py` |
| **4.8** | **Kredensial Siswa Default = NISN** | 🔴 Critical (9.4) | Username & password akun siswa = NISN. NISN bersifat semi-publik → **account takeover massal**                    |

### Update pada Temuan Lama di V2

| #   | Temuan                  | Update                                                                                                                                         |
|-----|-------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|
| 4.3 | Database Dump Ke-commit | Dikonfirmasi file `.sql` **sudah dihapus dari branch**, tapi **masih ada di commit history** (`59ae5cd...`). Hash password bcrypt ditampilkan. |
| 4.5 | Session Hijacking       | Sama, tapi dikaitkan dengan temuan 4.7 (session siswa bisa dipakai untuk upload base64).                                                       |
| 4.6 | Validasi NISN           | Dikaitkan dengan 4.8 (NISN invalid tetap dipakai sebagai kredensial login).                                                                    |

### Perbedaan Credential yang Dikonfirmasi

| Role  | V1                   | V2                   |
|-------|----------------------|----------------------|
| Admin | `admin:kalinadmin08` | `admin:kalinadmin08` |
| User  | `user:user99887711`  | **`user:user123`**   |

### Perbaikan yang Diterapkan (V2)

Pada V2 disertakan **patch** untuk temuan 4.7:
- **File:** `LaporanV2/siswa_absensifix.php`
- **Catatan:** `LaporanV2/note.md`
- **Ringkasan perbaikan:**
  - CSRF token
  - Validasi base64 server-side (magic bytes, dimensi, ukuran)
  - Validasi GPS (is_numeric + range)
  - Validasi surat via magic bytes
  - Nama file random (`random_bytes(8)`)
  - Flag `webcamSnapped` di client
  - Cleanup file jika DB gagal

## 🎯 Tujuan

Laporan ini dibuat untuk keperluan **pembelajaran** dan **authorized pentest**. Segala aktivitas yang dilakukan hanya pada lingkungan lab yang telah diizinkan.

## 📖 Cara Membaca

1. Pilih versi laporan:
   - **Pemula / overview:** mulai dari [`LaporanV2/Laporanv2.md`](LaporanV2/Laporanv2.md) (paling lengkap)
   - **Riwayat awal:** baca [`Laporan/Laporan.md`](Laporan/Laporan.md)
2. Baca **Ringkasan Eksekutif** untuk gambaran umum
3. Lihat **Temuan** untuk detail teknis + PoC
4. Ikuti **Rekomendasi Perbaikan** untuk mitigasi
5. Untuk perbaikan upload bypass, lihat [`LaporanV2/note.md`](LaporanV2/note.md)

## ⚠️ Disclaimer

> Laporan ini dibuat untuk keperluan pembelajaran / authorized pentest.  
> Penggunaan tanpa izin adalah **ilegal**.

---

**Author:** gh0st4n  
**Tanggal:** 21–29 September 2026