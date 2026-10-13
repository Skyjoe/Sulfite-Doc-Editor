#!/bin/bash

echo "=== Instalando o Sulfite Doc Studio ==="

# 1. Detecta e instala dependências do sistema operacional
if command -v apt &> /dev/null; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv poppler-utils tesseract-ocr tesseract-ocr-por libxcb-cursor0
elif command -v dnf &> /dev/null; then
    sudo dnf install -y python3 python3-pip poppler-utils tesseract tesseract-langpack-por
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm python python-pip poppler tesseract tesseract-data-por
fi

# 2. Cria e ativa o ambiente virtual do Python
DIR_ATUAL=$(pwd)
python3 -m venv venv
source venv/bin/activate

# 3. Instala as bibliotecas Python necessárias
pip install PyQt6 pypdf pdf2image pytesseract Pillow reportlab

# 4. Cria o script de execução local
cat <<EOF > executar.sh
#!/bin/bash
cd "$DIR_ATUAL"
source venv/bin/activate
python3 word4.py
EOF
chmod +x executar.sh

# 5. Cria o atalho oficial no Menu do Linux do usuário
PASTA_ATALHOS="$HOME/.local/share/applications"
mkdir -p "$PASTA_ATALHOS"

cat <<EOF > "$PASTA_ATALHOS/sulfite.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Sulfite Doc Studio
Comment=Editor de Texto e Estúdio de PDF
Exec=$DIR_ATUAL/executar.sh
Icon=libreoffice-writer
Terminal=false
Categories=Office;Utility;
EOF

chmod +x "$PASTA_ATALHOS/sulfite.desktop"
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$PASTA_ATALHOS"
fi

echo "=== Instalação Concluída! ==="
echo "O aplicativo 'Sulfite Doc Studio' já está disponível no Menu de Aplicativos do sistema."