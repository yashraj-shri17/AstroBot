"""
Splash screen for Drishti App with Dzire Technologies logo.
"""
from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.clock import Clock

class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logo = Image(source='assets/dzire_logo.png', allow_stretch=True, keep_ratio=True)
        self.add_widget(self.logo)
        Clock.schedule_once(self.goto_main, 2.5)  # Show splash for 2.5 seconds

    def goto_main(self, dt):
        self.manager.current = 'main'
