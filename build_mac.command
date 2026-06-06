#!/bin/bash
# FHNW Modulplaner — baut die eigenständige macOS-App (.app) per PyInstaller.
# Doppelklick oder im Terminal ausführen. Ergebnis: dist/Modulplaner.app
set -e

cd "$(dirname "$0")" || exit 1

echo "Richte Build-Umgebung ein ..."
if [ ! -d ".build-venv" ]; then
  python3 -m venv .build-venv
fi
source .build-venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt -r requirements-dev.txt

echo "Baue Modulplaner.app ..."
rm -rf build dist
pyinstaller --noconfirm modulplaner.spec

echo ""
echo "Fertig: dist/Modulplaner.app"
echo "Zum Verteilen: dist/Modulplaner.app als ZIP weitergeben."
echo "(Erststart: Rechtsklick -> Öffnen, wegen unsignierter App.)"
