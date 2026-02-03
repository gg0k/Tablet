from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QPushButton
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QSize
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
        self.setStyleSheet("background: #cccccc; border: 1px solid #444;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Estado de visibilidad (expandido/colapsado)
        self.is_expanded = True
        self.expanded_size = QSize(160, 226)
        self.collapsed_size = QSize(30, 30)

        # Botón Ojo (Toggle)
        self.btn_toggle = QPushButton("👁️", self)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 63, 65, 200);
                color: white;
                border: none;
                border-radius: 3px;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #4b6eaf;
            }
        """)
        self.btn_toggle.setFixedSize(24, 24)
        self.btn_toggle.clicked.connect(self.toggle_minimap)

        # Posicionar botón inicialmente
        self.update_button_pos()

    def toggle_minimap(self):
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.setFixedSize(self.expanded_size)
            self.btn_toggle.setText("👁️")
            self.setStyleSheet("background: #cccccc; border: 1px solid #444;")
        else:
            self.setFixedSize(self.collapsed_size)
            # Ojo tachado (simbolizado)
            self.btn_toggle.setText("🙈")
            self.setStyleSheet("background: transparent; border: none;")

        self.update_button_pos()

        # Forzar actualización de posición en MainWindow
        if self.main_view and hasattr(self.main_view.main, 'update_minimap'):
            self.main_view.main.update_minimap()

    def update_button_pos(self):
        # Botón siempre arriba a la derecha
        margin = 3
        self.btn_toggle.move(self.width() - self.btn_toggle.width() - margin, margin)

    def resizeEvent(self, event):
        self.update_button_pos()
        if self.is_expanded and self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        super().resizeEvent(event)

    def drawForeground(self, painter, rect):
        if not self.is_expanded or not self.main_view or not self.scene():
            return

        viewport_rect = self.main_view.viewport().rect()
        visible_scene_poly = self.main_view.mapToScene(viewport_rect)
        visible_scene_rect = visible_scene_poly.boundingRect()

        painter.save()

        scene_rect = self.scene().sceneRect()
        path_full = QPainterPath()
        path_full.addRect(scene_rect)

        path_visible = QPainterPath()
        path_visible.addRect(visible_scene_rect)

        path_overlay = path_full.subtracted(path_visible)

        overlay_color = QColor(0, 0, 0, 120)
        painter.setBrush(overlay_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path_overlay)

        scale_x = self.transform().m11()
        pen_width = 2.0 / scale_x if scale_x > 0 else 2.0

        stroke_pen = QPen(QColor(255, 0, 0), pen_width)
        painter.setPen(stroke_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(visible_scene_rect)

        painter.restore()


class EditorView(QGraphicsView):
    coords_changed = pyqtSignal(str)
    viewport_changed = pyqtSignal()

    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main = main_window
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setAcceptDrops(True)
        self.current_tool = None
        self.setMouseTracking(True)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def scale(self, sx, sy):
        super().scale(sx, sy)
        self.viewport_changed.emit()

    def fitInView(self, rect, mode=Qt.AspectRatioMode.IgnoreAspectRatio):
        super().fitInView(rect, mode)
        self.viewport_changed.emit()

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
        # Aquí la herramienta tiene prioridad absoluta (si existe)
        if self.current_tool:
            self.current_tool.mouse_press(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # --- CORRECCIÓN CRÍTICA ---
        # 1. Primero llamamos a super() para que Qt maneje eventos de hover, items y cursores estándar.
        super().mouseMoveEvent(event)

        # 2. Luego, la herramienta tiene la última palabra y puede sobreescribir el cursor si lo necesita.
        if self.current_tool:
            self.current_tool.mouse_move(event)

        # 3. Emitimos coordenadas
        pos = self.mapToScene(event.pos())
        self.coords_changed.emit(f"X: {int(pos.x())}, Y: {int(pos.y())}")

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