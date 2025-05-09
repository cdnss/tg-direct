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

# Fungsi helper untuk menulis ulang URL
def rewrite_url(base_url, proxy_prefix, url_to_rewrite):
    if not url_to_rewrite:
        return url_to_rewrite

    # Jangan rewrite URL yang bukan HTTP/HTTPS atau URL data
    if url_to_rewrite.startswith('mailto:') or \
       url_to_rewrite.startswith('tel:') or \
       url_to_rewrite.startswith('javascript:') or \
       url_to_rewrite.startswith('#') or \
       url_to_rewrite.startswith('data:'):
        return url_to_rewrite

    # Gabungkan URL relatif dengan base_url untuk mendapatkan URL absolut
    absolute_url = urljoin(base_url, url_to_rewrite)

    # Parse URL absolut
    parsed_url = urlparse(absolute_url)

    # Bangun path baru untuk proxy
    # Kita hanya mengambil path dan query string dari URL absolut
    # Dan menambahkannya setelah prefix proxy
    # Contoh: https://lk21.film/some/page?q=test -> /film/some/page?q=test
    new_path = parsed_url.path
    if parsed_url.query:
        new_path += '?' + parsed_url.query

    # Gabungkan prefix proxy dengan path baru
    proxied_url = proxy_prefix.rstrip('/') + new_path # Pastikan hanya satu '/' antara prefix dan path

    # Anda mungkin perlu menangani skema dan netloc secara eksplisit jika proxyPrefix tidak menyediakannya
    # Untuk kasus ini, kita berasumsi prefix proxy '/film/' sudah cukup

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
    headers = request.headers.copy()
    data = await request.read()

    headers.pop('Host', None)
    headers.pop('Origin', None)
    headers.pop('If-Modified-Since', None)
    headers.pop('If-None-Match', None)
    headers.pop('Connection', None)
    headers.pop('Proxy-Connection', None)
    headers.pop('Upgrade', None)

    timeout = ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.request(method, target_url, headers=headers, data=data) as target_response:
                logging.info(f"Menerima respons dari {target_url} dengan status: {target_response.status}")

                proxy_response = web.Response(status=target_response.status)

                for header, value in target_response.headers.items():
                    if header not in ['Content-Encoding', 'Connection', 'Transfer-Encoding']:
                         proxy_response.headers[header] = value

                response_body = await target_response.read()

                # --- Logika penulisan ulang URL dimulai di sini ---
                content_type = target_response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    try:
                        # Dekode body respons (misalnya dari gzip atau deflate jika Content-Encoding ada,
                        # tapi kita sudah menghapus header itu di atas, jadi ini mungkin tidak diperlukan
                        # atau perlu penanganan decoding yang lebih canggih)
                        # Untuk saat ini, asumsikan body adalah byte dari HTML
                        soup = BeautifulSoup(response_body, 'html.parser')

                        # Tulis ulang URL di tag <a>
                        for a_tag in soup.find_all('a', href=True):
                            original_href = a_tag['href']
                            a_tag['href'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_href)

                        # Tulis ulang URL di tag <link> (misalnya CSS)
                        for link_tag in soup.find_all('link', href=True):
                             original_href = link_tag['href']
                             link_tag['href'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_href)

                        # Tulis ulang URL di tag <script> (atribut src)
                        for script_tag in soup.find_all('script', src=True):
                             original_src = script_tag['src']
                             script_tag['src'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_src)

                         # Tulis ulang URL di tag <img> (atribut src)
                        for img_tag in soup.find_all('img', src=True):
                             original_src = img_tag['src']
                             img_tag['src'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_src)

                         # Tulis ulang URL di tag <form> (atribut action)
                        for form_tag in soup.find_all('form', action=True):
                             original_action = form_tag['action']
                             form_tag['action'] = rewrite_url(target_url, PROXY_PREFIX_FILM, original_action)


                        # Dapatkan kembali HTML yang dimodifikasi sebagai string
                        modified_body = str(soup)
                        proxy_response.body = modified_body.encode('utf-8') # Encode kembali ke bytes

                        # Perbarui Content-Length jika ada
                        if 'Content-Length' in proxy_response.headers:
                            proxy_response.headers['Content-Length'] = str(len(proxy_response.body))

                    except Exception as e:
                        logging.error(f"Gagal memproses HTML untuk {target_url}: {e}")
                        # Jika gagal memproses HTML, kirimkan body asli saja
                        proxy_response.body = response_body
                else:
                    # Jika bukan HTML, kirimkan body asli
                    proxy_response.body = response_body
                 # --- Logika penulisan ulang URL berakhir di sini ---


                return proxy_response

        except aiohttp.ClientError as e:
            logging.error(f"Kesalahan saat meminta {target_url}: {e}")
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
