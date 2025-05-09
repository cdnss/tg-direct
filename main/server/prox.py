# File: prox.py

import aiohttp
from aiohttp import web, ClientTimeout # Import ClientTimeout
import logging # Pastikan logging diimpor

# Definisikan objek RouteTableDef untuk route proxy
routes = web.RouteTableDef()

# Definisikan timeout untuk permintaan klien aiohttp (misal, total 60 detik)
request_timeout = ClientTimeout(total=30)


# Handler untuk route spesifik '/film' (tanpa slash di akhir)
@routes.route('*', '/film')
async def cors_proxy_root(request):
    """
    Handler untuk permintaan ke '/film'. Melakukan proxy ke target URL dasar.
    """
    target_url = 'https://lk21.film/'
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

            # Lakukan permintaan ke target URL DENGAN TIMEOUT
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=payload,
                timeout=request_timeout # <--- Timeout diterapkan di sini
            ) as resp:
                # Baca body respons dari target URL
                body = await resp.read() # <--- 'body' diberi nilai di sini jika berhasil

                # Salin header respons dari target URL dan tambahkan header CORS
                proxy_headers = dict(resp.headers)
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*'

                # Buat objek respons web
                return_resp = web.Response(
                    status=resp.status,
                    headers=proxy_headers,
                    body=body
                )

                # --- Penempatan logging yang lebih aman ---
                # Logging dilakukan setelah body berhasil dibaca dan response dibuat
                logging.debug(f"Returning response for {target_url} with status {return_resp.status}. Body len: {len(body)}. First 200 bytes: {body[:200]!r}")
                # --- Akhir penempatan logging ---

                return return_resp # Kembalikan respons

    except Exception as e:
        # Exception apa pun selama session, request, atau read akan tertangkap di sini
        # Ini termasuk asyncio.TimeoutError jika timeout terjadi
        logging.error(f"Proxy error for {target_url}: {e}", exc_info=True) # Log error lengkap
        return web.Response(status=500, text=f"Proxy error: {str(e)}") # Kembalikan respons error 500


# Handler untuk route '/film/{tail:.*}' (dengan slash dan path setelahnya)
@routes.route('*', '/film/{tail:.*}')
async def cors_proxy_tail(request):
    """
    Handler untuk permintaan ke '/film/...'. Melakukan proxy ke target URL dengan path tambahan.
    """
    tail = request.match_info.get('tail', '')
    target_url = f'https://lk21.film/{tail}'
    logging.info(f"Proxying request for /film/{tail} to {target_url}")

    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    if request.method == "OPTIONS":
        logging.debug(f"Handling OPTIONS preflight request for /film/{tail}")
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

            # Lakukan permintaan ke target URL DENGAN TIMEOUT
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=payload,
                timeout=request_timeout # <--- Timeout diterapkan di sini
            ) as resp:
                # Baca body respons dari target URL
                body = await resp.read() # <--- 'body' diberi nilai di sini jika berhasil

                # Salin header respons dari target URL dan tambahkan header CORS
                proxy_headers = dict(resp.headers)
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*'

                # Buat objek respons web
                return_resp = web.Response(
                    status=resp.status,
                    headers=proxy_headers,
                    body=body
                )

                # --- Penempatan logging yang lebih aman ---
                # Logging dilakukan setelah body berhasil dibaca dan response dibuat
                logging.debug(f"Returning response for {target_url} with status {return_resp.status}. Body len: {len(body)}. First 200 bytes: {body[:200]!r}")
                # --- Akhir penempatan logging ---

                return return_resp # Kembalikan respons

    except Exception as e:
        # Exception apa pun selama session, request, atau read akan tertangkap di sini
        logging.error(f"Proxy error for {target_url}: {e}", exc_info=True)
        return web.Response(status=500, text=f"Proxy error: {str(e)}")

# Tidak ada kode lain di sini
