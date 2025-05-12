# File: main/main.py (atau nama file script utama Anda)

import sys
import asyncio
import logging
from .vars import Var
from aiohttp import web
from pyrogram import idle, Client # Import Client jika digunakan
from main import utils
from main import StreamBot
from main.server import web_server
from main.bot.clients import initialize_clients

# Konfigurasi Logging sudah benar disetel ke DEBUG untuk pyrogram
logging.basicConfig(
    level=logging.DEBUG,
    datefmt="%d/%m/%Y %H:%M:%S",
    format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(stream=sys.stdout),
              logging.FileHandler("streambot.log", mode="a", encoding="utf-8")],)

logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.DEBUG) # Pertahankan DEBUG
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)

server = web.AppRunner(web_server())

# Menggunakan asyncio.run jika Python 3.7+
if sys.version_info[1] > 6: # Cek untuk Python 3.7 atau lebih tinggi
    loop = asyncio.get_event_loop() # Ambil loop default
else: # Untuk versi Python yang lebih lama
    loop = asyncio.get_event_loop()


async def start_services():
    print()
    print("-------------------- Initializing Telegram Bot --------------------")
    # StreamBot.start() akan terhubung dan memulai tugas polling di background
    await StreamBot.start()
    try: # Tambahkan try block untuk get_me
      bot_info = await StreamBot.get_me()
      StreamBot.username = bot_info.username
      logging.info(f"Bot started as @{StreamBot.username}") # Tambahkan logging konfirmasi bot info
    except Exception as e:
      logging.error(f"Failed to get bot info after start: {e}", exc_info=True)
      # Pertimbangkan apa yang harus dilakukan jika gagal mendapatkan info bot (lanjut atau hentikan?)
      # Untuk saat ini, log dan lanjut

    print("------------------------------ DONE ------------------------------")
    print()
    print(
        "---------------------- Initializing Clients ----------------------"
    )
    # Pastikan initialize_clients selesai tanpa memblokir loop utama
    await initialize_clients()
    print("------------------------------ DONE ------------------------------")
    if Var.ON_HEROKU:
        print("------------------ Starting Keep Alive Service ------------------")
        print()
        # Pastikan utils.ping_server() adalah awaitable yang berjalan di background
        asyncio.create_task(utils.ping_server())
    print("--------------------- Initalizing Web Server ---------------------")
    # Pastikan setup server selesai tanpa memblokir loop utama
    await server.setup()
    bind_address = "0.0.0.0" if Var.ON_HEROKU else Var.BIND_ADDRESS
    # Gunakan Var.PORT dari konfigurasi/variabel lingkungan
    await web.TCPSite(server, bind_address, Var.PORT).start()
    logging.info(f"Web server started at {bind_address}:{Var.PORT}") # Tambahkan logging konfirmasi server
    print("------------------------------ DONE ------------------------------")
    print()
    print("------------------------- Service Started -------------------------")
    # Gunakan bot_info yang diperoleh sebelumnya
    print("                        bot =>> {}".format(bot_info.first_name if 'bot_info' in locals() else 'N/A'))
    if 'bot_info' in locals() and bot_info.dc_id:
        print("                        DC ID =>> {}".format(str(bot_info.dc_id)))
    print("                        server ip =>> {}".format(bind_address)) # Menghapus duplikasi Var.PORT
    if Var.ON_HEROKU:
        print("                        app running on =>> {}".format(Var.FQDN))
    print("------------------------------------------------------------------")
    print()
    print("""
 _____________________________________________
|                                             |
|          Deployed Successfully              |
|              Join @TechZBots                |
|_____________________________________________|
    """)

    # --- Tambahkan logging di sini sebelum idle ---
    # Pesan ini akan muncul jika script berhasil mencapai titik ini
    logging.info("--- BEFORE calling await idle() --- Bot should now be connected and listening for updates.")
    # ------------------------------------

    await idle() # Fungsi ini akan memblokir dan menjaga loop asyncio tetap berjalan
                # sambil mendengarkan update dari Pyrogram.

    # --- Log ini hanya akan muncul ketika idle() berhenti (misalnya, setelah Ctrl+C) ---
    logging.info("--- AFTER await idle() --- Bot was likely interrupted and is stopping.")
    # -------------------------------------------------------------------------------


