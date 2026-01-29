import math
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainterPath, QPen, QCursor, QTransform, QPainterPathStroker, QBrush, QColor
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsPixmapItem

from config import Herramienta
from custom_items import EditableTextItem, TransformGizmo
from undo_commands import CommandAdd, CommandDelete, CommandMoveRotate, CommandReplace


class Tool:
    def __init__(self, view):
        self.view = view
        self.scene = view.scene()
        self.main = view.main

    def mouse_press(self, event): pass

    def mouse_move(self, event): pass

    def mouse_release(self, event): pass

    def activate(self): pass

    def deactivate(self): pass


class PenTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.is_drawing = False
        self.puntos_trazados = []
        self.temp_path_item = None

    def activate(self):
        self.update_cursor()

    def update_cursor(self):
        from PyQt6.QtGui import QPixmap, QPainter
        size = max(10, self.main.grosor_lapiz * 2)
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.setBrush(QBrush(self.main.color_actual))
        painter.drawEllipse(int(size / 2) - 2, int(size / 2) - 2, 4, 4)
        painter.end()
        self.view.setCursor(QCursor(pix))

    def mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            capa = self.main.get_current_layer()
            if capa and not capa.bloqueada and capa.visible:
                self.is_drawing = True
                pos = self.view.mapToScene(event.pos())
                self.puntos_trazados = [pos]
                self.temp_path_item = None

    def mouse_move(self, event):
        if self.is_drawing:
            pos = self.view.mapToScene(event.pos())
            self.puntos_trazados.append(pos)
            if len(self.puntos_trazados) > 1:
                path = QPainterPath()
                path.moveTo(self.puntos_trazados[0])
                for p in self.puntos_trazados[1:]:
                    path.lineTo(p)

                if self.temp_path_item:
                    self.scene.removeItem(self.temp_path_item)

                self.temp_path_item = QGraphicsPathItem(path)
                pen = QPen(self.main.color_actual, self.main.grosor_lapiz,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                self.temp_path_item.setPen(pen)
                # IMPORTANTE: Forzar Z alto temporalmente para que se vea encima mientras se dibuja
                self.temp_path_item.setZValue(99999)
                self.scene.addItem(self.temp_path_item)

    def mouse_release(self, event):
        if self.is_drawing:
            self.finish_drawing()

    def finish_drawing(self):
        self.is_drawing = False
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


class EraserTool(Tool):
    def activate(self):
        from PyQt6.QtGui import QPixmap, QPainter
        size = self.main.grosor_borrador
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.drawEllipse(0, 0, size - 1, size - 1)
        painter.end()
        self.view.setCursor(QCursor(pix))

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        self.borrar_vectorial(pos)

    def mouse_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = self.view.mapToScene(event.pos())
            self.borrar_vectorial(pos)

    def borrar_vectorial(self, pos):
        """
        Implementación estilo Flash:
        1. Detecta si el item es un trazo (Stroke).
        2. Si lo es, lo convierte en una forma rellena (Outline) usando QPainterPathStroker.
        3. Realiza la resta booleana.
        Esto evita que el path intente 'cerrarse' conectando el principio con el final.
        """
        radio = self.main.grosor_borrador / 2
        goma_path = QPainterPath()
        goma_path.addEllipse(pos, radio, radio)
        rect_borrado = QRectF(pos.x() - radio, pos.y() - radio, radio * 2, radio * 2)

        # Obtenemos items en el área de la goma
        items = self.scene.items(rect_borrado)

        for item in items:
            if isinstance(item, QGraphicsPathItem):
                capa_obj = None
                for capa in self.main.capas:
                    if item in capa.items:
                        capa_obj = capa
                        break

                if not capa_obj or capa_obj.bloqueada or not capa_obj.visible:
                    continue

                original_path = item.path()

                # --- LÓGICA FLASH: Convertir trazo a forma ---
                pen = item.pen()
                brush = item.brush()

                path_to_cut = original_path
                is_stroke_conversion = False

                # Verificamos si es un trazo puro (tiene Pen pero no Brush)
                # Esto es típico del Lápiz. Al borrar, lo convertiremos en "Tinta" (Forma rellena)
                if pen.style() != Qt.PenStyle.NoPen and brush.style() == Qt.BrushStyle.NoBrush:
                    stroker = QPainterPathStroker()
                    stroker.setWidth(pen.width())
                    stroker.setCapStyle(pen.capStyle())
                    stroker.setJoinStyle(pen.joinStyle())
                    # Creamos un path que representa el contorno del trazo original
                    path_to_cut = stroker.createStroke(original_path)
                    is_stroke_conversion = True

                # Verificamos intersección rápida
                if not path_to_cut.intersects(rect_borrado):
                    continue

                # Resta Booleana: Aquí ocurre la magia de cortar
                new_path = path_to_cut.subtracted(goma_path)

                if new_path != path_to_cut:
                    # Si el corte dejó el path vacío, lo borramos
                    if new_path.isEmpty():
                        cmd = CommandDelete(self.scene, [(item, capa_obj)], self.main)
                        self.main.undo_stack.push(cmd)
                    else:
                        # Creamos el nuevo item recortado
                        new_item = QGraphicsPathItem(new_path)
                        new_item.setZValue(item.zValue())
                        self.view.set_item_props(new_item)

                        if is_stroke_conversion:
                            # Si era un trazo, ahora es una forma rellena.
                            # Usamos el color del pen original como relleno (Brush)
                            # y quitamos el borde (Pen).
                            new_fill_color = pen.color()
                            new_item.setBrush(QBrush(new_fill_color))
                            new_item.setPen(QPen(Qt.PenStyle.NoPen))
                        else:
                            # Si ya era una forma (ej. importada o ya convertida), mantenemos propiedades
                            new_item.setBrush(brush)
                            new_item.setPen(pen)

                        cmd = CommandReplace(self.scene, item, [new_item], capa_obj, self.main)
                        self.main.undo_stack.push(cmd)

            elif isinstance(item, (QGraphicsTextItem, QGraphicsPixmapItem)):
                # Lógica para borrar textos e imágenes completos si se tocan
                capa_obj = None
                for capa in self.main.capas:
                    if item in capa.items:
                        capa_obj = capa
                        break
                if capa_obj and not capa_obj.bloqueada and capa_obj.visible:
                    if item.collidesWithPath(goma_path):
                        cmd = CommandDelete(self.scene, [(item, capa_obj)], self.main)
                        self.main.undo_stack.push(cmd)


class TextTool(Tool):
    def activate(self):
        self.view.setCursor(Qt.CursorShape.IBeamCursor)

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        item = self.scene.itemAt(pos, QTransform())

        if isinstance(item, EditableTextItem) or isinstance(item, QGraphicsTextItem):
            for c in self.main.capas:
                if item in c.items and c.bloqueada:
                    return
            QGraphicsView_mousePressEvent = super(self.view.__class__, self.view).mousePressEvent
            QGraphicsView_mousePressEvent(event)
            return

        self.crear_texto_inline(pos)

    def crear_texto_inline(self, pos):
        capa = self.main.get_current_layer()
        if not capa or capa.bloqueada or not capa.visible:
            return

        text_item = EditableTextItem("Texto")
        text_item.setFont(self.main.font_texto)
        text_item.setDefaultTextColor(self.main.color_actual)
        text_item.setPos(pos)

        self.view.set_item_props(text_item)
        cmd = CommandAdd(self.scene, text_item, capa, self.main)
        self.main.undo_stack.push(cmd)
        text_item.setFocus()
        cursor = text_item.textCursor()
        cursor.select(cursor.SelectionType.Document)
        text_item.setTextCursor(cursor)


class ZoomTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.zoom_start = None
        self.zoom_rect_item = None

    def activate(self):
        self.view.setCursor(Qt.CursorShape.CrossCursor)

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.RightButton:
            self.view.resetTransform()
            self.view.scale(0.8, 0.8)
        else:
            self.zoom_start = pos
            self.zoom_rect_item = QGraphicsRectItem()
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
            self.scene.removeItem(self.zoom_rect_item)
            self.zoom_rect_item = None
            self.zoom_start = None
            if rect.width() > 10 and rect.height() > 10:
                self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class SelectionTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.gizmo = TransformGizmo(view)
        self.scene.addItem(self.gizmo)

        self.is_dragging = False
        self.is_transforming = False  # handle drag
        self.active_handle = None
        self.start_pos = None
        self.items_start_state = {}

        # Conectar cambios de selección
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def activate(self):
        self.view.setDragMode(self.view.DragMode.RubberBandDrag)
        self.view.setCursor(Qt.CursorShape.ArrowCursor)
        self.update_gizmo()

    def deactivate(self):
        self.view.setDragMode(self.view.DragMode.NoDrag)
        self.gizmo.hide()

    def on_selection_changed(self):
        if self.main.herramienta_actual == Herramienta.SELECCION:
            self.update_gizmo()

    def update_gizmo(self):
        selected = self.scene.selectedItems()
        # Filtrar el gizmo mismo o sus hijos
        selected = [i for i in selected if i != self.gizmo and i.parentItem() != self.gizmo]
        self.gizmo.update_geometry(selected)

    def mouse_press(self, event):
        scene_pos = self.view.mapToScene(event.pos())

        # 1. Verificar si clicamos un handle del Gizmo
        handle_role = self.gizmo.get_handle_at(scene_pos)

        if handle_role and self.scene.selectedItems():
            self.is_transforming = True
            self.active_handle = handle_role
            self.start_pos = scene_pos
            self.view.setDragMode(self.view.DragMode.NoDrag)

            # Guardar estado para Undo
            self.items_start_state = {}
            for item in self.scene.selectedItems():
                self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())
            return

        # 2. Lógica normal de selección (Bloqueo de capa)
        item = self.scene.itemAt(scene_pos, QTransform())
        if item and item != self.gizmo and item.parentItem() != self.gizmo:
            for c in self.main.capas:
                if item in c.items and c.bloqueada:
                    item.setSelected(False)
                    return

        # Si clicamos fuera o en un item para arrastrar
        super(self.view.__class__, self.view).mousePressEvent(event)

        # Si empezamos a arrastrar items (movimiento normal)
        if self.scene.selectedItems() and not self.is_transforming:
            # Guardamos estado por si es un move
            self.items_start_state = {}
            for item in self.scene.selectedItems():
                self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())

    def mouse_move(self, event):
        if self.is_transforming:
            current_pos = self.view.mapToScene(event.pos())
            self.apply_transform(current_pos)
            self.update_gizmo()
        else:
            super(self.view.__class__, self.view).mouseMoveEvent(event)

    def mouse_release(self, event):
        if self.is_transforming:
            self.is_transforming = False
            self.active_handle = None
            self.view.setDragMode(self.view.DragMode.RubberBandDrag)
            self.finalize_transform_undo()

        # Verificar si hubo movimiento de items (no transformación de handles)
        elif self.items_start_state:
            self.finalize_transform_undo()

        super(self.view.__class__, self.view).mouseReleaseEvent(event)
        self.update_gizmo()

    def apply_transform(self, current_pos):
        # Lógica simplificada de transformación
        dx = current_pos.x() - self.start_pos.x()
        dy = current_pos.y() - self.start_pos.y()

        center = self.gizmo.rect.center()

        if self.active_handle == 'rotate':
            # Calcular ángulo
            angle_start = math.atan2(self.start_pos.y() - center.y(), self.start_pos.x() - center.x())
            angle_end = math.atan2(current_pos.y() - center.y(), current_pos.x() - center.x())
            angle_diff = math.degrees(angle_end - angle_start)

            for item in self.scene.selectedItems():
                # Rotar alrededor del centro del item
                item.setRotation(item.rotation() + angle_diff)

            # Resetear start para rotación incremental suave
            self.start_pos = current_pos

        elif 't' in self.active_handle or 'b' in self.active_handle or 'l' in self.active_handle or 'r' in self.active_handle:
            # Escalar
            dist_start = math.hypot(self.start_pos.x() - center.x(), self.start_pos.y() - center.y())
            dist_curr = math.hypot(current_pos.x() - center.x(), current_pos.y() - center.y())

            if dist_start == 0: return
            scale_factor = dist_curr / dist_start

            for item in self.scene.selectedItems():
                item.setScale(item.scale() * scale_factor)

            self.start_pos = current_pos

    def finalize_transform_undo(self):
        # Registrar Undo si hubo cambios reales
        changed = False
        for item, (old_pos, old_rot, old_scale) in self.items_start_state.items():
            if item.pos() != old_pos or item.rotation() != old_rot or item.scale() != old_scale:
                changed = True
                break

        if changed:
            self.main.undo_stack.beginMacro("Transformar Selección")
            for item, (old_pos, old_rot, old_scale) in self.items_start_state.items():
                if item.pos() != old_pos or item.rotation() != old_rot or item.scale() != old_scale:
                    cmd = CommandMoveRotate(item, old_pos, item.pos(),
                                            old_rot, item.rotation(),
                                            old_scale, item.scale())
                    self.main.undo_stack.push(cmd)
            self.main.undo_stack.endMacro()

        self.items_start_state = {}


class PanTool(Tool):
    def activate(self):
        self.view.setDragMode(self.view.DragMode.ScrollHandDrag)
        self.view.setCursor(Qt.CursorShape.OpenHandCursor)

    def deactivate(self):
        self.view.setDragMode(self.view.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.ArrowCursor)