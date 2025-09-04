import os
import sys
import json
import subprocess
from shutil import copy2
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QScrollArea, QGroupBox, QGridLayout, QMessageBox,
    QFileDialog, QInputDialog, QHBoxLayout
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

# Caminho da pasta de config no AppData
APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MeuHub")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")


class HubApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Libby")
        self.resize(900, 600)

        # Carrega configuração
        self.hub_dir = self.carregar_config()
        self.botoes = []

        self.layout = QVBoxLayout(self)

        # Barra superior com botões
        top_bar = QHBoxLayout()
        self.layout.addLayout(top_bar)

        self.btn_escolher_pasta = QPushButton("📂 Escolher Pasta Hub")
        self.btn_escolher_pasta.clicked.connect(self.escolher_pasta)
        top_bar.addWidget(self.btn_escolher_pasta)

        self.btn_nova_categoria = QPushButton("➕ Nova Categoria")
        self.btn_nova_categoria.clicked.connect(self.nova_categoria)
        top_bar.addWidget(self.btn_nova_categoria)

        self.btn_adicionar_programa = QPushButton("📥 Adicionar Programa")
        self.btn_adicionar_programa.clicked.connect(self.adicionar_programa)
        top_bar.addWidget(self.btn_adicionar_programa)

        self.btn_atualizar = QPushButton("🔄 Atualizar")
        self.btn_atualizar.clicked.connect(self.carregar_programas)
        top_bar.addWidget(self.btn_atualizar)

        # Campo de busca
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar programa...")
        self.search_bar.textChanged.connect(self.filtrar_programas)
        self.layout.addWidget(self.search_bar)

        # Área rolável
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)

        # Se já tinha uma pasta salva, carrega
        if self.hub_dir:
            self.carregar_programas()
        else:
            self.toggle_botoes(False)

    def toggle_botoes(self, ativo: bool):
        """Ativa/desativa botões e busca dependendo se há pasta Hub selecionada"""
        self.btn_nova_categoria.setEnabled(ativo)
        self.btn_adicionar_programa.setEnabled(ativo)
        self.btn_atualizar.setEnabled(ativo)
        self.search_bar.setEnabled(ativo)

    def salvar_config(self):
        """Salva o diretório atual no config.json dentro do AppData"""
        try:
            os.makedirs(APPDATA_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"hub_dir": self.hub_dir}, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Aviso", f"Não foi possível salvar config:\n{e}")

    def carregar_config(self):
        """Carrega o diretório salvo em config.json"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("hub_dir", None)
            except Exception:
                return None
        return None

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
            self, "Escolher programa", "", "Executáveis (*.exe *.lnk)"
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
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível adicionar:\n{e}")

    def abrir_programa(self, caminho):
        try:
            subprocess.Popen(caminho, shell=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível abrir:\n{e}")

    def carregar_programas(self):
        if not self.hub_dir:
            return

        # Limpa área
        for i in reversed(range(self.scroll_layout.count())):
            item = self.scroll_layout.itemAt(i).widget()
            if item:
                item.deleteLater()
        self.botoes.clear()

        # Lê categorias
        for categoria in os.listdir(self.hub_dir):
            categoria_path = os.path.join(self.hub_dir, categoria)
            if os.path.isdir(categoria_path):
                group_box = QGroupBox(categoria)
                grid = QGridLayout()
                group_box.setLayout(grid)

                col, row = 0, 0
                for arquivo in os.listdir(categoria_path):
                    if arquivo.lower().endswith((".exe", ".lnk")):
                        caminho = os.path.join(categoria_path, arquivo)
                        nome = os.path.splitext(arquivo)[0]

                        btn = QPushButton(nome)
                        btn.setIcon(QIcon(caminho))  # tenta puxar ícone
                        btn.setIconSize(btn.sizeHint())
                        btn.clicked.connect(lambda _, c=caminho: self.abrir_programa(c))

                        grid.addWidget(btn, row, col)
                        self.botoes.append((nome.lower(), btn))

                        col += 1
                        if col > 3:  # 4 botões por linha
                            col = 0
                            row += 1

                self.scroll_layout.addWidget(group_box)

    def filtrar_programas(self):
        texto = self.search_bar.text().lower()
        for nome, btn in self.botoes:
            btn.setVisible(texto in nome)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HubApp()
    window.show()
    sys.exit(app.exec())
