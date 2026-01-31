import traceback
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainterPath, QPen, QPixmap, QPainter, QBrush, QColor, QPainterPathStroker, QCursor
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem


from .base import Tool
from Tablet.config import Herramienta
from Tablet.undo_commands import CommandDelete, CommandReplace
from Tablet.custom_items import EditableTextItem


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
                if item.scene() is None: continue

                if isinstance(item, QGraphicsPathItem):
                    capa_obj = None
                    for capa in self.main.capas:
                        if item in capa.items:
                            capa_obj = capa
                            break

                    if not capa_obj or capa_obj.bloqueada or not capa_obj.visible:
                        continue

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