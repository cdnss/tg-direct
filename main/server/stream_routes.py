# File: stream_routes.py
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
from urllib.parse import urljoin


routes = web.RouteTableDef()

class StreamParsingFailed(Exception):
    """Exception kustom saat path tidak cocok dengan format stream atau validasi awal gagal."""
    pass


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

    try:
        logging.info(f"Attempting to handle /{requested_path} as stream download...")
        message_id = None
        secure_hash = None

        # --- Logika Parsing Stream ---
        match_hash_id = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", requested_path)
        if match_hash_id:
            secure_hash = match_hash_id.group(1)
            message_id = int(match_hash_id.group(2))
            logging.debug(f"Parsed as hash+id: ID={message_id}, Hash={secure_hash}")
        else:
            match_id_only = re.search(r"(\d+)(?:\/\S+)?", requested_path)
            if match_id_only:
                 message_id = int(match_id_only.group(1))
                 secure_hash = request.rel_url.query.get("hash")

                 if not secure_hash:
                      logging.warning(f"Hash missing for stream ID path: /{requested_path}. Stream parsing failed.")
                      raise StreamParsingFailed("Hash missing for ID-only stream path")

                 logging.debug(f"Parsed as id_only: ID={message_id}, Hash={secure_hash}")
            else:
                 logging.warning(f"Path does not match any stream format: /{requested_path}. Stream parsing failed.")
                 # --- PERBAIKAN DI SINI: Naikkan StreamParsingFailed BUKAN HTTPNotFound ---
                 # Ketika parsing stream gagal, picu exception kustom untuk beralih ke proxy fallback
                 raise StreamParsingFailed("Path does not match stream format")
                 # --- End Perbaikan ---
        # --- Akhir Logika Parsing Stream ---

        # Jika parsing berhasil (tidak ada StreamParsingFailed yang dinaikkan), panggil media_streamer.
        # media_streamer bisa melempar InvalidHash (hash mismatch) atau FIleNotFound saat validasi lebih lanjut.
        return await media_streamer(request, message_id, secure_hash)

    # --- Penanganan Exception: Jika Parsing Stream Gagal ATAU Error Saat Streaming ---
    # Menangkap StreamParsingFailed ATAU exception yang mungkin dilempar oleh media_streamer
    # saat mencoba mendapatkan properti file (InvalidHash, FIleNotFound, error koneksi, ValueError dari int(), dll.)
    except (StreamParsingFailed, InvalidHash, FIleNotFound, ValueError, AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.info(f"Stream handling failed for /{requested_path} (Error: {type(e).__name__}: {e}). Attempting proxying.")
        # Konstruksi target URL untuk domain asli
        target_url = urljoin(BASE_URL_FILM, requested_path)
        # Panggil fungsi pemrosesan proxy dari prox.py
        # Tangkap exception yang mungkin muncul dari process_with_deno sebagai internal error server
        try:
             return await process_with_deno(request, target_url)
        except Exception as proxy_e:
             logging.error(f"Error during proxy processing after stream handling failed for /{requested_path}: {proxy_e}", exc_info=True)
             # Kembalikan 500 jika bahkan fallback proxy pun gagal
             raise web.HTTPInternalServerError(text="An error occurred during proxy processing fallback.")


    # Menangkap exception LAINNYA yang benar-benar tidak terduga
    # Ini adalah kegagalan kritis yang tidak terkait dengan parsing atau error stream/proxy yang diharapkan
    except Exception as e:
        logging.critical(f"Truly unexpected error during initial stream handling attempt for /{requested_path}: {e}", exc_info=True)
        # Kembalikan 500 untuk kegagalan kritis
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
