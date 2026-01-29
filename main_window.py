import sys
import json
import os
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QDockWidget,
                             QListWidget, QPushButton, QLabel, QSlider, QColorDialog, QFileDialog,
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QComboBox, QSpinBox,
                             QFontComboBox, QStackedWidget, QFormLayout, QInputDialog)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QPixmap, QPainter, QPen, QColor, QBrush, QFont, QCursor, \
    QShortcut, QUndoStack, QPainterPath

from config import Herramienta, ROOT_DIR
from data_models import CapaData
from custom_items import EditableTextItem
from canvas_widget import VectorScene, EditorView
from undo_commands import CommandAdd

from tools import PenTool, EraserTool, TextTool, ZoomTool, SelectionTool, PanTool


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notebook Vectorial Modular v1.2")
        self.resize(1300, 850)

        self.undo_stack = QUndoStack(self)
        self.settings = QSettings("MiEscuelaApp", "VectorNotebook")

        self.color_actual = QColor("#000000")
        self.grosor_lapiz = 3
        self.suavizado_nivel = 30
        self.grosor_borrador = 20
        self.font_texto = QFont("Arial", 12)

        self.load_settings()

        self.capas = []
        self.current_project_dir = None

        if not os.path.exists(ROOT_DIR):
            try:
                os.makedirs(ROOT_DIR)
            except Exception as e:
                pass

        self.scene = VectorScene()
        self.view = EditorView(self.scene, self)
        self.setCentralWidget(self.view)

        self.tools = {
            Herramienta.LAPIZ: PenTool(self.view),
            Herramienta.BORRADOR: EraserTool(self.view),
            Herramienta.TEXTO: TextTool(self.view),
            Herramienta.SELECCION: SelectionTool(self.view),
            Herramienta.ZOOM: ZoomTool(self.view),
            Herramienta.MOVER_CANVAS: PanTool(self.view)
        }

        self.setup_docks()
        self.setup_toolbar()
        self.setup_hotkeys()

        self.refresh_tree()
        self.add_layer("Capa 1")

        self.herramienta_actual = Herramienta.LAPIZ
        self.herramienta_previa_mano = None
        self.set_herramienta(Herramienta.LAPIZ)

    def load_settings(self):
        val_color = self.settings.value("color", "#000000")
        self.color_actual = QColor(val_color)
        self.grosor_lapiz = int(self.settings.value("grosor_lapiz", 3))
        self.suavizado_nivel = int(self.settings.value("suavizado", 30))
        self.grosor_borrador = int(self.settings.value("grosor_borrador", 20))

        font_family = self.settings.value("font_family", "Arial")
        font_size = int(self.settings.value("font_size", 12))
        self.font_texto = QFont(font_family, font_size)

    def save_settings(self):
        self.settings.setValue("color", self.color_actual.name())
        self.settings.setValue("grosor_lapiz", self.grosor_lapiz)
        self.settings.setValue("suavizado", self.suavizado_nivel)
        self.settings.setValue("grosor_borrador", self.grosor_borrador)
        self.settings.setValue("font_family", self.font_texto.family())
        self.settings.setValue("font_size", self.font_texto.pointSize())

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            if self.herramienta_actual != Herramienta.MOVER_CANVAS:
                self.herramienta_previa_mano = self.herramienta_actual
                self.set_herramienta(Herramienta.MOVER_CANVAS)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            if self.herramienta_previa_mano:
                self.set_herramienta(self.herramienta_previa_mano)
                self.herramienta_previa_mano = None
        super().keyReleaseEvent(event)

    def setup_toolbar(self):
        toolbar = QToolBar("Herramientas")
        toolbar.setOrientation(Qt.Orientation.Vertical)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

        self.action_group = {}

        def add_tool_action(name, icon_emoji, tool_enum):
            action = QAction(icon_emoji, self)
            action.setCheckable(True)
            action.setToolTip(name)
            action.triggered.connect(lambda: self.set_herramienta(tool_enum))
            toolbar.addAction(action)
            self.action_group[tool_enum] = action
            return action

        add_tool_action("Lápiz (B)", "✏️", Herramienta.LAPIZ).setChecked(True)
        add_tool_action("Borrador (E)", "🧽", Herramienta.BORRADOR)
        add_tool_action("Selección (S)", "🤚", Herramienta.SELECCION)
        add_tool_action("Texto (T)", "T", Herramienta.TEXTO)
        add_tool_action("Imagen (I)", "🖼️", Herramienta.IMAGEN)
        add_tool_action("Zoom (Z)", "🔍", Herramienta.ZOOM)
        add_tool_action("Mano (Espacio)", "📄", Herramienta.MOVER_CANVAS)

        toolbar.addSeparator()

        action_undo = self.undo_stack.createUndoAction(self, "Deshacer")
        action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        action_undo.setIconText("↩️")
        toolbar.addAction(action_undo)

        action_redo = self.undo_stack.createRedoAction(self, "Rehacer")
        action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        action_redo.setIconText("↪️")
        toolbar.addAction(action_redo)

    def setup_docks(self):
        # 1. Dock Organizador
        dock_org = QDockWidget("Escuela", self)
        dock_org.setFixedWidth(250)
        self.tree_files = QTreeWidget()
        self.tree_files.setHeaderHidden(True)
        self.tree_files.itemDoubleClicked.connect(self.abrir_archivo)

        widget_org = QWidget()
        layout_org = QVBoxLayout()
        layout_org.setContentsMargins(0, 0, 0, 0)

        h_files = QHBoxLayout()
        btn_refresh = QPushButton("🔄")
        btn_refresh.clicked.connect(self.refresh_tree)
        btn_new_subject = QPushButton("➕ Mat")
        btn_new_subject.clicked.connect(self.nueva_materia)
        btn_new_page = QPushButton("📄 Hoy")
        btn_new_page.clicked.connect(self.nueva_pagina)

        h_files.addWidget(btn_refresh)
        h_files.addWidget(btn_new_subject)
        h_files.addWidget(btn_new_page)
        layout_org.addLayout(h_files)
        layout_org.addWidget(self.tree_files)

        h_actions = QHBoxLayout()
        btn_save = QPushButton("💾 Guardar")
        btn_save.clicked.connect(self.guardar_archivo)
        btn_del = QPushButton("🗑️")
        btn_del.setStyleSheet("color: red;")
        btn_del.clicked.connect(self.borrar_archivo)
        h_actions.addWidget(btn_save)
        h_actions.addWidget(btn_del)
        layout_org.addLayout(h_actions)
        widget_org.setLayout(layout_org)
        dock_org.setWidget(widget_org)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_org)

        # 2. Dock Propiedades
        dock_props = QDockWidget("Propiedades", self)
        self.stack_props = QStackedWidget()
        self.stack_props.addWidget(QLabel("Herramienta"))

        # Panel Lápiz
        panel_lapiz = QWidget()
        form_lapiz = QFormLayout()
        spin_grosor = QSpinBox()
        spin_grosor.setRange(1, 50)
        spin_grosor.setValue(self.grosor_lapiz)
        spin_grosor.valueChanged.connect(self.set_grosor_lapiz)

        self.lbl_suavizado = QLabel(f"{self.suavizado_nivel}%")
        slide_suavizado = QSlider(Qt.Orientation.Horizontal)
        slide_suavizado.setRange(0, 100)
        slide_suavizado.setValue(self.suavizado_nivel)
        slide_suavizado.valueChanged.connect(self.update_suavizado)

        form_lapiz.addRow("Grosor:", spin_grosor)
        form_lapiz.addRow("Suavizado:", slide_suavizado)
        form_lapiz.addRow("", self.lbl_suavizado)
        panel_lapiz.setLayout(form_lapiz)
        self.stack_props.addWidget(panel_lapiz)

        # Panel Borrador
        panel_goma = QWidget()
        form_goma = QFormLayout()
        spin_goma = QSpinBox()
        spin_goma.setRange(5, 100)
        spin_goma.setValue(self.grosor_borrador)
        spin_goma.valueChanged.connect(lambda v: self.set_grosor_borrador(v))
        form_goma.addRow("Tamaño:", spin_goma)
        panel_goma.setLayout(form_goma)
        self.stack_props.addWidget(panel_goma)

        # Panel Texto
        panel_texto = QWidget()
        form_texto = QFormLayout()
        font_combo = QFontComboBox()
        font_combo.setCurrentFont(self.font_texto)
        font_combo.currentFontChanged.connect(lambda f: setattr(self, 'font_texto', f))
        spin_size = QSpinBox()
        spin_size.setValue(12)
        spin_size.valueChanged.connect(lambda s: self.font_texto.setPointSize(s))
        form_texto.addRow("Fuente:", font_combo)
        form_texto.addRow("Tamaño:", spin_size)
        panel_texto.setLayout(form_texto)
        self.stack_props.addWidget(panel_texto)

        # Panel Selección (Simplificado)
        panel_sel = QWidget()
        form_sel = QFormLayout()

        lbl_info = QLabel("Arrastra los puntos azules\npara transformar.")
        lbl_info.setStyleSheet("color: #aaa; font-style: italic;")

        btn_cortar = QPushButton("✂️ Cortar Vector (Exp)")
        btn_cortar.setToolTip("Corta vectores usando el área de selección actual")
        btn_cortar.clicked.connect(self.cortar_seleccion_vectorial)

        form_sel.addRow(lbl_info)
        form_sel.addRow(btn_cortar)
        panel_sel.setLayout(form_sel)
        self.stack_props.addWidget(panel_sel)

        dock_props.setWidget(self.stack_props)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_props)

        # 3. Dock Color
        dock_color = QDockWidget("Color", self)
        widget_color = QWidget()
        layout_color = QVBoxLayout()
        self.btn_color_picker = QPushButton()
        self.btn_color_picker.setFixedSize(50, 50)
        self.btn_color_picker.setStyleSheet(f"background-color: {self.color_actual.name()}; border: 2px solid #555;")
        self.btn_color_picker.clicked.connect(self.elegir_color)

        grid_colores = QHBoxLayout()
        colores = ["#000000", "#FF0000", "#0000FF", "#008000", "#FFFF00"]
        for c in colores:
            btn = QPushButton()
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"background-color: {c}; border: 1px solid #555;")
            btn.clicked.connect(lambda checked, col=c: self.set_color_hex(col))
            grid_colores.addWidget(btn)

        layout_color.addWidget(QLabel("Color:"))
        layout_color.addWidget(self.btn_color_picker)
        layout_color.addLayout(grid_colores)
        widget_color.setLayout(layout_color)
        dock_color.setWidget(widget_color)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_color)

        # 4. Dock Capas
        dock_capas = QDockWidget("Capas", self)
        widget_capas = QWidget()
        layout_capas = QVBoxLayout()

        self.list_capas = QListWidget()
        self.list_capas.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_capas.currentRowChanged.connect(self.on_capa_selected)
        self.list_capas.model().rowsMoved.connect(self.reordenar_capas)
        self.list_capas.itemDoubleClicked.connect(self.renombrar_capa)

        btns_capa = QHBoxLayout()
        btn_add_c = QPushButton("➕")
        btn_add_c.clicked.connect(lambda: self.add_layer(f"Capa {self.list_capas.count() + 1}"))

        btn_del_c = QPushButton("🗑️")
        btn_del_c.clicked.connect(self.eliminar_capa)

        btn_hide_c = QPushButton("👁️")
        btn_hide_c.setToolTip("Ocultar/Mostrar")
        btn_hide_c.clicked.connect(self.toggle_capa_visibilidad)

        btn_lock_c = QPushButton("🔒")
        btn_lock_c.setToolTip("Bloquear/Desbloquear")
        btn_lock_c.clicked.connect(self.toggle_capa_bloqueo)

        btns_capa.addWidget(btn_add_c)
        btns_capa.addWidget(btn_del_c)
        btns_capa.addWidget(btn_hide_c)
        btns_capa.addWidget(btn_lock_c)

        layout_capas.addWidget(self.list_capas)
        layout_capas.addLayout(btns_capa)
        widget_capas.setLayout(layout_capas)
        dock_capas.setWidget(widget_capas)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_capas)

    def setup_hotkeys(self):
        def hk(key, func):
            QShortcut(QKeySequence(key), self).activated.connect(func)

        hk("B", lambda: self.set_herramienta(Herramienta.LAPIZ))
        hk("E", lambda: self.set_herramienta(Herramienta.BORRADOR))
        hk("T", lambda: self.set_herramienta(Herramienta.TEXTO))
        hk("I", lambda: self.set_herramienta(Herramienta.IMAGEN))
        hk("S", lambda: self.set_herramienta(Herramienta.SELECCION))
        hk("Z", lambda: self.set_herramienta(Herramienta.ZOOM))

        btn_add_img = QPushButton("Insertar Imagen")
        btn_add_img.clicked.connect(self.dialogo_imagen)
        self.findChild(QToolBar).addWidget(btn_add_img)

    def set_herramienta(self, herramienta):
        self.herramienta_actual = herramienta

        for tool, action in self.action_group.items():
            action.setChecked(tool == herramienta)

        map_props = {
            Herramienta.LAPIZ: 1,
            Herramienta.BORRADOR: 2,
            Herramienta.TEXTO: 3,
            Herramienta.SELECCION: 4
        }
        self.stack_props.setCurrentIndex(map_props.get(herramienta, 0))

        if herramienta in self.tools:
            self.view.set_tool(self.tools[herramienta])
        else:
            self.view.set_tool(None)

    def update_suavizado(self, val):
        self.suavizado_nivel = val
        self.lbl_suavizado.setText(f"{val}%")

    def set_grosor_lapiz(self, val):
        self.grosor_lapiz = val
        if self.herramienta_actual == Herramienta.LAPIZ:
            self.tools[Herramienta.LAPIZ].update_cursor()

    def set_grosor_borrador(self, val):
        self.grosor_borrador = val

    def elegir_color(self):
        col = QColorDialog.getColor(self.color_actual, self)
        if col.isValid():
            self.color_actual = col
            self.btn_color_picker.setStyleSheet(f"background-color: {col.name()}; border: 2px solid #555;")
            if self.herramienta_actual == Herramienta.LAPIZ:
                self.tools[Herramienta.LAPIZ].update_cursor()

    def set_color_hex(self, hex_code):
        self.color_actual = QColor(hex_code)
        self.btn_color_picker.setStyleSheet(f"background-color: {hex_code}; border: 2px solid #555;")
        if self.herramienta_actual == Herramienta.LAPIZ:
            self.tools[Herramienta.LAPIZ].update_cursor()

    def dialogo_imagen(self):
        path, _ = QFileDialog.getOpenFileName(self, "Imagen", "", "Imagenes (*.png *.jpg *.jpeg)")
        if path:
            self.insertar_imagen_path(path)

    def insertar_imagen_path(self, path, pos=None):
        from PyQt6.QtWidgets import QGraphicsPixmapItem
        if pos is None:
            pos = self.view.mapToScene(self.view.viewport().rect().center())

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return

        item = QGraphicsPixmapItem(pixmap)
        item.setPos(pos)
        item.setData(Qt.ItemDataRole.UserRole + 1, path)

        if pixmap.width() > 500:
            item.setScale(500 / pixmap.width())

        capa = self.get_current_layer()
        if capa and not capa.bloqueada:
            self.view.set_item_props(item)
            cmd = CommandAdd(self.scene, item, capa, self)
            self.undo_stack.push(cmd)
            self.set_herramienta(Herramienta.SELECCION)

    def cortar_seleccion_vectorial(self):
        # Mantenemos esta función de utilidad aunque no esté en el sidebar principal
        # para uso avanzado si es necesario, o la dejamos conectada al botón del panel
        from PyQt6.QtWidgets import QGraphicsPathItem
        selection_path = QPainterPath()
        selection_rect = self.scene.selectionArea().boundingRect()
        if selection_rect.isEmpty():
            return
        selection_path.addRect(selection_rect)

        items_to_process = self.scene.selectedItems()
        if not items_to_process:
            items_to_process = self.scene.items(selection_path)

        for item in items_to_process:
            if isinstance(item, QGraphicsPathItem):
                capa = None
                for c in self.capas:
                    if item in c.items:
                        capa = c
                        break

                if not capa or capa.bloqueada: continue

                original_path = item.path()
                path_inside = original_path.intersected(selection_path)
                path_outside = original_path.subtracted(selection_path)

                if not path_inside.isEmpty() and not path_outside.isEmpty():
                    item_out = QGraphicsPathItem(path_outside)
                    item_out.setPen(item.pen())
                    item_out.setZValue(item.zValue())
                    self.view.set_item_props(item_out)

                    item_in = QGraphicsPathItem(path_inside)
                    item_in.setPen(item.pen())
                    item_in.setZValue(item.zValue())
                    self.view.set_item_props(item_in)

                    from undo_commands import CommandReplace
                    cmd = CommandReplace(self.scene, item, [item_out, item_in], capa, self)
                    self.undo_stack.push(cmd)

    def add_layer(self, nombre):
        capa = CapaData(nombre)
        self.capas.insert(0, capa)
        self.list_capas.insertItem(0, nombre)
        self.list_capas.setCurrentRow(0)
        self.actualizar_z_values()

    def eliminar_capa(self):
        row = self.list_capas.currentRow()
        if row == -1 or len(self.capas) <= 1:
            return

        capa = self.capas[row]
        for item in capa.items:
            self.scene.removeItem(item)

        self.capas.pop(row)
        self.list_capas.takeItem(row)
        self.actualizar_z_values()

    def toggle_capa_visibilidad(self):
        row = self.list_capas.currentRow()
        if row != -1:
            capa = self.capas[row]
            capa.visible = not capa.visible
            for item in capa.items:
                item.setVisible(capa.visible)

            self.actualizar_estilo_capa(row)

    def toggle_capa_bloqueo(self):
        row = self.list_capas.currentRow()
        if row != -1:
            capa = self.capas[row]
            capa.bloqueada = not capa.bloqueada
            if capa.bloqueada:
                for item in capa.items:
                    item.setSelected(False)
            self.actualizar_estilo_capa(row)

    def actualizar_estilo_capa(self, row):
        item_list = self.list_capas.item(row)
        capa = self.capas[row]
        font = item_list.font()
        font.setStrikeOut(not capa.visible)
        item_list.setFont(font)

        texto = capa.nombre
        if not capa.visible: texto += " (Oculta)"
        if capa.bloqueada: texto += " 🔒"
        item_list.setText(texto)

    def renombrar_capa(self, item):
        old_name = item.text().replace(" (Oculta)", "").replace(" 🔒", "")
        new_name, ok = QInputDialog.getText(self, "Renombrar Capa", "Nombre:", text=old_name)
        if ok and new_name:
            for c in self.capas:
                if c.nombre == old_name:
                    c.nombre = new_name
                    break
            self.actualizar_estilo_capa(self.list_capas.row(item))

    def on_capa_selected(self, index):
        pass

    def get_current_layer(self):
        row = self.list_capas.currentRow()
        if 0 <= row < len(self.capas):
            return self.capas[row]
        return None

    def reordenar_capas(self):
        nuevas_capas = []
        for i in range(self.list_capas.count()):
            text_raw = self.list_capas.item(i).text()
            nombre = text_raw.replace(" (Oculta)", "").replace(" 🔒", "")
            for c in self.capas:
                if c.nombre == nombre:
                    nuevas_capas.append(c)
                    break
        self.capas = nuevas_capas
        self.actualizar_z_values()

    def actualizar_z_values(self):
        # Actualizar Z-Index basado en el orden de las capas
        total = len(self.capas)
        for i, capa in enumerate(self.capas):
            # Capa 0 (UI) es la más alta.
            # Damos un rango de 1000 por capa.
            base_z = (total - 1 - i) * 1000
            for j, item in enumerate(capa.items):
                item.setZValue(base_z + j)

    def refresh_tree(self):
        self.tree_files.clear()
        try:
            if not os.path.exists(ROOT_DIR):
                return
            materias = [d for d in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, d))]
            for mat in materias:
                item_mat = QTreeWidgetItem([mat])
                item_mat.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon)))
                path_mat = os.path.join(ROOT_DIR, mat)

                paginas = [d for d in os.listdir(path_mat) if os.path.isdir(os.path.join(path_mat, d))]
                for pag in paginas:
                    if os.path.exists(os.path.join(path_mat, pag, "data.json")):
                        item_pag = QTreeWidgetItem([pag])
                        item_pag.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)))
                        item_pag.setData(0, Qt.ItemDataRole.UserRole, os.path.join(path_mat, pag))
                        item_mat.addChild(item_pag)

                self.tree_files.addTopLevelItem(item_mat)
        except Exception as e:
            print(f"Error refresh tree: {e}")

    def nueva_materia(self):
        nombre, ok = QInputDialog.getText(self, "Nueva Materia", "Nombre:")
        if ok and nombre:
            path = os.path.join(ROOT_DIR, nombre)
            os.makedirs(path, exist_ok=True)
            self.refresh_tree()

    def nueva_pagina(self):
        item = self.tree_files.currentItem()
        if not item:
            QMessageBox.warning(self, "Error", "Selecciona una materia primero")
            return
        while item.parent():
            item = item.parent()

        materia_path = os.path.join(ROOT_DIR, item.text(0))
        fecha = datetime.now().strftime("%d-%m-%Y")

        nombre_base = fecha
        contador = 1
        while os.path.exists(os.path.join(materia_path, nombre_base)):
            nombre_base = f"{fecha}_{contador}"
            contador += 1

        project_path = os.path.join(materia_path, nombre_base)
        os.makedirs(project_path)
        os.makedirs(os.path.join(project_path, "assets"))

        with open(os.path.join(project_path, "data.json"), 'w') as f:
            json.dump({"capas": []}, f)

        self.refresh_tree()
        self.cargar_desde_archivo(project_path)

    def abrir_archivo(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.cargar_desde_archivo(path)

    def guardar_archivo(self):
        from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem
        if not self.current_project_dir:
            return

        json_path = os.path.join(self.current_project_dir, "data.json")
        assets_dir = os.path.join(self.current_project_dir, "assets")

        data_to_save = {"capas": []}

        try:
            for c_idx, capa in enumerate(self.capas):
                layer_data = {
                    "nombre": capa.nombre,
                    "visible": capa.visible,
                    "items": []
                }

                for i_idx, item in enumerate(capa.items):
                    if item.scene() != self.scene: continue

                    item_data = {
                        "pos_x": item.pos().x(),
                        "pos_y": item.pos().y(),
                        "rot": item.rotation(),
                        "scale": item.scale(),
                        "z": item.zValue()
                    }

                    if isinstance(item, QGraphicsPathItem):
                        item_data["type"] = "path"
                        path = item.path()
                        if path is None: continue

                        elm_count = path.elementCount()
                        elements = []
                        for k in range(elm_count):
                            e = path.elementAt(k)
                            elements.append({"t": e.type.value, "x": float(e.x), "y": float(e.y)})

                        item_data["path_elements"] = elements
                        item_data["pen_color"] = item.pen().color().name()
                        item_data["pen_width"] = item.pen().width()

                    elif isinstance(item, EditableTextItem) or isinstance(item, QGraphicsTextItem):
                        item_data["type"] = "text"
                        item_data["content"] = item.toPlainText()
                        item_data["font_family"] = item.font().family()
                        item_data["font_size"] = item.font().pointSize()
                        item_data["color"] = item.defaultTextColor().name()

                    elif isinstance(item, QGraphicsPixmapItem):
                        item_data["type"] = "image"
                        original_path = item.data(Qt.ItemDataRole.UserRole + 1)
                        if original_path:
                            filename = os.path.basename(original_path)
                            dest_path = os.path.join(assets_dir, filename)
                            if not os.path.exists(dest_path):
                                try:
                                    shutil.copy2(original_path, dest_path)
                                except:
                                    pass
                            item_data["img_filename"] = filename
                        else:
                            filename = item.data(Qt.ItemDataRole.UserRole + 2)
                            item_data["img_filename"] = filename

                    layer_data["items"].append(item_data)

                data_to_save["capas"].append(layer_data)

            with open(json_path, 'w') as f:
                json.dump(data_to_save, f)
            self.statusBar().showMessage(f"Guardado exitoso.", 3000)

        except Exception as e:
            QMessageBox.critical(self, "Error Fatal", f"No se pudo guardar: {e}")

    def cargar_desde_archivo(self, project_path):
        from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem
        self.scene.clear()
        self.undo_stack.clear()
        self.capas = []
        self.list_capas.clear()
        self.current_project_dir = project_path
        self.setWindowTitle(f"Notebook - {os.path.basename(project_path)}")

        json_path = os.path.join(project_path, "data.json")
        assets_dir = os.path.join(project_path, "assets")

        try:
            with open(json_path, 'r') as f:
                data = json.load(f)

            capas_data = data.get("capas", [])
            for layer_data in reversed(capas_data):
                self.add_layer(layer_data["nombre"])
                current_capa = self.capas[0]
                current_capa.visible = layer_data.get("visible", True)

                for item_data in layer_data.get("items", []):
                    new_item = None
                    if item_data["type"] == "path":
                        path = QPainterPath()
                        elems = item_data.get("path_elements", [])

                        if elems:
                            path.moveTo(elems[0]["x"], elems[0]["y"])
                            i = 1
                            while i < len(elems):
                                e = elems[i]
                                type_val = e["t"]

                                if type_val == 1:
                                    path.lineTo(e["x"], e["y"])
                                    i += 1
                                elif type_val == 2:
                                    if i + 2 < len(elems):
                                        cp1 = elems[i]
                                        cp2 = elems[i + 1]
                                        end = elems[i + 2]
                                        path.cubicTo(cp1["x"], cp1["y"], cp2["x"], cp2["y"], end["x"], end["y"])
                                        i += 3
                                    else:
                                        path.lineTo(e["x"], e["y"])
                                        i += 1
                                else:
                                    path.moveTo(e["x"], e["y"])
                                    i += 1

                        new_item = QGraphicsPathItem(path)
                        pen = QPen(QColor(item_data["pen_color"]))
                        pen.setWidth(item_data["pen_width"])
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        new_item.setPen(pen)

                    elif item_data["type"] == "text":
                        new_item = EditableTextItem(item_data["content"])
                        font = QFont(item_data["font_family"], item_data["font_size"])
                        new_item.setFont(font)
                        new_item.setDefaultTextColor(QColor(item_data["color"]))

                    elif item_data["type"] == "image":
                        filename = item_data.get("img_filename")
                        if filename:
                            img_path = os.path.join(assets_dir, filename)
                            if os.path.exists(img_path):
                                pixmap = QPixmap(img_path)
                                new_item = QGraphicsPixmapItem(pixmap)
                                new_item.setData(Qt.ItemDataRole.UserRole + 2, filename)

                    if new_item:
                        new_item.setPos(item_data["pos_x"], item_data["pos_y"])
                        new_item.setRotation(item_data.get("rot", 0))
                        new_item.setScale(item_data.get("scale", 1))

                        self.view.set_item_props(new_item)
                        self.scene.addItem(new_item)
                        current_capa.items.append(new_item)
                        new_item.setVisible(current_capa.visible)

            if not self.capas:
                self.add_layer("Capa 1")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error de carga: {e}")
            if not self.capas: self.add_layer("Capa 1")

    def borrar_archivo(self):
        if not self.current_project_dir:
            return
        if QMessageBox.question(self, "Borrar",
                                "¿Seguro que quieres borrar toda esta página?") == QMessageBox.StandardButton.Yes:
            shutil.rmtree(self.current_project_dir)
            self.scene.clear()
            self.current_project_dir = None
            self.refresh_tree()