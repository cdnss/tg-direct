import aiohttp
from aiohttp import web

routes = web.RouteTableDef()

@routes.route('*', '/film/{tail:.*}')
async def cors_proxy(request):
    tail = request.match_info.get('tail', '')
    target_url = f'https://lk21.film/{tail}'
    headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}

    # Handle preflight CORS
    if request.method == "OPTIONS":
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
            if request.can_read_body and request.method not in ("GET", "HEAD"):
                payload = await request.read()
            async with session.request(
                request.method,
                target_url,
                headers=headers,
                data=payload
            ) as resp:
                body = await resp.read()
                proxy_headers = dict(resp.headers)
                proxy_headers['Access-Control-Allow-Origin'] = '*'
                proxy_headers['Access-Control-Allow-Headers'] = '*'
                proxy_headers['Access-Control-Allow-Methods'] = '*'
                return web.Response(
                    status=resp.status,
                    headers=proxy_headers,
                    body=body
                )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.Response(status=500, text=f"Proxy error: {str(e)}")

    # Safety net: always return a response
    return web.Response(status=500, text="Unknown proxy error")
