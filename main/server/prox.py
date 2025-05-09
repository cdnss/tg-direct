# File: prox.py - Dengan Content Rewriting (HTML Sederhana)

import aiohttp
from aiohttp import web, ClientTimeout
import logging
# Import library untuk parsing URL
from urllib.parse import urlparse, urljoin, unquote
# Import library untuk parsing HTML
from bs4 import BeautifulSoup # Pastikan Anda sudah menginstal beautifulsoup4 (pip install beautifulsoup4)

# Definisikan objek RouteTableDef untuk route proxy
routes = web.RouteTableDef()

# Definisikan timeout untuk permintaan klien aiohttp
request_timeout = ClientTimeout(total=60)

# Fungsi helper untuk me-rewrite URL dari target ke format proxy
# Skema rewriting: /film/scheme/host/path...
def _rewrite_url(url: str, original_request_url: str, base_url: str) -> str:
    """
    Mere-rewrite URL (relatif atau absolut) agar menunjuk kembali ke proxy.

    Args:
        url: URL yang ditemukan di konten target (misal: '/css/style.css' atau 'https://lk21.film/img/logo.png').
        original_request_url: URL permintaan asli yang masuk ke proxy (misal: 'http://your_server/film/').
        base_url: Base URL dari halaman target (misal: 'https://lk21.film/').
                  Digunakan untuk menyelesaikan URL relatif.
    Returns:
        URL yang di-rewrite agar menunjuk ke proxy (misal: '/film/https/lk21.film/css/style.css').
    """
    # Selesaikan URL relatif menggunakan base_url dari target
    resolved_url = urljoin(base_url, url)

    # Parse URL yang sudah diselesaikan
    parsed_url = urlparse(resolved_url)

    # Kita hanya me-rewrite URL yang menunjuk kembali ke host target asli
    # atau URL yang aslinya relatif dan sudah diselesaikan ke host target.
    # Jika menunjuk ke domain lain, biarkan apa adanya (atau bisa ditangani jika perlu)
    # Untuk penyederhanaan, kita asumsikan hanya me-rewrite yang ke host target.
    # Host target adalah host dari base_url
    parsed_base = urlparse(base_url)
    if parsed_url.netloc != parsed_base.netloc:
         logging.debug(f"Skipping rewrite for external URL: {url} -> {resolved_url}")
         return url # Jangan rewrite URL eksternal (atau tambahkan logika jika perlu)

    # Buat path proxy baru
    # Format: /film/scheme/host/path?query#fragment
    # Kita encode host karena bisa mengandung karakter spesial atau titik
    # Kita encode path juga untuk keamanan
    proxy_path = f"/film/{parsed_url.scheme}/{parsed_url.netloc}{parsed_url.path}"

    # Gabungkan kembali query dan fragment jika ada
    if parsed_url.query:
        proxy_path += f"?{parsed_url.query}"
    if parsed_url.fragment:
        proxy_path += f"#{parsed_url.fragment}"

    # Note: Untuk URL yang sangat kompleks atau mengandung karakter khusus di path/query,
    # Mungkin perlu encoding URL yang lebih cermat dari hanya menggabungkan string.
    # urljoin dengan path proxy yang sudah benar seharusnya menangani sebagian besar kasus.

    logging.debug(f"Rewriting URL: {url} (resolved to {resolved_url}) -> {proxy_path}")

    return proxy_path

# Fungsi helper untuk merekonstruksi URL target asli dari URL proxy
# Kebalikan dari _rewrite_url
def _decode_proxy_url(scheme: str, host: str, path: str, query: str, fragment: str) -> str:
    """
    Merekonstruksi URL target asli dari komponen URL proxy.

    Args:
        scheme: Bagian scheme dari URL proxy (misal: 'https').
        host: Bagian host dari URL proxy (misal: 'lk21.film').
        path: Sisa path setelah scheme/host dari URL proxy.
        query: Bagian query string (tanpa '?').
        fragment: Bagian fragment (tanpa '#').
    Returns:
        URL target asli (misal: 'https://lk21.film/path/to/asset.css?query#fragment').
    """
    # Decode host dan path jika diperlukan (jika _rewrite_url meng-encode-nya)
    # Dalam implementasi _rewrite_url di atas, kita tidak encode host/path secara eksplisit
    # jadi unquote mungkin tidak selalu diperlukan kecuali ada karakter khusus dari URL asli
    original_host = unquote(host)
    original_path = unquote(path)

    target_url = f"{scheme}://{original_host}{original_path}"

    if query:
        target_url += f"?{query}"
    if fragment:
        target_url += f"#{fragment}"

    logging.debug(f"Decoding proxy URL components to target URL: {target_url}")
    return target_url


