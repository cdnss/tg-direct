
import aiohttp
from aiohttp import web

routes = web.RouteTableDef()

@routes.route('*', '/film/{tail:.*}')
async def cors_proxy(request):
    tail = request.match_info['tail']
    target_url = f'https://lk21.film/{tail}'
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=await request.read()
            ) as resp:
                body = await resp.read()
                proxy_headers = dict(resp.headers)
                # Tambahkan CORS headers
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*'
                return web.Response(
                    status=resp.status,
                    headers=proxy_headers,
                    body=body
                )
    except Exception as e:
        return web.Response(status=500, text=str(e))
