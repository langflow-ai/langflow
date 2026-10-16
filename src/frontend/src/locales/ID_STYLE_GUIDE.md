# Panduan Gaya Lokalisasi Bahasa Indonesia Langflow

Panduan ini mendokumentasikan konvensi yang digunakan oleh lokalisasi Bahasa Indonesia (`id`) di Langflow. Dokumen ini ditujukan untuk kontributor dan reviewer yang menambah atau memperbaiki string Bahasa Indonesia.

Prinsip utamanya adalah: **pertahankan istilah Langflow/developer yang sudah dikenal, tetapi tulis kalimat di sekitarnya dalam Bahasa Indonesia yang alami.** Jangan menerjemahkan kata demi kata jika hasilnya membuat UI terdengar kaku atau tidak lazim.

## 1. Cakupan

Lokalisasi Bahasa Indonesia mencakup dua katalog:

- Frontend: `src/frontend/src/locales/id.json`
  - seluruh katalog UI frontend
  - tombol, label, menu, dialog, pesan error, pengaturan, UI Playground, dan teks antarmuka lainnya
- Backend: `src/backend/base/langflow/locales/id.json`
  - deskripsi Component
  - `info` pada field
  - `placeholder` backend yang memang perlu diterjemahkan
  - deskripsi/konten starter Flow yang termasuk dalam konvensi lokalisasi backend
  - `template_notes.*`

Kategori nama/display name di backend sengaja **tidak** diterjemahkan agar fallback ke Bahasa Inggris tetap berlaku:

- Component `display_name`
- display name field/output jika termasuk kategori nama
- `starter_flows.*.name`

Keputusan ini disengaja. Nama yang juga muncul di dokumentasi, contoh, referensi Component, atau bagian Langflow lain tetap mudah dikenali, sementara teks penjelasan dan bantuan tersedia dalam Bahasa Indonesia.

## 2. Istilah produk dan teknis

Istilah Langflow dan developer yang sudah umum biasanya tetap menggunakan Bahasa Inggris jika itu membuat UI lebih jelas dan konsisten.

Istilah yang umum dipertahankan antara lain:

```text
Flow
Component
Agent
Tool
Provider
Model
Prompt
Template
Playground
Token
Embedding
Vector Store
Knowledge Base
API Key
MCP Server
Global Variable
LLM
JSON
Python
OAuth
endpoint
workflow
```

Ini **bukan** berarti semua istilah teknis berbahasa Inggris harus selalu dibiarkan dalam Bahasa Inggris. Konteks dan kealamian Bahasa Indonesia tetap menjadi prioritas.

Pertahankan istilah Bahasa Inggris jika:

- istilah tersebut merupakan konsep atau nama UI Langflow yang perlu dikenali pengguna di tempat lain;
- terjemahannya akan membuat istilah kurang familier bagi developer;
- istilah yang sama digunakan dalam dokumentasi, konfigurasi, kode, atau permukaan UI Langflow lain.

Gunakan Bahasa Indonesia yang alami jika:

- kata tersebut merupakan prose UI biasa, bukan konsep produk;
- sudah ada istilah perangkat lunak Bahasa Indonesia yang jelas dan umum;
- mempertahankan Bahasa Inggris menghasilkan bentuk campuran yang terasa janggal.

Contoh:

```text
Flow tidak ditemukan.
Pilih Provider untuk Model ini.
Tambahkan API Key sebelum menjalankan Flow.
Respons dikirim secara streaming.
URL Otorisasi
```

Jangan memaksakan istilah glossary tetap dalam Bahasa Inggris jika kata pada sumber sedang dipakai dalam arti umum, bukan sebagai konsep produk. Selalu periksa konteks UI.

## 3. Nada dan gaya Bahasa Indonesia

Gunakan Bahasa Indonesia UI perangkat lunak yang profesional tetapi tetap alami.