# Handler untuk route spesifik '/film' (tanpa slash di akhir)
@routes.route('*', '/film')
async def cors_proxy_root(request):
    """
    Handler untuk permintaan ke '/film'. Melakukan proxy ke target URL dasar dan rewriting HTML.
    """
    target_url = 'https://lk21.film/' # Target URL untuk /film
    logging.info(f"Proxying request for /film to {target_url}")

    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    if request.method == "OPTIONS":
        logging.debug("Handling OPTIONS preflight request for /film")
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            }
        )

    try:
        async with aiohttp.ClientSession() as session:
            payload = None
            if request.can_read_body and request.method not in ("GET", "HEAD", "OPTIONS"):
                payload = await request.read()
                logging.debug(f"Reading request body for method {request.method}")

            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=payload,
                timeout=request_timeout
            ) as resp:
                content_type = resp.headers.get('Content-Type', '').lower()
                logging.debug(f"Received Content-Type: {content_type} from {target_url}")

                body = await resp.read() # Body dibaca sebagai byte

                proxy_headers = dict(resp.headers)
                # Tambahkan header CORS
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*'

                # --- Logika Rewriting Konten ---
                if 'text/html' in content_type:
                    logging.debug("Content is HTML, attempting rewriting.")
                    try:
                        # Decode body ke string untuk parsing HTML
                        # Gunakan encoding dari header atau default ke utf-8
                        encoding = resp.charset or 'utf-8'
                        html_string = body.decode(encoding, errors='ignore')

                        soup = BeautifulSoup(html_string, 'html.parser')

                        # Base URL yang akan digunakan untuk menyelesaikan URL relatif
                        # Cari tag <base> di HTML jika ada, jika tidak gunakan target_url
                        base_tag = soup.find('base')
                        if base_tag and base_tag.get('href'):
                             base_for_resolving = urljoin(target_url, base_tag['href'])
                             logging.debug(f"Found <base href='{base_for_resolving}'>")
                        else:
                             base_for_resolving = target_url
                             logging.debug(f"Using target URL as base for resolving: {base_for_resolving}")


                        # Cari dan rewrite URL di berbagai elemen
                        for tag in soup.find_all(['a', 'link', 'script', 'img', 'form']):
                            if tag.has_attr('href'):
                                tag['href'] = _rewrite_url(tag['href'], request.url, base_for_resolving)
                            if tag.has_attr('src'):
                                tag['src'] = _rewrite_url(tag['src'], request.url, base_for_resolving)
                            if tag.has_attr('action'):
                                tag['action'] = _rewrite_url(tag['action'], request.url, base_for_resolving)
                            # Tambahkan atribut atau tag lain jika diperlukan (misal: data-src, poster di video)

                        # Serialisasi kembali HTML yang sudah dimodifikasi
                        modified_body_bytes = str(soup).encode(encoding, errors='ignore')

                        # Update Content-Length header
                        proxy_headers['Content-Length'] = str(len(modified_body_bytes))
                        logging.debug(f"Rewriting HTML body. Original size: {len(body)}, Modified size: {len(modified_body_bytes)}")

                        # Gunakan body yang sudah dimodifikasi
                        body_to_return = modified_body_bytes
                        # Update Content-Type jika charset berubah (walaupun kita coba pertahankan)
                        if 'charset' in proxy_headers.get('Content-Type', ''):
                             proxy_headers['Content-Type'] = f'text/html; charset={encoding}'
                        else:
                             proxy_headers['Content-Type'] = 'text/html' # Pastikan Content-Type tetap text/html


                    except Exception as rewrite_e:
                        logging.error(f"Error during HTML rewriting for {target_url}: {rewrite_e}", exc_info=True)
                        # Jika rewriting gagal, kembalikan body asli (opsional, bisa juga kembalikan error 500)
                        logging.warning("HTML rewriting failed, returning original body.")
                        body_to_return = body
                        # Update Content-Length kembali ke ukuran asli
                        proxy_headers['Content-Length'] = str(len(body_to_return))
                else:
                    # Jika bukan HTML, kembalikan body asli apa adanya
                    logging.debug(f"Content is not HTML ({content_type}), skipping rewriting.")
                    body_to_return = body
                    # Pastikan Content-Length header sesuai body asli
                    proxy_headers['Content-Length'] = str(len(body_to_return))


                # Buat objek respons web dengan body yang sudah dimodifikasi (atau asli jika bukan HTML)
                return_resp = web.Response(
                    status=resp.status,
                    headers=proxy_headers,
                    body=body_to_return # Gunakan body yang sudah di-rewrite atau asli
                )

                # --- Penempatan logging yang lebih aman ---
                logging.debug(f"Returning response for {target_url} with status {return_resp.status}. Body len (returned): {len(body_to_return)}. Original body len: {len(body)}. First 200 bytes (returned): {body_to_return[:200]!r}")
                # --- Akhir penempatan logging ---

                return return_resp # Kembalikan respons

    except Exception as e:
        logging.error(f"Proxy error for {target_url}: {e}", exc_info=True)
        return web.Response(status=500, text=f"Proxy error: {str(e)}")


