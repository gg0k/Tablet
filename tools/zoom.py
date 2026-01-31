from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPen, QPixmap, QPainter, QBrush, QColor, QCursor
from PyQt6.QtWidgets import QGraphicsRectItem

from .base import Tool


class ZoomTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.zoom_start = None
        self.zoom_rect_item = None
        self.mode = None
        self.is_alt_pressed = False

    def activate(self):
        self.update_cursor()

    def key_press(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self.is_alt_pressed = True
            self.update_cursor()

    def key_release(self, event):
        if event.key() == Qt.Key.Key_Alt:
            self.is_alt_pressed = False
            self.update_cursor()

    def update_cursor(self):
        # Crear un cursor de lupa personalizado
        size = 32
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dibujar la lupa
        painter.setPen(QPen(QColor("black"), 2))
        painter.setBrush(QBrush(QColor("white")))  # Cristal

        # Círculo
        painter.drawEllipse(4, 4, 16, 16)
        # Mango
        painter.setPen(QPen(QColor("black"), 3))
        painter.drawLine(18, 18, 26, 26)

        # Dibujar símbolo (+ o -)
        painter.setPen(QPen(QColor("black"), 2))

        # Linea horizontal (siempre presente en + y -)
        painter.drawLine(8, 12, 16, 12)

        if not self.is_alt_pressed:
            # Linea vertical (solo para +)
            painter.drawLine(12, 8, 12, 16)

        painter.end()

        # El hotspot (punto activo) está en el centro de la lente (aprox 12,12)
        self.view.setCursor(QCursor(pix, 12, 12))

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        self.zoom_start = pos
        self.zoom_rect_item = QGraphicsRectItem()

        # Zoom OUT si es click derecho O si se mantiene presionado ALT
        if event.button() == Qt.MouseButton.RightButton or (event.modifiers() & Qt.KeyboardModifier.AltModifier):
            self.mode = 'out'
            self.zoom_rect_item.setPen(QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine))
        else:
            self.mode = 'in'
            self.zoom_rect_item.setPen(QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine))

        self.scene.addItem(self.zoom_rect_item)

    def mouse_move(self, event):
        if self.zoom_start:
            pos = self.view.mapToScene(event.pos())
            rect = QRectF(self.zoom_start, pos).normalized()
            self.zoom_rect_item.setRect(rect)

    def mouse_release(self, event):
        if self.zoom_start:
            pos = self.view.mapToScene(event.pos())
            rect = QRectF(self.zoom_start, pos).normalized()

            if self.zoom_rect_item.scene():
                self.scene.removeItem(self.zoom_rect_item)
            self.zoom_rect_item = None

            is_click = rect.width() < 10 or rect.height() < 10

            if self.mode == 'in':
                if is_click:
                    self.view.scale(1.25, 1.25)
                    self.view.centerOn(pos)
                else:
                    self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

            elif self.mode == 'out':
                if is_click:
                    self.view.scale(0.8, 0.8)
                    self.view.centerOn(pos)
                else:
                    view_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect()

                    if rect.width() > 0:
                        factor = rect.width() / view_rect.width()
                        if factor < 0.05: factor = 0.05
                        self.view.scale(factor, factor)
                        self.view.centerOn(rect.center())

            self.zoom_start = None
            self.mode = None