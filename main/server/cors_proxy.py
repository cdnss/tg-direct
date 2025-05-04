import aiohttp
from aiohttp import web

async def cors_proxy_handler(request):
    target_url = "https://lk21.film"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(target_url) as response:
                body = await response.read()
                headers = {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Content-Type": response.headers.get("Content-Type", "application/json"),
                }
                return web.Response(body=body, status=response.status, headers=headers)
    except aiohttp.ClientError as e:
        return web.json_response({"error": f"Failed to fetch the target URL: {str(e)}"}, status=500)
    except Exception as e:
        return web.json_response({"error": f"Unexpected error: {str(e)}"}, status=500)

app = web.Application()
app.router.add_get('/film', cors_proxy_handler)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
