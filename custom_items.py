from PyQt6.QtWidgets import QGraphicsTextItem
from PyQt6.QtCore import Qt


class EditableTextItem(QGraphicsTextItem):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            # Salir de edición
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            self.clearFocus()
            # Devolver foco a la vista para que atajos globales funcionen
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