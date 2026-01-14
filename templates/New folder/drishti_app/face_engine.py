"""
face_engine.py

Handles all face encoding and recognition logic for Drishti App.
Runs 100% offline. Uses face_recognition (dlib-based) for encoding and matching.
"""

import os
import pickle
import face_recognition

ENCODINGS_PATH = os.path.join(os.path.dirname(__file__), 'encodings.pkl')
DATABASE_DIR = os.path.join(os.path.dirname(__file__), 'database')

class FaceEngine:
    def __init__(self):
        self.encodings = []
        self.metadata = []
        if os.path.exists(ENCODINGS_PATH):
            self._load_encodings()
        else:
            self._encode_database()

    def _encode_database(self):
        """
        Loads all images from database/, encodes faces, saves encodings.pkl, clears images from memory.
        """
        for fname in os.listdir(DATABASE_DIR):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                path = os.path.join(DATABASE_DIR, fname)
                image = face_recognition.load_image_file(path)
                encs = face_recognition.face_encodings(image)
                if encs:
                    self.encodings.append(encs[0])
                    self.metadata.append({
                        'student_id': os.path.splitext(fname)[0],
                        'filename': fname
                    })
        with open(ENCODINGS_PATH, 'wb') as f:
            pickle.dump({'encodings': self.encodings, 'metadata': self.metadata}, f)

    def _load_encodings(self):
        with open(ENCODINGS_PATH, 'rb') as f:
            data = pickle.load(f)
            self.encodings = data['encodings']
            self.metadata = data['metadata']

    def recognize(self, image, threshold=0.45):
        """
        Given a BGR/RGB image, returns (student_id, confidence) if match > threshold, else (None, None)
        """
        encs = face_recognition.face_encodings(image)
        if not encs:
            return None, None
        face_enc = encs[0]
        if not self.encodings:
            return None, None
        dists = face_recognition.face_distance(self.encodings, face_enc)
        min_idx = dists.argmin()
        min_dist = dists[min_idx]
        confidence = 1 - min_dist  # Lower distance = higher confidence
        if confidence >= threshold:
            return self.metadata[min_idx]['student_id'], confidence
        return None, None
