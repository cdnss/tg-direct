# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>

import re
import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
# Asumsi import berikut sudah benar dan sesuai dengan struktur project Anda
from main.bot import multi_clients, work_loads
from main.server.exceptions import FIleNotFound, InvalidHash
from main import Var, utils, StartTime, __version__, StreamBot
from main.utils.render_template import render_page


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(_):
    """
    Handler untuk rute utama '/'. Mengembalikan status server dalam format JSON.
    """
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
async def stream_handler_watch(request: web.Request): # Mengganti nama fungsi agar lebih jelas
    """
    Handler untuk rute '/watch/...'. Merender halaman HTML untuk menonton.
    """
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            # Asumsi jika tidak sesuai format hash+id, path mengandung ID
            match_id_only = re.search(r"(\d+)(?:\/\S+)?", path)
            if not match_id_only:
                 raise web.HTTPBadRequest(text="Invalid path format") # Menambah error handling jika path tidak sesuai
            message_id = int(match_id_only.group(1))
            secure_hash = request.rel_url.query.get("hash") # Ambil hash dari query param

        # Pastikan render_page mengembalikan string yang valid
        html_content = await render_page(message_id, secure_hash)
        return web.Response(text=html_content, content_type='text/html')

    except InvalidHash as e:
        logging.warning(f"Invalid hash: {e.message}")
        raise web.HTTPForbidden(text=e.message) # Naikkan respons 403 Forbidden
    except FIleNotFound as e:
        logging.warning(f"File not found: {e.message}")
        raise web.HTTPNotFound(text=e.message) # Naikkan respons 404 Not Found
    # --- PERBAIKAN DIMULAI DI SINI ---
    # Tangkap exception spesifik ini dan kembalikan respons error yang valid
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception(f"Specific error in stream_handler_watch: {e}")
        raise web.HTTPInternalServerError(text="An internal streaming error occurred.") # Naikkan respons 500 Internal Server Error
    except Exception as e:
        # Tangkap exception lainnya, log, dan kembalikan respons 500
        logging.critical(f"Unexpected error in stream_handler_watch: {e}", exc_info=True) # exc_info=True untuk melog traceback
        raise web.HTTPInternalServerError(text=f"An unexpected server error occurred: {str(e)}") # Naikkan respons 500 Internal Server Error

@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler_download(request: web.Request): # Mengganti nama fungsi agar lebih jelas
    """
    Handler untuk rute default '/...'. Memulai proses streaming file.
    """
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            # Asumsi jika tidak sesuai format hash+id, path mengandung ID
            match_id_only = re.search(r"(\d+)(?:\/\S+)?", path)
            if not match_id_only:
                 raise web.HTTPBadRequest(text="Invalid path format") # Menambah error handling jika path tidak sesuai
            message_id = int(match_id_only.group(1))
            secure_hash = request.rel_url.query.get("hash") # Ambil hash dari query param

        # media_streamer seharusnya mengembalikan web.Response
        return await media_streamer(request, message_id, secure_hash)

    except InvalidHash as e:
        logging.warning(f"Invalid hash: {e.message}")
        raise web.HTTPForbidden(text=e.message) # Naikkan respons 403 Forbidden
    except FIleNotFound as e:
        logging.warning(f"File not found: {e.message}")
        raise web.HTTPNotFound(text=e.message) # Naikkan respons 404 Not Found
    # --- PERBAIKAN DIMULAI DI SINI ---
    # Tangkap exception spesifik ini dan kembalikan respons error yang valid
    except (AttributeError, BadStatusLine, ConnectionResetError) as e:
        logging.exception(f"Specific error in stream_handler_download: {e}")
        raise web.HTTPInternalServerError(text="An internal streaming error occurred.") # Naikkan respons 500 Internal Server Error
    except Exception as e:
        # Tangkap exception lainnya, log, dan kembalikan respons 500
        logging.critical(f"Unexpected error in stream_handler_download: {e}", exc_info=True) # exc_info=True untuk melog traceback
        raise web.HTTPInternalServerError(text=f"An unexpected server error occurred: {str(e)}") # Naikkan respons 500 Internal Server Error


class_cache = {} # Cache objek ByteStreamer

