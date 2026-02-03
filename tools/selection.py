import math
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QTransform
from PyQt6.QtWidgets import QGraphicsView

from Tablet.config import Herramienta
from Tablet.custom_items import TransformGizmo
from Tablet.undo_commands import CommandMoveRotate
from .base import Tool


class SelectionTool(Tool):
    def __init__(self, view):
        super().__init__(view)
        self.gizmo = None

        self.is_dragging = False
        self.is_transforming = False
        self.active_handle = None
        self.start_pos = None
        self.items_start_state = {}

        self.selection_center = QPointF(0, 0)
        self.selection_angle = 0.0

        self.scene.selectionChanged.connect(self.on_selection_changed)

    def _check_gizmo(self):
        recreate = False
        if self.gizmo is None:
            recreate = True
        else:
            try:
                if self.gizmo.scene() != self.scene:
                    recreate = True
            except RuntimeError:
                recreate = True

        if recreate:
            self.gizmo = TransformGizmo(self.view)
            self.scene.addItem(self.gizmo)
            self.gizmo.hide()

    def activate(self):
        self.view.setDragMode(self.view.DragMode.RubberBandDrag)
        self.view.setCursor(Qt.CursorShape.ArrowCursor)
        self._check_gizmo()
        self.update_gizmo()

    def deactivate(self):
        self.view.setDragMode(self.view.DragMode.NoDrag)
        if self.gizmo:
            try:
                if self.gizmo.scene():
                    self.gizmo.hide()
            except RuntimeError:
                self.gizmo = None

    def on_selection_changed(self):
        if self.main.herramienta_actual == Herramienta.SELECCION:
            self.selection_angle = 0.0
            self.update_gizmo()

    def update_gizmo(self):
        self._check_gizmo()

        selected = self.scene.selectedItems()
        selected = [i for i in selected if i != self.gizmo and i.parentItem() != self.gizmo]

        if not selected:
            if self.gizmo: self.gizmo.hide()
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
        self._check_gizmo()

        handle_role = None
        if self.gizmo and self.gizmo.isVisible():
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

        if item and (not self.gizmo or item != self.gizmo):
            for c in self.main.capas:
                if item in c.items and c.bloqueada:
                    item.setSelected(False)
                    return

        # Mantenemos este call porque en EditorView.mousePress NO llamamos a super()
        QGraphicsView.mousePressEvent(self.view, event)

        if self.scene.selectedItems() and not self.is_transforming:
            self.items_start_state = {}
            for item in self.scene.selectedItems():
                self.items_start_state[item] = (item.pos(), item.rotation(), item.scale())

    def mouse_move(self, event):
        if self.is_transforming:
            current_pos = self.view.mapToScene(event.pos())
            self.apply_transform(current_pos)
            self.update_gizmo()

        # NOTA: Eliminamos el 'else' y las llamadas manuales a super() o setCursor.
        # EditorView ahora se encarga de llamar a super().mouseMoveEvent() PRIMERO,
        # lo que maneja automáticamente los cursores de hover (resize handles) y RubberBand.

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

        # Mantenemos este call porque en EditorView.mouseRelease NO llamamos a super()
        QGraphicsView.mouseReleaseEvent(self.view, event)
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