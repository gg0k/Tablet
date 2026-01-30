import math
import traceback
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainterPath, QPen, QCursor, QTransform, QPainterPathStroker, QBrush, QColor, QPixmap, QPainter
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

    def update_cursor(self): pass


class PenTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.is_drawing = False
        self.puntos_trazados = []
        self.temp_path_item = None
        self.current_path = None  # Fix glitch (0,0)

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

                # Fix: Guardar el QPainterPath en variable local
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

                # Fix: Actualizar nuestra copia del path y setearla al item
                if self.current_path:
                    self.current_path.lineTo(pos)
                    self.temp_path_item.setPath(self.current_path)

    def mouse_release(self, event):
        if self.is_drawing:
            self.finish_drawing()

    def finish_drawing(self):
        self.is_drawing = False
        self.current_path = None  # Limpiar referencia

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
    def __init__(self, view):
        super().__init__(view)
        self.last_pos = None

    def activate(self):
        self.update_cursor()

    def update_cursor(self):
        size = max(4, self.main.grosor_borrador)
        pix = QPixmap(size + 2, size + 2)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
        margin = 1
        painter.drawEllipse(margin, margin, size, size)
        painter.end()
        hotspot = size // 2 + 1
        self.view.setCursor(QCursor(pix, hotspot, hotspot))

    def mouse_press(self, event):
        pos = self.view.mapToScene(event.pos())
        self.borrar_vectorial(pos)
        self.last_pos = pos

    def mouse_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            pos = self.view.mapToScene(event.pos())
            if self.last_pos:
                dist = (pos - self.last_pos).manhattanLength()
                step = max(2, self.main.grosor_borrador / 3)

                if dist > step:
                    steps = int(dist / step)
                    for i in range(1, steps + 1):
                        factor = i / steps
                        inter_pos = self.last_pos + (pos - self.last_pos) * factor
                        self.borrar_vectorial(inter_pos)
                else:
                    self.borrar_vectorial(pos)
            else:
                self.borrar_vectorial(pos)
            self.last_pos = pos

    def mouse_release(self, event):
        self.last_pos = None

    def borrar_vectorial(self, pos):
        try:
            radio = self.main.grosor_borrador / 2
            goma_path = QPainterPath()
            goma_path.addEllipse(pos, radio, radio)
            rect_borrado = QRectF(pos.x() - radio, pos.y() - radio, radio * 2, radio * 2)

            items = self.scene.items(rect_borrado)

            for item in items:
                # Fix: Verificar si el item sigue vivo en la escena
                if item.scene() is None: continue

                if isinstance(item, QGraphicsPathItem):
                    capa_obj = None
                    for capa in self.main.capas:
                        if item in capa.items:
                            capa_obj = capa
                            break

                    if not capa_obj or capa_obj.bloqueada or not capa_obj.visible:
                        continue

                    # 1. Transformar el path de la goma a coordenadas del item
                    goma_path_in_item = item.mapFromScene(goma_path)

                    original_path = item.path()
                    pen = item.pen()
                    brush = item.brush()

                    path_to_cut = original_path
                    is_stroke_conversion = False

                    if pen.style() != Qt.PenStyle.NoPen and brush.style() == Qt.BrushStyle.NoBrush:
                        stroker = QPainterPathStroker()
                        stroker.setWidth(pen.width())
                        stroker.setCapStyle(pen.capStyle())
                        stroker.setJoinStyle(pen.joinStyle())
                        path_to_cut = stroker.createStroke(original_path)
                        is_stroke_conversion = True

                    if not path_to_cut.intersects(goma_path_in_item.boundingRect()):
                        if not item.shape().intersects(goma_path_in_item):
                            continue

                    new_path = path_to_cut.subtracted(goma_path_in_item)

                    if new_path != path_to_cut:
                        if new_path.isEmpty():
                            cmd = CommandDelete(self.scene, [(item, capa_obj)], self.main)
                            self.main.undo_stack.push(cmd)
                        else:
                            new_item = QGraphicsPathItem(new_path)

                            new_item.setPos(item.pos())
                            new_item.setRotation(item.rotation())
                            new_item.setScale(item.scale())
                            new_item.setZValue(item.zValue())

                            self.view.set_item_props(new_item)

                            if is_stroke_conversion:
                                new_fill_color = pen.color()
                                new_item.setBrush(QBrush(new_fill_color))
                                new_item.setPen(QPen(Qt.PenStyle.NoPen))
                            else:
                                new_item.setBrush(brush)
                                new_item.setPen(pen)

                            cmd = CommandReplace(self.scene, item, [new_item], capa_obj, self.main)
                            self.main.undo_stack.push(cmd)

                elif isinstance(item, (EditableTextItem, QGraphicsTextItem)):
                    capa_obj = None
                    for capa in self.main.capas:
                        if item in capa.items:
                            capa_obj = capa
                            break
                    if capa_obj and not capa_obj.bloqueada and capa_obj.visible:
                        if item.sceneBoundingRect().intersects(rect_borrado):
                            cmd = CommandDelete(self.scene, [(item, capa_obj)], self.main)
                            self.main.undo_stack.push(cmd)
        except Exception as e:
            print("CRASH EVITADO EN GOMA DE BORRAR:")
            traceback.print_exc()


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
            super(self.view.__class__, self.view).mousePressEvent(event)
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
        self.mode = None  # 'in' or 'out'

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


class SelectionTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.gizmo = TransformGizmo(view)
        self.scene.addItem(self.gizmo)

        self.is_dragging = False
        self.is_transforming = False
        self.active_handle = None
        self.start_pos = None
        self.items_start_state = {}

        self.selection_center = QPointF(0, 0)
        self.selection_angle = 0.0

        self.scene.selectionChanged.connect(self.on_selection_changed)

    def activate(self):
        self.view.setDragMode(self.view.DragMode.RubberBandDrag)
        self.view.setCursor(Qt.CursorShape.ArrowCursor)
        self.update_gizmo()

    def deactivate(self):
        self.view.setDragMode(self.view.DragMode.NoDrag)
        # Fix: Validar si gizmo y su escena existen antes de ocultar
        if self.gizmo and self.gizmo.scene():
            self.gizmo.hide()

    def on_selection_changed(self):
        if self.main.herramienta_actual == Herramienta.SELECCION:
            self.selection_angle = 0.0
            self.update_gizmo()

    def update_gizmo(self):
        # Fix: Protección contra crash si el Gizmo ya fue borrado por scene.clear()
        if not self.gizmo or not self.gizmo.scene():
            return

        selected = self.scene.selectedItems()
        selected = [i for i in selected if i != self.gizmo and i.parentItem() != self.gizmo]

        if not selected:
            self.gizmo.hide()
            return

        full_rect = QRectF()
        for item in selected:
            if full_rect.isNull():
                full_rect = item.sceneBoundingRect()
            else:
                full_rect = full_rect.united(item.sceneBoundingRect())

        self.selection_center = full_rect.center()
        self.gizmo.update_geometry(self.selection_center, full_rect.size(), self.selection_angle)

    def mouse_press(self, event):
        scene_pos = self.view.mapToScene(event.pos())

        # Fix: Validar gizmo
        handle_role = None
        if self.gizmo and self.gizmo.scene() and self.gizmo.isVisible():
            handle_role = self.gizmo.get_handle_at(scene_pos)

        if handle_role and self.scene.selectedItems():
            self.is_transforming = True
            self.active_handle = handle_role
            self.start_pos = scene_pos
            self.view.setDragMode(self.view.DragMode.NoDrag)

            self.items_start_state = {}
            for item in self.scene.selectedItems():
                self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())
            return

        item = self.scene.itemAt(scene_pos, QTransform())
        # Fix: Validar gizmo
        if item and (not self.gizmo or item != self.gizmo):
            for c in self.main.capas:
                if item in c.items and c.bloqueada:
                    item.setSelected(False)
                    return

        super(self.view.__class__, self.view).mousePressEvent(event)

        if self.scene.selectedItems() and not self.is_transforming:
            self.items_start_state = {}
            for item in self.scene.selectedItems():
                self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())

    def mouse_move(self, event):
        if self.is_transforming:
            current_pos = self.view.mapToScene(event.pos())
            self.apply_transform(current_pos)
            self.update_gizmo()
        else:
            if not self.view.cursor().shape() == Qt.CursorShape.ArrowCursor and not self.view.dragMode() == self.view.DragMode.RubberBandDrag:
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
            super(self.view.__class__, self.view).mouseMoveEvent(event)

    def mouse_release(self, event):
        if self.is_transforming:
            self.is_transforming = False
            self.active_handle = None
            self.view.setDragMode(self.view.DragMode.RubberBandDrag)
            self.finalize_transform_undo()

        elif self.items_start_state:
            has_moved = False
            for item in self.items_start_state:
                if item.pos() != self.items_start_state[item][0]:
                    has_moved = True
                    break

            if has_moved:
                self.finalize_transform_undo()

        super(self.view.__class__, self.view).mouseReleaseEvent(event)
        self.update_gizmo()

    def apply_transform(self, current_pos):
        center = self.selection_center

        if self.active_handle == 'rotate':
            start_vec = self.start_pos - center
            curr_vec = current_pos - center

            angle_start = math.degrees(math.atan2(start_vec.y(), start_vec.x()))
            angle_end = math.degrees(math.atan2(curr_vec.y(), curr_vec.x()))
            angle_diff = angle_end - angle_start

            self.selection_angle += angle_diff

            for item in self.scene.selectedItems():
                offset = item.pos() - center
                rad = math.radians(angle_diff)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)

                new_x = offset.x() * cos_a - offset.y() * sin_a
                new_y = offset.x() * sin_a + offset.y() * cos_a
                new_pos = center + QPointF(new_x, new_y)

                item.setPos(new_pos)
                item.setRotation(item.rotation() + angle_diff)

            self.start_pos = current_pos

        elif self.active_handle in ['tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r']:
            vec_start = self.start_pos - center
            vec_curr = current_pos - center

            scale_x = 1.0
            scale_y = 1.0

            if abs(vec_start.x()) > 1:
                scale_x = vec_curr.x() / vec_start.x()
            if abs(vec_start.y()) > 1:
                scale_y = vec_curr.y() / vec_start.y()

            if self.active_handle in ['t', 'b']: scale_x = 1.0
            if self.active_handle in ['l', 'r']: scale_y = 1.0

            for item in self.scene.selectedItems():
                offset = item.pos() - center
                new_x = offset.x() * scale_x
                new_y = offset.y() * scale_y
                item.setPos(center + QPointF(new_x, new_y))

                trans = item.transform()
                trans.scale(scale_x, scale_y)
                item.setTransform(trans)

            self.start_pos = current_pos

    def finalize_transform_undo(self):
        changed = False
        for item, (old_pos, old_rot, old_scale) in self.items_start_state.items():
            if item.pos() != old_pos or item.rotation() != old_rot or item.scale() != old_scale:
                changed = True
                break

        if changed:
            self.main.undo_stack.beginMacro("Transformar")
            for item, (old_pos, old_rot, old_scale) in self.items_start_state.items():
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
        self.view.setInteractive(False)

    def deactivate(self):
        self.view.setDragMode(self.view.DragMode.NoDrag)
        self.view.setCursor(Qt.CursorShape.ArrowCursor)
        self.view.setInteractive(True)