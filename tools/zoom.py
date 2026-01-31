from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QGraphicsRectItem

from .base import Tool

class ZoomTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.zoom_start = None
        self.zoom_rect_item = None
        self.mode = None

    def activate(self):
        self.view.setCursor(Qt.CursorShape.CrossCursor)

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        self.zoom_start = pos
        self.zoom_rect_item = QGraphicsRectItem()

        if event.button() == Qt.MouseButton.RightButton:
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