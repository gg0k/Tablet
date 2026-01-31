from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTransform
from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsView

from Tablet.custom_items import EditableTextItem
from Tablet.undo_commands import CommandAdd
from .base import Tool

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
            QGraphicsView.mousePressEvent(self.view, event)
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