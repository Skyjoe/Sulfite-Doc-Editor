import sys
import os
import tempfile
import base64
import subprocess
import re
from datetime import datetime

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import (
    QAction, QFont, QColor, QTextCharFormat, 
    QTextBlockFormat, QPageLayout, QPageSize, QKeySequence, QIcon, QTextLength
)
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QFileDialog, 
    QToolBar, QFontComboBox, QSpinBox, QColorDialog, 
    QLabel, QScrollArea, QWidget, QVBoxLayout,
    QInputDialog, QMessageBox, QToolButton, QMenu, QSizePolicy, QLineEdit
)

from pypdf import PdfReader, PdfWriter
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageDraw, ImageFont

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class MiniWordLinux(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sulfite Doc Studio")
        self.setGeometry(100, 100, 1200, 850)

        # Define o ícone da janela
        self.setWindowIcon(QIcon.fromTheme("libreoffice-writer"))

        # Histórico de PDF/Imagens e variáveis de estado
        self.pdf_paginas_imagens = []
        self.historico_pdf_paginas = []
        self.caminho_pdf_atual = None
        self.modo_leitura_ativo = False
        self.margem_atual = 40

        # Tema escuro na janela principal e barra de status
        self.setStyleSheet("""
            QMainWindow { background-color: #202124; }
            QStatusBar { background-color: #1e1e1e; color: #cccccc; }
        """)

        # Área de trabalho cinza
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #323639; border: none; }")
        self.scroll_area.setWidgetResizable(True)
        self.setCentralWidget(self.scroll_area)

        # Container central para centralizar a folha
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #323639;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.container_layout.setContentsMargins(20, 30, 20, 30)

        # Editor de Texto Principal (Folha A4 Branca)
        self.editor = QTextEdit()
        self.editor.setFixedWidth(800)
        self.editor.setMinimumHeight(1000)

        # Oculta a barra de rolagem interna da folha (mantém apenas a da janela principal)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.atualizar_estilo_edicao()

        # Estilo do Modo Leitura
        self.estilo_leitura = """
            QTextEdit {
                background-color: #fbf8f1;
                color: #1a1a1a;
                border: 2px solid #007acc;
                border-radius: 4px;
                padding: 40px 50px;
                font-family: 'Georgia', 'Liberation Serif', serif;
                font-size: 13pt;
                column-count: 2;
                column-gap: 50px;
                column-rule: 1px solid #e0dcd3;
            }
        """

        self.container_layout.addWidget(self.editor)
        self.scroll_area.setWidget(self.container)

        self.criar_barra_ferramentas()
        self.statusBar()

        # Se um arquivo for passado via linha de comando, abre automaticamente
        if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
            self.abrir_arquivo(caminho_inicial=sys.argv[1])

    def atualizar_estilo_edicao(self):
        """Garante que a folha permaneça sempre BRANCA sem injetar conflitos em tabelas."""
        self.estilo_edicao = f"""
            QTextEdit {{
                background-color: #ffffff !important;
                color: #000000 !important;
                border: 1px solid #1a1a1a;
                border-radius: 2px;
                padding: {self.margem_atual}px;
                font-family: 'Liberation Serif', 'Times New Roman', serif;
                font-size: 12pt;
            }}
        """
        if not self.modo_leitura_ativo:
            self.editor.setStyleSheet(self.estilo_edicao)

    def criar_barra_ferramentas(self):
        toolbar = QToolBar("Barra de Ferramentas")
        toolbar.setIconSize(QSize(18, 18))
        
        toolbar.setStyleSheet("""
            QToolBar { 
                background-color: #2b2b2b; 
                border-bottom: 1px solid #1e1e1e; 
                padding: 6px; 
                spacing: 4px; 
            }
            QToolButton { 
                color: #ffffff; 
                background-color: #3c3f41; 
                border: 1px solid #555555; 
                border-radius: 4px; 
                padding: 5px 10px; 
                font-size: 13px;
                font-weight: bold;
            }
            QToolButton:hover { background-color: #4c5052; }
            QToolButton::menu-indicator { image: none; }
            QLabel { color: #ffffff; font-weight: bold; font-size: 13px; }
            QComboBox, QSpinBox { 
                background-color: #3c3f41; 
                color: #ffffff; 
                border: 1px solid #555555; 
                border-radius: 4px; 
                padding: 3px 6px; 
                font-size: 13px;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #4c5052;
            }
        """)
        self.addToolBar(toolbar)

        # ESPAÇADOR DA ESQUERDA
        spacer_left = QWidget()
        spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_left)

        # ----------------------------------------------------
        # GRUPO 1: ARQUIVO
        # ----------------------------------------------------
        btn_arquivo = QToolButton(self)
        btn_arquivo.setText("📁 Arquivo ▾")
        btn_arquivo.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_arquivo = QMenu(btn_arquivo)

        act_abrir = QAction("📂 Abrir (Ctrl+O)", self)
        act_abrir.triggered.connect(self.abrir_arquivo)
        menu_arquivo.addAction(act_abrir)

        act_salvar = QAction("💾 Salvar / Salvar Como (Ctrl+S)", self)
        act_salvar.triggered.connect(self.salvar_arquivo)
        menu_arquivo.addAction(act_salvar)

        act_salvar_senha = QAction("🔒 Salvar com Senha... (Ctrl+Shift+S)", self)
        act_salvar_senha.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_salvar_senha.triggered.connect(self.salvar_com_senha)
        menu_arquivo.addAction(act_salvar_senha)

        menu_arquivo.addSeparator()

        act_exportar_pdf = QAction("📄 Exportar como PDF", self)
        act_exportar_pdf.triggered.connect(self.exportar_pdf)
        menu_arquivo.addAction(act_exportar_pdf)

        act_juntar_pdf = QAction("🧩 Juntar PDFs", self)
        act_juntar_pdf.triggered.connect(self.juntar_pdfs)
        menu_arquivo.addAction(act_juntar_pdf)

        btn_arquivo.setMenu(menu_arquivo)
        toolbar.addWidget(btn_arquivo)

        # ----------------------------------------------------
        # GRUPO 2: EDIÇÃO
        # ----------------------------------------------------
        btn_edicao = QToolButton(self)
        btn_edicao.setText("✏️ Editar ▾")
        btn_edicao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_edicao = QMenu(btn_edicao)

        act_desfazer = QAction("↩️ Desfazer (Ctrl+Z)", self)
        act_desfazer.triggered.connect(self.desfazer_acao)
        menu_edicao.addAction(act_desfazer)

        menu_edicao.addSeparator()

        act_copiar = QAction("📋 Copiar (Ctrl+C)", self)
        act_copiar.triggered.connect(self.editor.copy)
        menu_edicao.addAction(act_copiar)

        act_colar = QAction("📌 Colar (Ctrl+V)", self)
        act_colar.triggered.connect(self.editor.paste)
        menu_edicao.addAction(act_colar)

        btn_edicao.setMenu(menu_edicao)
        toolbar.addWidget(btn_edicao)

        # ----------------------------------------------------
        # GRUPO 3: FERRAMENTAS & PDF
        # ----------------------------------------------------
        btn_ferramentas = QToolButton(self)
        btn_ferramentas.setText("✨ Ferramentas & PDF ▾")
        btn_ferramentas.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_ferramentas = QMenu(btn_ferramentas)

        act_carimbo = QAction("🏷️ Inserir Carimbo (PAGO / Data)", self)
        act_carimbo.triggered.connect(self.adicionar_carimbo)
        menu_ferramentas.addAction(act_carimbo)

        act_imagem = QAction("🖼️ Inserir Imagem", self)
        act_imagem.triggered.connect(self.inserir_imagem)
        menu_ferramentas.addAction(act_imagem)

        btn_ferramentas.setMenu(menu_ferramentas)
        toolbar.addWidget(btn_ferramentas)

        # MENU DE TABELAS
        btn_tabela = QToolButton(self)
        btn_tabela.setText("📊 Tabela ▾")
        btn_tabela.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_tabela = QMenu(btn_tabela)

        act_inserir_tabela = QAction("➕ Inserir Tabela...", self)
        act_inserir_tabela.triggered.connect(self.inserir_tabela)
        menu_tabela.addAction(act_inserir_tabela)

        menu_tabela.addSeparator()

        act_add_linha = QAction("⬇️ Inserir Linha Abaixo", self)
        act_add_linha.triggered.connect(self.inserir_linha_tabela)
        menu_tabela.addAction(act_add_linha)

        act_rem_linha = QAction("❌ Remover Linha", self)
        act_rem_linha.triggered.connect(self.remover_linha_tabela)
        menu_tabela.addAction(act_rem_linha)

        menu_tabela.addSeparator()

        act_add_coluna = QAction("➡️ Inserir Coluna à Direita", self)
        act_add_coluna.triggered.connect(self.inserir_coluna_tabela)
        menu_tabela.addAction(act_add_coluna)

        act_rem_coluna = QAction("❌ Remover Coluna", self)
        act_rem_coluna.triggered.connect(self.remover_coluna_tabela)
        menu_tabela.addAction(act_rem_coluna)

        menu_tabela.addSeparator()

        act_prop_tabela = QAction("⚙️ Propriedades da Tabela (Largura)", self)
        act_prop_tabela.triggered.connect(self.ajustar_propriedades_tabela)
        menu_tabela.addAction(act_prop_tabela)

        btn_tabela.setMenu(menu_tabela)
        toolbar.addWidget(btn_tabela)

        toolbar.addSeparator()

        # ----------------------------------------------------
        # GRUPO 4: FORMATAÇÃO DE FONTE, ESTILOS E CORES
        # ----------------------------------------------------
        self.combo_fonte = QFontComboBox()
        self.combo_fonte.setMaximumWidth(160)
        self.combo_fonte.currentFontChanged.connect(self.alterar_fonte)
        toolbar.addWidget(self.combo_fonte)

        self.spin_tamanho = QSpinBox()
        self.spin_tamanho.setRange(6, 144)
        self.spin_tamanho.setValue(12)
        self.spin_tamanho.valueChanged.connect(self.alterar_tamanho_fonte)
        toolbar.addWidget(self.spin_tamanho)

        # BOTÃO NEGRITO (N)
        btn_negrito = QAction(" N ", self)
        btn_negrito.setToolTip("Negrito (Ctrl+B)")
        btn_negrito.setCheckable(True)
        btn_negrito.setShortcut("Ctrl+B")
        btn_negrito.triggered.connect(self.alternar_negrito)
        toolbar.addAction(btn_negrito)

        # BOTÃO ITÁLICO (I)
        btn_italico = QAction(" I ", self)
        btn_italico.setToolTip("Itálico (Ctrl+I)")
        btn_italico.setCheckable(True)
        btn_italico.setShortcut("Ctrl+I")
        btn_italico.triggered.connect(self.alternar_italico)
        toolbar.addAction(btn_italico)

        # BOTÃO SUBLINHADO (S)
        btn_sublinhado = QAction(" S ", self)
        btn_sublinhado.setToolTip("Sublinhado (Ctrl+U)")
        btn_sublinhado.setCheckable(True)
        btn_sublinhado.setShortcut("Ctrl+U")
        btn_sublinhado.triggered.connect(self.alternar_sublinhado)
        toolbar.addAction(btn_sublinhado)

        # MENU DE CORES
        btn_cores = QToolButton(self)
        btn_cores.setText("🎨 Cores ▾")
        btn_cores.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_cores = QMenu(btn_cores)

        act_cor_fonte = QAction("🎨 Cor da Fonte (Letra)", self)
        act_cor_fonte.triggered.connect(self.alterar_cor_fonte)
        menu_cores.addAction(act_cor_fonte)

        act_cor_fundo = QAction("🖌️ Cor de Fundo (Realce / Marca-texto)", self)
        act_cor_fundo.triggered.connect(self.alterar_cor_fundo)
        menu_cores.addAction(act_cor_fundo)

        menu_cores.addSeparator()

        act_limpar_fundo = QAction("🧹 Limpar Cor de Fundo do Texto", self)
        act_limpar_fundo.triggered.connect(self.limpar_cor_fundo)
        menu_cores.addAction(act_limpar_fundo)

        btn_cores.setMenu(menu_cores)
        toolbar.addWidget(btn_cores)

        toolbar.addSeparator()

        # ----------------------------------------------------
        # GRUPO 5: ALINHAMENTO
        # ----------------------------------------------------
        btn_alinhamento = QToolButton(self)
        btn_alinhamento.setText("☰ Alinhar ▾")
        btn_alinhamento.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_alinhar = QMenu(btn_alinhamento)

        act_esq = QAction("⬅️ Esquerda", self)
        act_esq.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignLeft))
        menu_alinhar.addAction(act_esq)

        act_cent = QAction("↔️ Centralizar", self)
        act_cent.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignCenter))
        menu_alinhar.addAction(act_cent)

        act_dir = QAction("➡️ Direita", self)
        act_dir.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignRight))
        menu_alinhar.addAction(act_dir)

        act_just = QAction("☰ Justificado", self)
        act_just.triggered.connect(lambda: self.editor.setAlignment(Qt.AlignmentFlag.AlignJustify))
        menu_alinhar.addAction(act_just)

        btn_alinhamento.setMenu(menu_alinhar)
        toolbar.addWidget(btn_alinhamento)

        # ----------------------------------------------------
        # GRUPO 6: FORMATAÇÃO DE PÁGINA
        # ----------------------------------------------------
        btn_formatacao = QToolButton(self)
        btn_formatacao.setText("📏 Formatação ▾")
        btn_formatacao.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_formatacao = QMenu(btn_formatacao)

        act_margem = QAction("📏 Margens da Folha...", self)
        act_margem.triggered.connect(self.alterar_margens)
        menu_formatacao.addAction(act_margem)

        act_espaco = QAction("↕️ Espaçamento de Linhas...", self)
        act_espaco.triggered.connect(self.alterar_espacamento_linhas)
        menu_formatacao.addAction(act_espaco)

        btn_formatacao.setMenu(menu_formatacao)
        toolbar.addWidget(btn_formatacao)

        toolbar.addSeparator()

        # ----------------------------------------------------
        # GRUPO 7: MODO LEITURA
        # ----------------------------------------------------
        self.btn_leitura = QAction("📖 Leitura", self)
        self.btn_leitura.setCheckable(True)
        self.btn_leitura.triggered.connect(self.alternar_modo_leitura)
        toolbar.addAction(self.btn_leitura)

        # ESPAÇADOR DA DIREITA
        spacer_right = QWidget()
        spacer_right.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer_right)

    # --- Manipulação de Tabelas ---

    def inserir_tabela(self):
        linhas, ok1 = QInputDialog.getInt(self, "Criar Tabela", "Número de Linhas:", 3, 1, 50)
        if not ok1:
            return
        colunas, ok2 = QInputDialog.getInt(self, "Criar Tabela", "Número de Colunas:", 3, 1, 20)
        if not ok2:
            return

        cursor = self.editor.textCursor()
        tabela = cursor.insertTable(linhas, colunas)
        fmt = tabela.format()
        fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        fmt.setBorder(1)
        fmt.setCellPadding(6)
        fmt.setCellSpacing(0)
        tabela.setFormat(fmt)
        self.statusBar().showMessage(f"Tabela {linhas}x{colunas} inserida.")

    def inserir_linha_tabela(self):
        cursor = self.editor.textCursor()
        tabela = cursor.currentTable()
        if tabela:
            celula = tabela.cellAt(cursor)
            tabela.insertRows(celula.row() + 1, 1)
            self.statusBar().showMessage("Linha inserida.")
        else:
            QMessageBox.warning(self, "Atenção", "Posicione o cursor dentro de uma célula da tabela.")

    def remover_linha_tabela(self):
        cursor = self.editor.textCursor()
        tabela = cursor.currentTable()
        if tabela:
            celula = tabela.cellAt(cursor)
            tabela.removeRows(celula.row(), 1)
            self.statusBar().showMessage("Linha removida.")
        else:
            QMessageBox.warning(self, "Atenção", "Posicione o cursor dentro de uma célula da tabela.")

    def inserir_coluna_tabela(self):
        cursor = self.editor.textCursor()
        tabela = cursor.currentTable()
        if tabela:
            celula = tabela.cellAt(cursor)
            tabela.insertColumns(celula.column() + 1, 1)
            self.statusBar().showMessage("Coluna inserida.")
        else:
            QMessageBox.warning(self, "Atenção", "Posicione o cursor dentro de uma célula da tabela.")

    def remover_coluna_tabela(self):
        cursor = self.editor.textCursor()
        tabela = cursor.currentTable()
        if tabela:
            celula = tabela.cellAt(cursor)
            tabela.removeColumns(celula.column(), 1)
            self.statusBar().showMessage("Coluna removida.")
        else:
            QMessageBox.warning(self, "Atenção", "Posicione o cursor dentro de uma célula da tabela.")

    def ajustar_propriedades_tabela(self):
        cursor = self.editor.textCursor()
        tabela = cursor.currentTable()
        if not tabela:
            QMessageBox.warning(self, "Atenção", "Posicione o cursor dentro da tabela que deseja formatar.")
            return

        porcentagem, ok = QInputDialog.getInt(
            self, 
            "Largura da Tabela", 
            "Digite a largura total da tabela em porcentagem (10% a 100%):", 
            100, 10, 100, 5
        )
        if ok:
            fmt = tabela.format()
            fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, porcentagem))
            fmt.setBorder(1)
            fmt.setCellPadding(6)
            fmt.setCellSpacing(0)
            tabela.setFormat(fmt)
            self.statusBar().showMessage(f"Tabela ajustada para {porcentagem}% da largura da folha.")

    # --- Segurança e Criptografia (.sft) ---

    def gerar_chave(self, senha: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(senha.encode('utf-8')))

    def salvar_com_senha(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, 
            "Salvar Documento Protegido", 
            "", 
            "Documento Protegido Sulfite (*.sft)"
        )
        if caminho:
            if not caminho.endswith('.sft'):
                caminho += '.sft'

            senha, ok = QInputDialog.getText(
                self, 
                "Criar Senha de Proteção", 
                "Digite uma senha para proteger este documento:", 
                QLineEdit.EchoMode.Password
            )
            if ok and senha:
                try:
                    conteudo_html = self.editor.toHtml()
                    salt = os.urandom(16)
                    chave = self.gerar_chave(senha, salt)
                    fernet = Fernet(chave)
                    
                    dados_criptografados = fernet.encrypt(conteudo_html.encode('utf-8'))
                    
                    with open(caminho, 'wb') as f:
                        f.write(salt + dados_criptografados)
                        
                    self.statusBar().showMessage(f"Documento protegido salvo: {os.path.basename(caminho)}")
                    QMessageBox.information(
                        self, 
                        "Sucesso", 
                        "Arquivo salvo e protegido com sucesso!\nNinguém poderá abri-lo sem a senha."
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível proteger o arquivo: {str(e)}")

    # --- Edição e Formatação ---

    def alterar_fonte(self, font):
        self.editor.setCurrentFont(font)

    def alterar_tamanho_fonte(self, tamanho):
        self.editor.setFontPointSize(tamanho)

    def alternar_negrito(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if self.editor.fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)
        self.editor.mergeCurrentCharFormat(fmt)

    def alternar_italico(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.editor.fontItalic())
        self.editor.mergeCurrentCharFormat(fmt)

    def alternar_sublinhado(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.editor.fontUnderline())
        self.editor.mergeCurrentCharFormat(fmt)

    def alterar_cor_fonte(self):
        cor = QColorDialog.getColor()
        if cor.isValid():
            self.editor.setTextColor(cor)

    def alterar_cor_fundo(self):
        cor = QColorDialog.getColor()
        if cor.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(cor)
            self.editor.mergeCurrentCharFormat(fmt)

    def limpar_cor_fundo(self):
        fmt = QTextCharFormat()
        fmt.setBackground(Qt.GlobalColor.transparent)
        self.editor.mergeCurrentCharFormat(fmt)

    def alterar_margens(self):
        opcoes = [
            "Normal (40px)",
            "Estreita (20px)",
            "Larga (70px)",
            "Personalizada..."
        ]
        escolha, ok = QInputDialog.getItem(
            self, "Margens da Folha", 
            "Selecione o tamanho das margens:", 
            opcoes, 0, False
        )
        if not ok:
            return

        if "Normal" in escolha:
            self.margem_atual = 40
        elif "Estreita" in escolha:
            self.margem_atual = 20
        elif "Larga" in escolha:
            self.margem_atual = 70
        elif "Personalizada" in escolha:
            val, ok_val = QInputDialog.getInt(
                self, "Margem Personalizada", 
                "Digite o valor da margem interna (em pixels):", 
                self.margem_atual, 10, 150, 5
            )
            if ok_val:
                self.margem_atual = val

        self.atualizar_estilo_edicao()
        self.statusBar().showMessage(f"Margens ajustadas para {self.margem_atual}px")

    def alterar_espacamento_linhas(self):
        opcoes = [
            "1.0x (Simples)",
            "1.15x (Padrão Word)",
            "1.5x (Intermediário)",
            "2.0x (Duplo)",
            "Personalizado..."
        ]
        escolha, ok = QInputDialog.getItem(
            self, "Espaçamento de Linhas", 
            "Escolha a distância entre as linhas:", 
            opcoes, 1, False
        )
        if not ok:
            return

        fator = 100
        if "1.0x" in escolha:
            fator = 100
        elif "1.15x" in escolha:
            fator = 115
        elif "1.5x" in escolha:
            fator = 150
        elif "2.0x" in escolha:
            fator = 200
        elif "Personalizado" in escolha:
            val, ok_val = QInputDialog.getDouble(
                self, "Espaçamento Personalizado", 
                "Multiplicador do espaçamento (ex: 1.25):", 
                1.15, 0.8, 3.0, 2
            )
            if ok_val:
                fator = int(val * 100)

        fmt = QTextBlockFormat()
        fmt.setLineHeight(fator, 1)
        cursor = self.editor.textCursor()
        cursor.mergeBlockFormat(fmt)
        self.statusBar().showMessage("Espaçamento de linhas atualizado.")

    def inserir_imagem(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem", "", "Imagens (*.png *.jpg *.jpeg *.bmp)")
        if caminho:
            largura, ok = QInputDialog.getInt(self, "Tamanho da Imagem", "Largura em pixels:", 400, 50, 700, 25)
            if ok:
                cursor = self.editor.textCursor()
                cursor.insertHtml(f'<img src="{caminho}" width="{largura}"/>')

    def alternar_modo_leitura(self, checado):
        self.modo_leitura_ativo = checado
        self.editor.setReadOnly(checado)
        
        if checado:
            self.editor.setFixedWidth(1150)
            self.editor.setMinimumHeight(650)
            self.editor.setStyleSheet(self.estilo_leitura)
            self.statusBar().showMessage("Modo Leitura Ativado (Layout Livro / Página Dupla)")
        else:
            self.editor.setFixedWidth(800)
            self.editor.setMinimumHeight(1000)
            self.atualizar_estilo_edicao()
            self.statusBar().showMessage("Modo Edição Ativado")

    # --- Desfazer e Carimbos ---

    def desfazer_acao(self):
        if self.pdf_paginas_imagens and self.historico_pdf_paginas:
            self.pdf_paginas_imagens = self.historico_pdf_paginas.pop()
            self.atualizar_visualizacao_pdf()
            self.statusBar().showMessage("Carimbo/Ação desfeita com sucesso!")
        else:
            self.editor.undo()
            self.statusBar().showMessage("Ação desfeita.")

    def adicionar_carimbo(self):
        texto, ok = QInputDialog.getText(self, "Texto do Carimbo", "Digite a palavra do carimbo:", text="PAGO")
        if not ok or not texto.strip():
            return

        posicoes = [
            "Canto Superior Direito",
            "Canto Superior Esquerdo",
            "Centralizado na Folha",
            "Canto Inferior Direito",
            "Canto Inferior Esquerdo"
        ]
        posicao, ok = QInputDialog.getItem(
            self, "Posição do Carimbo", 
            "Onde deseja posicionar o carimbo?", 
            posicoes, 0, False
        )
        if not ok:
            return

        cor_dialog = QColorDialog.getColor(QColor(200, 0, 0), self, "Escolha a cor do Carimbo")
        if not cor_dialog.isValid():
            return
            
        r, g, b = cor_dialog.red(), cor_dialog.green(), cor_dialog.blue()
        cor_rgb = (r, g, b)

        data_hoje = datetime.now().strftime("%d/%m/%Y")

        if self.pdf_paginas_imagens:
            self.statusBar().showMessage("Aplicando carimbo no documento...")
            
            copia_historico = [img.copy() for img in self.pdf_paginas_imagens]
            self.historico_pdf_paginas.append(copia_historico)

            img_pagina = self.pdf_paginas_imagens[0].copy()
            draw = ImageDraw.Draw(img_pagina)

            try:
                font_grande = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
                font_pequena = ImageFont.truetype("DejaVuSans-Bold.ttf", 25)
            except IOError:
                font_grande = ImageFont.load_default()
                font_pequena = ImageFont.load_default()

            largura_img, altura_img = img_pagina.size
            largura_box, altura_box = 380, 160

            if "Superior Direito" in posicao:
                x_inicio, y_inicio = largura_img - largura_box - 80, 100
            elif "Superior Esquerdo" in posicao:
                x_inicio, y_inicio = 80, 100
            elif "Centralizado" in posicao:
                x_inicio, y_inicio = (largura_img - largura_box) // 2, (altura_img - altura_box) // 2
            elif "Inferior Direito" in posicao:
                x_inicio, y_inicio = largura_img - largura_box - 80, altura_img - altura_box - 120
            else:
                x_inicio, y_inicio = 80, altura_img - altura_box - 120

            draw.rounded_rectangle([x_inicio, y_inicio, x_inicio + largura_box, y_inicio + altura_box], radius=15, outline=cor_rgb, width=6)
            draw.rounded_rectangle([x_inicio + 8, y_inicio + 8, x_inicio + largura_box - 8, y_inicio + altura_box - 8], radius=10, outline=cor_rgb, width=2)

            draw.text((x_inicio + 35, y_inicio + 20), texto.upper(), fill=cor_rgb, font=font_grande)
            draw.text((x_inicio + 85, y_inicio + 100), f"DATA: {data_hoje}", fill=cor_rgb, font=font_pequena)

            self.pdf_paginas_imagens[0] = img_pagina
            self.atualizar_visualizacao_pdf()
            self.statusBar().showMessage("Carimbo aplicado! Use 'Desfazer' (Ctrl+Z) se quiser remover.")
        else:
            hex_cor = cor_dialog.name()
            alinhamento = "right" if "Direito" in posicao else ("left" if "Esquerdo" in posicao else "center")
            html_carimbo = f"""
            <div style="text-align: {alinhamento}; margin: 15px;">
                <div style="border: 4px double {hex_cor}; border-radius: 8px; padding: 10px 20px; display: inline-block; text-align: center; color: {hex_cor}; font-weight: bold;">
                    <span style="font-size: 28pt;">{texto.upper()}</span><br>
                    <span style="font-size: 11pt;">DATA: {data_hoje}</span>
                </div>
            </div><br>
            """
            cursor = self.editor.textCursor()
            cursor.insertHtml(html_carimbo)

    def atualizar_visualizacao_pdf(self):
        temp_dir = tempfile.gettempdir()
        html_conteudo = ""

        for i, img in enumerate(self.pdf_paginas_imagens):
            img_path = os.path.join(temp_dir, f"temp_pdf_page_{i}.png")
            img.save(img_path, "PNG")
            html_conteudo += f'<img src="{img_path}" width="700"/><br><br>'

        self.editor.setHtml(html_conteudo)

    # --- Persistência de Arquivos & Exportação ---

    def abrir_arquivo(self, caminho_inicial=None):
        if caminho_inicial:
            caminho = caminho_inicial
        else:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Abrir Arquivo", "", 
                "Todos os Suportados (*.html *.htm *.txt *.pdf *.odt *.docx *.sft);;"
                "Documentos do Word (*.docx);;"
                "Documentos ODT (*.odt);;"
                "Documentos Protegidos Sulfite (*.sft);;"
                "Arquivos PDF (*.pdf);;"
                "Documentos HTML (*.html *.htm);;"
                "Texto Puro (*.txt)"
            )

        if caminho:
            self.caminho_pdf_atual = caminho
            self.historico_pdf_paginas.clear()

            # --- SUPORTE A ARQUIVOS PROTEGIDOS DO SULFITE (.sft) ---
            if caminho.lower().endswith('.sft'):
                senha, ok = QInputDialog.getText(
                    self, 
                    "Documento Protegido", 
                    "Este arquivo está protegido com senha.\nDigite a senha para abrir:", 
                    QLineEdit.EchoMode.Password
                )
                if ok and senha:
                    try:
                        with open(caminho, 'rb') as f:
                            conteudo = f.read()
                            
                        salt = conteudo[:16]
                        dados_criptografados = conteudo[16:]
                        
                        chave = self.gerar_chave(senha, salt)
                        fernet = Fernet(chave)
                        
                        conteudo_html = fernet.decrypt(dados_criptografados).decode('utf-8')
                        self.editor.setHtml(conteudo_html)
                        self.statusBar().showMessage(f"Documento descriptografado carregado: {os.path.basename(caminho)}")
                    except Exception:
                        QMessageBox.warning(
                            self, 
                            "Senha Incorreta", 
                            "Não foi possível abrir o documento.\nA senha digitada está incorreta!"
                        )

            # --- SUPORTE A ARQUIVOS .ODT E .DOCX ---
            elif caminho.lower().endswith(('.odt', '.docx')):
                try:
                    self.pdf_paginas_imagens = []
                    self.statusBar().showMessage(f"Carregando {os.path.basename(caminho)}...")
                    QApplication.processEvents()

                    temp_dir = tempfile.gettempdir()
                    nome_base = os.path.splitext(os.path.basename(caminho))[0] + ".html"
                    caminho_temp_html = os.path.join(temp_dir, nome_base)

                    if os.path.exists(caminho_temp_html):
                        os.remove(caminho_temp_html)

                    cmd = [
                        'libreoffice', '--headless',
                        f'-env:UserInstallation=file://{temp_dir}/lo_temp_profile',
                        '--convert-to', 'html', caminho,
                        '--outdir', temp_dir
                    ]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                    if os.path.exists(caminho_temp_html):
                        with open(caminho_temp_html, 'r', encoding='utf-8', errors='replace') as f:
                            conteudo_html = f.read()

                        # Remove apenas definições de cor de fundo escuras na tag body para preservar a folha branca
                        conteudo_html = re.sub(r'body\s*{[^}]*}', '', conteudo_html, flags=re.IGNORECASE)

                        self.editor.setHtml(conteudo_html)
                        self.statusBar().showMessage(f"Documento carregado com sucesso: {os.path.basename(caminho)}")
                    else:
                        QMessageBox.warning(
                            self, 
                            "Arquivo Protegido / Erro", 
                            "Não foi possível ler o arquivo. Se este documento ODT/DOCX tiver senha de proteção, "
                            "remova-a no LibreOffice/Word para abri-lo no Sulfite."
                        )

                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Falha ao processar arquivo: {str(e)}")

            # --- SUPORTE A ARQUIVOS PDF ---
            elif caminho.lower().endswith('.pdf'):
                opcoes_pdf = [
                    "🖼️ Preservar Layout e Imagens (Ideal para boletos/faturas)",
                    "🔍 Reconhecer Texto via OCR (PDF/Imagem para Texto Editável)",
                    "📝 Extrair Texto Simples (Sem OCR)"
                ]
                modo, ok = QInputDialog.getItem(
                    self, "Modo de Leitura de PDF", 
                    "Como você deseja abrir este PDF?", 
                    opcoes_pdf, 0, False
                )
                if not ok:
                    return

                if "Preservar Layout" in modo:
                    try:
                        self.statusBar().showMessage("Renderizando páginas do PDF...")
                        QApplication.processEvents()
                        
                        self.pdf_paginas_imagens = convert_from_path(caminho, dpi=150)
                        self.atualizar_visualizacao_pdf()
                        self.statusBar().showMessage(f"PDF renderizado com sucesso: {os.path.basename(caminho)}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Não foi possível converter o PDF: {str(e)}")

                elif "OCR" in modo:
                    try:
                        self.pdf_paginas_imagens = []
                        self.statusBar().showMessage("Executando OCR no PDF...")
                        QApplication.processEvents()
                        
                        imagens = convert_from_path(caminho, dpi=200)
                        texto_completo = ""
                        
                        for i, img in enumerate(imagens):
                            texto_pagina = pytesseract.image_to_string(img, lang='por')
                            texto_completo += f"--- Página {i+1} ---\n\n" + texto_pagina + "\n\n"
                            
                        self.editor.setPlainText(texto_completo)
                        self.statusBar().showMessage("OCR concluído!")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro no OCR", f"Erro ao executar OCR: {str(e)}")
                else:
                    try:
                        self.pdf_paginas_imagens = []
                        reader = PdfReader(caminho)
                        texto_pdf = ""
                        for pagina in reader.pages:
                            texto_pdf += pagina.extract_text() + "\n\n--- Página ---\n\n"
                        self.editor.setPlainText(texto_pdf)
                        self.statusBar().showMessage(f"Texto extraído: {os.path.basename(caminho)}")
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", f"Erro ao ler texto do PDF: {str(e)}")

            # --- SUPORTE A ARQUIVOS HTML ---
            elif caminho.lower().endswith('.html') or caminho.lower().endswith('.htm'):
                self.pdf_paginas_imagens = []
                with open(caminho, 'r', encoding='utf-8') as f:
                    self.editor.setHtml(f.read())
            
            # --- SUPORTE A TEXTO PURO ---
            else:
                self.pdf_paginas_imagens = []
                with open(caminho, 'r', encoding='utf-8') as f:
                    self.editor.setPlainText(f.read())

    def salvar_arquivo(self):
        if self.pdf_paginas_imagens:
            self.exportar_pdf()
            return

        caminho, filtro_selecionado = QFileDialog.getSaveFileName(
            self, 
            "Salvar Arquivo", 
            "", 
            "Documento do Word (*.docx);;"
            "Documento ODT (*.odt);;"
            "Documento Protegido Sulfite (*.sft);;"
            "Documento PDF (*.pdf);;"
            "Documento HTML (*.html);;"
            "Texto Puro (*.txt)"
        )

        if caminho:
            if "(*.docx)" in filtro_selecionado or caminho.endswith('.docx'):
                if not caminho.endswith('.docx'):
                    caminho += '.docx'
                self.salvar_como_docx(caminho)

            elif "(*.odt)" in filtro_selecionado or caminho.endswith('.odt'):
                if not caminho.endswith('.odt'):
                    caminho += '.odt'
                self.salvar_como_odt(caminho)

            elif "(*.sft)" in filtro_selecionado or caminho.endswith('.sft'):
                self.salvar_com_senha_caminho(caminho)

            elif "(*.pdf)" in filtro_selecionado or caminho.endswith('.pdf'):
                self.exportar_pdf_caminho(caminho)

            elif caminho.endswith('.txt'):
                with open(caminho, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toPlainText())
                self.statusBar().showMessage(f"Arquivo salvo: {os.path.basename(caminho)}")

            else:
                if not caminho.endswith('.html'):
                    caminho += '.html'
                with open(caminho, 'w', encoding='utf-8') as f:
                    f.write(self.editor.toHtml())
                self.statusBar().showMessage(f"Arquivo salvo: {os.path.basename(caminho)}")

    def salvar_como_docx(self, caminho_saida):
        try:
            temp_dir = tempfile.gettempdir()
            caminho_temp_html = os.path.join(temp_dir, "temp_export_word.html")

            with open(caminho_temp_html, 'w', encoding='utf-8') as f:
                f.write(self.editor.toHtml())

            cmd = [
                'libreoffice', '--headless',
                '--convert-to', 'docx', caminho_temp_html,
                '--outdir', os.path.dirname(caminho_saida)
            ]
            subprocess.run(cmd, check=True)

            arquivo_gerado = os.path.join(os.path.dirname(caminho_saida), "temp_export_word.docx")
            if os.path.exists(arquivo_gerado):
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
                os.rename(arquivo_gerado, caminho_saida)

            self.statusBar().showMessage(f"Documento Word (.docx) salvo com sucesso: {os.path.basename(caminho_saida)}")
            QMessageBox.information(self, "Sucesso", f"Arquivo DOCX gerado em:\n{caminho_saida}")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar DOCX", f"Não foi possível gerar o arquivo Word: {str(e)}")

    def salvar_como_odt(self, caminho_saida):
        try:
            temp_dir = tempfile.gettempdir()
            caminho_temp_html = os.path.join(temp_dir, "temp_export.html")

            with open(caminho_temp_html, 'w', encoding='utf-8') as f:
                f.write(self.editor.toHtml())

            cmd = [
                'libreoffice', '--headless',
                '--convert-to', 'odt', caminho_temp_html,
                '--outdir', os.path.dirname(caminho_saida)
            ]
            subprocess.run(cmd, check=True)

            arquivo_gerado = os.path.join(os.path.dirname(caminho_saida), "temp_export.odt")
            if os.path.exists(arquivo_gerado):
                if os.path.exists(caminho_saida):
                    os.remove(caminho_saida)
                os.rename(arquivo_gerado, caminho_saida)

            self.statusBar().showMessage(f"Documento ODT salvo com sucesso: {os.path.basename(caminho_saida)}")
            QMessageBox.information(self, "Sucesso", f"Arquivo ODT gerado em:\n{caminho_saida}")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar ODT", f"Não foi possível gerar o arquivo ODT: {str(e)}")

    def salvar_com_senha_caminho(self, caminho):
        if not caminho.endswith('.sft'):
            caminho += '.sft'

        senha, ok = QInputDialog.getText(
            self, 
            "Criar Senha de Proteção", 
            "Digite uma senha para proteger este documento:", 
            QLineEdit.EchoMode.Password
        )
        if ok and senha:
            try:
                conteudo_html = self.editor.toHtml()
                salt = os.urandom(16)
                chave = self.gerar_chave(senha, salt)
                fernet = Fernet(chave)
                
                dados_criptografados = fernet.encrypt(conteudo_html.encode('utf-8'))
                
                with open(caminho, 'wb') as f:
                    f.write(salt + dados_criptografados)
                    
                self.statusBar().showMessage(f"Documento protegido salvo: {os.path.basename(caminho)}")
                QMessageBox.information(
                    self, 
                    "Sucesso", 
                    "Arquivo salvo e protegido com sucesso!\nNinguém poderá abri-lo sem a senha."
                )
            except Exception as e:
                QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível proteger o arquivo: {str(e)}")

    def exportar_pdf_caminho(self, caminho):
        if not caminho.endswith('.pdf'):
            caminho += '.pdf'
            
        if self.pdf_paginas_imagens:
            try:
                self.statusBar().showMessage("Gerando arquivo PDF final...")
                QApplication.processEvents()
                
                primeira_pagina = self.pdf_paginas_imagens[0].convert('RGB')
                demais_paginas = [img.convert('RGB') for img in self.pdf_paginas_imagens[1:]]
                
                primeira_pagina.save(caminho, save_all=True, append_images=demais_paginas)
                
                self.statusBar().showMessage("PDF salvo com sucesso!")
                QMessageBox.information(self, "Sucesso", f"PDF salvo com sucesso em:\n{caminho}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao salvar PDF: {str(e)}")
        else:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(caminho)
            
            layout = QPageLayout(
                QPageSize(QPageSize.PageSizeId.A4),
                QPageLayout.Orientation.Portrait,
                Qt.Edge.Margins
            )
            printer.setPageLayout(layout)
            
            self.editor.document().print(printer)
            QMessageBox.information(self, "Sucesso", f"PDF gerado com sucesso em:\n{caminho}")

    def exportar_pdf(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar/Salvar como PDF", "", "Arquivo PDF (*.pdf)")
        if caminho:
            self.exportar_pdf_caminho(caminho)

    def juntar_pdfs(self):
        arquivos, _ = QFileDialog.getOpenFileNames(
            self, "Selecione os arquivos PDF para juntar", "", "Arquivos PDF (*.pdf)"
        )
        if len(arquivos) < 2:
            QMessageBox.warning(self, "Atenção", "Selecione pelo menos 2 arquivos PDF para mesclar.")
            return

        caminho_saida, _ = QFileDialog.getSaveFileName(self, "Salvar PDF Unificado", "", "Arquivo PDF (*.pdf)")
        if caminho_saida:
            if not caminho_saida.endswith('.pdf'):
                caminho_saida += '.pdf'
                
            try:
                merger = PdfWriter()
                for pdf in arquivos:
                    merger.append(pdf)
                
                with open(caminho_saida, "wb") as f_out:
                    merger.write(f_out)
                merger.close()

                QMessageBox.information(self, "Sucesso", f"PDFs unidos com sucesso em:\n{caminho_saida}")
            except Exception as e:
                QMessageBox.critical(self, "Erro ao juntar PDFs: " + str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    app.setDesktopFileName("TextEditor.desktop")
    
    janela = MiniWordLinux()
    janela.show()
    sys.exit(app.exec())
