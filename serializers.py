import os
import shutil
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainterPath, QPen, QColor, QBrush, QFont, QTransform, QPixmap
from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsItem

from custom_items import EditableTextItem

def serialize_current_scene(main_window):
    """Convierte las capas y items de la escena actual a una lista de diccionarios."""
    serialized_layers = []
    assets_dir = os.path.join(main_window.current_project_dir, "assets") if main_window.current_project_dir else ""
    if assets_dir and not os.path.exists(assets_dir):
        os.makedirs(assets_dir, exist_ok=True)

    for capa in main_window.capas:
        layer_data = {
            "nombre": capa.nombre,
            "visible": capa.visible,
            "items": []
        }

        for item in capa.items:
            try:
                if item.scene() != main_window.scene: continue

                item_data = {
                    "pos_x": item.pos().x(),
                    "pos_y": item.pos().y(),
                    "rot": item.rotation(),
                    "scale": item.scale(),
                    "z": item.zValue()
                }

                # Transform matrix
                trans = item.transform()
                item_data.update({"m11": trans.m11(), "m12": trans.m12(), "m21": trans.m21(), "m22": trans.m22()})

                if isinstance(item, QGraphicsPathItem):
                    item_data["type"] = "path"
                    path = item.path()
                    if not path: continue

                    elements = []
                    for k in range(path.elementCount()):
                        e = path.elementAt(k)
                        elements.append({"t": e.type.value, "x": float(e.x), "y": float(e.y)})
                    item_data["path_elements"] = elements
                    item_data["pen_color"] = item.pen().color().name()
                    item_data["pen_width"] = item.pen().width()
                    item_data["has_pen"] = item.pen().style() != Qt.PenStyle.NoPen
                    item_data["has_fill"] = item.brush().style() != Qt.BrushStyle.NoBrush
                    if item_data["has_fill"]:
                        item_data["fill_color"] = item.brush().color().name()

                elif isinstance(item, (EditableTextItem, QGraphicsTextItem)):
                    item_data["type"] = "text"
                    item_data["content"] = item.toPlainText()
                    item_data["font_family"] = item.font().family()
                    item_data["font_size"] = item.font().pointSize()
                    item_data["color"] = item.defaultTextColor().name()

                elif isinstance(item, QGraphicsPixmapItem):
                    item_data["type"] = "image"
                    # Lógica de imagen...
                    original_path = item.data(Qt.ItemDataRole.UserRole + 1)
                    filename = item.data(Qt.ItemDataRole.UserRole + 2)  # Filename guardado previamente

                    if original_path and assets_dir:
                        filename = os.path.basename(original_path)
                        dest = os.path.join(assets_dir, filename)
                        if not os.path.exists(dest):
                            try:
                                shutil.copy2(original_path, dest)
                            except:
                                pass

                    item_data["img_filename"] = filename

                layer_data["items"].append(item_data)
            except RuntimeError:
                continue

        serialized_layers.append(layer_data)
    return serialized_layers


def render_layers_to_scene(main_window, layers_data):
    """Reconstruye los objetos gráficos en la escena a partir de una lista de datos de capas."""
    assets_dir = os.path.join(main_window.current_project_dir, "assets") if main_window.current_project_dir else ""

    # Si no hay capas, crear una por defecto
    if not layers_data:
        main_window.add_layer("Capa 1")
        return

    for layer_data in reversed(layers_data):
        main_window.add_layer(layer_data["nombre"])
        current_capa = main_window.capas[0]
        current_capa.visible = layer_data.get("visible", True)

        for item_data in layer_data.get("items", []):
            new_item = None
            type_str = item_data["type"]

            if type_str == "path":
                path = QPainterPath()
                elems = item_data.get("path_elements", [])
                if elems:
                    path.moveTo(elems[0]["x"], elems[0]["y"])
                    i = 1
                    while i < len(elems):
                        e = elems[i]
                        if e["t"] == 1:
                            path.lineTo(e["x"], e["y"]); i += 1
                        elif e["t"] == 2:
                            if i + 2 < len(elems):
                                path.cubicTo(elems[i]["x"], elems[i]["y"], elems[i + 1]["x"], elems[i + 1]["y"],
                                             elems[i + 2]["x"], elems[i + 2]["y"])
                                i += 3
                            else:
                                i += 1
                        else:
                            path.moveTo(e["x"], e["y"]); i += 1

                new_item = QGraphicsPathItem(path)
                if item_data.get("has_pen", True):
                    pen = QPen(QColor(item_data["pen_color"]))
                    pen.setWidth(item_data.get("pen_width", 1))
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    new_item.setPen(pen)
                else:
                    new_item.setPen(QPen(Qt.PenStyle.NoPen))

                if item_data.get("has_fill", False):
                    new_item.setBrush(QBrush(QColor(item_data["fill_color"])))

            elif type_str == "text":
                new_item = EditableTextItem(item_data["content"])
                new_item.setFont(QFont(item_data["font_family"], item_data["font_size"]))
                new_item.setDefaultTextColor(QColor(item_data["color"]))

            elif type_str == "image":
                fname = item_data.get("img_filename")
                if fname and assets_dir:
                    ipath = os.path.join(assets_dir, fname)
                    if os.path.exists(ipath):
                        new_item = QGraphicsPixmapItem(QPixmap(ipath))
                        new_item.setData(Qt.ItemDataRole.UserRole + 2, fname)

            if new_item:
                new_item.setPos(item_data["pos_x"], item_data["pos_y"])
                new_item.setRotation(item_data.get("rot", 0))
                if "m11" in item_data:
                    new_item.setTransform(
                        QTransform(item_data["m11"], item_data["m12"], item_data["m21"], item_data["m22"], 0, 0))
                else:
                    new_item.setScale(item_data.get("scale", 1))

                new_item.setZValue(item_data.get("z", 0))
                new_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
                new_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
                main_window.scene.addItem(new_item)
                current_capa.items.append(new_item)
                new_item.setVisible(current_capa.visible)

    main_window.actualizar_z_values()