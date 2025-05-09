# File: prox.py

import aiohttp
from aiohttp import web, ClientTimeout
import logging
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup

# Definisikan objek RouteTableDef untuk route proxy
routes = web.RouteTableDef()

# Definisikan base URL untuk rute /film
BASE_URL_FILM = "https://lk21.film"
# Definisikan prefix proxy untuk rute ini
PROXY_PREFIX_FILM = "/film/"

# Definisikan header default yang akan digunakan
DEFAULT_HEADERS = {
    # Coba User-Agent yang berbeda atau biarkan aiohttp default
    # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'User-Agent': 'Mozilla/5.0', # Contoh User-Agent yang lebih sederhana
    # Coba atur Origin, atau hapus jika memicu error 0
    'Origin': BASE_URL_FILM,
    # Tambahkan Referer
    'Referer': BASE_URL_FILM + '/', # Mengatur Referer ke halaman utama target
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive', # aiohttp mengelola ini, tapi kadang membantu
    'Upgrade-Insecure-Requests': '1', # Header umum dari browser
}


# Fungsi helper untuk menulis ulang URL
def rewrite_url(base_url, proxy_prefix, url_to_rewrite):
    if not url_to_rewrite:
        return url_to_rewrite

    if url_to_rewrite.startswith('mailto:') or \
       url_to_rewrite.startswith('tel:') or \
       url_to_rewrite.startswith('javascript:') or \
       url_to_rewrite.startswith('#') or \
       url_to_rewrite.startswith('data:'):
        return url_to_rewrite

    absolute_url = urljoin(base_url, url_to_rewrite)
    parsed_url = urlparse(absolute_url)

    new_path = parsed_url.path
    if parsed_url.query:
        new_path += '?' + parsed_url.query

    proxied_url = proxy_prefix.rstrip('/') + new_path

    return proxied_url


# Definisikan handler asinkron untuk rute /film
@routes.route('*', PROXY_PREFIX_FILM + '{path:.*}')
async def film_proxy_handler(request):
    path_from_request = request.match_info['path']

    if path_from_request:
        target_url = urljoin(BASE_URL_FILM, path_from_request)
    else:
        target_url = BASE_URL_FILM

    target_url = unquote(target_url)

    logging.info(f"Meneruskan permintaan ke: {target_url}")

    method = request.method
    request_data = await request.read()

    # Mulai dengan header default
    headers = DEFAULT_HEADERS.copy()

    # Salin header relevan dari permintaan klien (opsional, hati-hati menimpa DEFAULT_HEADERS)
    # Misalnya, Anda bisa memilih untuk mempertahankan Cookie dari klien jika ada
    # for header, value in request.headers.items():
    #     if header.lower() not in ['host', 'origin', 'user-agent', 'referer', 'connection', 'content-length']: # Jangan timpa header penting kita
    #         headers[header] = value

    # aiohttp akan mengelola header seperti Host, Connection, Content-Length

    timeout = ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            # Kirim permintaan ke URL target dengan header yang dimodifikasi
            async with session.request(method, target_url, headers=headers, data=request_data) as target_response:

                logging.info(f"Mendapat respons {target_response.status} dari {target_url}") # Log status respons

                proxy_response = web.Response(status=target_response.status)

                for header, value in target_response.headers.items():
                    if header.lower() not in ['content-encoding', 'connection', 'transfer-encoding', 'content-length']: # Hapus header yang aiohttp akan kelola atau yang bisa bermasalah
                         proxy_response.headers[header] = value

                response_body = await target_response.read()

                # --- Logika penulisan ulang URL dimulai di sini ---
                content_type = target_response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    try:
                        # Coba deteksi encoding dari respons atau header
                        charset = target_response.charset or 'utf-8'
                        soup = BeautifulSoup(response_body.decode(charset, errors='ignore'), 'html.parser')

                        for tag in soup.find_all(['a', 'link', 'script', 'img', 'form']):
                             if 'href' in tag.attrs:
                                 original_url = tag['href']
                                 tag['href'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_url)
                             elif 'src' in tag.attrs:
                                 original_url = tag['src']
                                 tag['src'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_url)
                             elif 'action' in tag.attrs:
                                 original_url = tag['action']
                                 tag['action'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_url)

                        modified_body = str(soup)
                        proxy_response.body = modified_body.encode('utf-8') # Selalu encode ke utf-8 untuk respons kita

                        if 'Content-Length' in proxy_response.headers:
                             # Perbarui Content-Length karena body sudah dimodifikasi
                             proxy_response.headers['Content-Length'] = str(len(proxy_response.body))
                        # else: # Tambahkan Content-Length jika belum ada
                        #      proxy_response.headers['Content-Length'] = str(len(proxy_response.body))


                    except Exception as e:
                        logging.error(f"Gagal memproses HTML untuk {target_url}: {e}")
                        proxy_response.body = response_body # Kirim body asli jika gagal proses
                else:
                    proxy_response.body = response_body
                # --- Logika penulisan ulang URL berakhir di sini ---


                return proxy_response

        except aiohttp.ClientError as e:
            logging.error(f"Kesalahan saat meminta {target_url}: {e}")
            # Error 0 atau error koneksi lainnya akan tertangkap di sini
            return web.Response(status=500, text=f"Error fetching target URL: {e}")
        except Exception as e:
            logging.error(f"Terjadi kesalahan tak terduga: {e}")
            return web.Response(status=500, text=f"An unexpected error occurred: {e}")

# Anda juga perlu menambahkan bagian untuk menjalankan aplikasi aiohttp
# Contoh sederhana (letakkan di bagian akhir file prox.py):
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.INFO)
#     app = web.Application(routes=routes)
#     web.run_app(app, port=8080)
