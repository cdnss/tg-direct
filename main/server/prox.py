# File: prox.py
import aiohttp
from aiohttp import web, ClientTimeout
import logging
from urllib.parse import urlparse, urljoin, unquote
import subprocess
import json
import base64
import os
import asyncio

routes = web.RouteTableDef()

BASE_URL_FILM = "https://lk21.film"
PROXY_PREFIX_FILM = "/film/"

DENO_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'proxy.ts')

async def check_deno_and_script():
    try:
        proc_check = await asyncio.create_subprocess_exec(
            'deno', '--version',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        await proc_check.wait()
        if proc_check.returncode != 0:
             logging.error("Deno command not found or failed. Please install Deno.")
        else:
            stdout, _ = await proc_check.communicate()
            logging.info(f"Using Deno version: {stdout.decode().strip()}")

        if not os.path.exists(DENO_SCRIPT_PATH):
            logging.error(f"Deno script not found at {DENO_SCRIPT_PATH}")
        else:
             logging.info(f"Deno script found at: {DENO_SCRIPT_PATH}")

    except FileNotFoundError:
        logging.error("Deno command not found. Please install Deno.")
    except Exception as e:
        logging.error(f"Unexpected error during Deno setup check: {e}")

@routes.route('*', PROXY_PREFIX_FILM + '{path:.*}')
async def film_proxy_handler(request):
    path_from_request = request.match_info['path']

    if path_from_request:
        target_url = urljoin(BASE_URL_FILM, path_from_request)
    else:
        target_url = BASE_URL_FILM

    target_url = unquote(target_url)

    logging.info(f"Meneruskan permintaan ke Deno for: {target_url}")

    method = request.method
    request_headers = dict(request.headers)
    request_body = await request.read()
    request_body_str = request_body.decode('utf-8', errors='ignore')


    input_data = {
        'targetUrl': target_url,
        'baseUrl': BASE_URL_FILM,
        'method': method,
        'headers': request_headers,
        'body': request_body_str if request_body else None,
        'proxyPrefix': PROXY_PREFIX_FILM,
    }

    try:
        deno_command = [
            'deno', 'run',
            '--allow-net',
            '--allow-read=' + os.path.dirname(DENO_SCRIPT_PATH),
            '--quiet',
            DENO_SCRIPT_PATH
        ]

        process = await asyncio.create_subprocess_exec(
            *deno_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(input=json.dumps(input_data).encode('utf-8')),
                timeout=60
            )
        except asyncio.TimeoutError:
            logging.error(f"Deno script timed out after 60 seconds for {target_url}")
            process.kill()
            await process.wait()
            return web.Response(status=504, text="Proxy Gateway Timeout: Deno script took too long.")
        except Exception as e:
             logging.error(f"Error during Deno process communication for {target_url}: {e}")
             if process.returncode is None:
                 process.kill()
                 await process.wait()
             return web.Response(status=500, text=f"Proxy Error: Deno communication failed: {e}")


        if process.returncode != 0:
            stderr_output = stderr_data.decode('utf-8', errors='ignore')
            logging.error(f"Deno script failed with exit code {process.returncode} for {target_url}")
            logging.error(f"Deno Stderr:\n{stderr_output}")
            try:
                 partial_stdout = stdout_data.decode('utf-8', errors='ignore')
                 logging.error(f"Deno partial Stdout:\n{partial_stdout}")
            except Exception:
                 pass
            return web.Response(status=500, text=f"Proxy Error: Deno script failed (Code {process.returncode}).")

        try:
            deno_output_str = stdout_data.decode('utf-8').strip()
            if not deno_output_str:
                 logging.error(f"Deno script produced empty stdout for {target_url}. Stderr:\n{stderr_data.decode('utf-8', errors='ignore')}")
                 return web.Response(status=500, text="Proxy Error: Deno script produced no output.")

            deno_output = json.loads(deno_output_str)

        except json.JSONDecodeError:
             stderr_output = stderr_data.decode('utf-8', errors='ignore')
             logging.error(f"Failed to decode JSON from Deno stdout for {target_url}:\n{stdout_data.decode('utf-8', errors='ignore')}")
             logging.error(f"Deno Stderr:\n{stderr_output}")
             return web.Response(status=500, text="Proxy Error: Invalid JSON response from Deno script.")
        except Exception as e:
             stderr_output = stderr_data.decode('utf-8', errors='ignore')
             logging.error(f"Unexpected error processing Deno stdout for {target_url}: {e}")
             logging.error(f"Deno Stderr:\n{stderr_output}")
             return web.Response(status=500, text="Proxy Error: Failed to process Deno output.")

        proxy_response = web.Response(status=deno_output.get('status', 500))

        output_headers = deno_output.get('headers', {})
        for header, value in output_headers.items():
             proxy_response.headers[header] = value

        output_body = deno_output.get('body', '')
        if output_headers.get('X-Proxy-Body-Encoding') == 'base64':
             try:
                 proxy_response.body = base64.b64decode(output_body)
                 del proxy_response.headers['X-Proxy-Body-Encoding']
             except Exception as e:
                 logging.error(f"Failed to decode base64 body from Deno for {target_url}: {e}")
                 proxy_response.body = output_body.encode('utf-8', errors='ignore')
                 if 'Content-Type' not in proxy_response.headers or proxy_response.headers['Content-Type'].lower().startswith('application/octet-stream'):
                     proxy_response.headers['Content-Type'] = 'text/plain'

        else:
             proxy_response.body = output_body.encode('utf-8', errors='ignore')


        return proxy_response

    except FileNotFoundError:
        logging.error("Deno command not found. Is Deno installed and in PATH?")
        return web.Response(status=500, text="Proxy Error: Deno not found.")
    except Exception as e:
        logging.error(f"Error executing Deno subprocess for {target_url}: {e}")
        return web.Response(status=500, text=f"Proxy Error: Subprocess setup failed: {e}")
