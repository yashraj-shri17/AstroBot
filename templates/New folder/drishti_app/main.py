"""
main.py

Kivy app entry point for Drishti Mobile App.
Integrates face recognition, local storage, and sync logic.
"""

import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.uix.screenmanager import ScreenManager, Screen
import cv2
import numpy as np
from face_engine import FaceEngine
from local_store import LocalStore
from sync import Syncer
from splash import SplashScreen

class DrishtiMainScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical')
        self.face_engine = FaceEngine()
        self.local_store = LocalStore()
        self.syncer = Syncer()
        self.camera = cv2.VideoCapture(0)
        self.img_widget = Image()
        self.status_label = Label(text="Ready", size_hint=(1, 0.1))
        layout.add_widget(self.img_widget)
        layout.add_widget(self.status_label)
        self.capture_btn = Button(text="Capture & Mark Attendance", size_hint=(1, 0.15))
        self.capture_btn.bind(on_press=self.capture_face)
        layout.add_widget(self.capture_btn)
        self.sync_btn = Button(text="Sync Attendance", size_hint=(1, 0.15))
        self.sync_btn.bind(on_press=self.sync_attendance)
        layout.add_widget(self.sync_btn)
        self.add_widget(layout)
        Clock.schedule_interval(self.update, 1.0/20.0)

    def update(self, dt):
        ret, frame = self.camera.read()
        if ret:
            buf = cv2.flip(frame, 0).tobytes()
            img_texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            img_texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.img_widget.texture = img_texture
            self.current_frame = frame

    def capture_face(self, instance):
        frame = getattr(self, 'current_frame', None)
        if frame is None:
            self.status_label.text = "No frame captured. Try again."
            return
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        student_id, confidence = self.face_engine.recognize(rgb_frame)
        if student_id:
            # For demo, use dummy name/class/section
            self.local_store.log_attendance(student_id, student_id, "10", "A")
            self.status_label.text = f"{student_id} – Present (Confidence: {int(confidence*100)}%)"
        else:
            self.status_label.text = "Face not recognized."

    def sync_attendance(self, instance):
        if self.syncer.sync():
            self.status_label.text = "Attendance synced!"
        else:
            self.status_label.text = "Offline or sync failed."

    def on_stop(self):
        self.camera.release()


class DrishtiApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SplashScreen(name='splash'))
        sm.add_widget(DrishtiMainScreen(name='main'))
        return sm

    def on_start(self):
        # Switch from splash to main after splash duration
        sm = self.root
        def switch_to_main(dt):
            sm.current = 'main'
        Clock.schedule_once(switch_to_main, 2.5)

if __name__ == '__main__':
    DrishtiApp().run()
