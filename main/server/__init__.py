import aiohttp
from aiohttp import web
from aiohttp import CookieJar
from .stream_routes import routes as stream_routes_routes
from .prox import routes as prox_routes_routes, check_deno_and_script
import asyncio
import logging


async def startup_tasks(app):
    logging.info("Running startup tasks...")
    app['cookie_jar'] = CookieJar(unsafe=True)
    logging.info("CookieJar created and attached to app state.")

    await check_deno_and_script()
    logging.info("Deno and script check completed.")


def web_server():
    logging.info("Creating web application...")
    web_app = web.Application(client_max_size=30000000)

    web_app.on_startup.append(startup_tasks)
    logging.info("Startup task registered.")

    web_app.add_routes(prox_routes_routes)
    logging.info("Proxy routes added.")

    web_app.add_routes(stream_routes_routes)
    logging.info("Stream routes added.")

    logging.info("Web application creation complete.")
    return web_app
