from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor, QCursor


class EditableTextItem(QGraphicsTextItem):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            self.clearFocus()
            if self.scene() and self.scene().views():
                self.scene().views()[0].setFocus()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            self.setFocus()
        super().mouseDoubleClickEvent(event)


# --- SISTEMA DE TRANSFORMACIÓN VISUAL (GIZMO) ---

class HandleItem(QGraphicsRectItem):
    """Puntos de control (cuadraditos) para escalar/rotar"""

    def __init__(self, x, y, size, cursor_shape, role, parent=None):
        super().__init__(0, 0, size, size, parent)
        self.setPos(x - size / 2, y - size / 2)
        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(QColor("#3388ff"), 1))
        self.setCursor(cursor_shape)
        self.role = role  # 'top-left', 'bottom-right', 'rotate', etc.
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)  # Mantiene tamaño visual


class TransformGizmo(QGraphicsItem):
    """
    Contenedor visual que dibuja el recuadro y los handles alrededor de la selección.
    No contiene los items reales, solo los manipula.
    """

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.rect = QRectF()
        self.handles = {}
        self.target_items = []
        self.setZValue(999999)  # Siempre arriba de todo
        self.visible_pen = QPen(QColor("#3388ff"), 1.5, Qt.PenStyle.DashLine)

        self.create_handles()
        self.hide()

    def create_handles(self):
        size = 8
        # Esquinas
        self.handles['tl'] = HandleItem(0, 0, size, Qt.CursorShape.SizeFDiagCursor, 'tl', self)
        self.handles['tr'] = HandleItem(0, 0, size, Qt.CursorShape.SizeBDiagCursor, 'tr', self)
        self.handles['bl'] = HandleItem(0, 0, size, Qt.CursorShape.SizeBDiagCursor, 'bl', self)
        self.handles['br'] = HandleItem(0, 0, size, Qt.CursorShape.SizeFDiagCursor, 'br', self)

        # Lados (Opcional, agregamos para completar "9 puntos" aprox)
        self.handles['t'] = HandleItem(0, 0, size, Qt.CursorShape.SizeVerCursor, 't', self)
        self.handles['b'] = HandleItem(0, 0, size, Qt.CursorShape.SizeVerCursor, 'b', self)
        self.handles['l'] = HandleItem(0, 0, size, Qt.CursorShape.SizeHorCursor, 'l', self)
        self.handles['r'] = HandleItem(0, 0, size, Qt.CursorShape.SizeHorCursor, 'r', self)

        # Rotador (Un poco más arriba)
        self.rotate_handle = HandleItem(0, 0, size, Qt.CursorShape.PointingHandCursor, 'rotate', self)
        self.rotate_handle.setBrush(QBrush(QColor("#3388ff")))  # Azul para distinguir
        self.rotate_line = QGraphicsLineItem(self)
        self.rotate_line.setPen(QPen(QColor("#3388ff"), 1))

    def boundingRect(self):
        # Area de dibujo incluyendo el rotador que sobresale
        return self.rect.adjusted(-20, -40, 20, 20)

    def paint(self, painter, option, widget):
        painter.setPen(self.visible_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)

    def update_geometry(self, items):
        self.target_items = items
        if not items:
            self.hide()
            return

        # Calcular BoundingBox unificado de la selección
        full_rect = QRectF()
        for item in items:
            # Mapear el rect del item a coordenadas de la escena
            scene_rect = item.mapToScene(item.boundingRect()).boundingRect()
            full_rect = full_rect.united(scene_rect)

        self.rect = full_rect

        # Actualizar posición de handles
        r = self.rect
        self.handles['tl'].setPos(r.left(), r.top())
        self.handles['tr'].setPos(r.right(), r.top())
        self.handles['bl'].setPos(r.left(), r.bottom())
        self.handles['br'].setPos(r.right(), r.bottom())

        self.handles['t'].setPos(r.center().x(), r.top())
        self.handles['b'].setPos(r.center().x(), r.bottom())
        self.handles['l'].setPos(r.left(), r.center().y())
        self.handles['r'].setPos(r.right(), r.center().y())

        # Rotador
        rot_pos = QPointF(r.center().x(), r.top() - 25)
        self.rotate_handle.setPos(rot_pos)
        self.rotate_line.setLine(r.center().x(), r.top(), r.center().x(), r.top() - 25)

        self.show()
        self.update()

    def get_handle_at(self, scene_pos):
        # Verificar si el click fue en un handle
        # Convertir pos de escena a local
        local_pos = self.mapFromScene(scene_pos)

        # Chequear rotador primero
        if self.rotate_handle.contains(self.rotate_handle.mapFromParent(local_pos)):
            return 'rotate'

        for role, handle in self.handles.items():
            if handle.contains(handle.mapFromParent(local_pos)):
                return role
        return None