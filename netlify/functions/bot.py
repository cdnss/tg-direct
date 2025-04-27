import os
from dotenv import load_dotenv
from main import StreamBot, utils
from main.vars import Var

load_dotenv()

def handler(event, context):
    # Inisialisasi bot
    try:
        StreamBot.start()
        return {
            "statusCode": 200,
            "body": "Bot berhasil dijalankan"
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }
