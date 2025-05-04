# Taken from megadlbot_oss <https://github.com/eyaadh/megadlbot_oss/blob/master/mega/webserver/routes.py>
# Thanks to Eyaadh <https://github.com/eyaadh>
import aiohttp
import re
import time
import math
import logging
import secrets
import mimetypes
import os
import yt_dlp
import asyncio
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from main.bot import multi_clients, work_loads
from main.server.exceptions import FIleNotFound, InvalidHash
from main import Var, utils, StartTime, __version__, StreamBot
from main.utils.render_template import render_page
from pyrogram.types import InputMediaDocument
from main.utils.file_properties import get_hash


routes = web.RouteTableDef()

async def send_link_to_sheets(link):
    url = "https://script.google.com/macros/s/AKfycby0oWD0zj9OW70pm3eS9Pe4GPHlEMsvbM3VNZuS5xXV90XQW_kzNZH6u1z_3AFxAqmh1Q/exec"
    params = {"tok": "ok", "crit": link}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    logging.info("Link successfully sent to Google Sheets.")
                else:
                    logging.error(f"Failed to send link to Google Sheets. Status code: {response.status}")
        except Exception as e:
            logging.error(f"Error sending link to Google Sheets: {e}")

async def process_url(url):
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)
    try:
        # Download video using yt-dlp
        ydl_opts = {
            'outtmpl': f'{download_dir}/%(title)s.%(ext)s',
            'format': 'best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # Use the already connected StreamBot instance to upload
        log_msg = await StreamBot.send_document(
            chat_id=Var.BIN_CHANNEL,
            document=file_path,
            caption=f"**Title:** {info.get('title', 'Unknown')}\n**Size:** {os.path.getsize(file_path) // 1024} KB"
        )

        # Generate secure hash from the file's unique ID
        secure_hash = get_hash(log_msg)

        # Generate download and streaming links
        stream_link = f"{Var.URL}{secure_hash}{log_msg.id}/{os.path.basename(file_path)}"
        page_link = f"{Var.URL}watch/{secure_hash}{log_msg.id}"

        # Send the generated links to the bot's BIN_CHANNEL
        await StreamBot.send_message(
            chat_id=Var.BIN_CHANNEL,
            text=f"**Generated Links:**\n\n**Stream Link:** {stream_link}\n**Page Link:** {page_link}",
            disable_web_page_preview=True
        )

        # Call the send_link_to_sheets function to send the link to Google Sheets
        await send_link_to_sheets(stream_link)

        # Clean up the downloaded file
        os.remove(file_path)
    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")

@routes.get("/", allow_head=True)
async def root_route_handler(request: web.Request):
    url = request.rel_url.query.get("url")
    if url:
        # Start the download/upload process in the background
        asyncio.create_task(process_url(url))

        # Return a placeholder response immediately
        return web.json_response({
            "status": "processing",
            "message": "The file is being processed. Links will be available soon."
        })

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
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            raise InvalidHash("Invalid URL format")
        return web.Response(text=await render_page(message_id, secure_hash), content_type='text/html')
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        return web.HTTPInternalServerError(text="Internal Server Error")
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))

@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            message_id = int(match.group(2))
        else:
            raise InvalidHash("Invalid URL format")
        return await media_streamer(request, message_id, secure_hash)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        return web.HTTPInternalServerError(text="Internal Server Error")
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}

async def media_streamer(request: web.Request, message_id: int, secure_hash: str):
    range_header = request.headers.get("Range", 0)
    
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
        logging.debug(f"Invalid hash for message with ID {message_id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = request.http_range.stop or file_size - 1

    req_length = until_bytes - from_bytes
    new_chunk_size = await utils.chunk_size(req_length)
    offset = await utils.offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % new_chunk_size) + 1
    part_count = math.ceil(req_length / new_chunk_size)
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, new_chunk_size
    )

    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment"
    if mime_type:
        if not file_name:
            try:
                file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
            except (IndexError, AttributeError):
                file_name = f"{secrets.token_hex(2)}.unknown"
    else:
        if file_name:
            mime_type = mimetypes.guess_type(file_id.file_name)
        else:
            mime_type = "application/octet-stream"
            file_name = f"{secrets.token_hex(2)}.unknown"
    if "video/" in mime_type or "audio/" in mime_type:
        disposition = "inline"
    return_resp = web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Range": f"bytes={from_bytes}-{until_bytes}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )

    if return_resp.status == 200:
        return_resp.headers.add("Content-Length", str(file_size))

    return return_resp