#!/bin/bash

# Nastavení cesty k projektu
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Kontrola existence virtuálního prostředí
if [ ! -d "venv" ]; then
    echo "Vytvářím virtuální prostředí..."
    python -m venv venv
fi

# Aktivace virtuálního prostředí
source venv/bin/activate

# Kontrola a instalace potřebných knihoven
echo "Kontrola a instalace potřebných knihoven..."
pip install -r requirements.txt

# Pokus o instalaci geopandas (volitelné)
echo "Pokus o instalaci geopandas (volitelné)..."
pip install geopandas || echo "Nepodařilo se nainstalovat geopandas, ale dashboard bude fungovat i bez něj."

# Pokus o instalaci AI knihoven (volitelné)
echo "Pokus o instalaci AI knihoven (volitelné)..."
pip install scikit-learn statsmodels prophet || echo "Nepodařilo se nainstalovat některé AI knihovny. Pokročilé funkce nemusí být dostupné."

# Kontrola instalovaného Pythonu a knihoven
echo "Používám Python: $(which python)"
echo "PYTHONPATH: $PYTHONPATH"
echo "Nainstalované knihovny:"
pip list | grep -E "dash|geopandas|numpy|pandas|plotly|scikit-learn|statsmodels|prophet"

# Spuštění dashboardu
echo "Spouštím dashboard..."
python src/visualization/dashboard.py 