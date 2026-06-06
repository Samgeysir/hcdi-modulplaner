#!/bin/bash
# FHNW Modulplaner — Doppelklick-Starter (macOS)
# Startet den lokalen Server und öffnet das Dashboard im Browser.

cd "$(dirname "$0")" || exit 1

# Virtuelle Umgebung anlegen/aktivieren (einmalig), Abhängigkeiten installieren
if [ ! -d ".venv" ]; then
  echo "Erstelle virtuelle Umgebung und installiere Abhängigkeiten ..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --quiet --upgrade pip
  pip install --quiet -r requirements.txt
else
  source .venv/bin/activate
fi

echo ""
echo "Starte FHNW Modulplaner auf http://localhost:8000 ..."
echo "(Fenster offen lassen. Zum Beenden: Strg+C)"
echo ""
python app.py
