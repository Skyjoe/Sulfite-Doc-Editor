#!/bin/bash

echo "=== Instalando o Sulfite Doc Studio ==="

# 1. Instala dependências do sistema operacional
if command -v apt &> /dev/null; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv poppler-utils tesseract-ocr tesseract-ocr-por libxcb-cursor0 libreoffice
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip poppler-utils tesseract tesseract-langpack-por libreoffice
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm python python-pip poppler tesseract tesseract-data-por libreoffice-fresh
fi

# 2. Cria e ativa o ambiente virtual Python
DIR_ATUAL=$(pwd)
python3 -m venv venv
source venv/bin/activate

# 3. Instala as bibliotecas Python
pip install --upgrade pip
pip install PyQt6 pypdf pdf2image pytesseract Pillow reportlab cryptography

# 4. Cria o script de execução repassando parâmetros ("$@")
cat <<EOF > executar.sh
#!/bin/bash
cd "$DIR_ATUAL"
source venv/bin/activate
python3 word4.py "\$@"
EOF
chmod +x executar.sh

# 5. Cria o atalho no Menu com suporte a ODT, DOCX, PDF, TXT, HTML e SFT
PASTA_ATALHOS="$HOME/.local/share/applications"
mkdir -p "$PASTA_ATALHOS"

cat <<EOF > "$PASTA_ATALHOS/TextEditor.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Sulfite Doc Studio
Comment=Editor de Texto e Estúdio de PDF com Criptografia
Exec=$DIR_ATUAL/executar.sh %U
Icon=libreoffice-writer
Terminal=false
Categories=Office;Utility;
MimeType=application/vnd.oasis.opendocument.text;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/pdf;text/plain;text/html;application/x-sulfite;
EOF

chmod +x "$PASTA_ATALHOS/TextEditor.desktop"

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$PASTA_ATALHOS"
fi

echo "=== Instalação Concluída com Sucesso! ==="