# Handler untuk route '/film/{scheme}/{host:.*}/{path:.*}'
# Ini menangani permintaan untuk aset (CSS, JS, gambar) yang URL-nya sudah di-rewrite
@routes.route('*', '/film/{scheme}/{host:.*}/{path:.*}')
async def cors_proxy_asset(request):
    """
    Handler untuk aset yang di-rewrite URL-nya. Merekonstruksi URL target asli dan mem-proxy permintaan.
    """
    scheme = request.match_info.get('scheme')
    host = request.match_info.get('host')
    path = request.match_info.get('path', '')
    query = request.rel_url.query_string # Ambil query string dari permintaan proxy
    fragment = request.rel_url.fragment # Ambil fragment dari permintaan proxy

    # Rekonstruksi URL target asli
    try:
         # Gunakan fungsi helper untuk decode
         target_url = _decode_proxy_url(scheme, host, path, query, fragment)
         logging.info(f"Proxying asset request for {request.url} to original target {target_url}")

    except Exception as decode_e:
         logging.error(f"Error decoding proxy asset URL {request.url}: {decode_e}", exc_info=True)
         return web.Response(status=400, text=f"Bad Request: Cannot decode proxied URL: {str(decode_e)}")


    headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'referer', 'origin']} # Mungkin perlu filter header lain
    # Header Referer dan Origin mungkin perlu disesuaikan atau dihapus agar tidak diblokir oleh target server aset

    # Hapus If-None-Match dan If-Modified-Since untuk menghindari cache aset yang salah di browser
    # Ini opsional tapi bisa membantu debugging
    if 'If-None-Match' in headers: del headers['If-None-Match']
    if 'If-Modified-Since' in headers: del headers['If-Modified-Since']


    if request.method == "OPTIONS":
        logging.debug(f"Handling OPTIONS preflight request for asset {request.url}")
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            }
        )

    try:
        async with aiohttp.ClientSession() as session:
            payload = None
            if request.can_read_body and request.method not in ("GET", "HEAD", "OPTIONS"):
                payload = await request.read()
                logging.debug(f"Reading request body for method {request.method}")

            # Lakukan permintaan ke target URL aset DENGAN TIMEOUT
            async with session.request(
                request.method,
                target_url,
                headers=headers, # Gunakan header yang sudah disaring
                data=payload,
                timeout=request_timeout,
                allow_redirects=True # Pastikan mengikuti redirect untuk aset juga
            ) as resp:
                 # Baca body respons dari aset target
                 body = await resp.read() # Body dibaca sebagai byte

                 proxy_headers = dict(resp.headers)
                 # Tambahkan header CORS
                 proxy_headers['Access-Control-Allow-Origin'] = '*'
                 proxy_headers['Access-Control-Allow-Headers'] = '*'
                 proxy_headers['Access-Control-Allow-Methods'] = '*'

                 # Hapus atau modifikasi header yang mungkin menyebabkan masalah di browser
                 # Misalnya, Content-Encoding jika tidak di-handle, X-Frame-Options, dll.
                 # Ini butuh penyesuaian tergantung perilaku situs target
                 if 'Content-Encoding' in proxy_headers and proxy_headers['Content-Encoding'] == 'br' and 'brotli' not in aiohttp.__version__:
                      # Jika brotli tidak diinstal, coba hapus header encoding agar browser tidak salah paham
                      # Alternatifnya, dekompresi di sini jika brotli diinstal
                      logging.warning(f"Brotli encoding detected for asset, but brotli not in aiohttp version. Removing Content-Encoding header.")
                      del proxy_headers['Content-Encoding']
                      # Catatan: Jika body adalah byte terkompresi brotli dan kita hapus headernya,
                      # browser akan menerima byte terkompresi tapi tidak tahu cara mendekompresinya.
                      # Solusi terbaik adalah memastikan brotli terinstal dan aiohttp menanganinya.
                      # Jika tetap error, mungkin perlu dekompresi manual di sini jika body diterima terkompresi.
                 if 'X-Frame-Options' in proxy_headers:
                      # Menghapus ini bisa membantu jika target mencegah rendering di frame
                      logging.debug("Removing X-Frame-Options header.")
                      del proxy_headers['X-Frame-Options']


                 # Pastikan Content-Length sesuai dengan body yang dikembalikan
                 proxy_headers['Content-Length'] = str(len(body))


                 # Buat objek respons web
                 return_resp = web.Response(
                     status=resp.status,     # Gunakan status respons dari target
                     headers=proxy_headers,  # Gunakan header yang dimodifikasi
                     body=body               # Gunakan body respons dari target
                 )

                 # --- Penempatan logging ---
                 logging.debug(f"Returning asset response for {target_url} with status {return_resp.status}. Body len: {len(body)}. First 200 bytes: {body[:200]!r}")
                 # --- Akhir penempatan logging ---

                 return return_resp # Kembalikan respons aset

    except Exception as e:
        # Tangani error yang terjadi selama proses proxy aset
        logging.error(f"Proxy asset error for {target_url} (requested as {request.url}): {e}", exc_info=True)
        return web.Response(status=500, text=f"Proxy asset error: {str(e)}")


# Tidak ada kode lain di sini