async def media_streamer(request: web.Request, message_id: int, secure_hash: str):
    """
    Fungsi helper untuk menangani proses streaming byte file.
    Mengembalikan objek web.Response.
    """
    range_header = request.headers.get("Range", None) # Gunakan None sebagai default jika header tidak ada

    # Pilih klien Telegram dengan beban kerja terendah
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]

    if Var.MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.remote}")

    # Gunakan atau buat objek ByteStreamer dari cache
    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        # Asumsi utils.ByteStreamer dapat diinisialisasi dengan faster_client
        tg_connect = utils.ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect

    logging.debug("before calling get_file_properties")
    # Asumsi tg_connect.get_file_properties mengembalikan objek dengan unique_id dan file_size
    file_id = await tg_connect.get_file_properties(message_id)
    logging.debug("after calling get_file_properties")

    # Validasi hash
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash '{secure_hash}' for message with ID {message_id}. Expected '{file_id.unique_id[:6]}'")
        raise InvalidHash("Invalid file hash provided.") # Naikkan exception kustom

    file_size = file_id.file_size

    # Tangani Range header untuk streaming (mendukung resume download)
    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            # Jika until_bytes kosong, berarti sampai akhir file
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
            # Pastikan rentang valid
            if from_bytes < 0 or until_bytes >= file_size or from_bytes > until_bytes:
                 logging.warning(f"Invalid Range header: {range_header}. File size: {file_size}")
                 raise web.HTTPBadRequest(text="Invalid Range header")

        except ValueError:
            logging.warning(f"Malformed Range header: {range_header}")
            raise web.HTTPBadRequest(text="Malformed Range header")
    else:
         # Jika tidak ada Range header, download penuh (dari 0 sampai akhir)
        from_bytes = 0 # request.http_range.start or 0 (http_range mungkin None jika tidak ada Range header)
        until_bytes = file_size - 1 # request.http_range.stop or file_size - 1

    req_length = until_bytes - from_bytes + 1 # Panjang data yang diminta

    # Kalkulasi offset dan ukuran chunk untuk mengunduh dari Telegram
    # Asumsi utils.chunk_size dan utils.offset_fix tersedia dan berfungsi
    new_chunk_size = await utils.chunk_size(req_length)
    offset = await utils.offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes + 1) % new_chunk_size # +1 karena until_bytes berbasis 0
    if last_part_cut == 0:
        last_part_cut = new_chunk_size # Jika pas di batas chunk, ambil seluruh chunk terakhir

    part_count = math.ceil(req_length / new_chunk_size)

    # Asumsi tg_connect.yield_file adalah generator asinkron yang menghasilkan byte
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, new_chunk_size
    )

    # Tentukan mime type dan nama file
    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment" # Defaultnya attachment (download)

    if not mime_type: # Jika mime_type tidak tersedia dari file_id
        if file_name:
            # Coba tebak dari nama file
            guessed_type, _ = mimetypes.guess_type(file_name)
            mime_type = guessed_type if guessed_type else "application/octet-stream"
        else:
            # Jika nama file juga tidak ada
            mime_type = "application/octet-stream"
            # Buat nama file acak dengan ekstensi unknown
            file_name = f"{secrets.token_hex(4)}.unknown"
    else: # Jika mime_type tersedia
         if not file_name:
            # Buat nama file acak dengan ekstensi dari mime type jika nama file tidak ada
            try:
                # Ambil ekstensi dari mime type (misal video/mp4 -> mp4)
                extension = mime_type.split('/')[1]
                file_name = f"{secrets.token_hex(4)}.{extension}"
            except (IndexError, AttributeError):
                 # Fallback jika mime type tidak sesuai format
                 file_name = f"{secrets.token_hex(4)}.unknown"


    # Tentukan disposition (inline untuk video/audio, attachment lainnya)
    if "video/" in mime_type or "audio/" in mime_type:
        disposition = "inline"

    # Buat objek Response
    return_resp = web.Response(
        # Status 206 Partial Content jika ada Range header, 200 OK jika download penuh
        status=206 if range_header else 200,
        body=body, # Body adalah generator byte dari yield_file
        headers={
            "Content-Type": mime_type,
            # Header Range dan Content-Range penting untuk resume download
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes", # Memberi tahu klien bahwa server mendukung Range header
            "Content-Length": str(req_length), # Ukuran bagian yang dikirim, bukan ukuran total file!
        },
    )

    # Catatan: Header Content-Length harus mencerminkan jumlah byte yang *dikirim*
    # Untuk 206, ini adalah req_length. Untuk 200, ini adalah file_size.
    # Kode sudah mengaturnya ke req_length, yang benar untuk 206.
    # Untuk 200, req_length == file_size, jadi ini juga benar.
    # Baris if return_resp.status == 200: return_resp.headers.add("Content-Length", str(file_size))
    # ini sebenarnya redudan jika req_length dihitung dengan benar untuk kasus 200 (dari 0 sampai size-1)

    logging.debug(f"Returning response with status {return_resp.status}, range: {from_bytes}-{until_bytes}/{file_size}, filename: {file_name}")

    return return_resp
