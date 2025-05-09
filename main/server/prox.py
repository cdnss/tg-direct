# File: prox.py

import aiohttp
from aiohttp import web

# Definisikan objek RouteTableDef untuk route proxy
routes = web.RouteTableDef()

# Handler untuk route spesifik '/film' (tanpa slash di akhir)
@routes.route('*', '/film')
async def cors_proxy_root(request):
    """
    Handler untuk permintaan ke '/film'. Melakukan proxy ke target URL dasar.
    """
    # Target URL untuk /film. Mungkin halaman utama atau halaman default lainnya.
    target_url = 'https://lk21.film/'
    logging.info(f"Proxying request for /film to {target_url}")

    # Salin header dari permintaan asli, kecuali header 'Host'
    # Header 'Host' perlu disesuaikan dengan target_url oleh aiohttp.ClientSession
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    # Tangani permintaan preflight CORS (OPTIONS)
    if request.method == "OPTIONS":
        logging.debug("Handling OPTIONS preflight request for /film")
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*", # Izinkan asal mana pun
                "Access-Control-Allow-Headers": "*", # Izinkan header apa pun
                "Access-Control-Allow-Methods": "*", # Izinkan metode apa pun (GET, POST, OPTIONS, dll)
            }
        )

    try:
        # Buat sesi HTTP klien asinkron
        async with aiohttp.ClientSession() as session:
            # Baca body permintaan jika ada dan bukan metode GET atau HEAD
            payload = None
            if request.can_read_body and request.method not in ("GET", "HEAD", "OPTIONS"): # OPTIONS tidak perlu body
                payload = await request.read()
                logging.debug(f"Reading request body for method {request.method}")

            # Lakukan permintaan ke target URL
            async with session.request(
                request.method,
                target_url,
                headers=headers, # Teruskan header asli
                data=payload     # Teruskan body permintaan
            ) as resp:
                # Baca body respons dari target URL
                body = await resp.read()
                logging.debug(f"Received response from {target_url} with status {resp.status}")

                # Salin header respons dari target URL dan tambahkan header CORS
                proxy_headers = dict(resp.headers)
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*' # Tambahkan lagi untuk respons utama

                # Buat dan kembalikan respons web
                return web.Response(
                    status=resp.status,     # Gunakan status respons dari target
                    headers=proxy_headers,  # Gunakan header yang dimodifikasi
                    body=body               # Gunakan body respons dari target
                )
    except Exception as e:
        # Tangani error yang terjadi selama proses proxy
        import traceback
        logging.error(f"Proxy error for /film: {e}", exc_info=True) # Log error lengkap dengan traceback
        # traceback.print_exc() # Anda bisa tetap mencetak ke konsol jika perlu
        return web.Response(status=500, text=f"Proxy error for /film: {str(e)}") # Kembalikan respons error 500


# Handler untuk route '/film/{tail:.*}' (dengan slash dan path setelahnya)
@routes.route('*', '/film/{tail:.*}')
async def cors_proxy_tail(request):
    """
    Handler untuk permintaan ke '/film/...'. Melakukan proxy ke target URL dengan path tambahan.
    """
    # Ambil sisa path setelah /film/
    tail = request.match_info.get('tail', '')
    # Buat target URL lengkap
    target_url = f'https://lk21.film/{tail}'
    logging.info(f"Proxying request for /film/{tail} to {target_url}")

    # Salin header dari permintaan asli, kecuali header 'Host'
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    # Tangani permintaan preflight CORS (OPTIONS)
    if request.method == "OPTIONS":
        logging.debug(f"Handling OPTIONS preflight request for /film/{tail}")
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*", # Izinkan asal mana pun
                "Access-Control-Allow-Headers": "*", # Izinkan header apa pun
                "Access-Control-Allow-Methods": "*", # Izinkan metode apa pun
            }
        )

    try:
        # Buat sesi HTTP klien asinkron
        async with aiohttp.ClientSession() as session:
            # Baca body permintaan jika ada dan bukan metode GET atau HEAD
            payload = None
            if request.can_read_body and request.method not in ("GET", "HEAD", "OPTIONS"):
                payload = await request.read()
                logging.debug(f"Reading request body for method {request.method}")

            # Lakukan permintaan ke target URL
            async with session.request(
                request.method,
                target_url,
                headers=headers, # Teruskan header asli
                data=payload     # Teruskan body permintaan
            ) as resp:
                # Baca body respons dari target URL
                body = await resp.read()
                logging.debug(f"Received response from {target_url} with status {resp.status}")

                # Salin header respons dari target URL dan tambahkan header CORS
                proxy_headers = dict(resp.headers)
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*' # Tambahkan lagi

                # Buat dan kembalikan respons web
                return web.Response(
                    status=resp.status,     # Gunakan status respons dari target
                    headers=proxy_headers,  # Gunakan header yang dimodifikasi
                    body=body               # Gunakan body respons dari target
                )
    except Exception as e:
        # Tangani error yang terjadi selama proses proxy
        import traceback
        logging.error(f"Proxy error for /film/{tail}: {e}", exc_info=True) # Log error lengkap
        # traceback.print_exc()
        return web.Response(status=500, text=f"Proxy error for /film/...: {str(e)}") # Kembalikan respons error 500

# Tidak ada kode lain di sini, hanya definisi routes dan handlers
