# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/__init__.py>
# Thanks to Eyaadh
# This file is a part of TG-Direct-Link-Generator

from aiohttp import web
from aiohttp import CookieJar
from .stream_routes import routes
# Import routes dan fungsi check dari prox.py
from .prox import routes as prox_routes, check_deno_and_script
import asyncio # Perlu import asyncio untuk startup task

# Fungsi yang akan dijalankan saat aplikasi dimulai
async def startup_tasks(app):
    # Jalankan pemeriksaan Deno dan script saat aplikasi startup
    await check_deno_and_script()

def web_server():
    web_app = web.Application(client_max_size=30000000)

    # Tambahkan tugas startup
    web_app.on_startup.append(startup_tasks)

    # Buat CookieJar persisten dan simpan di objek app
    web_app['cookie_jar'] = CookieJar(unsafe=True)

    # Tambahkan routes
    web_app.add_routes(prox_routes)
    # web_app.add_routes(routes) # Baris ini tetap dikomentari sesuai input Anda

    return web_app
