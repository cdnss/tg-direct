# Definisikan handler asinkron untuk semua metode HTTP
@routes.route('*', '/{url:.*}')
async def proxy_handler(request):
    url_path = request.match_info['url']
    target_url = unquote(url_path)

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

                # Di sini adalah tempat kita akan menambahkan logika untuk memproses body respons
                # Saat ini, hanya mengembalikan body asli
                proxy_response.body = response_body

                return proxy_response

        except aiohttp.ClientError as e:
            logging.error(f"Kesalahan saat meminta {target_url}: {e}")
            return web.Response(status=500, text=f"Error fetching target URL: {e}")
        except Exception as e:
            logging.error(f"Terjadi kesalahan tak terduga: {e}")
            return web.Response(status=500, text=f"An unexpected error occurred: {e}")
