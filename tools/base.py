from PyQt6.QtCore import QObject

class Tool(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.scene = view.scene()
        self.main = view.main

    def mouse_press(self, event): pass
    def mouse_move(self, event): pass
    def mouse_release(self, event): pass
    def activate(self): pass
    def deactivate(self): pass
    def update_cursor(self): pass