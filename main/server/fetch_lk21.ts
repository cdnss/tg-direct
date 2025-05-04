import cheerio from "https://esm.sh/cheerio@1.0.0-rc.12";

// --- Konfigurasi ---
const TARGET_BASE_URL: string = "https://lk21.film";
const PATH_PREFIX: string = "/film"; // Prefix yang akan ditambahkan ke link internal

// --- Fungsi Utama untuk Mengambil dan Memodifikasi Halaman ---
/**
 * Mengambil halaman dari URL target, memodifikasi link internal menjadi path dengan prefix,
 * dan mengembalikan HTML yang dimodifikasi.
 * @param baseUrl - URL dasar target.
 * @param path - Path spesifik yang akan ditambahkan ke URL dasar.
 * @param prefix - Prefix yang akan ditambahkan ke path link internal.
 * @returns Promise yang mengembalikan string HTML yang sudah dimodifikasi.
 * @throws Error jika gagal mengambil atau memproses halaman.
 */
async function fetchAndModifyPage(baseUrl: string, path: string, prefix: string): Promise<string> {
    const fullUrl = `${baseUrl}/${path}`;
    console.log(`Mengambil data dari: ${fullUrl}`);

    try {
        const response = await fetch(fullUrl);

        if (!response.ok) {
            throw new Error(`Gagal mengambil ${fullUrl}: ${response.statusText} (Status: ${response.status})`);
        }

        const body = await response.text();

        // Muat HTML dengan cheerio
        const $ = cheerio.load(body);

        // Ambil origin dari URL target di luar loop untuk efisiensi
        let targetOrigin: string;
        try {
             targetOrigin = new URL(baseUrl).origin;
        } catch (e) {
             console.error(`URL dasar target tidak valid: ${baseUrl}`, e);
             throw new Error(`Konfigurasi URL dasar target tidak valid.`);
        }


        // Perbarui semua tag <a> dan <link>
        $("a, link").each((_, el) => {
            const $el = $(el);
            const href = $el.attr("href");

            if (!href || href.startsWith('#')) {
                // Abaikan jika href kosong atau hanya link fragment
                return;
            }

            try {
                // Coba parse href menggunakan URL dasar sebagai referensi
                const url = new URL(href, baseUrl);

                // Periksa apakah origin URL yang diparse sama dengan origin URL target
                if (url.origin === targetOrigin) {
                    // Ini adalah link internal (bisa aslinya absolute atau relatif)
                    // Ambil hanya pathname dan query string, lalu tambahkan prefix
                    const newHref = prefix + url.pathname + url.search;
                    $el.attr("href", newHref);
                    // console.log(`Modifikasi internal link: ${href} -> ${newHref}`); // Opsional untuk debugging
                } else {
                    // Ini adalah link eksternal, biarkan apa adanya
                    // console.log(`Melewati link eksternal: ${href}`); // Opsional untuk debugging
                }

            } catch (e) {
                // Tangani error jika href tidak bisa diparse sebagai URL yang valid
                console.warn(`Tidak dapat memproses href "${href}": ${e.message}. Link tidak diubah.`);
                // Link yang tidak bisa diparse dibiarkan apa adanya
            }
        });

        // Kembalikan HTML yang sudah dimodifikasi
        return $.html();

    } catch (error: any) {
        console.error(`Terjadi kesalahan saat memproses ${fullUrl}: ${error.message}`);
        throw error;
    }
}

// --- Fungsi Eksekusi Utama Script ---
async function main() {
    // Ambil path dari argumen baris perintah
    const path = Deno.args[0] || "";

    try {
        // Panggil fungsi untuk mengambil dan memodifikasi halaman
        const modifiedHtml = await fetchAndModifyPage(TARGET_BASE_URL, path, PATH_PREFIX);

        // Cetak HTML yang sudah dimodifikasi ke standard output
        console.log(modifiedHtml);

    } catch (error) {
        // Tangani error yang dilempar oleh fungsi fetchAndModifyPage
        // Pesan error sudah dicetak di dalam fetchAndModifyPage
        Deno.exit(1); // Keluar dengan kode non-nol untuk menandakan kegagalan
    }
}

// Jalankan fungsi main jika script dijalankan langsung
if (import.meta.main) {
    main();
}