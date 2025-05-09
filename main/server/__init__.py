# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/__init__.py>
# Thanks to Eyaadh
# This file is a part of TG-Direct-Link-Generator

from aiohttp import web
from .stream_routes import routes
from .prox import routes as prox_routes   # Tambahkan baris ini
def web_server():
    web_app = web.Application(client_max_size=30000000)
    # Tambahkan routes proxy terlebih dahulu (yang berisi /film/...)
    web_app.add_routes(prox_routes)
    # Kemudian tambahkan routes streaming/download (yang berisi /{path:\S+})
    web_app.add_routes(routes)
    return web_app
