from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath

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
            # IMPORTANTE: Evitar dibujar el rótulo en el MiniMapa
            # Si la escala es muy pequeña (como en el minimapa), no dibujamos el texto flotante
            current_transform = painter.transform()
            if current_transform.m11() < 0.5:
                return

            painter.setTransform(
                painter.transform().reset())  # Dibujar en coordenadas de pantalla relativas a la escena

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


class MiniMapWidget(QGraphicsView):
    def __init__(self, scene, main_view, parent=None):
        super().__init__(scene, parent)
        self.main_view = main_view
        self.setInteractive(False)  # Solo visualización
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Fondo gris suave para el widget en sí
        self.setStyleSheet("background: #cccccc; border: 1px solid #444;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def resizeEvent(self, event):
        # Siempre encajar toda la escena en el minimapa
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)

    def drawForeground(self, painter, rect):
        if not self.main_view or not self.scene():
            return

        # 1. Calcular el rectángulo visible del MainView en coordenadas de la escena
        viewport_rect = self.main_view.viewport().rect()
        # Mapeamos el rectángulo del viewport (pixels) a la escena
        visible_scene_poly = self.main_view.mapToScene(viewport_rect)
        visible_scene_rect = visible_scene_poly.boundingRect()

        painter.save()

        # 2. Crear las formas para la sustracción (Overlay oscuro)
        scene_rect = self.scene().sceneRect()
        path_full = QPainterPath()
        path_full.addRect(scene_rect)

        path_visible = QPainterPath()
        path_visible.addRect(visible_scene_rect)

        # Restamos la parte visible al rectángulo total -> queda el "marco" oscuro
        path_overlay = path_full.subtracted(path_visible)

        # Dibujar overlay negro translúcido
        overlay_color = QColor(0, 0, 0, 120)  # Negro con transparencia
        painter.setBrush(overlay_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path_overlay)

        # 3. Dibujar borde rojo alrededor del área visible
        # Ajustamos el grosor para que se vea constante independientemente del zoom del minimapa
        scale_x = self.transform().m11()
        pen_width = 2.0 / scale_x if scale_x > 0 else 2.0

        stroke_pen = QPen(QColor(255, 0, 0), pen_width)
        painter.setPen(stroke_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(visible_scene_rect)

        painter.restore()


class EditorView(QGraphicsView):
    coords_changed = pyqtSignal(str)
    viewport_changed = pyqtSignal()  # Señal para avisar al minimapa

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

    # --- Overrides para detectar cambios de vista ---
    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def scale(self, sx, sy):
        # Override del método scale (llamado por ZoomTool)
        super().scale(sx, sy)
        self.viewport_changed.emit()

    def fitInView(self, rect, mode=Qt.AspectRatioMode.IgnoreAspectRatio):
        super().fitInView(rect, mode)
        self.viewport_changed.emit()

    # ------------------------------------------------

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

    def keyPressEvent(self, event):
        if self.current_tool:
            self.current_tool.key_press(event)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.current_tool:
            self.current_tool.key_release(event)
        super().keyReleaseEvent(event)

    def set_item_props(self, item):
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.main.actualizar_z_values()