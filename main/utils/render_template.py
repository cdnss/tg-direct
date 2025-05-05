# This file is a part of TG-Direct-Link-Generator

from main.vars import Var
from main.bot import StreamBot
from main.utils.human_readable import humanbytes
from main.utils.file_properties import get_file_ids
from main.server.exceptions import InvalidHash
import urllib.parse
import aiofiles
import logging
import aiohttp
from aiohttp import web  # Tambahkan ini untuk membaca query dari request


async def render_page(message_id, secure_hash, request: web.Request):
    query_url = request.rel_url.query.get("urhgfc")  # Ambil query `url` jika ada
    if query_url:
        src = query_url  # Gunakan URL dari query sebagai sumber video
    else:
        file_data = await get_file_ids(StreamBot, int(Var.BIN_CHANNEL), int(message_id))
        if file_data.unique_id[:6] != secure_hash:
            logging.debug(f'link hash: {secure_hash} - {file_data.unique_id[:6]}')
            logging.debug(f"Invalid hash for message with - ID {message_id}")
            raise InvalidHash
        src = urllib.parse.urljoin(Var.URL, f'{secure_hash}{str(message_id)}')

    if str(file_data.mime_type.split('/')[0].strip()) == 'video':
        heading = f"Watch {file_data.file_name}"  # Assign heading for video
        async with aiofiles.open('main/template/req.html') as r:
            tag = file_data.mime_type.split('/')[0].strip()
            html = (await r.read()).replace('tag', tag) % (heading, file_data.file_name, src)
    else:
        heading = f"Download {file_data.file_name}"  # Assign heading for non-video
        async with aiofiles.open('main/template/dl.html') as r:
            async with aiohttp.ClientSession() as s:
                async with s.get(src) as u:
                    file_size = humanbytes(int(u.headers.get('Content-Length')))
                    html = (await r.read()) % (heading, file_data.file_name, src, file_size)
    return html
