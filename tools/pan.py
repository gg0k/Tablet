from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGraphicsView
from .base import Tool

class PanTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.is_panning = False
        self.start_pos = None
        self.h_sb_start = 0
        self.v_sb_start = 0

    def activate(self):
        # Desactivamos modos automáticos de Qt que interfieren
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.OpenHandCursor)

    def deactivate(self):
        self.view.setCursor(Qt.CursorShape.ArrowCursor)

    def mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.view.setCursor(Qt.CursorShape.ClosedHandCursor)

            # Guardamos la posición en pantalla (coordenadas de widget)
            self.start_pos = event.pos()

            # Guardamos el estado inicial de las barras de scroll
            self.h_sb_start = self.view.horizontalScrollBar().value()
            self.v_sb_start = self.view.verticalScrollBar().value()

    def mouse_move(self, event):
        if self.is_panning:
            # Calculamos diferencia desde el punto de inicio
            delta = event.pos() - self.start_pos

            # Aplicamos la diferencia inversa a las barras (para simular arrastre de papel)
            self.view.horizontalScrollBar().setValue(self.h_sb_start - delta.x())
            self.view.verticalScrollBar().setValue(self.v_sb_start - delta.y())

    def mouse_release(self, event):
        if self.is_panning:
            self.is_panning = False
            self.view.setCursor(Qt.CursorShape.OpenHandCursor)