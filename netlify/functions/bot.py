from http.server import BaseHTTPRequestHandler
import os
from dotenv import load_dotenv
import json

load_dotenv()

def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Telegram Bot is running"
        })
    }