- Buat tombol dan label sesingkat mungkin tanpa kehilangan makna.
- Tulis seperti aplikasi yang sejak awal dibuat dalam Bahasa Indonesia, bukan seperti kalimat Bahasa Inggris yang dipindahkan susunannya.
- Hindari bahasa yang terlalu birokratis atau terlalu formal.
- Hindari penggunaan bentuk pasif berlebihan jika bentuk aktif terdengar lebih alami.
- Hindari kata kerja campuran Inggris-Indonesia yang janggal jika tersedia ungkapan Bahasa Indonesia yang umum.
- Pertahankan istilah teknis Bahasa Inggris jika terjemahannya justru membuat UI lebih sulit dikenali.
- Pertahankan tingkat ketegasan dan maksud sumber.
- Jangan menambahkan penjelasan, janji, atau makna baru yang tidak ada pada sumber Bahasa Inggris.

Contoh yang disukai:

```text
Coba lagi.
Workflow gagal dijalankan.
Data pengguna berhasil diperbarui.
Build ulang Flow sebelum menggunakan chat.
```

Hindari bentuk kaku seperti:

```text
Run workflow gagal
Build Flow kembali sebelum menggunakan chat
respons di-stream
Diresolve di ...
```

## 4. Pola UI yang disukai

Gunakan pola berikut sebagai acuan umum, tetapi tetap periksa konteks.

| Bahasa Inggris | Bahasa Indonesia yang disukai |
|---|---|
| Save | Simpan |
| Delete | Hapus |
| Cancel | Batal |
| Retry | Coba lagi |
| Download | Unduh |
| Upload | Unggah |
| Loading | Memuat |
| Failed to… | Gagal … |
| Configure | Konfigurasikan |
| Authorization | Otorisasi |

Contoh lain dari locale yang sudah selesai:

```text
User edited         → Data pengguna berhasil diperbarui.
Run workflow failed → Workflow gagal dijalankan.
Authorization URL   → URL Otorisasi
stream the response → respons dikirim secara streaming
```

### `run`, `deploy`, `build`, dan istilah developer serupa

Pemakaiannya bergantung pada konteks.

Pertahankan bentuk Bahasa Inggris/developer jika istilah tersebut berfungsi sebagai konsep, nama proses, command, atau kata benda yang memang umum dikenali:

```text
background run
build process
deploy configuration
```

Gunakan frase Bahasa Indonesia jika kalimat menjadi lebih alami tanpa menghilangkan makna teknis:

```text
Run workflow failed          → Workflow gagal dijalankan
Rebuild Flow before chatting → Build ulang Flow sebelum menggunakan chat
stream the response          → respons dikirim secara streaming
```

Jangan membuat bentuk campuran hanya demi mempertahankan kata kerja Bahasa Inggris. Hindari bentuk seperti `di-stream`, `di-strip`, atau `di-resolve` jika ada konstruksi Bahasa Indonesia yang jelas.

## 5. Format dan invariant

Terjemahan wajib mempertahankan struktur runtime dan format yang memiliki makna teknis.

Pertahankan:

```text
{{variable}}
{variable}
${variable}
%(name)s
<0>...</0>
Markdown
URLs
code
commands
environment variable names
identifiers
API names
filenames
paths
product names
```

### Placeholder

Jangan menerjemahkan, mengganti nama, menambah, atau menghapus identifier placeholder.

Contoh:

```text
{{name}}
{{count}}
{current_date}
${value}
%(name)s
```

Jika tata bahasa di sekitar placeholder terasa janggal dalam Bahasa Indonesia, ubah susunan kalimat di sekitarnya. Jangan mengubah placeholder.

### Tag bernomor

Tag seperti:

```text
<0>...</0>
<1>...</1>
```

harus tetap memiliki pasangan dan nesting yang benar. Satu pasangan tag lengkap boleh berpindah bersama teks yang dibungkusnya, tetapi urutan tag pembuka dan penutup harus tetap valid.

Tidak valid:

```text
</1>text<1>
<1>text</2>
```

### Markdown dan kode

