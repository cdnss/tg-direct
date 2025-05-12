# This file is a part of TG-Direct-Link-Generator

# Tambahkan baris import logging jika belum ada di file ini
import logging
# Pastikan logging dasar sudah dikonfigurasi di aplikasi Anda (misalnya di file utama)
# Contoh: logging.basicConfig(level=logging.INFO)


from main.bot import StreamBot
from main.vars import Var
from pyrogram import filters, Client # Import Client jika digunakan (diparameter handler start dan group)
from pyrogram.types import Message # Import Message untuk type hinting

@StreamBot.on_message(~filters.user(Var.BANNED_USERS) & filters.command('start'))
async def start_command_handler(b: Client, m: Message): # Mengganti nama handler start untuk kejelasan
    # --- Tambahkan logging di sini ---
    logging.info(f"'{start_command_handler.__name__}' triggered by user {m.from_user.id}")
    # ------------------------
    # lang = getattr(Language, m.from_user.language_code)
    lang = getattr(Language, "en") # Menggunakan English sebagai default
    try:
        await m.reply_text(
            text=lang.START_TEXT.format(m.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=BUTTON.START_BUTTONS
            )
    except Exception as e:
        # Tambahkan logging untuk error di dalam handler
        logging.error(f"Error in '{start_command_handler.__name__}' for user {m.from_user.id}: {e}", exc_info=True)


@StreamBot.on_message(~filters.user(Var.BANNED_USERS) & filters.command(["about"]))
async def about_handler(bot: Client, update: Message): # Mengganti nama handler about dan menambahkan type hint
    # --- Tambahkan logging di sini ---
    logging.info(f"'{about_handler.__name__}' triggered by user {update.from_user.id}")
    # ------------------------
    # lang = getattr(Language, update.from_user.language_code)
    lang = getattr(Language, "en") # Menggunakan English sebagai default
    try:
        await update.reply_text(
            text=lang.ABOUT_TEXT.format(update.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=BUTTON.ABOUT_BUTTONS
        )
    except Exception as e:
        # Tambahkan logging untuk error di dalam handler
        logging.error(f"Error in '{about_handler.__name__}' for user {update.from_user.id}: {e}", exc_info=True)


@StreamBot.on_message((filters.command('help')) & ~filters.user(Var.BANNED_USERS))
async def help_handler(bot: Client, message: Message): # Menambahkan type hint
    # --- Tambahkan logging di sini ---
    logging.info(f"'{help_handler.__name__}' triggered by user {message.from_user.id}")
    # ------------------------
    # lang = getattr(Language, message.from_user.language_code)
    lang = getattr(Language, "en") # Menggunakan English sebagai default
    try:
        await message.reply_text(
            text=lang.HELP_TEXT.format(Var.UPDATES_CHANNEL),
            disable_web_page_preview=True,
            reply_markup=BUTTON.HELP_BUTTONS
            )
    except Exception as e:
        # Tambahkan logging untuk error di dalam handler
        logging.error(f"Error in '{help_handler.__name__}' for user {message.from_user.id}: {e}", exc_info=True)
