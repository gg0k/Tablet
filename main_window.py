import sys
import json
import os
import shutil
import traceback
from datetime import datetime

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QDockWidget,
                             QListWidget, QPushButton, QLabel, QSlider, QColorDialog, QFileDialog,
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QComboBox, QSpinBox,
                             QFontComboBox, QStackedWidget, QFormLayout, QInputDialog, QFrame)
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
        self.setWindowTitle("Notebook Vectorial Modular v1.3 (STABLE)")
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
        self.current_materia_name = ""
        self.current_fecha = ""
        self.current_page_name = ""

        print(f"DEBUG INIT: ROOT_DIR configurado en: {ROOT_DIR}")
        if not os.path.exists(ROOT_DIR):
            try:
                os.makedirs(ROOT_DIR)
                print(f"DEBUG INIT: ROOT_DIR creado exitosamente.")
            except Exception as e:
                print(f"DEBUG INIT: Error creando ROOT_DIR: {e}")
                pass
        else:
            print(f"DEBUG INIT: ROOT_DIR ya existe.")

        self.scene = VectorScene()
        self.view = EditorView(self.scene, self)

        # --- NUEVO LAYOUT CENTRAL ---
        container = QWidget()
        layout_main = QVBoxLayout(container)
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.setSpacing(0)

        layout_main.addWidget(self.view)

        # Barra de Páginas
        self.page_controls = QFrame()
        self.page_controls.setFixedHeight(50)
        self.page_controls.setStyleSheet("background-color: #3c3f41; border-top: 1px solid #555;")
        layout_pages = QHBoxLayout(self.page_controls)
        layout_pages.setContentsMargins(10, 5, 10, 5)

        btn_prev_page = QPushButton("◀ Anterior")
        btn_next_page = QPushButton("Siguiente ▶")
        self.lbl_page_info = QLabel("Página: --")
        self.lbl_page_info.setStyleSheet("color: white; font-weight: bold;")

        btn_new_page_fast = QPushButton("➕ Nueva Pág")
        btn_new_page_fast.clicked.connect(self.nueva_pagina)

        layout_pages.addWidget(btn_prev_page)
        layout_pages.addStretch()
        layout_pages.addWidget(self.lbl_page_info)
        layout_pages.addStretch()
        layout_pages.addWidget(btn_next_page)
        layout_pages.addWidget(btn_new_page_fast)

        layout_main.addWidget(self.page_controls)
        self.setCentralWidget(container)

        self.setup_docks()
        self.setup_toolbar()  # Toolbar vacía primero
        self.setup_tools()  # Inicializar herramientas y acciones
        self.setup_hotkeys()

        self.refresh_tree()
        self.add_layer("Capa 1")

        self.herramienta_actual = Herramienta.LAPIZ
        self.herramienta_previa_mano = None
        self.set_herramienta(Herramienta.LAPIZ)

    def setup_tools(self):
        """Inicializa o Reinicializa las herramientas y sus conexiones"""
        # Limpiar referencias antiguas si existen
        if hasattr(self, 'tools'):
            for tool in self.tools.values():
                if hasattr(tool, 'deactivate'):
                    try:
                        tool.deactivate()
                    except:
                        pass

        self.tools = {
            Herramienta.LAPIZ: PenTool(self.view),
            Herramienta.BORRADOR: EraserTool(self.view),
            Herramienta.TEXTO: TextTool(self.view),
            Herramienta.SELECCION: SelectionTool(self.view),
            Herramienta.ZOOM: ZoomTool(self.view),
            Herramienta.MOVER_CANVAS: PanTool(self.view)
        }

        # Si la herramienta actual estaba seleccionada, reactivarla en el nuevo set
        if hasattr(self, 'herramienta_actual'):
            self.set_herramienta(self.herramienta_actual)

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
        # Delete key for selection
        if event.key() == Qt.Key.Key_Delete:
            if self.scene.selectedItems() and self.herramienta_actual == Herramienta.SELECCION:
                items_to_del = []
                for item in self.scene.selectedItems():
                    for c in self.capas:
                        if item in c.items and not c.bloqueada:
                            items_to_del.append((item, c))
                if items_to_del:
                    from undo_commands import CommandDelete
                    self.undo_stack.push(CommandDelete(self.scene, items_to_del, self))

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            if self.herramienta_previa_mano:
                self.set_herramienta(self.herramienta_previa_mano)
                self.herramienta_previa_mano = None
        super().keyReleaseEvent(event)

    def setup_toolbar(self):
        # Crear Toolbar UNA SOLA VEZ
        if hasattr(self, 'main_toolbar'):
            return

        self.main_toolbar = QToolBar("Herramientas")
        self.main_toolbar.setOrientation(Qt.Orientation.Vertical)
        self.main_toolbar.setIconSize(QSize(32, 32))
        self.main_toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.main_toolbar)

        self.action_group = {}

        def add_tool_action(name, icon_emoji, tool_enum):
            action = QAction(icon_emoji, self)
            action.setCheckable(True)
            action.setToolTip(name)
            action.triggered.connect(lambda: self.set_herramienta(tool_enum))
            self.main_toolbar.addAction(action)
            self.action_group[tool_enum] = action
            return action

        add_tool_action("Lápiz (B)", "✏️", Herramienta.LAPIZ).setChecked(True)
        add_tool_action("Borrador (E)", "🧽", Herramienta.BORRADOR)
        add_tool_action("Selección (S)", "🤚", Herramienta.SELECCION)
        add_tool_action("Texto (T)", "T", Herramienta.TEXTO)
        add_tool_action("Imagen (I)", "🖼️", Herramienta.IMAGEN)
        add_tool_action("Zoom (Z)", "🔍", Herramienta.ZOOM)
        add_tool_action("Mano (Espacio)", "📄", Herramienta.MOVER_CANVAS)

        self.main_toolbar.addSeparator()

        action_undo = self.undo_stack.createUndoAction(self, "Deshacer")
        action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        action_undo.setIconText("↩️")
        self.main_toolbar.addAction(action_undo)

        action_redo = self.undo_stack.createRedoAction(self, "Rehacer")
        action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        action_redo.setIconText("↪️")
        self.main_toolbar.addAction(action_redo)

        btn_add_img = QPushButton("Insertar Imagen")
        btn_add_img.clicked.connect(self.dialogo_imagen)
        self.main_toolbar.addWidget(btn_add_img)

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

        # Panel Selección
        panel_sel = QWidget()
        form_sel = QFormLayout()

        lbl_info = QLabel("Arrastra los puntos azules\npara transformar.")
        lbl_info.setStyleSheet("color: #aaa; font-style: italic;")

        form_sel.addRow(lbl_info)
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
        colores = ["#000000", "#FF0000", "#0000FF", "#008000", "#FFFF00", "#FFFFFF"]
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
        if self.herramienta_actual == Herramienta.BORRADOR:
            self.tools[Herramienta.BORRADOR].update_cursor()

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
            cmd = CommandAdd(self.scene, item, capa, self.main)
            self.undo_stack.push(cmd)
            self.set_herramienta(Herramienta.SELECCION)

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
        total = len(self.capas)
        for i, capa in enumerate(self.capas):
            base_z = (total - 1 - i) * 10000
            for j, item in enumerate(capa.items):
                item.setZValue(base_z + j)

    def refresh_tree(self):
        self.tree_files.clear()
        print(f"DEBUG REFRESH: Iniciando escaneo en ROOT_DIR: {ROOT_DIR}")
        try:
            if not os.path.exists(ROOT_DIR):
                print(f"DEBUG REFRESH ERROR: ROOT_DIR no existe en disco: {ROOT_DIR}")
                return

            materias = [d for d in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, d))]
            print(f"DEBUG REFRESH: Materias detectadas: {materias}")

            for mat in materias:
                item_mat = QTreeWidgetItem([mat])
                item_mat.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon)))
                path_mat = os.path.join(ROOT_DIR, mat)

                paginas = [d for d in os.listdir(path_mat) if os.path.isdir(os.path.join(path_mat, d))]
                # print(f"DEBUG REFRESH: Materia '{mat}' tiene subcarpetas: {paginas}")

                for pag in paginas:
                    full_path_pag = os.path.join(path_mat, pag)
                    json_check = os.path.join(full_path_pag, "data.json")
                    if os.path.exists(json_check):
                        # print(f"DEBUG REFRESH: Página VÁLIDA encontrada: {pag} (Path: {full_path_pag})")
                        item_pag = QTreeWidgetItem([pag])
                        item_pag.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)))
                        item_pag.setData(0, Qt.ItemDataRole.UserRole, full_path_pag)
                        item_mat.addChild(item_pag)

                self.tree_files.addTopLevelItem(item_mat)
        except Exception as e:
            print(f"DEBUG REFRESH EXCEPTION: {e}")
            traceback.print_exc()

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

        # Encontrar el padre (Materia)
        while item.parent():
            item = item.parent()

        materia_path = os.path.join(ROOT_DIR, item.text(0))
        fecha = datetime.now().strftime("%d-%m-%Y")

        nombre_base = fecha
        contador = 1

        while os.path.exists(os.path.join(materia_path, f"{nombre_base}_Pag{contador}")):
            contador += 1

        project_name = f"{nombre_base}_Pag{contador}"
        project_path = os.path.join(materia_path, project_name)

        try:
            os.makedirs(project_path)
            os.makedirs(os.path.join(project_path, "assets"))

            print(f"DEBUG NUEVA PAG: Creando proyecto en: {project_path}")

            with open(os.path.join(project_path, "data.json"), 'w') as f:
                json.dump({"capas": [], "meta": {"materia": item.text(0), "fecha": fecha, "pagina": str(contador)}}, f)

            self.refresh_tree()
            self.cargar_desde_archivo(project_path)
        except Exception as e:
            print(f"DEBUG NUEVA PAG ERROR: {e}")
            traceback.print_exc()

    def abrir_archivo(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        print(f"DEBUG ABRIR: Click en '{item.text(0)}'. Path recuperado: {path}")

        if path and os.path.exists(path):
            print(f"DEBUG ABRIR: Path existe. Cargando...")
            self.cargar_desde_archivo(path)
        else:
            print(f"DEBUG ABRIR ERROR: Path es None o no existe.")

    def guardar_archivo(self):
        try:
            from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem
            print(f"DEBUG GUARDAR: ================= INICIO GUARDADO =================")
            print(f"DEBUG GUARDAR: current_project_dir: {self.current_project_dir}")

            if not self.current_project_dir:
                print("DEBUG GUARDAR ERROR: No hay directorio de proyecto seleccionado.")
                QMessageBox.warning(self, "Error", "No hay un proyecto abierto para guardar.")
                return

            json_path = os.path.join(self.current_project_dir, "data.json")
            assets_dir = os.path.join(self.current_project_dir, "assets")

            print(f"DEBUG GUARDAR: JSON destino: {json_path}")

            # --- FIX CRITICO: Crear directorio si no existe ---
            if not os.path.exists(assets_dir):
                try:
                    os.makedirs(assets_dir, exist_ok=True)
                except Exception as e:
                    print(f"DEBUG GUARDAR ERROR: Fallo creando assets folder: {e}")
                    return

            data_to_save = {
                "capas": [],
                "meta": {
                    "materia": self.current_materia_name,
                    "fecha": self.current_fecha,
                    "pagina": self.current_page_name
                }
            }

            for c_idx, capa in enumerate(self.capas):
                layer_data = {
                    "nombre": capa.nombre,
                    "visible": capa.visible,
                    "items": []
                }

                for item in capa.items:
                    # FIX: Proteger acceso a items que podrían haber sido eliminados
                    try:
                        if item.scene() != self.scene:
                            continue

                        item_data = {
                            "pos_x": item.pos().x(),
                            "pos_y": item.pos().y(),
                            "rot": item.rotation(),
                            "scale": item.scale(),
                            "z": item.zValue()
                        }

                        # Guardar Transformación completa
                        trans = item.transform()
                        item_data["m11"] = trans.m11()
                        item_data["m12"] = trans.m12()
                        item_data["m21"] = trans.m21()
                        item_data["m22"] = trans.m22()

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
                            original_path = item.data(Qt.ItemDataRole.UserRole + 1)
                            if original_path:
                                filename = os.path.basename(original_path)
                                dest_path = os.path.join(assets_dir, filename)
                                # Copiar solo si no existe o es diferente
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
                    except RuntimeError:
                        # Objeto C++ ya eliminado
                        continue

                data_to_save["capas"].append(layer_data)

            with open(json_path, 'w') as f:
                json.dump(data_to_save, f)
            print("DEBUG GUARDAR: ================= FIN GUARDADO EXITOSO =================")
            self.statusBar().showMessage(f"Guardado exitoso.", 3000)

        except Exception as e:
            print(f"DEBUG GUARDAR EXCEPTION: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error Fatal", f"No se pudo guardar: {e}")

    def cargar_desde_archivo(self, project_path):
        from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem
        from PyQt6.QtGui import QTransform

        print(f"DEBUG CARGAR: ================= INICIO CARGA =================")
        print(f"DEBUG CARGAR: Path: {project_path}")

        # === FIX CRÍTICO: Desconectar todo antes de limpiar ===
        print("DEBUG CARGAR: Desactivando herramientas para evitar crash...")

        # 1. Quitar herramienta de la vista (para que no reciba eventos)
        if hasattr(self, 'view'):
            self.view.set_tool(None)

        # 2. Desactivar lógicamente las herramientas
        if hasattr(self, 'tools'):
            for tool in self.tools.values():
                if hasattr(tool, 'deactivate'):
                    try:
                        tool.deactivate()
                    except:
                        pass

        # 3. Limpiar selección explícitamente (evita disparar selectionChanged durante el clear)
        self.scene.clearSelection()

        print("DEBUG CARGAR: Limpiando escena...")
        # 4. Ahora sí es seguro limpiar
        self.scene.clear()

        # Reiniciar variables de estado
        self.undo_stack.clear()
        self.capas = []
        self.list_capas.clear()
        self.setup_tools()  # Recrear herramientas frescas

        self.current_project_dir = project_path
        self.setWindowTitle(f"Notebook - {os.path.basename(project_path)}")

        json_path = os.path.join(project_path, "data.json")
        assets_dir = os.path.join(project_path, "assets")

        try:
            if not os.path.exists(json_path):
                print(f"DEBUG CARGAR ERROR: No existe data.json en {json_path}")
                # Crear capa por defecto si está vacío
                self.add_layer("Capa 1")
                return

            print(f"DEBUG CARGAR: Leyendo JSON...")
            with open(json_path, 'r') as f:
                data = json.load(f)

            meta = data.get("meta", {})
            self.current_materia_name = meta.get("materia", "")
            self.current_fecha = meta.get("fecha", "")
            self.current_page_name = meta.get("pagina", "")

            print(f"DEBUG CARGAR: Meta recuperada - Mat: {self.current_materia_name}, Pag: {self.current_page_name}")

            self.scene.set_metadata(self.current_materia_name, self.current_fecha, self.current_page_name)
            self.lbl_page_info.setText(f"Página: {self.current_page_name}")

            capas_data = data.get("capas", [])
            print(f"DEBUG CARGAR: Capas encontradas en JSON: {len(capas_data)}")

            for layer_data in reversed(capas_data):
                l_name = layer_data["nombre"]
                self.add_layer(l_name)
                current_capa = self.capas[0]
                current_capa.visible = layer_data.get("visible", True)

                for item_data in layer_data.get("items", []):
                    new_item = None
                    type_str = item_data["type"]

                    if type_str == "path":
                        path = QPainterPath()
                        elems = item_data.get("path_elements", [])

                        if elems:
                            # Asegurar movimiento inicial correcto
                            if elems[0]["t"] == 0:  # MoveTo
                                path.moveTo(elems[0]["x"], elems[0]["y"])
                            else:
                                path.moveTo(elems[0]["x"], elems[0]["y"])  # Fallback

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

                        if item_data.get("has_pen", True):
                            pen = QPen(QColor(item_data["pen_color"]))
                            pen.setWidth(item_data["pen_width"])
                            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                            new_item.setPen(pen)
                        else:
                            new_item.setPen(QPen(Qt.PenStyle.NoPen))

                        if item_data.get("has_fill", False):
                            new_item.setBrush(QBrush(QColor(item_data["fill_color"])))

                    elif type_str == "text":
                        new_item = EditableTextItem(item_data["content"])
                        font = QFont(item_data["font_family"], item_data["font_size"])
                        new_item.setFont(font)
                        new_item.setDefaultTextColor(QColor(item_data["color"]))

                    elif type_str == "image":
                        filename = item_data.get("img_filename")
                        if filename:
                            img_path = os.path.join(assets_dir, filename)
                            if os.path.exists(img_path):
                                pixmap = QPixmap(img_path)
                                new_item = QGraphicsPixmapItem(pixmap)
                                new_item.setData(Qt.ItemDataRole.UserRole + 2, filename)
                            else:
                                print(f"DEBUG CARGAR ERROR: Imagen no encontrada en {img_path}")

                    if new_item:
                        new_item.setPos(item_data["pos_x"], item_data["pos_y"])
                        new_item.setRotation(item_data.get("rot", 0))

                        # Restaurar Transformacion Avanzada
                        if "m11" in item_data:
                            trans = QTransform(item_data["m11"], item_data["m12"],
                                               item_data["m21"], item_data["m22"],
                                               0, 0)
                            new_item.setTransform(trans)
                        else:
                            new_item.setScale(item_data.get("scale", 1))

                        z_val = item_data.get("z", 0)
                        new_item.setZValue(z_val)

                        self.view.set_item_props(new_item)
                        self.scene.addItem(new_item)
                        current_capa.items.append(new_item)
                        new_item.setVisible(current_capa.visible)

            self.actualizar_z_values()
            print("DEBUG CARGAR: ================= FIN CARGA EXITOSA =================")

            if not self.capas:
                self.add_layer("Capa 1")

        except Exception as e:
            print(f"DEBUG CARGAR EXCEPTION: {e}")
            traceback.print_exc()
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