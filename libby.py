import os
import sys
import json
import subprocess
import threading
from shutil import copy2, move
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QMessageBox, QFileDialog, QInputDialog, QHBoxLayout,
    QMenu, QDialog, QLabel, QTextEdit, QCheckBox, QComboBox,
    QProgressBar, QSplashScreen, QFrame, QSizePolicy, QSystemTrayIcon
)
from PySide6.QtGui import QIcon, QAction, QPixmap, QColor, QCursor, QImage
from PySide6.QtCore import Qt, QThread, Signal

# Caminho da pasta de assets (relativo ao script)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Caminho da pasta de config no AppData
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MeuHub")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")
CACHE_DIR = os.path.join(APPDATA_DIR, "icon_cache")

class IconLoader(QThread):
    """Thread para carregar ícones de forma assíncrona"""
    icon_loaded = Signal(str, QIcon)
    
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        
    def run(self):
        for path in self.file_paths:
            try:
                icon = QIcon(path)
                if not icon.isNull():
                    self.icon_loaded.emit(path, icon)
                else:
                    # Ícone padrão se não conseguir carregar
                    default_icon = QIcon.fromTheme("application-x-executable")
                    self.icon_loaded.emit(path, default_icon)
            except Exception:
                continue

# --- dentro da classe EditProgramDialog ---
class EditProgramDialog(QDialog):
    """Dialog para editar informações do programa"""

    AVAILABLE_TAGS = ["trabalho", "pessoal", "urgente", "teste", "producao"]

    def __init__(self, program_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Programa")
        self.setModal(True)
        self.resize(420, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Nome de exibição
        layout.addWidget(QLabel("Nome de Exibição:"))
        self.name_edit = QLineEdit(program_info.get('display_name', ''))
        layout.addWidget(self.name_edit)

        # Descrição
        layout.addWidget(QLabel("Descrição:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(program_info.get('description', ''))
        self.desc_edit.setMaximumHeight(80)
        layout.addWidget(self.desc_edit)

        # Tags
        layout.addWidget(QLabel("Tags:"))
        tags_layout = QHBoxLayout()
        self.tag_checks = {}
        current_tags = program_info.get('tags', [])
        for tag in self.AVAILABLE_TAGS:
            cb = QCheckBox(tag.capitalize())
            cb.setChecked(tag in current_tags)
            self.tag_checks[tag] = cb
            tags_layout.addWidget(cb)
        layout.addLayout(tags_layout)

        # Favorito
        self.favorite_check = QCheckBox("Marcar como favorito")
        self.favorite_check.setChecked(program_info.get('favorite', False))
        layout.addWidget(self.favorite_check)

        # Ícone personalizado
        layout.addWidget(QLabel("Ícone/Logo:"))
        self.icon_path_edit = QLineEdit(program_info.get('icon', ''))
        self.icon_btn = QPushButton("Escolher")
        self.icon_btn.setFixedWidth(80)
        self.icon_btn.clicked.connect(self.escolher_icone)
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.icon_path_edit)
        icon_layout.addWidget(self.icon_btn)
        layout.addLayout(icon_layout)

        layout.addStretch()

        # Botões
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Salvar")
        self.cancel_btn = QPushButton("Cancelar")

        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def escolher_icone(self):
        arquivo, _ = QFileDialog.getOpenFileName(
            self, "Escolher ícone", "", "Imagens (*.png *.ico *.jpg);;Todos (*.*)"
        )
        if arquivo:
            self.icon_path_edit.setText(arquivo)

    def get_program_info(self):
        tags = [tag for tag, cb in self.tag_checks.items() if cb.isChecked()]
        return {
            'display_name': self.name_edit.text(),
            'description': self.desc_edit.toPlainText(),
            'favorite': self.favorite_check.isChecked(),
            'icon': self.icon_path_edit.text(),
            'tags': tags
        }


class ListItem(QFrame):
    """Item de lista para programa"""
    clicked = Signal()
    rightClicked = Signal()

    # Cores das tags
    TAG_COLORS = {
        "trabalho": "#3498db",
        "pessoal": "#9b59b6",
        "urgente": "#e74c3c",
        "teste": "#f39c12",
        "producao": "#27ae60"
    }

    def __init__(self, nome, descricao="", tipo="", last_run="", tags=None, parent=None):
        super().__init__(parent)
        self.nome = nome
        self.is_favorite = False
        self.is_dark_theme = False
        self.is_running = False
        self.tags = tags or []
        self.caminho = ""
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Indicador de execucao
        self.running_indicator = QLabel()
        self.running_indicator.setFixedSize(8, 8)
        self.running_indicator.setVisible(False)
        layout.addWidget(self.running_indicator)

        # Icone
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(28, 28)
        layout.addWidget(self.icon_label)

        # Nome
        self.name_label = QLabel(nome)
        self.name_label.setMinimumWidth(120)
        layout.addWidget(self.name_label)

        # Tags container
        self.tags_container = QHBoxLayout()
        self.tags_container.setSpacing(4)
        self.tags_container.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.tags_container)

        # Descricao
        self.desc_label = QLabel(descricao)
        self.desc_label.setMinimumWidth(80)
        layout.addWidget(self.desc_label, 1)

        # Tipo (extensao)
        self.type_label = QLabel(tipo)
        self.type_label.setFixedWidth(40)
        self.type_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.type_label)

        # Ultima execucao
        self.last_run_label = QLabel(last_run)
        self.last_run_label.setFixedWidth(50)
        self.last_run_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.last_run_label)

        # Indicador de favorito
        self.fav_label = QLabel()
        self.fav_label.setFixedWidth(16)
        layout.addWidget(self.fav_label)

        self._create_tag_labels()
        self.update_style()

    def _create_tag_labels(self):
        # Limpa tags existentes
        while self.tags_container.count():
            item = self.tags_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Cria novas tags
        for tag in self.tags[:2]:  # Max 2 tags visiveis
            tag_label = QLabel(tag)
            tag_label.setFixedHeight(16)
            color = self.TAG_COLORS.get(tag.lower(), "#888")
            tag_label.setStyleSheet(f"font-size: 9px; color: white; background: {color}; border-radius: 3px; padding: 1px 4px;")
            self.tags_container.addWidget(tag_label)

    def set_tags(self, tags):
        self.tags = tags or []
        self._create_tag_labels()

    def set_running(self, running):
        self.is_running = running
        self.running_indicator.setVisible(running)
        self.update_style()

    def set_icon(self, icon):
        if not icon.isNull():
            pixmap = icon.pixmap(28, 28)
            self.icon_label.setPixmap(pixmap)

    def set_favorite(self, is_favorite):
        self.is_favorite = is_favorite
        self.fav_label.setText("*" if is_favorite else "")
        self.update_style()

    def set_theme(self, is_dark):
        self.is_dark_theme = is_dark
        self.update_style()

    def update_style(self):
        if self.is_dark_theme:
            bg = "#16213e"
            bg_hover = "#1a2744"
            border_color = "#0f3460"
            text_color = "#eaeaea"
            secondary = "#888"
        else:
            bg = "#ffffff"
            bg_hover = "#f8fafc"
            border_color = "#e8e8e8"
            text_color = "#2d3436"
            secondary = "#888"

        accent = "#e74c3c" if self.is_favorite else "#0078d4"
        running_color = "#27ae60" if self.is_running else "transparent"

        self.setStyleSheet(f"""
            ListItem {{
                background-color: {bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            ListItem:hover {{
                background-color: {bg_hover};
                border-left: 3px solid {accent};
            }}
        """)
        self.running_indicator.setStyleSheet(f"background: {running_color}; border-radius: 4px;")
        self.name_label.setStyleSheet(f"font-weight: 500; font-size: 12px; color: {text_color};")
        self.desc_label.setStyleSheet(f"font-size: 11px; color: {secondary};")
        self.type_label.setStyleSheet(f"font-size: 9px; color: {secondary}; background: {border_color}; border-radius: 3px; padding: 2px 4px;")
        self.last_run_label.setStyleSheet(f"font-size: 10px; color: {secondary};")
        self.fav_label.setStyleSheet(f"color: {accent}; font-weight: bold;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.RightButton:
            self.rightClicked.emit()
        super().mousePressEvent(event)


class CollapsibleCategory(QWidget):
    """Categoria colapsavel"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        self.is_dark_theme = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 4)
        main_layout.setSpacing(0)

        # Header clicavel
        self.header = QFrame()
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setFixedHeight(32)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 0, 8, 0)

        self.arrow_label = QLabel(">")
        self.arrow_label.setFixedWidth(16)
        header_layout.addWidget(self.arrow_label)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: 600; font-size: 12px;")
        header_layout.addWidget(self.title_label, 1)

        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("color: #888; font-size: 11px;")
        header_layout.addWidget(self.count_label)

        main_layout.addWidget(self.header)

        # Container para itens
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 4, 0, 4)
        self.content_layout.setSpacing(4)
        main_layout.addWidget(self.content)

        self.header.mousePressEvent = self.toggle_collapse
        self.update_style()

    def toggle_collapse(self, event=None):
        self.is_collapsed = not self.is_collapsed
        self.content.setVisible(not self.is_collapsed)
        self.arrow_label.setText(">" if self.is_collapsed else "v")

    def add_item(self, item):
        self.content_layout.addWidget(item)
        count = self.content_layout.count()
        self.count_label.setText(str(count))

    def set_theme(self, is_dark):
        self.is_dark_theme = is_dark
        self.update_style()

    def update_style(self):
        if self.is_dark_theme:
            bg = "#1a2744"
            text = "#eaeaea"
        else:
            bg = "#f0f4f8"
            text = "#2d3436"

        self.header.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border-radius: 4px;
            }}
        """)
        self.title_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {text};")
        self.arrow_label.setStyleSheet(f"color: #0078d4; font-weight: bold;")

class HubApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Libby v2.0")
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "logolibby.png")))
        self.resize(1000, 700)

        # Configurações
        self.hub_dir = None
        self.botoes = []
        self.program_info = {}  # Informações adicionais dos programas
        self.current_theme = "light"
        self.icon_cache = {}

        # Carrega configuração
        self.carregar_config()

        self.setup_ui()
        self.apply_theme()
        self.setup_tray_icon()

        # Cria diretório de cache se não existir
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Se já tinha uma pasta salva, carrega
        if self.hub_dir:
            self.carregar_programas()
        else:
            self.toggle_botoes(False)

    def setup_tray_icon(self):
        """Configura o ícone da bandeja do sistema"""
        img = QImage(os.path.join(ASSETS_DIR, "android-chrome-192x192.png"))

        # Recorta margens transparentes para o ícone ocupar mais espaço na bandeja
        w, h = img.width(), img.height()
        left, top, right, bottom = w, h, 0, 0
        for y in range(h):
            for x in range(w):
                if (img.pixel(x, y) >> 24) & 0xFF > 0:
                    left = min(left, x)
                    top = min(top, y)
                    right = max(right, x)
                    bottom = max(bottom, y)

        if right > left and bottom > top:
            cropped = img.copy(left, top, right - left + 1, bottom - top + 1)
            tray_pixmap = QPixmap.fromImage(cropped)
        else:
            tray_pixmap = QPixmap(os.path.join(ASSETS_DIR, "android-chrome-192x192.png"))

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(tray_pixmap))
        self.tray_icon.setToolTip("Libby - Gerenciador de Programas")

        # Menu da bandeja
        tray_menu = QMenu()

        show_action = QAction("Mostrar", self)
        show_action.triggered.connect(self.show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        exit_action = QAction("Sair", self)
        exit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def show_from_tray(self):
        """Restaura a janela da bandeja"""
        self.showNormal()
        self.activateWindow()

    def quit_app(self):
        """Fecha completamente o aplicativo"""
        self.tray_icon.hide()
        QApplication.quit()

    def tray_icon_activated(self, reason):
        """Ação ao clicar no ícone da bandeja"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()

    def closeEvent(self, event):
        """Minimiza para bandeja ao invés de fechar"""
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Libby",
            "O programa foi minimizado para a bandeja.",
            QSystemTrayIcon.Information,
            2000
        )

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header compacto
        header = QFrame()
        header.setFixedHeight(50)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        # Logo + Titulo
        header_logo = QLabel()
        header_logo_pixmap = QPixmap(os.path.join(ASSETS_DIR, "favicon-32x32.png"))
        if not header_logo_pixmap.isNull():
            header_logo.setPixmap(header_logo_pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_logo.setFixedSize(28, 28)
        header_layout.addWidget(header_logo)

        title = QLabel("Libby")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0078d4;")
        header_layout.addWidget(title)

        # Busca
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar...")
        self.search_bar.setFixedWidth(250)
        self.search_bar.textChanged.connect(self.filtrar_programas)
        header_layout.addWidget(self.search_bar)

        # Filtro
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todos", "Favoritos", "Recentes"])
        self.filter_combo.setFixedWidth(100)
        self.filter_combo.currentTextChanged.connect(self.filtrar_programas)
        header_layout.addWidget(self.filter_combo)

        header_layout.addStretch()

        # Botoes com icones unicode
        self.btn_importar = QPushButton("\u2b07")  # seta para baixo
        self.btn_importar.setToolTip("Importar pasta RPA")
        self.btn_importar.setFixedWidth(36)
        self.btn_importar.clicked.connect(self.importar_pasta_rpa)
        header_layout.addWidget(self.btn_importar)

        self.btn_escolher_pasta = QPushButton("\U0001F4C1")  # pasta
        self.btn_escolher_pasta.setToolTip("Escolher pasta Hub")
        self.btn_escolher_pasta.setFixedWidth(36)
        self.btn_escolher_pasta.clicked.connect(self.escolher_pasta)
        header_layout.addWidget(self.btn_escolher_pasta)

        self.btn_nova_categoria = QPushButton("\u2795")  # mais
        self.btn_nova_categoria.setToolTip("Nova categoria")
        self.btn_nova_categoria.setFixedWidth(36)
        self.btn_nova_categoria.clicked.connect(self.nova_categoria)
        header_layout.addWidget(self.btn_nova_categoria)

        self.btn_adicionar_programa = QPushButton("\U0001F4E5")  # caixa entrada
        self.btn_adicionar_programa.setToolTip("Adicionar programa")
        self.btn_adicionar_programa.setFixedWidth(36)
        self.btn_adicionar_programa.clicked.connect(self.adicionar_programa)
        header_layout.addWidget(self.btn_adicionar_programa)

        self.btn_atualizar = QPushButton("\u21BB")  # refresh
        self.btn_atualizar.setToolTip("Atualizar lista")
        self.btn_atualizar.setFixedWidth(36)
        self.btn_atualizar.clicked.connect(self.carregar_programas)
        header_layout.addWidget(self.btn_atualizar)

        self.btn_theme = QPushButton("\u263D")  # lua
        self.btn_theme.setToolTip("Alternar tema")
        self.btn_theme.setFixedWidth(36)
        self.btn_theme.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.btn_theme)

        self.layout.addWidget(header)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        # Area de conteudo
        content_area = QFrame()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(12, 8, 12, 4)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area)

        self.layout.addWidget(content_area, 1)

        # Status bar
        self.status_label = QLabel("Pronto")
        self.status_label.setFixedHeight(24)
        self.status_label.setStyleSheet("padding-left: 16px; color: #666; font-size: 11px;")
        self.layout.addWidget(self.status_label)

    def apply_theme(self):
        """Aplica tema escuro ou claro"""
        if self.current_theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #1a1a2e;
                    color: #eaeaea;
                    font-family: 'Segoe UI', Arial;
                }
                QFrame {
                    background-color: #1a1a2e;
                }
                QLineEdit {
                    background-color: #16213e;
                    border: 1px solid #0f3460;
                    padding: 8px 12px;
                    border-radius: 6px;
                    color: #eaeaea;
                }
                QLineEdit:focus {
                    border: 1px solid #0078d4;
                }
                QPushButton {
                    background-color: #0f3460;
                    color: white;
                    border: none;
                    padding: 8px 14px;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QGroupBox {
                    font-weight: 600;
                    font-size: 13px;
                    border: none;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding-top: 16px;
                    background-color: #16213e;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                    color: #0078d4;
                }
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QComboBox {
                    background-color: #16213e;
                    border: 1px solid #0f3460;
                    padding: 6px 10px;
                    border-radius: 6px;
                    color: #eaeaea;
                }
                QComboBox:hover {
                    border: 1px solid #0078d4;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 8px;
                }
                QProgressBar {
                    background-color: #16213e;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                }
            """)
            self.btn_theme.setToolTip("Tema Claro")
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #f5f7fa;
                    color: #2d3436;
                    font-family: 'Segoe UI', Arial;
                }
                QFrame {
                    background-color: #ffffff;
                }
                QLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #dfe6e9;
                    padding: 8px 12px;
                    border-radius: 6px;
                }
                QLineEdit:focus {
                    border: 1px solid #0078d4;
                }
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 14px;
                    border-radius: 6px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QGroupBox {
                    font-weight: 600;
                    font-size: 13px;
                    border: none;
                    border-radius: 8px;
                    margin-top: 8px;
                    padding-top: 16px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 8px;
                    color: #0078d4;
                }
                QScrollArea {
                    border: none;
                    background-color: transparent;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #dfe6e9;
                    padding: 6px 10px;
                    border-radius: 6px;
                }
                QComboBox:hover {
                    border: 1px solid #0078d4;
                }
                QComboBox::drop-down {
                    border: none;
                    padding-right: 8px;
                }
                QProgressBar {
                    background-color: #dfe6e9;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                }
            """)
            self.btn_theme.setToolTip("Tema Escuro")

    def toggle_theme(self):
        """Alterna entre tema claro e escuro"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()
        # Atualiza tema dos itens e categorias
        is_dark = self.current_theme == "dark"
        for _, item, _ in self.botoes:
            item.set_theme(is_dark)
        for cat in getattr(self, 'categories', []):
            cat.set_theme(is_dark)
        self.salvar_config()

    def toggle_botoes(self, ativo: bool):
        """Ativa/desativa botões dependendo se há pasta Hub selecionada"""
        self.btn_nova_categoria.setEnabled(ativo)
        self.btn_adicionar_programa.setEnabled(ativo)
        self.btn_atualizar.setEnabled(ativo)
        self.search_bar.setEnabled(ativo)
        self.filter_combo.setEnabled(ativo)

    def mostrar_informacoes(self, caminho):
        """Mostra informações do programa em um popup"""
        key = caminho.replace(self.hub_dir, "").strip(os.sep)
        program_data = self.program_info.get(key, {})

        nome = program_data.get('display_name', os.path.basename(caminho))
        descricao = program_data.get('description', "Sem descrição")
        contador = program_data.get('launch_count', 0)
        ultima = program_data.get('last_opened', "Nunca")

        QMessageBox.information(
            self, "Informações",
            f"Nome: {nome}\n\n"
            f"Descrição: {descricao}\n\n"
            f"Executado: {contador} vez(es)\n"
            f"Última vez: {ultima}"
        )

    def salvar_config(self):
        """Salva configurações no config.json"""
        try:
            os.makedirs(APPDATA_DIR, exist_ok=True)
            config = {
                "hub_dir": self.hub_dir,
                "theme": self.current_theme,
                "program_info": self.program_info
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Não foi possível salvar config:\n{e}")

    def carregar_config(self):
        """Carrega configurações do config.json"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.hub_dir = data.get("hub_dir", None)
                    self.current_theme = data.get("theme", "light")
                    self.program_info = data.get("program_info", {})
            except Exception:
                pass

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, "Escolher pasta Hub")
        if pasta:
            self.hub_dir = pasta
            self.salvar_config()
            self.toggle_botoes(True)
            self.carregar_programas()

    def importar_pasta_rpa(self):
        """Importa programas de uma pasta externa (detecta .bat, .py, etc)"""
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta para importar")
        if not pasta:
            return

        if not self.hub_dir:
            QMessageBox.warning(self, "Aviso", "Primeiro escolha uma pasta Hub!")
            return

        # Pede nome da categoria
        nome_sugerido = os.path.basename(pasta)
        categoria, ok = QInputDialog.getText(
            self, "Nome da Categoria",
            "Nome para a categoria importada:",
            text=nome_sugerido
        )
        if not ok or not categoria:
            return

        # Cria categoria
        categoria_path = os.path.join(self.hub_dir, categoria)
        os.makedirs(categoria_path, exist_ok=True)

        # Procura programas na pasta
        importados = 0
        for item in os.listdir(pasta):
            item_path = os.path.join(pasta, item)

            # Se for subpasta com .py ou .bat, cria um .bat apontando para ela
            if os.path.isdir(item_path):
                # Procura arquivo principal
                main_file = None
                for ext in ['.py', '.bat', '.cmd', '.exe']:
                    candidates = [f for f in os.listdir(item_path) if f.lower().endswith(ext)]
                    if candidates:
                        # Prioriza arquivos com nome parecido com a pasta
                        for c in candidates:
                            if item.lower().replace('-', '_').replace(' ', '_') in c.lower().replace('-', '_'):
                                main_file = c
                                break
                        if not main_file:
                            main_file = candidates[0]
                        break

                if main_file:
                    # Cria .bat que aponta para o programa
                    bat_name = f"{item}.bat"
                    bat_path = os.path.join(categoria_path, bat_name)
                    main_path = os.path.join(item_path, main_file)

                    if main_file.endswith('.py'):
                        content = f'@echo off\ncd /d "{item_path}"\nstart "" pythonw {main_file}'
                    else:
                        content = f'@echo off\ncd /d "{item_path}"\nstart "" "{main_file}"'

                    with open(bat_path, 'w') as f:
                        f.write(content)

                    # Detecta logo na pasta
                    logo_path = self._find_logo_in_folder(item_path)
                    if logo_path:
                        key = bat_path.replace(self.hub_dir, "").strip(os.sep)
                        self.program_info[key] = self.program_info.get(key, {})
                        self.program_info[key]['icon'] = logo_path

                    importados += 1

            # Se for arquivo executavel direto
            elif item.lower().endswith(('.bat', '.cmd', '.py', '.exe', '.lnk')):
                destino = os.path.join(categoria_path, item)
                if not os.path.exists(destino):
                    copy2(item_path, destino)
                    importados += 1

        self.salvar_config()
        self.carregar_programas()
        self.status_label.setText(f"Importados {importados} programas de '{nome_sugerido}'")

    def _find_logo_in_folder(self, folder):
        """Procura arquivo de logo em uma pasta"""
        logo_names = ['logo', 'icon', 'icone', 'favicon', 'app']
        logo_exts = ['.png', '.ico', '.jpg', '.jpeg', '.bmp']

        for name in logo_names:
            for ext in logo_exts:
                path = os.path.join(folder, name + ext)
                if os.path.exists(path):
                    return path
                # Tenta com maiusculas
                path = os.path.join(folder, name.capitalize() + ext)
                if os.path.exists(path):
                    return path

        # Procura qualquer .ico na pasta
        for f in os.listdir(folder):
            if f.lower().endswith('.ico'):
                return os.path.join(folder, f)

        return None

    def nova_categoria(self):
        if not self.hub_dir:
            return
        categoria, ok = QInputDialog.getText(self, "Nova Categoria", "Nome da categoria:")
        if ok and categoria:
            destino = os.path.join(self.hub_dir, categoria)
            os.makedirs(destino, exist_ok=True)
            self.carregar_programas()

    def adicionar_programa(self):
        if not self.hub_dir:
            return

        arquivo, _ = QFileDialog.getOpenFileName(
            self, "Escolher programa", "", "Programas (*.exe *.lnk *.bat *.cmd *.py);;Todos os arquivos (*.*)"
        )
        if arquivo:
            categorias = [d for d in os.listdir(self.hub_dir)
                          if os.path.isdir(os.path.join(self.hub_dir, d))]
            if not categorias:
                QMessageBox.warning(self, "Aviso", "Nenhuma categoria criada ainda!")
                return
            categoria, ok = QInputDialog.getItem(
                self, "Escolher Categoria", "Selecione a categoria:",
                categorias, 0, False
            )
            if ok and categoria:
                destino = os.path.join(self.hub_dir, categoria, os.path.basename(arquivo))
                try:
                    copy2(arquivo, destino)
                    self.carregar_programas()
                    self.status_label.setText(f"Programa adicionado: {os.path.basename(arquivo)}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível adicionar:\n{e}")

    def abrir_programa(self, caminho):
        """Abre programa e atualiza contador"""
        try:
            subprocess.Popen(caminho, shell=True)

            # Atualiza contador de execuções
            key = caminho.replace(self.hub_dir, "").strip(os.sep)
            if key not in self.program_info:
                self.program_info[key] = {}

            self.program_info[key]['launch_count'] = self.program_info[key].get('launch_count', 0) + 1
            self.program_info[key]['last_opened'] = datetime.now().isoformat()

            # Marca item como em execução
            for _, item, _ in self.botoes:
                if hasattr(item, 'caminho') and item.caminho == caminho:
                    item.set_running(True)
                    # Remove indicador após 3 segundos
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(3000, lambda i=item: i.set_running(False))
                    break

            self.salvar_config()
            self.status_label.setText(f"Abrindo: {os.path.basename(caminho)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir:\n{e}")

    def show_context_menu(self, item, caminho):
        """Mostra menu de contexto para o item"""
        menu = QMenu(self)

        open_action = QAction("Abrir", self)
        open_action.triggered.connect(lambda: self.abrir_programa(caminho))
        menu.addAction(open_action)

        menu.addSeparator()

        edit_action = QAction("Editar", self)
        edit_action.triggered.connect(lambda: self.editar_programa(caminho))
        menu.addAction(edit_action)

        favorite_action = QAction("Desfavoritar" if self.is_favorite(caminho) else "Favoritar", self)
        favorite_action.triggered.connect(lambda: self.toggle_favorite(caminho))
        menu.addAction(favorite_action)

        menu.addSeparator()

        delete_action = QAction("Remover", self)
        delete_action.triggered.connect(lambda: self.remover_programa(caminho))
        menu.addAction(delete_action)

        # Mostra menu na posicao do cursor
        menu.exec(QCursor.pos())

    def editar_programa(self, caminho):
        """Abre dialog para editar programa"""
        key = caminho.replace(self.hub_dir, "").strip(os.sep)
        program_data = self.program_info.get(key, {})
        
        dialog = EditProgramDialog(program_data, self)
        if dialog.exec() == QDialog.Accepted:
            self.program_info[key] = {**program_data, **dialog.get_program_info()}
            self.salvar_config()
            self.carregar_programas()

    def toggle_favorite(self, caminho):
        """Alterna status de favorito"""
        key = caminho.replace(self.hub_dir, "").strip(os.sep)
        if key not in self.program_info:
            self.program_info[key] = {}
        
        current_fav = self.program_info[key].get('favorite', False)
        self.program_info[key]['favorite'] = not current_fav
        self.salvar_config()
        self.carregar_programas()

    def is_favorite(self, caminho):
        """Verifica se programa é favorito"""
        key = caminho.replace(self.hub_dir, "").strip(os.sep)
        return self.program_info.get(key, {}).get('favorite', False)

    def remover_programa(self, caminho):
        """Remove programa após confirmação"""
        nome = os.path.basename(caminho)
        reply = QMessageBox.question(
            self, "Confirmar Remoção", 
            f"Deseja realmente remover '{nome}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(caminho)
                key = caminho.replace(self.hub_dir, "").strip(os.sep)
                if key in self.program_info:
                    del self.program_info[key]
                self.salvar_config()
                self.carregar_programas()
                self.status_label.setText(f"Programa removido: {nome}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Não foi possível remover:\n{e}")

    def carregar_programas(self):
        """Carrega programas com melhor tratamento de erros e cache de ícones"""
        if not self.hub_dir or not os.path.exists(self.hub_dir):
            self.status_label.setText("Pasta Hub não encontrada!")
            return

        self.progress_bar.setVisible(True)
        self.status_label.setText("Carregando programas...")
        
        # Limpa área
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i).widget()
            if item:
                item.deleteLater()
        self.botoes.clear()

        total_programs = 0
        program_paths = []
        
        # Conta programas primeiro
        try:
            for categoria in os.listdir(self.hub_dir):
                categoria_path = os.path.join(self.hub_dir, categoria)
                if os.path.isdir(categoria_path):
                    for arquivo in os.listdir(categoria_path):
                        if arquivo.lower().endswith((".exe", ".lnk", ".bat", ".cmd")):
                            total_programs += 1
                            program_paths.append(os.path.join(categoria_path, arquivo))
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Erro ao ler diretório:\n{e}")
            self.progress_bar.setVisible(False)
            return

        self.progress_bar.setMaximum(total_programs)
        current_progress = 0

        is_dark = self.current_theme == "dark"
        self.categories = []

        # Carrega programas
        for categoria in sorted(os.listdir(self.hub_dir)):
            categoria_path = os.path.join(self.hub_dir, categoria)
            if os.path.isdir(categoria_path):
                category_widget = CollapsibleCategory(categoria)
                category_widget.set_theme(is_dark)
                category_has_programs = False

                for arquivo in sorted(os.listdir(categoria_path)):
                    if arquivo.lower().endswith((".exe", ".lnk", ".bat", ".cmd", ".py")):
                        category_has_programs = True
                        caminho = os.path.join(categoria_path, arquivo)

                        if not os.path.exists(caminho):
                            current_progress += 1
                            continue

                        key = caminho.replace(self.hub_dir, "").strip(os.sep)
                        program_data = self.program_info.get(key, {})

                        nome = program_data.get('display_name') or os.path.splitext(arquivo)[0]
                        descricao = program_data.get('description', '')

                        # Tipo de arquivo
                        ext = os.path.splitext(arquivo)[1].lower()
                        tipo = ext[1:].upper() if ext else ""

                        # Ultima execucao formatada
                        last_opened = program_data.get('last_opened', '')
                        last_run = ""
                        if last_opened:
                            try:
                                dt = datetime.fromisoformat(last_opened)
                                hoje = datetime.now().date()
                                if dt.date() == hoje:
                                    last_run = dt.strftime("%H:%M")
                                else:
                                    last_run = dt.strftime("%d/%m")
                            except:
                                pass

                        tags = program_data.get('tags', [])
                        item = ListItem(nome, descricao, tipo, last_run, tags)
                        item.caminho = caminho
                        item.set_theme(is_dark)
                        item.set_favorite(program_data.get('favorite', False))

                        # Icone - tenta detectar logo na pasta do programa
                        icon_path = program_data.get('icon', '')
                        if not icon_path or not os.path.exists(icon_path):
                            # Tenta encontrar logo na pasta pai do .bat
                            pasta_programa = os.path.dirname(caminho)
                            icon_path = self._find_logo_in_folder(pasta_programa)

                        if icon_path and os.path.exists(icon_path):
                            icon = QIcon(icon_path)
                        else:
                            icon = QIcon(caminho)
                        item.set_icon(icon)

                        # Conecta eventos
                        item.clicked.connect(lambda c=caminho: self.abrir_programa(c))
                        item.rightClicked.connect(lambda i=item, c=caminho: self.show_context_menu(i, c))

                        category_widget.add_item(item)
                        self.botoes.append((nome.lower(), item, program_data))

                        current_progress += 1
                        self.progress_bar.setValue(current_progress)
                        QApplication.processEvents()

                if category_has_programs:
                    self.scroll_layout.addWidget(category_widget)
                    self.categories.append(category_widget)

        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Carregados {total_programs} programas em {len([d for d in os.listdir(self.hub_dir) if os.path.isdir(os.path.join(self.hub_dir, d))])} categorias")

    def filtrar_programas(self):
        """Filtra programas por texto e filtros"""
        texto = self.search_bar.text().lower()
        filtro = self.filter_combo.currentText()
        
        for nome, btn, program_data in self.botoes:
            show = True
            
            # Filtro por texto
            if texto and texto not in nome:
                show = False
            
            # Filtro por tipo
            if filtro == "Favoritos" and not program_data.get('favorite', False):
                show = False
            elif filtro == "Recentes" and not program_data.get('last_opened'):
                show = False
            
            btn.setVisible(show)


def main():
    app = QApplication(sys.argv)
    
    # Splash screen com logo
    logo_path = os.path.join(ASSETS_DIR, "logolibby.png")
    pixmap = QPixmap(logo_path)
    if pixmap.isNull():
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor("#0078d4"))
    else:
        pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    
    # Simula carregamento
    import time
    time.sleep(0.5)
    
    window = HubApp()
    window.show()
    splash.finish(window)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()