async def cleanup():
    logging.info("--- Starting cleanup ---") # Tambahkan logging di awal cleanup
    try:
        await server.cleanup() # Membersihkan resource server web
        logging.info("Web server cleaned up.") # Tambahkan logging
    except Exception as e:
        logging.error(f"Error during web server cleanup: {e}", exc_info=True)

    try:
        # StreamBot.stop() akan memutuskan koneksi Pyrogram dan menghentikan tugas internal
        await StreamBot.stop()
        logging.info("Telegram bot stopped.") # Tambahkan logging
    except Exception as e:
        logging.error(f"Error during bot stop: {e}", exc_info=True)

    logging.info("--- Cleanup complete ---") # Tambahkan logging di akhir cleanup


if __name__ == "__main__":
    # Menggunakan asyncio.run() (tersedia di Python 3.7+) adalah cara yang lebih bersih
    # untuk menjalankan async main dan menangani cleanup saat keluar.
    # Jika Anda menggunakan Python 3.7+, pertimbangkan mengganti blok try/except/finally ini
    # dengan struktur asyncio.run(main_run()) seperti di komentar di kode Anda atau contoh di bawah.

    async def main_run():
        try:
            await start_services()
        except KeyboardInterrupt:
             # idle() biasanya menangkap Ctrl+C dan kembali, jadi KeyboardInterrupt mungkin tidak selalu mencapai sini
            print("Keyboard interrupt received, idle() returned.")
            pass # idle() sudah menangani interupsi
        except Exception as err:
            # Tangkap exception tak terduga di start_services sebelum cleanup
            logging.critical(f"Unhandled exception in start_services: {err}", exc_info=True)
        finally:
            # Cleanup akan dijalankan setelah start_services selesai atau ada exception tak tertangani
            print("Executing cleanup...")
            await cleanup()

    # Menggunakan asyncio.run() (Python 3.7+)
    # Pastikan Anda tidak mencampur loop.run_until_complete dan asyncio.run
    # Jika Anda sudah menggunakan loop.run_until_complete, tetap gunakan itu.

    # Contoh menjalankan dengan loop.run_until_complete (sesuai kode asli Anda)
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
         print("\nKeyboard interrupt detected. Stopping services...")
        # idle() akan kembali, lalu cleanup akan dijalankan di finally
         pass
    except Exception as err:
        logging.critical(f"Critical error before cleanup: {err}", exc_info=True)
    finally:
        # Cleanup akan dijalankan setelah start_services (karena idle() kembali) atau exception
        print("Running final cleanup...")
        try:
            loop.run_until_complete(cleanup())
        except Exception as cleanup_err:
            logging.error(f"Error running cleanup: {cleanup_err}", exc_info=True)

        # loop.stop() dan loop.close() biasanya diperlukan jika Anda membuat loop baru
        # dan mengelola siklus hidupnya secara manual. Dalam kasus ini, karena loop didapat
        # dari get_event_loop atau new_event_loop, clean up loop juga penting.
        # Namun, hati-hati dengan state loop setelah run_until_complete.
        # Jika loop.run_until_complete(start_services()) selesai karena idle() kembali,
        # loop mungkin masih dalam state berjalan atau tertutup.
        # Pengelolaan loop secara manual bisa rumit.

        # Untuk sementara, mari kita fokus pada log dari start_services dan cleanup.
        # loop.stop() dan loop.close() bisa jadi diperlukan tergantung cara persis loop diinisiasi dan dijalankan.
        # Namun, error "tidak mendispatch" lebih mungkin terjadi sebelum cleanup.

    print("------------------------ Application Exited ------------------------") # Tambahkan logging di akhir eksekusi script
