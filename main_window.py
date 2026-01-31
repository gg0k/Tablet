import sys
import json
import os
import shutil
import traceback
from datetime import datetime

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QDockWidget,
                             QListWidget, QPushButton, QLabel, QSlider, QColorDialog, QFileDialog,
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QComboBox, QSpinBox,
                             QFontComboBox, QStackedWidget, QFormLayout, QInputDialog, QFrame,
                             QGraphicsItem)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QIcon, QAction, QKeySequence, QPixmap, QPainter, QPen, QColor, QBrush, QFont, QCursor, \
    QShortcut, QUndoStack, QPainterPath, QTransform

from config import Herramienta, ROOT_DIR
from data_models import CapaData
from custom_items import EditableTextItem
from canvas_widget import VectorScene, EditorView
from undo_commands import CommandAdd

from tools import PenTool, EraserTool, TextTool, ZoomTool, SelectionTool, PanTool


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Notebook Vectorial Modular v2.0 (Multi-Page)")
        self.resize(1300, 850)

        self.undo_stack = QUndoStack(self)
        self.settings = QSettings("MiEscuelaApp", "VectorNotebook")

        self.color_actual = QColor("#000000")
        self.grosor_lapiz = 3
        self.suavizado_nivel = 30
        self.grosor_borrador = 20
        self.font_texto = QFont("Arial", 12)

        self.load_settings()

        # --- GESTIÓN DE PÁGINAS ---
        self.capas = []
        self.pages_data = []  # Lista de listas de capas (memoria de todas las páginas)
        self.current_page_index = 0
        self.current_project_dir = None

        # DEBUG INIT
        if not os.path.exists(ROOT_DIR):
            try:
                os.makedirs(ROOT_DIR)
            except Exception as e:
                pass

        self.scene = VectorScene()
        self.view = EditorView(self.scene, self)

        # --- LAYOUT CENTRAL ---
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

        self.btn_prev_page = QPushButton("◀ Anterior")
        self.btn_prev_page.clicked.connect(self.prev_page)

        self.btn_next_page = QPushButton("Siguiente ▶")
        self.btn_next_page.clicked.connect(self.next_page)

        self.lbl_page_info = QLabel("Página: 1 / 1")
        self.lbl_page_info.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

        self.btn_new_page_fast = QPushButton("➕ Nueva Pág")
        self.btn_new_page_fast.clicked.connect(self.add_new_page_internal)
        self.btn_new_page_fast.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

        layout_pages.addWidget(self.btn_prev_page)
        layout_pages.addStretch()
        layout_pages.addWidget(self.lbl_page_info)
        layout_pages.addStretch()
        layout_pages.addWidget(self.btn_next_page)
        layout_pages.addWidget(self.btn_new_page_fast)

        layout_main.addWidget(self.page_controls)
        self.setCentralWidget(container)

        self.setup_docks()
        self.setup_toolbar()
        self.setup_tools()
        self.setup_hotkeys()

        self.refresh_tree()

        # Iniciar con una página en blanco por defecto en memoria
        self.init_empty_state()

        self.herramienta_actual = Herramienta.LAPIZ
        self.herramienta_previa_mano = None
        self.set_herramienta(Herramienta.LAPIZ)

        self.update_page_ui()

    def init_empty_state(self):
        """Reinicia el estado a una sesión vacía sin archivo."""
        self.pages_data = []
        self.current_page_index = 0
        self.current_project_dir = None
        self.scene.clear()
        self.capas = []
        self.list_capas.clear()
        self.add_layer("Capa 1")
        self.setWindowTitle("Notebook - Sin Guardar")
        # Guardar el estado inicial de la pagina 1
        self.save_current_page_to_memory()

    def setup_tools(self):
        """Inicializa las herramientas."""
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

        # Boton "Hoy" ahora crea o abre la clase del día
        btn_new_class = QPushButton("📄 Hoy")
        btn_new_class.clicked.connect(self.crear_clase_hoy)

        h_files.addWidget(btn_refresh)
        h_files.addWidget(btn_new_subject)
        h_files.addWidget(btn_new_class)
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
        colores = ["#000000", "#FF0000", "#0000FF", "#008000", "#CC25FA", "#FFFFFF"]
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
            cmd = CommandAdd(self.scene, item, capa, self)
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
        try:
            if not os.path.exists(ROOT_DIR):
                return

            materias = [d for d in os.listdir(ROOT_DIR) if os.path.isdir(os.path.join(ROOT_DIR, d))]
            for mat in materias:
                item_mat = QTreeWidgetItem([mat])
                item_mat.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon)))
                path_mat = os.path.join(ROOT_DIR, mat)

                clases = [d for d in os.listdir(path_mat) if os.path.isdir(os.path.join(path_mat, d))]
                for clase in clases:
                    full_path_clase = os.path.join(path_mat, clase)
                    json_check = os.path.join(full_path_clase, "data.json")
                    if os.path.exists(json_check):
                        item_clase = QTreeWidgetItem([clase])
                        item_clase.setIcon(0, QIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon)))
                        item_clase.setData(0, Qt.ItemDataRole.UserRole, full_path_clase)
                        item_mat.addChild(item_clase)

                self.tree_files.addTopLevelItem(item_mat)
        except Exception as e:
            traceback.print_exc()

    def nueva_materia(self):
        nombre, ok = QInputDialog.getText(self, "Nueva Materia", "Nombre:")
        if ok and nombre:
            path = os.path.join(ROOT_DIR, nombre)
            os.makedirs(path, exist_ok=True)
            self.refresh_tree()

    # --- NUEVAS FUNCIONES DE PAGINACIÓN Y CLASE ---

    def crear_clase_hoy(self):
        """Crea una carpeta de clase para HOY dentro de la materia seleccionada."""
        item = self.tree_files.currentItem()
        if not item:
            QMessageBox.warning(self, "Error", "Selecciona una materia primero")
            return

        # Asegurarse que es una materia (item de nivel superior o padre)
        while item.parent():
            item = item.parent()

        materia_path = os.path.join(ROOT_DIR, item.text(0))
        fecha = datetime.now().strftime("%d-%m-%Y")

        project_path = os.path.join(materia_path, fecha)

        # Si ya existe, abrimos, si no, creamos
        if not os.path.exists(project_path):
            try:
                os.makedirs(project_path)
                os.makedirs(os.path.join(project_path, "assets"))

                # Crear estructura inicial multipágina
                initial_data = {
                    "pages": [],  # Se llenará al guardar la primera vez o por defecto
                    "version": "2.0"
                }

                with open(os.path.join(project_path, "data.json"), 'w') as f:
                    json.dump(initial_data, f)

                self.refresh_tree()
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"No se pudo crear la clase: {e}")
                return

        # Cargar el proyecto (nuevo o existente)
        self.cargar_desde_archivo(project_path)

    def add_new_page_internal(self):
        """Agrega una nueva página blanca dentro del archivo actual."""
        if not self.current_project_dir:
            return

        # 1. Guardar la página actual en memoria
        self.save_current_page_to_memory()

        # 2. Crear una nueva página (lista de capas vacía)
        new_page_layers = [{"nombre": "Capa 1", "visible": True, "items": []}]
        self.pages_data.append(new_page_layers)

        # 3. Moverse a la nueva página (que es la última)
        self.load_page_from_memory(len(self.pages_data) - 1)

        # Opcional: Auto-guardar para evitar perdida de datos si crashea
        self.guardar_archivo()

    def prev_page(self):
        if self.current_page_index > 0:
            self.save_current_page_to_memory()
            self.load_page_from_memory(self.current_page_index - 1)

    def next_page(self):
        if self.current_page_index < len(self.pages_data) - 1:
            self.save_current_page_to_memory()
            self.load_page_from_memory(self.current_page_index + 1)

    def save_current_page_to_memory(self):
        """Serializa la escena actual y la guarda en self.pages_data[self.current_page_index]."""
        page_layers = self.serialize_current_scene()

        # Asegurar que pages_data sea lo suficientemente grande
        while len(self.pages_data) <= self.current_page_index:
            self.pages_data.append([])

        self.pages_data[self.current_page_index] = page_layers

    def serialize_current_scene(self):
        """Convierte las capas y items de la escena actual a una lista de diccionarios."""
        from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem

        serialized_layers = []
        assets_dir = os.path.join(self.current_project_dir, "assets") if self.current_project_dir else ""
        if assets_dir and not os.path.exists(assets_dir):
            os.makedirs(assets_dir, exist_ok=True)

        for capa in self.capas:
            layer_data = {
                "nombre": capa.nombre,
                "visible": capa.visible,
                "items": []
            }

            for item in capa.items:
                try:
                    if item.scene() != self.scene: continue

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

    def load_page_from_memory(self, page_index):
        """Carga una página específica desde self.pages_data a la escena."""
        if page_index < 0 or page_index >= len(self.pages_data):
            return

        # 1. Limpieza segura
        if hasattr(self, 'view'):
            self.view.set_tool(None)

        self.scene.clearSelection()
        self.scene.clear()
        self.undo_stack.clear()
        self.capas = []
        self.list_capas.clear()

        # 2. Cargar datos
        self.current_page_index = page_index
        layers_data = self.pages_data[page_index]
        self.render_layers_to_scene(layers_data)

        # 3. Restaurar UI y Herramientas
        self.update_page_ui()
        if hasattr(self, 'herramienta_actual'):
            self.set_herramienta(self.herramienta_actual)

    def render_layers_to_scene(self, layers_data):
        """Reconstruye los objetos gráficos en la escena a partir de una lista de datos de capas."""
        from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem

        assets_dir = os.path.join(self.current_project_dir, "assets") if self.current_project_dir else ""

        # Si no hay capas, crear una por defecto
        if not layers_data:
            self.add_layer("Capa 1")
            return

        for layer_data in reversed(layers_data):
            self.add_layer(layer_data["nombre"])
            current_capa = self.capas[0]
            current_capa.visible = layer_data.get("visible", True)

            for item_data in layer_data.get("items", []):
                new_item = None
                type_str = item_data["type"]

                # ... Reconstrucción de items (Similar a antes, pero extraído) ...
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
                    self.scene.addItem(new_item)
                    current_capa.items.append(new_item)
                    new_item.setVisible(current_capa.visible)

        self.actualizar_z_values()

    def update_page_ui(self):
        total = len(self.pages_data)
        current = self.current_page_index + 1
        self.lbl_page_info.setText(f"Página: {current} / {max(1, total)}")
        self.btn_prev_page.setEnabled(self.current_page_index > 0)
        self.btn_next_page.setEnabled(self.current_page_index < len(self.pages_data) - 1)

    def abrir_archivo(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.cargar_desde_archivo(path)

    def guardar_archivo(self):
        try:
            if not self.current_project_dir:
                QMessageBox.warning(self, "Error", "No hay un proyecto abierto para guardar.")
                return

            json_path = os.path.join(self.current_project_dir, "data.json")

            # 1. Guardar la página actual en memoria antes de escribir a disco
            self.save_current_page_to_memory()

            # 2. Estructura de guardado V2
            full_data = {
                "version": "2.0",
                "pages": self.pages_data
            }

            with open(json_path, 'w') as f:
                json.dump(full_data, f)

            self.statusBar().showMessage(f"Guardado exitoso (Multipage).", 3000)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error Fatal", f"No se pudo guardar: {e}")

    def cargar_desde_archivo(self, project_path):
        """Carga un proyecto. Soporta formato v1 (solo capas) y v2 (paginas)."""
        # Desactivar herramientas por seguridad durante carga
        if hasattr(self, 'view'): self.view.set_tool(None)

        self.current_project_dir = project_path
        self.setWindowTitle(f"Notebook - {os.path.basename(project_path)}")
        json_path = os.path.join(project_path, "data.json")

        try:
            if not os.path.exists(json_path):
                # Archivo nuevo / vacio
                self.init_empty_state()
                self.current_project_dir = project_path  # Restaurar path
                self.pages_data = [[{"nombre": "Capa 1", "visible": True, "items": []}]]
                self.load_page_from_memory(0)
                return

            with open(json_path, 'r') as f:
                data = json.load(f)

            # Detectar formato
            if "pages" in data:
                # Formato V2 Multi-page
                self.pages_data = data["pages"]
                if not self.pages_data: self.pages_data = [[{"nombre": "Capa 1", "visible": True, "items": []}]]
            else:
                # Formato V1 Legacy (Solo capas en root) -> Convertir a página 1
                legacy_layers = data.get("capas", [])
                self.pages_data = [legacy_layers]

            # Cargar la primera página
            self.load_page_from_memory(0)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error de carga: {e}")
            self.init_empty_state()

    def borrar_archivo(self):
        if not self.current_project_dir:
            return
        if QMessageBox.question(self, "Borrar",
                                "¿Seguro que quieres borrar toda esta clase?") == QMessageBox.StandardButton.Yes:
            shutil.rmtree(self.current_project_dir)
            self.init_empty_state()
            self.refresh_tree()