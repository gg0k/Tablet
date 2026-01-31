from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainterPath, QPen, QPixmap, QPainter, QBrush, QColor, QCursor
from PyQt6.QtWidgets import QGraphicsPathItem

from Tablet.config import Herramienta
from Tablet.undo_commands import CommandAdd
from .base import Tool

class PenTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.is_drawing = False
        self.puntos_trazados = []
        self.temp_path_item = None
        self.current_path = None

    def activate(self):
        self.update_cursor()

    def update_cursor(self):
        size = max(4, self.main.grosor_lapiz)
        pix = QPixmap(size + 2, size + 2)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(self.main.color_actual))
        margin = 1
        painter.drawEllipse(margin, margin, size, size)
        painter.end()

        hotspot = size // 2 + 1
        self.view.setCursor(QCursor(pix, hotspot, hotspot))

    def mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            capa = self.main.get_current_layer()
            if capa and not capa.bloqueada and capa.visible:
                self.is_drawing = True
                pos = self.view.mapToScene(event.pos())
                self.puntos_trazados = [pos]

                self.current_path = QPainterPath()
                self.current_path.moveTo(pos)

                self.temp_path_item = QGraphicsPathItem(self.current_path)
                pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.temp_path_item.setPen(pen)
                self.temp_path_item.setZValue(99999)
                self.scene.addItem(self.temp_path_item)

    def mouse_move(self, event):
        if self.is_drawing and self.temp_path_item:
            pos = self.view.mapToScene(event.pos())
            if (pos - self.puntos_trazados[-1]).manhattanLength() > 2:
                self.puntos_trazados.append(pos)

                if self.current_path:
                    self.current_path.lineTo(pos)
                    self.temp_path_item.setPath(self.current_path)

    def mouse_release(self, event):
        if self.is_drawing:
            self.finish_drawing()

    def finish_drawing(self):
        self.is_drawing = False
        self.current_path = None

        if self.temp_path_item:
            self.scene.removeItem(self.temp_path_item)
            self.temp_path_item = None

        if len(self.puntos_trazados) < 2:
            return

        path = QPainterPath()
        path.moveTo(self.puntos_trazados[0])

        skip = int(self.main.suavizado_nivel / 10)
        if skip < 1: skip = 1

        if self.main.suavizado_nivel == 0:
            for p in self.puntos_trazados[1:]:
                path.lineTo(p)
        else:
            puntos_filtrados = self.puntos_trazados[::skip]
            if puntos_filtrados[-1] != self.puntos_trazados[-1]:
                puntos_filtrados.append(self.puntos_trazados[-1])

            for i in range(len(puntos_filtrados) - 1):
                if i < len(puntos_filtrados) - 2:
                    mid_x = (puntos_filtrados[i + 1].x() + puntos_filtrados[i + 2].x()) / 2
                    mid_y = (puntos_filtrados[i + 1].y() + puntos_filtrados[i + 2].y()) / 2
                    path.quadTo(puntos_filtrados[i + 1], QPointF(mid_x, mid_y))
                else:
                    path.lineTo(puntos_filtrados[i + 1])

        pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        path_item = QGraphicsPathItem(path)
        path_item.setPen(pen)

        capa = self.main.get_current_layer()
        if capa:
            self.view.set_item_props(path_item)
            cmd = CommandAdd(self.scene, path_item, capa, self.main)
            self.main.undo_stack.push(cmd)