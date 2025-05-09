# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/__init__.py>
# Thanks to Eyaadh
# This file is a part of TG-Direct-Link-Generator

from aiohttp import web
from aiohttp import CookieJar
from .stream_routes import routes
# Import routes dan fungsi check dari prox.py
from .prox import routes as prox_routes, check_deno_and_script
import asyncio

# Fungsi yang akan dijalankan saat aplikasi dimulai
async def startup_tasks(app):
    # --- Perbaikan Error: Buat CookieJar DI SINI ---
    # CookieJar dibuat di sini, saat event loop sudah berjalan
    app['cookie_jar'] = CookieJar(unsafe=True)
    # --- End Perbaikan Error ---

    # Jalankan pemeriksaan Deno dan script setelah CookieJar dibuat (atau bisa di awal)
    await check_deno_and_script()


def web_server():
    web_app = web.Application(client_max_size=30000000)

    # Tambahkan tugas startup
    web_app.on_startup.append(startup_tasks)

    # HAPUS BARIS INI: web_app['cookie_jar'] = CookieJar(unsafe=True)

    # Tambahkan routes
    web_app.add_routes(prox_routes)
    # web_app.add_routes(routes) # Baris ini tetap dikomentari sesuai input Anda

    return web_app

# Pastikan Anda sudah menghapus baris 'app_cookie_jar = CookieJar(unsafe=True)'
# dari file prox.py.
