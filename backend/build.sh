#!/usr/bin/env bash
set -e

echo "=== 1. Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== 2. Checking / Installing Tesseract OCR ==="
if command -v tesseract >/dev/null 2>&1; then
    echo "Tesseract found on system PATH: $(command -v tesseract)"
    tesseract --version
elif [ -f ".tesseract/squashfs-root/AppRun" ]; then
    echo "Portable Tesseract already unpacked in .tesseract/squashfs-root"
    chmod +x .tesseract/squashfs-root/AppRun .tesseract/squashfs-root/usr/bin/tesseract
    ./.tesseract/squashfs-root/AppRun --version || true
else
    echo "Tesseract not installed system-wide. Setting up portable Tesseract for Linux..."
    mkdir -p .tesseract
    cd .tesseract
    echo "Downloading tesseract-5.4.1-x86_64.AppImage..."
    curl -fsSL -o tesseract.AppImage "https://github.com/AlexanderP/tesseract-appimage/releases/download/v5.4.1/tesseract-5.4.1-x86_64.AppImage"
    chmod +x tesseract.AppImage
    echo "Extracting portable Tesseract engine..."
    ./tesseract.AppImage --appimage-extract
    rm -f tesseract.AppImage
    chmod +x squashfs-root/AppRun squashfs-root/usr/bin/tesseract
    echo "Portable Tesseract ready at backend/.tesseract/squashfs-root/AppRun"
    ./squashfs-root/AppRun --version || true
    cd ..
fi
