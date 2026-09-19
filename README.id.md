<div align="center">

<img src="frame/data/ikon.png" alt="Frame logo" width="120">

# Frame

**Browser ringan berbasis PyQt6 WebEngine, dibangun untuk laptop berspesifikasi rendah.**

[![Tests](https://img.shields.io/github/actions/workflow/status/<owner>/<repo>/tests.yml?branch=main&label=tests)](../../actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#-prasyarat-sistem)
[![PyQt6](https://img.shields.io/badge/PyQt6-%E2%89%A56.6-41cd52)](#-prasyarat-sistem)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#-lisensi)
[![Version](https://img.shields.io/badge/version-0.2.0-orange)](#-status-proyek)

**Bahasa:** 🇮🇩 Indonesia · [🇬🇧 English](./README.md)

</div>

---

## 📋 Daftar Isi

1. [Pengenalan](#-pengenalan)
2. [Prasyarat Sistem](#-prasyarat-sistem)
3. [Instalasi](#-instalasi)
4. [Panduan Penggunaan](#-panduan-penggunaan)
5. [Struktur Proyek & Dokumentasi Kode](#-struktur-proyek--dokumentasi-kode)
6. [Pengujian](#-pengujian)
7. [Keterbatasan yang Diketahui](#-keterbatasan-yang-diketahui)
8. [Kontribusi](#-kontribusi)
9. [Melaporkan Bug](#-melaporkan-bug)
10. [Lisensi](#-lisensi)
11. [Kontak](#-kontak)
12. [Status Proyek](#-status-proyek)

---

## 📖 Pengenalan

**Frame** adalah browser web ringan yang dibangun di atas **PyQt6** dan mesin render **QtWebEngine (Chromium)**. Proyek ini dibuat untuk menjawab satu masalah spesifik: kebanyakan browser modern (Chrome, Edge, Firefox) cukup boros RAM/CPU, sehingga terasa berat di laptop berspesifikasi rendah — sementara alternatif browser "ringan" yang ada seringkali mengorbankan fitur keamanan dasar atau kenyamanan pemakaian sehari-hari.

Frame mencoba mengambil jalan tengah: tetap berbasis mesin Chromium yang matang dan aman (lewat QtWebEngine), tapi dengan konfigurasi, batasan proses, dan mode hemat daya yang bisa disesuaikan untuk perangkat dengan RAM terbatas — tanpa menghilangkan fitur inti yang diharapkan dari browser modern.

### ✨ Fitur Unggulan

| Kategori | Fitur |
|---|---|
| **Performa** | Mode Hemat Daya (WebGL/PDF viewer off, batas proses renderer), auto-deteksi RAM sistem, auto-suspend tab idle dengan whitelist domain |
| **Tab & Navigasi** | Multi-tab dengan pin, duplikat, buka ulang tab tertutup (`Ctrl+Shift+T`), restore session + posisi scroll, tab bar menyatu dengan title bar (gaya Chrome) |
| **Privasi & Keamanan** | AdBlocker berbasis daftar host, jendela penyamaran (cache di memori, tanpa cookie persisten), proteksi kebocoran IP via WebRTC, whitelist skema URL (blokir `javascript:`, `data:`, `vbscript:`, dll.), manajer izin per-situs (kamera/mikrofon/lokasi/notifikasi) |
| **Antarmuka** | Tema gelap/terang, jendela frameless dengan custom title bar + efek glow border, bookmark bar dengan overflow menu, temuan halaman (find-in-page), toast notification |
| **Kenyamanan** | Bookmark, riwayat (maks. 5000 entri), manajer unduhan — semuanya dengan UI bawaan |
| **Integrasi OS** | Bisa didaftarkan sebagai kandidat default browser (Windows/Linux), single-instance dengan IPC (klik link dari aplikasi lain akan diteruskan ke jendela yang sudah terbuka, bukan membuka jendela baru) |

### 🛠️ Teknologi Utama

- **[Python](https://www.python.org/)** 3.10+ — bahasa utama
- **[PyQt6](https://www.riverbankcomputing.com/software/pyqt/)** — binding Qt6 untuk antarmuka desktop
- **[PyQt6-WebEngine](https://pypi.org/project/PyQt6-WebEngine/)** (Chromium/QtWebEngine) — mesin render halaman web
- **[pytest](https://pytest.org/)** — kerangka pengujian otomatis
- **[PyInstaller](https://pyinstaller.org/)** — pembuatan build standalone (`.exe`/binary)
- **GitHub Actions** — CI, menjalankan test matrix di Ubuntu/Windows/macOS × Python 3.10/3.12

> Frame **tidak** menggunakan database eksternal maupun server backend — semua data (bookmark, riwayat, sesi, pengaturan) disimpan lokal dalam file JSON di direktori data pengguna. Tidak ada file `.env` yang dibutuhkan untuk menjalankan proyek ini.

---

## 💻 Prasyarat Sistem

Pastikan hal-hal berikut terpenuhi sebelum instalasi:

| Kebutuhan | Versi Minimum | Keterangan |
|---|---|---|
| **Python** | 3.10 atau lebih baru | Cek dengan `python --version` |
| **pip** | Versi terbaru disarankan | `python -m pip install --upgrade pip` |
| **RAM** | 4 GB (minimum), 8 GB (disarankan) | Di bawah 4 GB, Mode Hemat Daya otomatis aktif |
| **Sistem Operasi** | Windows 10+, macOS 11+, atau Linux (X11/Wayland) | |
| **Ruang disk** | ± 500 MB kosong | Untuk dependensi PyQt6 + komponen Chromium bawaan QtWebEngine |

### Dependensi Python (terpasang otomatis lewat `pip install`)

- `PyQt6 >= 6.6`
- `PyQt6-WebEngine >= 6.6`
- *(opsional, dev)* `pytest >= 7.0`
- *(opsional, perf)* `psutil >= 5.9`

### Library sistem tambahan (khusus Linux)

QtWebEngine butuh beberapa library sistem yang biasanya tidak terpasang secara default:

```bash
sudo apt install libegl1 libgl1 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
  libxcb-xfixes0 libxcb-sync1 libxcb-xkb1 libdbus-1-3
```

> Windows dan macOS tidak butuh langkah tambahan ini — semua dependensi native sudah dibawa oleh wheel `PyQt6-WebEngine`.

---

## 🚀 Instalasi

### 1. Kloning repositori

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
```

### 2. Buat virtual environment (sangat disarankan)

```bash
python -m venv .venv

# Aktifkan:
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# Linux / macOS
source .venv/bin/activate
```

### 3. Instal proyek beserta dependensinya

```bash
# Instalasi standar
pip install -e .

# Kalau ingin sekalian menjalankan test suite (dev)
pip install -e ".[dev]"

# Kalau ingin fitur deteksi RAM yang lebih akurat (opsional)
pip install -e ".[perf]"
```

Perintah `pip install -e .` membaca `pyproject.toml`, memasang `PyQt6`/`PyQt6-WebEngine`, dan mendaftarkan perintah `frame` sebagai entry point (lihat bagian `[project.scripts]` di `pyproject.toml`).

### 4. Variabel lingkungan & konfigurasi

Frame **tidak memerlukan file `.env`**. Tidak ada API key, secret, atau koneksi database yang perlu dikonfigurasi sebelum menjalankan aplikasi. Satu-satunya environment variable yang relevan bersifat opsional:

| Variabel | Fungsi | Wajib? |
|---|---|---|
| `QTWEBENGINE_CHROMIUM_FLAGS` | Override flag Chromium yang dipakai Frame secara default (mis. untuk eksperimen performa) | Tidak — kalau di-set manual, Frame akan menampilkan warning di stderr bahwa flag bawaannya (termasuk proteksi WebRTC) tidak diterapkan |

Pengaturan aplikasi sehari-hari (tema, mode hemat daya, whitelist auto-suspend, dsb.) **tidak** diatur lewat file konfigurasi manual — semuanya tersedia lewat menu **Settings** di dalam aplikasi setelah dijalankan, dan otomatis tersimpan sebagai JSON di direktori data pengguna.

### 5. Database

**Tidak ada database yang perlu disiapkan.** Bookmark, riwayat, sesi, dan pengaturan disimpan sebagai file JSON lokal (dikelola oleh modul `frame/store.py`), dibuat otomatis saat aplikasi pertama kali dijalankan.

---

## 📘 Panduan Penggunaan

### Menjalankan di lingkungan pengembangan

Dari root direktori proyek (dengan virtual environment aktif):

```bash
python -m frame
```

Alternatif — kalau proyek sudah ter-install (`pip install -e .`), bisa juga langsung:

```bash
frame
```

Saat pertama kali dijalankan, Frame otomatis mendeteksi RAM sistem. Kalau RAM terdeteksi di bawah 4 GB, **Mode Hemat Daya** akan aktif otomatis (bisa diubah manual kapan saja lewat Settings).

### Membuka URL langsung dari command line

```bash
python -m frame https://example.com
```

Kalau Frame sudah berjalan (instance lain terdeteksi lewat mekanisme single-instance), URL akan otomatis diteruskan ke jendela yang sudah terbuka — bukan membuka jendela baru.

### Menjalankan test suite

```bash
pytest -q
```

### Membangun executable standalone (build "produksi")

Frame sudah menyediakan `Frame.spec` untuk [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller Frame.spec
```

Hasil build akan muncul di folder `dist/`.

### Menjadikan Frame sebagai kandidat default browser (opsional)

- **Windows**: jalankan `python scripts/install_windows_default.py` lalu ikuti instruksi di layar (import file `.reg` yang dihasilkan, lalu pilih Frame secara manual lewat *Settings → Apps → Default apps* — Windows tidak mengizinkan aplikasi mengubah default browser secara otomatis).
- **Linux**: gunakan berkas `.desktop` standar (`xdg-settings set default-web-browser frame.desktop`).

### Contoh penggunaan fitur utama

| Aksi | Cara |
|---|---|
| Tab baru | `Ctrl+T` atau klik ikon `+` |
| Buka ulang tab yang baru ditutup | `Ctrl+Shift+T` |
| Pindah tab | `Ctrl+Tab` / klik tab |
| Cari di halaman | `Ctrl+F` |
| Jendela penyamaran | Menu ☰ → *New Private Window* |
| Fullscreen | `F11` |
| Buka Settings (tema, mode hemat daya, auto-suspend) | Menu ☰ → *Settings* |

---

## 🗂️ Struktur Proyek & Dokumentasi Kode

```
browser3/
├── frame/                      # Source code utama (package Python)
│   ├── __main__.py             # Entry point: python -m frame
│   ├── core.py                 # Path, logging, i18n, deteksi RAM, flag Chromium
│   ├── main_window.py          # Jendela utama (frameless + tab + toolbar)
│   ├── web.py                  # WebView, BrowserTab, BrowserTabBar, FrameWebPage
│   ├── tab_container.py        # Pemisah QTabBar dari QStackedWidget (tab di title bar)
│   ├── titlebar.py             # Custom title bar (drag, resize, tombol jendela)
│   ├── chrome.py               # Window chrome frameless + efek glow border
│   ├── ui_bars.py              # FindBar, BookmarkBar (dengan overflow), DownloadShelf
│   ├── theme.py                # Warna tema, stylesheet QSS, Qt palette
│   ├── icons.py                # Render ikon SVG → QIcon (DPI-aware, cached)
│   ├── dialogs.py               # Dialog Bookmarks, History, Downloads, Settings
│   ├── store.py                # Persistensi: bookmark, riwayat, sesi, pengaturan (JSON)
│   ├── suspend_manager.py      # Auto-suspend tab idle, pin, whitelist
│   ├── permissions.py          # Manajer izin per-origin (kamera, mikrofon, dll.)
│   ├── adblock.py              # AdBlocker berbasis daftar host
│   ├── internal.py             # Skema `frame://` + halaman New Tab
│   ├── private_window.py       # Jendela penyamaran (wrapper MainWindow)
│   ├── singleton.py            # Single-instance IPC (QLocalServer/QLocalSocket)
│   ├── spinner.py              # Indikator loading berputar di tab
│   ├── toast.py                # Notifikasi toast non-blocking
│   └── data/                   # Aset statis: adblock_hosts.txt, ikon, string i18n
├── scripts/                     # Script pendukung (registrasi default browser Windows)
├── tests/                       # Unit test (pytest)
├── run_frame.py                 # Entry point khusus untuk PyInstaller
├── Frame.spec                   # Konfigurasi build PyInstaller
├── pyproject.toml                # Metadata proyek & dependensi
└── .github/workflows/tests.yml   # CI: test matrix (3 OS × 2 versi Python)
```

### Penjelasan modul-modul utama

<details>
<summary><strong>frame/core.py</strong> — Fondasi aplikasi</summary>

Berisi path direktori data, setup logging, loader i18n, daftar mesin pencari, validasi keamanan URL (`is_safe_url`), dan logika deteksi RAM + pembangunan flag Chromium (`pre_init_should_use_low_end()`, `detect_total_ram_gb()`). Fungsi-fungsi ini dipanggil paling awal, **sebelum** `QApplication` dibuat.
</details>

<details>
<summary><strong>frame/main_window.py</strong> — Jendela utama</summary>

Kelas `MainWindow`: merangkai toolbar navigasi, address bar, tab container, dan seluruh dialog. Menangani restore session, shortcut keyboard, serta koordinasi antar-modul (tema, suspend manager, permission manager).
</details>

<details>
<summary><strong>frame/web.py</strong> — Lapisan web engine</summary>

`WebView` (subclass `QWebEngineView`), `BrowserTab` (satu tab = satu `WebView` + metadata), `BrowserTabBar` (tab bar custom dengan lebar tetap & elide), dan `FrameWebPage` (subclass `QWebEnginePage` untuk intercept navigasi, permission request, dan fullscreen).
</details>

<details>
<summary><strong>frame/store.py</strong> — Persistensi data</summary>

Kelas `Store`: baca/tulis bookmark, riwayat (dibatasi `deque` 5000 entri), sesi tab terakhir, dan pengaturan pengguna — semuanya sebagai file JSON di direktori data. Tidak ada dependensi database eksternal.
</details>

<details>
<summary><strong>frame/suspend_manager.py</strong> — Manajemen tab idle</summary>

Menidurkan tab yang tidak aktif melebihi durasi tertentu (default 180 detik) untuk menghemat RAM, dengan pengecualian untuk tab yang di-pin, domain whitelist, atau tab dengan form yang belum disubmit.
</details>

<details>
<summary><strong>frame/permissions.py</strong> — Izin per-situs</summary>

Menangani sinyal <code>featurePermissionRequested</code> dari <code>QWebEnginePage</code> (kamera, mikrofon, lokasi, notifikasi, clipboard, mouse lock). Keputusan izin disimpan per-origin sehingga tidak perlu ditanya berulang kali.
</details>

<details>
<summary><strong>frame/adblock.py</strong> — Pemblokir iklan</summary>

AdBlocker sederhana berbasis pencocokan host dari <code>frame/data/adblock_hosts.txt</code>, bisa ditambah (override) lewat file <code>filters.txt</code> di direktori data pengguna. Aktif di semua mode, termasuk jendela penyamaran.
</details>

> Setiap modul memiliki docstring di baris paling atas file yang menjelaskan tanggung jawabnya secara singkat — silakan buka langsung file terkait untuk detail parameter dan nilai kembalian tiap fungsi/kelas.

---

## 🧪 Pengujian

Proyek ini memiliki unit test di direktori `tests/`, mencakup:

- `test_adblock.py` — pencocokan host & parsing filter AdBlocker
- `test_permissions.py` — logika keputusan izin, persistensi, mode privat
- `test_store.py` — bookmark, riwayat, top sites, I/O JSON
- `test_suspend_manager.py` — whitelist, toggle, deteksi form "dirty" secara async
- `test_url_safety.py` — validasi skema URL yang diizinkan

Jalankan seluruh test:

```bash
pytest -q
```

CI (GitHub Actions, `.github/workflows/tests.yml`) menjalankan test ini otomatis di setiap `push`/`pull request` ke branch `main`/`master`, pada matriks **Ubuntu, Windows, dan macOS** × **Python 3.10 dan 3.12**.

Ada juga `.pre-commit-config.yaml` opsional yang menjalankan `pytest` otomatis sebelum setiap `git commit` (aktifkan dengan `pre-commit install`).

---

## ⚠️ Keterbatasan yang Diketahui

- **WebRTC**: Frame membatasi ICE candidate ke interface publik saja (`--force-webrtc-ip-handling-policy=default_public_interface_only`) untuk menutup celah kebocoran IP asli saat VPN aktif. Bisa dimatikan lewat *Settings → Privacy*.
- **User-Agent**: Frame **sengaja tidak menyamarkan** User-Agent QtWebEngine. Menyamarkan UA tanpa menyesuaikan Client Hints justru bisa membuat fingerprint lebih mencolok, dan tidak menyelesaikan fingerprinting dari sinyal lain (TLS ClientHello, canvas/WebGL, font list, dll).
- **DNS**: Query DNS keluar plaintext ke resolver OS (belum ada DNS-over-HTTPS bawaan). Sama seperti perilaku default mayoritas browser lain.
- **Permission default**: Semua permintaan izin situs web (kamera, mikrofon, lokasi, dll.) **ditolak secara default** kecuali pengguna mengizinkan secara eksplisit.
- **Bukan pengganti browser lengkap**: belum ada extension, bookmark sync antar-perangkat, atau password manager terintegrasi — cocok untuk pemakaian pribadi/eksperimen, belum ideal sebagai browser harian utama bagi pengguna umum.

---

## 🤝 Kontribusi

Kontribusi dalam bentuk apa pun — laporan bug, ide fitur, atau pull request — sangat diterima.

1. **Fork** repositori ini, lalu buat branch baru dari `main`:
   ```bash
   git checkout -b fitur/nama-fitur-anda
   ```
2. Pastikan lingkungan dev terpasang: `pip install -e ".[dev]"`.
3. Tulis/lengkapi test untuk perubahan Anda di `tests/`.
4. Jalankan test suite sebelum commit:
   ```bash
   pytest -q
   ```
5. (Opsional tapi disarankan) aktifkan pre-commit hook: `pre-commit install`.
6. Commit dengan pesan yang jelas, lalu buka **Pull Request** ke branch `main` dengan deskripsi perubahan dan alasannya.

Untuk perubahan besar (mis. redesign UI atau perubahan arsitektur), disarankan membuka **Issue** diskusi terlebih dahulu sebelum mulai coding, supaya arahnya sejalan dengan tujuan proyek.

---

## 🐛 Melaporkan Bug

Sebelum melapor, cek dulu apakah masalah serupa sudah ada di daftar **Issues**. Kalau belum, buat issue baru dan sertakan informasi berikut supaya lebih cepat ditelusuri:

- **Versi Frame** (lihat `frame/__init__.py` → `__version__`, atau `pyproject.toml`)
- **Sistem Operasi** dan versinya (mis. Windows 11 23H2)
- **Versi Python** (`python --version`) dan **PyQt6** (`pip show PyQt6`)
- **Langkah reproduksi** yang jelas dan terurut
- **Perilaku yang diharapkan** vs **yang terjadi**
- **Log konsol** saat menjalankan `python -m frame` dari terminal (bukan double-click), termasuk pesan error/traceback kalau ada
- **Screenshot/rekaman layar** kalau berkaitan dengan tampilan/UI

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah **Lisensi MIT** — lihat berkas [`LICENSE`](./LICENSE) untuk teks lengkapnya.

---

## 📬 Kontak

Cara tercepat untuk bertanya, memberi saran, atau melaporkan masalah adalah lewat **GitHub Issues** di repositori ini. Isi bagian kontak lain di bawah sesuai preferensi Anda sebagai pengelola proyek:

- **Issues/Diskusi**: gunakan tab *Issues* di repositori GitHub ini
- **Pengelola proyek**: `<isi nama/username Anda>`
- **Email** *(opsional)*: `<isi email kontak Anda>`

---

## 📊 Status Proyek

| Aspek | Status |
|---|---|
| **Versi rilis terbaru** | `0.2.0` (lihat `pyproject.toml`) |
| **Status pengembangan** | Aktif dikembangkan (pre-1.0, belum direkomendasikan untuk distribusi luas ke pengguna awam) |
| **CI/Build** | GitHub Actions — test matrix 3 OS × 2 versi Python (lihat badge di atas) |
| **Cakupan pengujian** | 5 modul inti tercakup unit test (`adblock`, `permissions`, `store`, `suspend_manager`, `url_safety`) |
| **Platform didukung** | Windows 10+, macOS 11+, Linux (X11/Wayland) |

---

<div align="center">

Dibuat dengan 🖤 menggunakan Python & PyQt6.

</div>
