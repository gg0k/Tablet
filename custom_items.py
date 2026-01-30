from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem, QGraphicsLineItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor, QTransform


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
        super().__init__(-size / 2, -size / 2, size, size, parent)  # Centrado localmente
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(QColor("#3388ff"), 1))
        self.setCursor(cursor_shape)
        self.role = role
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                     True)  # Ignora zoom de vista, pero no rotación del padre si está en grupo


class TransformGizmo(QGraphicsItem):
    """
    Contenedor visual que rota y escala para ajustarse a la selección.
    """

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.rect = QRectF()
        self.handles = {}
        self.setZValue(999999)
        self.visible_pen = QPen(QColor("#3388ff"), 1.5, Qt.PenStyle.DashLine)

        self.create_handles()
        self.hide()

    def create_handles(self):
        size = 10
        # Esquinas
        self.handles['tl'] = HandleItem(0, 0, size, Qt.CursorShape.SizeFDiagCursor, 'tl', self)
        self.handles['tr'] = HandleItem(0, 0, size, Qt.CursorShape.SizeBDiagCursor, 'tr', self)
        self.handles['bl'] = HandleItem(0, 0, size, Qt.CursorShape.SizeBDiagCursor, 'bl', self)
        self.handles['br'] = HandleItem(0, 0, size, Qt.CursorShape.SizeFDiagCursor, 'br', self)

        # Lados
        self.handles['t'] = HandleItem(0, 0, size, Qt.CursorShape.SizeVerCursor, 't', self)
        self.handles['b'] = HandleItem(0, 0, size, Qt.CursorShape.SizeVerCursor, 'b', self)
        self.handles['l'] = HandleItem(0, 0, size, Qt.CursorShape.SizeHorCursor, 'l', self)
        self.handles['r'] = HandleItem(0, 0, size, Qt.CursorShape.SizeHorCursor, 'r', self)

        # Rotador
        self.rotate_handle = HandleItem(0, 0, size, Qt.CursorShape.PointingHandCursor, 'rotate', self)
        self.rotate_handle.setBrush(QBrush(QColor("#3388ff")))
        self.rotate_line = QGraphicsLineItem(self)
        self.rotate_line.setPen(QPen(QColor("#3388ff"), 1))

    def boundingRect(self):
        return self.rect.adjusted(-50, -50, 50, 50)

    def paint(self, painter, option, widget):
        painter.setPen(self.visible_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)

    def update_geometry(self, center, size, angle):
        """
        Actualiza la posición y rotación del Gizmo completo.
        center: QPointF (centro de la selección)
        size: QSizeF (tamaño del bounding box no rotado)
        angle: float (grados)
        """
        self.setPos(center)
        self.setRotation(angle)

        w, h = size.width(), size.height()
        half_w = w / 2
        half_h = h / 2

        # El rect local ahora está centrado en (0,0) del item Gizmo
        self.rect = QRectF(-half_w, -half_h, w, h)

        # Posicionar handles relativos al centro (0,0)
        r = self.rect
        self.handles['tl'].setPos(r.left(), r.top())
        self.handles['tr'].setPos(r.right(), r.top())
        self.handles['bl'].setPos(r.left(), r.bottom())
        self.handles['br'].setPos(r.right(), r.bottom())

        self.handles['t'].setPos(0, r.top())
        self.handles['b'].setPos(0, r.bottom())
        self.handles['l'].setPos(r.left(), 0)
        self.handles['r'].setPos(r.right(), 0)

        # Rotador (arriba)
        self.rotate_handle.setPos(0, r.top() - 30)
        self.rotate_line.setLine(0, r.top(), 0, r.top() - 30)

        self.show()
        self.update()

    def get_handle_at(self, scene_pos):
        # Convertir pos de escena a local del Gizmo
        local_pos = self.mapFromScene(scene_pos)

        if self.rotate_handle.contains(self.rotate_handle.mapFromParent(local_pos)):
            return 'rotate'

        for role, handle in self.handles.items():
            if handle.contains(handle.mapFromParent(local_pos)):
                return role
        return None