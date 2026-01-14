"""
sync.py

Handles syncing of attendance logs to Supabase.
If offline, queues logs for later sync.
"""
import os
import requests
from local_store import LocalStore

SUPABASE_URL = "https://YOUR_SUPABASE_PROJECT.supabase.co/rest/v1/attendance_logs"
SUPABASE_API_KEY = "YOUR_SUPABASE_API_KEY"  # Store securely in production

class Syncer:
    def __init__(self):
        self.store = LocalStore()

    def is_online(self):
        try:
            requests.get("https://www.google.com", timeout=2)
            return True
        except requests.RequestException:
            return False

    def sync(self):
        if not self.is_online():
            return False
        queue = self.store.get_queue()
        headers = {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json"
        }
        success = True
        for entry in queue:
            resp = requests.post(SUPABASE_URL, json=entry, headers=headers)
            if not resp.ok:
                success = False
        if success:
            self.store.clear_queue()
        return success
