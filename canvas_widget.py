from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem, \
    QGraphicsRectItem, QGraphicsItem
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QCursor, QTransform, QTextCursor

from config import Herramienta, ANCHO_LIENZO, ALTO_LIENZO
from custom_items import EditableTextItem
from undo_commands import CommandAdd, CommandDelete, CommandMoveRotate


class VectorScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, ANCHO_LIENZO, ALTO_LIENZO)
        self.bg_color = QColor("#e0e0e0")

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

        pen_margin = QPen(QColor(255, 100, 100))
        pen_margin.setWidth(2)
        painter.setPen(pen_margin)
        painter.drawLine(60, 0, 60, ALTO_LIENZO)


class EditorView(QGraphicsView):
    coords_changed = pyqtSignal(str)

    def __init__(self, scene, main_window):
        super().__init__(scene)
        self.main = main_window
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setAcceptDrops(True)

        # Variables estado
        self.puntos_trazados = []
        self.is_drawing = False
        self.temp_path_item = None

        # Zoom Box
        self.zoom_start = None
        self.zoom_rect_item = None

        # Selección / Transformación
        self.is_transforming = False
        self.transform_start_pos = None
        self.items_start_state = {}

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
        pos = self.mapToScene(event.pos())

        # --- ZOOM ---
        if self.main.herramienta_actual == Herramienta.ZOOM:
            if event.button() == Qt.MouseButton.RightButton:
                self.resetTransform()
                self.scale(0.8, 0.8)
            else:
                self.zoom_start = pos
                self.zoom_rect_item = QGraphicsRectItem()
                self.zoom_rect_item.setPen(QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine))
                self.scene().addItem(self.zoom_rect_item)
            return

        # --- LÁPIZ ---
        if self.main.herramienta_actual == Herramienta.LAPIZ:
            if event.button() == Qt.MouseButton.LeftButton:
                capa = self.main.get_current_layer()
                if capa and not capa.bloqueada and capa.visible:
                    self.start_drawing(pos)
                return

                # --- TEXTO ---
        elif self.main.herramienta_actual == Herramienta.TEXTO:
            item = self.scene().itemAt(pos, QTransform())
            if isinstance(item, QGraphicsTextItem):
                super().mousePressEvent(event)  # Delegar para editar
                return
            self.crear_texto_inline(pos)
            return

        # --- BORRADOR ---
        elif self.main.herramienta_actual == Herramienta.BORRADOR:
            self.borrar_en_punto(pos)
            return

        # --- SELECCIÓN ---
        elif self.main.herramienta_actual == Herramienta.SELECCION:
            item = self.scene().itemAt(pos, QTransform())
            if item:
                self.is_transforming = True
                self.transform_start_pos = pos
                # Guardar estado inicial
                self.items_start_state = {}
                for sel_item in self.scene().selectedItems():
                    self.items_start_state[sel_item] = (sel_item.pos(), sel_item.rotation(), sel_item.scale())

                if not item.isSelected():
                    item.setSelected(True)
                    self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())

            super().mousePressEvent(event)
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        self.coords_changed.emit(f"X: {int(pos.x())}, Y: {int(pos.y())}")

        if self.main.herramienta_actual == Herramienta.ZOOM and self.zoom_start:
            rect = QRectF(self.zoom_start, pos).normalized()
            self.zoom_rect_item.setRect(rect)
            return

        if self.is_drawing and self.main.herramienta_actual == Herramienta.LAPIZ:
            self.puntos_trazados.append(pos)
            if len(self.puntos_trazados) > 1:
                path = QPainterPath()
                path.moveTo(self.puntos_trazados[0])
                for p in self.puntos_trazados[1:]:
                    path.lineTo(p)

                if self.temp_path_item:
                    self.scene().removeItem(self.temp_path_item)

                self.temp_path_item = QGraphicsPathItem(path)
                pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.temp_path_item.setPen(pen)
                self.scene().addItem(self.temp_path_item)

        elif self.main.herramienta_actual == Herramienta.BORRADOR:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self.borrar_en_punto(pos)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        pos = self.mapToScene(event.pos())

        if self.main.herramienta_actual == Herramienta.ZOOM and self.zoom_start:
            rect = QRectF(self.zoom_start, pos).normalized()
            self.scene().removeItem(self.zoom_rect_item)
            self.zoom_rect_item = None
            self.zoom_start = None
            if rect.width() > 10 and rect.height() > 10:
                self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            return

        if self.is_drawing and self.main.herramienta_actual == Herramienta.LAPIZ:
            self.finish_drawing()

        if self.is_transforming and self.main.herramienta_actual == Herramienta.SELECCION:
            self.is_transforming = False
            # Registrar Undo
            for item, (old_pos, old_rot, old_scale) in self.items_start_state.items():
                if item.pos() != old_pos or item.rotation() != old_rot or item.scale() != old_scale:
                    cmd = CommandMoveRotate(item, old_pos, item.pos(),
                                            old_rot, item.rotation(),
                                            old_scale, item.scale())
                    self.main.undo_stack.push(cmd)
            self.items_start_state = {}

        super().mouseReleaseEvent(event)

    def start_drawing(self, pos):
        self.is_drawing = True
        self.puntos_trazados = [pos]
        self.temp_path_item = None

    def finish_drawing(self):
        self.is_drawing = False
        if self.temp_path_item:
            self.scene().removeItem(self.temp_path_item)
            self.temp_path_item = None

        if len(self.puntos_trazados) < 2:
            return

        path = QPainterPath()
        path.moveTo(self.puntos_trazados[0])

        skip = 1
        if self.main.suavizado_nivel > 0:
            skip = int(self.main.suavizado_nivel) + 1

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
            self.set_item_props(path_item)
            cmd = CommandAdd(self.scene(), path_item, capa, self.main)
            self.main.undo_stack.push(cmd)

    def borrar_en_punto(self, pos):
        radio = self.main.grosor_borrador / 2
        rect_borrado = QRectF(pos.x() - radio, pos.y() - radio, radio * 2, radio * 2)
        items = self.scene().items(rect_borrado)

        items_to_delete = []
        for item in items:
            if isinstance(item, (QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem)):
                capa_obj = None
                for capa in self.main.capas:
                    if item in capa.items:
                        capa_obj = capa
                        break
                if capa_obj and not capa_obj.bloqueada and capa_obj.visible:
                    items_to_delete.append((item, capa_obj))

        if items_to_delete:
            cmd = CommandDelete(self.scene(), items_to_delete, self.main)
            self.main.undo_stack.push(cmd)

    def crear_texto_inline(self, pos):
        text_item = EditableTextItem("Texto")
        text_item.setFont(self.main.font_texto)
        text_item.setDefaultTextColor(self.main.color_actual)
        text_item.setPos(pos)

        capa = self.main.get_current_layer()
        if capa:
            self.set_item_props(text_item)
            cmd = CommandAdd(self.scene(), text_item, capa, self.main)
            self.main.undo_stack.push(cmd)
            text_item.setFocus()
            cursor = text_item.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            text_item.setTextCursor(cursor)

    def set_item_props(self, item):
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.main.actualizar_z_values()