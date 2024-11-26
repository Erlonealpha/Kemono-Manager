import telethon
import os


class TelegramAPI:
    def __init__(self, api_id, api_hash, session_name = 'session_name'):
        self.client = telethon.TelegramClient(session_name, api_id, api_hash)