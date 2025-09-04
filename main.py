import os
import sys
import json
import subprocess
import threading
from shutil import copy2, move
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QGroupBox, QGridLayout, QMessageBox, QFileDialog, 
    QInputDialog, QHBoxLayout, QMenu, QDialog, QLabel, QTextEdit,
    QCheckBox, QComboBox, QProgressBar, QSplashScreen
)
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QFont, QPalette, QColor
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize

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

class EditProgramDialog(QDialog):
    """Dialog para editar informações do programa"""
    def __init__(self, program_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Programa")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Nome de exibição
        layout.addWidget(QLabel("Nome de Exibição:"))
        self.name_edit = QLineEdit(program_info.get('display_name', ''))
        layout.addWidget(self.name_edit)
        
        # Descrição
        layout.addWidget(QLabel("Descrição:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlainText(program_info.get('description', ''))
        self.desc_edit.setMaximumHeight(100)
        layout.addWidget(self.desc_edit)
        
        # Favorito
        self.favorite_check = QCheckBox("Marcar como favorito")
        self.favorite_check.setChecked(program_info.get('favorite', False))
        layout.addWidget(self.favorite_check)
        
        # Botões
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("Salvar")
        self.cancel_btn = QPushButton("Cancelar")
        
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def get_program_info(self):
        return {
            'display_name': self.name_edit.text(),
            'description': self.desc_edit.toPlainText(),
            'favorite': self.favorite_check.isChecked()
        }

class ModernButton(QPushButton):
    """Botão customizado com visual moderno"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setMinimumSize(120, 80)
        self.is_favorite = False
        self.launch_count = 0
        
    def set_favorite(self, is_favorite):
        self.is_favorite = is_favorite
        self.update_style()
    
    def set_launch_count(self, count):
        self.launch_count = count
        self.update_style()
    
    def update_style(self):
        base_style = """
            QPushButton {
                border: 2px solid #3498db;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #3498db;
                color: white;
            }
            QPushButton:pressed {
                background-color: #2980b9;
            }
        """
        
        if self.is_favorite:
            base_style = base_style.replace("#3498db", "#e74c3c")
            
        self.setStyleSheet(base_style)

class HubApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Libby v2.0")
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
        
        # Cria diretório de cache se não existir
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        # Se já tinha uma pasta salva, carrega
        if self.hub_dir:
            self.carregar_programas()
        else:
            self.toggle_botoes(False)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # Barra superior
        top_bar = QHBoxLayout()
        self.layout.addLayout(top_bar)
        
        # Botões da barra superior
        self.btn_escolher_pasta = QPushButton("📂 Escolher Pasta Hub")
        self.btn_escolher_pasta.clicked.connect(self.escolher_pasta)
        top_bar.addWidget(self.btn_escolher_pasta)
        
        self.btn_nova_categoria = QPushButton("➕ Nova Categoria")
        self.btn_nova_categoria.clicked.connect(self.nova_categoria)
        top_bar.addWidget(self.btn_nova_categoria)
        
        self.btn_adicionar_programa = QPushButton("📥 Adicionar Programa")
        self.btn_adicionar_programa.clicked.connect(self.adicionar_programa)
        top_bar.addWidget(self.btn_adicionar_programa)
        
        self.btn_theme = QPushButton("🌙 Tema Escuro")
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.btn_theme)
        
        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.clicked.connect(self.carregar_programas)
        top_bar.addWidget(self.btn_atualizar)
        
        # Barra de busca e filtros
        search_layout = QHBoxLayout()
        self.layout.addLayout(search_layout)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar programa...")
        self.search_bar.textChanged.connect(self.filtrar_programas)
        search_layout.addWidget(self.search_bar)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todos", "Favoritos", "Recentes"])
        self.filter_combo.currentTextChanged.connect(self.filtrar_programas)
        search_layout.addWidget(self.filter_combo)
        
        # Progress bar para carregamento
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)
        
        # Área rolável
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)
        
        # Status bar
        self.status_label = QLabel("Pronto")
        self.layout.addWidget(self.status_label)

    def apply_theme(self):
        """Aplica tema escuro ou claro"""
        if self.current_theme == "dark":
            self.setStyleSheet("""
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QLineEdit {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #555555;
                    border-radius: 5px;
                    margin-top: 1ex;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QScrollArea {
                    border: 1px solid #555555;
                }
                QComboBox {
                    background-color: #3c3c3c;
                    border: 1px solid #555555;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
            self.btn_theme.setText("☀️ Tema Claro")
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    color: #000000;
                }
                QLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton {
                    background-color: #0078d4;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
                QPushButton:pressed {
                    background-color: #005a9e;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 2px solid #cccccc;
                    border-radius: 5px;
                    margin-top: 1ex;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QScrollArea {
                    border: 1px solid #cccccc;
                }
                QComboBox {
                    background-color: #ffffff;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
            self.btn_theme.setText("🌙 Tema Escuro")

    def toggle_theme(self):
        """Alterna entre tema claro e escuro"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()
        self.salvar_config()

    def toggle_botoes(self, ativo: bool):
        """Ativa/desativa botões dependendo se há pasta Hub selecionada"""
        self.btn_nova_categoria.setEnabled(ativo)
        self.btn_adicionar_programa.setEnabled(ativo)
        self.btn_atualizar.setEnabled(ativo)
        self.search_bar.setEnabled(ativo)
        self.filter_combo.setEnabled(ativo)

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
            self, "Escolher programa", "", "Executáveis (*.exe *.lnk);;Todos os arquivos (*.*)"
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
            
            self.salvar_config()
            self.status_label.setText(f"Abrindo: {os.path.basename(caminho)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir:\n{e}")

    def show_context_menu(self, button, caminho):
        """Mostra menu de contexto para o botão"""
        menu = QMenu(self)
        
        # Ações do menu
        edit_action = QAction("✏️ Editar", self)
        edit_action.triggered.connect(lambda: self.editar_programa(caminho))
        menu.addAction(edit_action)
        
        favorite_action = QAction("⭐ Favoritar" if not self.is_favorite(caminho) else "💔 Desfavoritar", self)
        favorite_action.triggered.connect(lambda: self.toggle_favorite(caminho))
        menu.addAction(favorite_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ Remover", self)
        delete_action.triggered.connect(lambda: self.remover_programa(caminho))
        menu.addAction(delete_action)
        
        # Mostra menu na posição do cursor
        menu.exec(button.mapToGlobal(button.rect().center()))

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

        # Carrega programas
        for categoria in sorted(os.listdir(self.hub_dir)):
            categoria_path = os.path.join(self.hub_dir, categoria)
            if os.path.isdir(categoria_path):
                group_box = QGroupBox(f"📁 {categoria}")
                grid = QGridLayout()
                group_box.setLayout(grid)

                col, row = 0, 0
                category_has_programs = False
                
                for arquivo in sorted(os.listdir(categoria_path)):
                    if arquivo.lower().endswith((".exe", ".lnk", ".bat", ".cmd")):
                        category_has_programs = True
                        caminho = os.path.join(categoria_path, arquivo)
                        
                        # Verifica se arquivo ainda existe
                        if not os.path.exists(caminho):
                            current_progress += 1
                            continue
                        
                        key = caminho.replace(self.hub_dir, "").strip(os.sep)
                        program_data = self.program_info.get(key, {})
                        
                        nome = program_data.get('display_name') or os.path.splitext(arquivo)[0]
                        
                        btn = ModernButton(nome)
                        btn.set_favorite(program_data.get('favorite', False))
                        btn.set_launch_count(program_data.get('launch_count', 0))
                        
                        # Tooltip com informações
                        tooltip = f"Arquivo: {arquivo}"
                        if program_data.get('description'):
                            tooltip += f"\nDescrição: {program_data['description']}"
                        if program_data.get('launch_count', 0) > 0:
                            tooltip += f"\nExecutado: {program_data['launch_count']} vez(es)"
                        btn.setToolTip(tooltip)
                        
                        # Conecta eventos
                        btn.clicked.connect(lambda _, c=caminho: self.abrir_programa(c))
                        btn.setContextMenuPolicy(Qt.CustomContextMenu)
                        btn.customContextMenuRequested.connect(
                            lambda pos, b=btn, c=caminho: self.show_context_menu(b, c)
                        )
                        
                        # Tenta carregar ícone (de forma mais segura)
                        try:
                            icon = QIcon(caminho)
                            if not icon.isNull():
                                btn.setIcon(icon)
                                btn.setIconSize(QSize(32, 32))
                        except Exception:
                            pass  # Se der erro, continua sem ícone
                        
                        grid.addWidget(btn, row, col)
                        self.botoes.append((nome.lower(), btn, program_data))

                        col += 1
                        if col > 3:  # 4 botões por linha
                            col = 0
                            row += 1
                        
                        current_progress += 1
                        self.progress_bar.setValue(current_progress)
                        QApplication.processEvents()  # Atualiza UI

                if category_has_programs:
                    self.scroll_layout.addWidget(group_box)

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
    
    # Splash screen
    pixmap = QPixmap(200, 200)
    pixmap.fill(QColor("#0078d4"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    font = QFont("Arial", 24, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "Libby\nv2.0")
    painter.end()
    
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