# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/__init__.py>
# Thanks to Eyaadh
# This file is a part of TG-Direct-Link-Generator

from aiohttp import web
# Import CookieJar di sini karena kita akan membuatnya di sini
from aiohttp import CookieJar
from .stream_routes import routes
from .prox import routes as prox_routes   # Tambahkan baris ini

def web_server():
    web_app = web.Application(client_max_size=30000000)

    # --- Perbaikan Error: Buat CookieJar DI SINI dan simpan di app ---
    # Event loop akan segera berjalan setelah web_app siap dijalankan
    # Ini adalah tempat yang aman untuk membuat CookieJar yang persisten
    web_app['cookie_jar'] = CookieJar(unsafe=True)
    # --- End Perbaikan Error ---

    # Tambahkan routes proxy terlebih dahulu (yang berisi /film/...)
    web_app.add_routes(prox_routes)
    # Kemudian tambahkan routes streaming/download (yang berisi /{path:\S+})
    #web_app.add_routes(routes)

    return web_app

# Pastikan Anda sudah menghapus baris 'app_cookie_jar = CookieJar(unsafe=True)'
# dari file prox.py seperti yang dibahas sebelumnya.
