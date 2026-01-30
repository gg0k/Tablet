from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QFont

from config import ANCHO_LIENZO, ALTO_LIENZO


class VectorScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, ANCHO_LIENZO, ALTO_LIENZO)
        self.bg_color = QColor("#e0e0e0")

        # Metadatos para el rótulo
        self.meta_materia = ""
        self.meta_fecha = ""
        self.meta_pagina = ""

    def set_metadata(self, materia, fecha, pagina):
        self.meta_materia = materia
        self.meta_fecha = fecha
        self.meta_pagina = pagina
        self.update()

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, self.bg_color)

        # Hoja
        paper_rect = QRectF(0, 0, ANCHO_LIENZO, ALTO_LIENZO)
        painter.setBrush(Qt.GlobalColor.white)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(paper_rect)

        # Grid
        grid_size = 40
        pen_grid = QPen(QColor(220, 230, 240))
        pen_grid.setWidth(1)
        painter.setPen(pen_grid)

        for x in range(0, ANCHO_LIENZO + 1, grid_size):
            painter.drawLine(x, 0, x, ALTO_LIENZO)
        for y in range(0, ALTO_LIENZO + 1, grid_size):
            painter.drawLine(0, y, ANCHO_LIENZO, y)

        # Margen rojo
        pen_margin = QPen(QColor(255, 100, 100))
        pen_margin.setWidth(2)
        painter.setPen(pen_margin)
        painter.drawLine(60, 0, 60, ALTO_LIENZO)

    def drawForeground(self, painter, rect):
        # Rótulo con información
        if self.meta_materia or self.meta_fecha:
            painter.setTransform(
                painter.transform().reset())  # Dibujar en coordenadas de pantalla relativas a la escena? No, coordenadas de escena fijas.
            # Mejor dibujamos fijo en la esquina de la hoja

            # Caja de texto
            box_rect = QRectF(ANCHO_LIENZO - 250, 10, 240, 70)

            painter.setPen(QPen(QColor("#555"), 1))
            painter.setBrush(QColor(255, 255, 255, 200))
            painter.drawRoundedRect(box_rect, 5, 5)

            painter.setPen(Qt.GlobalColor.black)
            font = QFont("Arial", 10)
            font.setBold(True)
            painter.setFont(font)

            painter.drawText(box_rect.adjusted(10, 10, -10, 0), Qt.AlignmentFlag.AlignLeft,
                             f"Materia: {self.meta_materia}")
            painter.drawText(box_rect.adjusted(10, 30, -10, 0), Qt.AlignmentFlag.AlignLeft, f"Fecha: {self.meta_fecha}")
            painter.drawText(box_rect.adjusted(10, 50, -10, 0), Qt.AlignmentFlag.AlignRight, f"Pág: {self.meta_pagina}")


class EditorView(QGraphicsView):
    coords_changed = pyqtSignal(str)

    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main = main_window
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # Controlado por herramientas
        self.setAcceptDrops(True)
        self.current_tool = None

        # Crucial para que los cursores personalizados funcionen bien
        self.setMouseTracking(True)

    def set_tool(self, tool_instance):
        if self.current_tool:
            self.current_tool.deactivate()

        self.current_tool = tool_instance
        if self.current_tool:
            self.current_tool.activate()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.main.insertar_imagen_path(path, self.mapToScene(event.position().toPoint()))

    def mousePressEvent(self, event):
        if self.current_tool:
            self.current_tool.mouse_press(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        self.coords_changed.emit(f"X: {int(pos.x())}, Y: {int(pos.y())}")

        if self.current_tool:
            self.current_tool.mouse_move(event)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_tool:
            self.current_tool.mouse_release(event)
        else:
            super().mouseReleaseEvent(event)

    def set_item_props(self, item):
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.main.actualizar_z_values()