Untuk `template_notes.*`:

- pertahankan struktur heading, list, link, dan code fence;
- pertahankan inline code dan contoh yang dapat dieksekusi;
- pertahankan command, filename, path, identifier, dan environment variable name;
- pastikan link Markdown tetap valid;
- jangan mengubah URL kecuali sumber Bahasa Inggris memang berubah.

Terjemahkan prose penjelas di sekitar struktur tersebut, bukan struktur teknisnya.

## 6. Konvensi lokalisasi backend

Lokalisasi backend sengaja menerjemahkan **teks deskriptif/bantuan**, bukan nama yang tampil di UI.

| Kategori key backend | Perlakuan dalam Bahasa Indonesia |
|---|---|
| Component `display_name` | jangan dimasukkan; fallback ke Bahasa Inggris |
| display name field/output | jangan dimasukkan jika termasuk kategori display name |
| `starter_flows.*.name` | jangan dimasukkan; fallback ke Bahasa Inggris |
| Component `description` | diterjemahkan |
| field `info` | diterjemahkan |
| `placeholder` yang relevan | diterjemahkan jika berupa teks instruksi UI |
| deskripsi/konten starter Flow dalam subset yang ditetapkan | diterjemahkan |
| `template_notes.*` | prose diterjemahkan; struktur Markdown/kode dipertahankan |

Alasan pembagian ini:

- Nama Component dan field merupakan identifier stabil yang juga dilihat pengguna di dokumentasi dan contoh.
- Deskripsi dan help text yang dilokalkan membantu pemahaman tanpa membuat identifier tersebut lebih sulit dikenali.
- Key backend mengandung hash yang berasal dari teks sumber Bahasa Inggris. Salin key apa adanya dan jangan pernah mengubah bagian hash.

Jika teks deskriptif menyebut Component lain, field, API, environment variable, filename, atau path, pertahankan nama teknis yang terlihat di UI/kode kecuali konteksnya jelas merupakan prose biasa.

## 7. Konsistensi

String sumber Bahasa Inggris yang sama sebaiknya menggunakan terjemahan Bahasa Indonesia yang sama jika konteksnya setara.

Namun, konteks lebih penting daripada konsistensi mekanis. Terjemahan suatu kata dapat berbeda secara sah jika:

- di satu tempat merupakan tombol, di tempat lain merupakan prose penjelasan;
- di satu tempat merupakan konsep produk, di tempat lain merupakan kata kerja/kata benda biasa;
- merupakan bagian dari contoh kode atau konfigurasi.

Karena itu, checker melaporkan banyak temuan kualitas bahasa sebagai **warning**, bukan hard error.

## 8. Validasi

Jalankan checker locale Bahasa Indonesia dari root repository:

```bash
uv run python scripts/i18n/check_id.py
```

Untuk memeriksa satu katalog saja:

```bash
uv run python scripts/i18n/check_id.py --only frontend
uv run python scripts/i18n/check_id.py --only backend
```

File checkpoint parsial juga dapat diperiksa terhadap salah satu katalog Bahasa Inggris:

```bash
uv run python scripts/i18n/check_id.py --file path/to/part.json --against frontend
uv run python scripts/i18n/check_id.py --file path/to/part.json --against backend
```

Checker memperlakukan masalah struktural sebagai hard error, termasuk:

- file locale hilang atau JSON tidak valid;
- key hilang atau tidak diharapkan;
- value bukan string atau kosong;
- placeholder tidak cocok;
- tag bernomor malformed atau tidak seimbang;
- perubahan URL, Markdown, kode, atau environment variable yang dapat dideteksi dengan aman.

Heuristik bahasa dibuat konservatif dan hanya menghasilkan warning. Hasil zero-error membuktikan konsistensi struktural, tetapi tidak menggantikan review manusia terhadap kealamian Bahasa Indonesia.

Untuk review akhir, jalankan juga:

```bash
git diff --check
git status --short
git diff --stat
```
