from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainterPath, QPen, QPixmap, QPainter, QBrush, QColor, QCursor
from PyQt6.QtWidgets import QGraphicsPathItem

from Tablet.config import Herramienta
from Tablet.undo_commands import CommandAdd
from .base import Tool


class ShapeTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.mode = "line"  # "line" o "curve"
        self.is_drawing = False
        self.step = 0  # Para curvas: 0=esperando, 1=dibujando linea base, 2=ajustando curva

        self.start_pos = QPointF()
        self.end_pos = QPointF()
        self.control_pos = QPointF()

        self.temp_item = None
        self.temp_path = None

    def activate(self):
        self.view.setCursor(Qt.CursorShape.CrossCursor)

    def set_mode(self, mode):
        """Define si es 'line' o 'curve'"""
        self.mode = mode
        self.step = 0
        self.is_drawing = False
        if self.temp_item:
            self.scene.removeItem(self.temp_item)
            self.temp_item = None

    def mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            capa = self.main.get_current_layer()
            if not capa or capa.bloqueada or not capa.visible:
                return

            pos = self.view.mapToScene(event.pos())

            if self.mode == "line":
                self.is_drawing = True
                self.start_pos = pos
                self.end_pos = pos
                self._create_temp_item()

            elif self.mode == "curve":
                if self.step == 0:
                    # Iniciar la base de la curva (recta inicial)
                    self.is_drawing = True
                    self.start_pos = pos
                    self.end_pos = pos
                    self.step = 1
                    self._create_temp_item()
                elif self.step == 2:
                    # Finalizar la curva con el click
                    self._commit_shape()

    def mouse_move(self, event):
        pos = self.view.mapToScene(event.pos())

        if self.mode == "line" and self.is_drawing:
            self.end_pos = pos
            self._update_temp_path()

        elif self.mode == "curve":
            if self.step == 1:
                # Estirando la linea base
                self.end_pos = pos
                self._update_temp_path()
            elif self.step == 2:
                # Moviendo el punto de control (curvatura)
                self.control_pos = pos
                self._update_temp_path()

    def mouse_release(self, event):
        if self.mode == "line" and self.is_drawing:
            self._commit_shape()

        elif self.mode == "curve" and self.step == 1:
            # Terminó de dibujar la base, ahora pasa a modo curva
            self.step = 2
            # Punto de control inicial en el medio
            self.control_pos = (self.start_pos + self.end_pos) / 2
            self._update_temp_path()
            # NO commiteamos aun, esperamos al siguiente click o movimiento

    def _create_temp_item(self):
        self.temp_path = QPainterPath()
        self.temp_item = QGraphicsPathItem()
        pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self.temp_item.setPen(pen)
        self.temp_item.setZValue(99999)
        self.scene.addItem(self.temp_item)
        self._update_temp_path()

    def _update_temp_path(self):
        if not self.temp_item: return

        path = QPainterPath()
        path.moveTo(self.start_pos)

        if self.mode == "line":
            path.lineTo(self.end_pos)
        elif self.mode == "curve":
            if self.step == 1:
                path.lineTo(self.end_pos)  # Visualiza recta mientras se define largo
            else:
                # Dibujar parábola (QuadTo)
                path.quadTo(self.control_pos, self.end_pos)

        self.temp_item.setPath(path)

    def _commit_shape(self):
        if not self.temp_item: return

        # Crear item final
        final_path = self.temp_item.path()

        # Limpiar temporal
        self.scene.removeItem(self.temp_item)
        self.temp_item = None
        self.is_drawing = False
        self.step = 0  # Reset para curva

        # Crear item persistente
        pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                   Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        path_item = QGraphicsPathItem(final_path)
        path_item.setPen(pen)

        capa = self.main.get_current_layer()
        if capa:
            self.view.set_item_props(path_item)
            cmd = CommandAdd(self.scene, path_item, capa, self.main)
            self.main.undo_stack.push(cmd)