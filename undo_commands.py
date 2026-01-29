from PyQt6.QtGui import QUndoCommand


class CommandAdd(QUndoCommand):
    def __init__(self, scene, item, capa_data, main_window):
        super().__init__()
        self.scene = scene
        self.item = item
        self.capa_data = capa_data
        self.main = main_window
        self.setText("Agregar Item")

    def redo(self):
        if self.item.scene() != self.scene:
            self.scene.addItem(self.item)
        if self.item not in self.capa_data.items:
            self.capa_data.items.append(self.item)
        # Asegurar Z correcto
        self.main.actualizar_z_values()

    def undo(self):
        if self.item.scene() == self.scene:
            self.scene.removeItem(self.item)
        if self.item in self.capa_data.items:
            self.capa_data.items.remove(self.item)


class CommandDelete(QUndoCommand):
    def __init__(self, scene, items_to_delete, main_window):
        super().__init__()
        self.scene = scene
        self.items = items_to_delete  # Lista de tuplas (item, capa_data)
        self.setText("Borrar Items")

    def redo(self):
        for item, capa in self.items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
            if item in capa.items:
                capa.items.remove(item)

    def undo(self):
        for item, capa in self.items:
            if item.scene() != self.scene:
                self.scene.addItem(item)
            if item not in capa.items:
                capa.items.append(item)


class CommandMoveRotate(QUndoCommand):
    def __init__(self, item, old_pos, new_pos, old_rot, new_rot, old_scale, new_scale):
        super().__init__()
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.old_rot = old_rot
        self.new_rot = new_rot
        self.old_scale = old_scale
        self.new_scale = new_scale
        self.setText("Transformar")

    def redo(self):
        self.item.setPos(self.new_pos)
        self.item.setRotation(self.new_rot)
        self.item.setScale(self.new_scale)

    def undo(self):
        self.item.setPos(self.old_pos)
        self.item.setRotation(self.old_rot)
        self.item.setScale(self.old_scale)