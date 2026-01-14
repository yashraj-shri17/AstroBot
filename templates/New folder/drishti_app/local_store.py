"""
local_store.py

Handles local attendance storage and queuing for offline-first operation.
"""
import os
import json
from datetime import datetime

ATTENDANCE_PATH = os.path.join(os.path.dirname(__file__), 'attendance_queue.json')

class LocalStore:
    def __init__(self):
        if not os.path.exists(ATTENDANCE_PATH):
            with open(ATTENDANCE_PATH, 'w') as f:
                json.dump([], f)

    def log_attendance(self, student_id, student_name, class_name, section):
        entry = {
            'student_id': student_id,
            'student_name': student_name,
            'class': class_name,
            'section': section,
            'timestamp': datetime.utcnow().isoformat()
        }
        data = self._load_all()
        data.append(entry)
        with open(ATTENDANCE_PATH, 'w') as f:
            json.dump(data, f)

    def get_queue(self):
        return self._load_all()

    def clear_queue(self):
        with open(ATTENDANCE_PATH, 'w') as f:
            json.dump([], f)

    def _load_all(self):
        with open(ATTENDANCE_PATH, 'r') as f:
            return json.load(f)
