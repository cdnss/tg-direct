import re
import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from main.bot import multi_clients, work_loads
from main.server.exceptions import FIleNotFound, InvalidHash
from main import Var, utils, StartTime, __version__, StreamBot
from main.utils.render_template import render_page
from .prox import process_with_deno, BASE_URL_FILM, PROXY_PREFIX_FILM


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": utils.get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.username,
            "connected_bots": len(multi_clients),
            "loads": dict(
                ("bot" + str(c + 1), l)
                for c, (_, l) in enumerate(
                    sorted(work_loads.items(), key=lambda x: x[1], reverse=True)
                )
            ),
            "version": __version__,
        }
    )

@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def stream_handler_watch(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            match_id_only = re.search(r"(\d+)(?:\/\S+)?", path)
            if not match_id_only:
                raise web.HTTPBadRequest(text="Invalid path format")
            message_id = int(match_id_only.group(1))
            secure_hash = request.rel_url.query.get("hash")

        html_content = await render_page(message_id, secure_hash)
        return web.Response(text=html_content, content_type='text/html')

    except InvalidHash as e:
        logging.warning(f"Invalid hash: {e.message}")
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        logging.warning(f"File not found: {e.message}")
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception(f"Specific error in stream_handler_watch: {e}")
        raise web.HTTPInternalServerError(text="An internal streaming error occurred.")
    except Exception as e:
        logging.critical(f"Unexpected error in stream_handler_watch: {e}", exc_info=True)
        raise web.HTTPInternalServerError(text=f"An unexpected server error occurred: {str(e)}")

@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler_download(request: web.Request):
    requested_path = request.match_info["path"]
    referer = request.headers.get("Referer")

    proxy_base_url_with_prefix = f"{request.url.scheme}://{request.url.host}{PROXY_PREFIX_FILM}"

    if referer and referer.startswith(proxy_base_url_with_prefix):
        logging.info(f"Proxying Referer-based request via stream_handler_download for: /{requested_path} (Referer: {referer})")

        target_url = urljoin(BASE_URL_FILM, requested_path)

        try:
            return await process_with_deno(request, target_url)
        except Exception as e:
            logging.error(f"Error during Deno processing from stream_handler_download for /{requested_path}: {e}")
            raise web.HTTPInternalServerError(text="An internal proxy processing error occurred.")

    else:
        logging.info(f"Handling non-proxy request as stream download for: /{requested_path}")

        try:
            match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", requested_path)
            if match:
                secure_hash = match.group(1)
                message_id = int(match.group(2))
            else:
                match_id_only = re.search(r"(\d+)(?:\/\S+)?", requested_path)
                if not match_id_only:
                    logging.warning(f"Stream path does not match format: /{requested_path}")
                    raise web.HTTPNotFound(text=f"File or resource not found: /{requested_path}")

                message_id = int(match_id_only.group(1))
                secure_hash = request.rel_url.query.get("hash")

            return await media_streamer(request, message_id, secure_hash)

        except InvalidHash as e:
            logging.warning(f"Invalid hash: {e.message}")
            raise web.HTTPForbidden(text=e.message)
        except FIleNotFound as e:
            logging.warning(f"File not found: {e.message}")
            raise web.HTTPNotFound(text=e.message)
        except (AttributeError, BadStatusLine, ConnectionResetError) as e:
            logging.exception(f"Specific error in stream_handler_download during stream handling: {e}")
            raise web.HTTPInternalServerError(text="An internal streaming error occurred.")
        except Exception as e:
            logging.critical(f"Unexpected error during stream handling in stream_handler_download: {e}", exc_info=True)
            raise web.HTTPInternalServerError(text=f"An unexpected server error occurred: {str(e)}")


class_cache = {}

async def media_streamer(request: web.Request, message_id: int, secure_hash: str):
    range_header = request.headers.get("Range", None)

    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    if Var.MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.remote}")

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect

    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(message_id)
    logging.debug("after calling get_file_properties")

    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash '{secure_hash}' for message with ID {message_id}. Expected '{file_id.unique_id[:6]}'")
        raise InvalidHash("Invalid file hash provided.")

    file_size = file_id.file_size

    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
            if from_bytes < 0 or until_bytes >= file_size or from_bytes > until_bytes:
                logging.warning(f"Invalid Range header: {range_header}. File size: {file_size}")
                raise web.HTTPBadRequest(text="Invalid Range header")

        except ValueError:
            logging.warning(f"Malformed Range header: {range_header}")
            raise web.HTTPBadRequest(text="Malformed Range header")
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    req_length = until_bytes - from_bytes + 1

    new_chunk_size = await utils.chunk_size(req_length)
    offset = await utils.offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes + 1) % new_chunk_size
    if last_part_cut == 0:
        last_part_cut = new_chunk_size

    part_count = math.ceil(req_length / new_chunk_size)

    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, new_chunk_size
    )

    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment"

    if not mime_type:
        if file_name:
            guessed_type, _ = mimetypes.guess_type(file_name)
            mime_type = guessed_type if guessed_type else "application/octet-stream"
        else:
            mime_type = "application/octet-stream"
            file_name = f"{secrets.token_hex(4)}.unknown"
    else:
        if not file_name:
            try:
                extension = mime_type.split('/')[1]
                file_name = f"{secrets.token_hex(4)}.{extension}"
            except (IndexError, AttributeError):
                file_name = f"{secrets.token_hex(4)}.unknown"


    if "video/" in mime_type or "audio/" in mime_type:
        disposition = "inline"

    return_resp = web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": mime_type,
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(req_length),
        },
    )

    logging.debug(f"Returning response with status {return_resp.status}, range: {from_bytes}-{until_bytes}/{file_size}, filename: {file_name}")

    return return_resp
