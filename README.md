# Vývoj cen tepla v ČR

Projekt pro analýzu a vizualizaci vývoje cen tepelné energie v České republice podle lokalit, krajů, typů paliva a způsobů dodávky.

## Popis projektu

Tento projekt se zaměřuje na zpracování dat o cenách tepelné energie z PDF souborů publikovaných Energetickým regulačním úřadem (ERÚ) a jejich vizualizaci pro účely analýzy trendů a porovnání.

### Hlavní funkce

- Extrakce dat z PDF souborů s cenami tepla pro jednotlivé roky
- Ukládání dat do relační databáze
- Interaktivní dashboard pro vizualizaci a analýzu dat
- Možnost filtrování podle lokalit, krajů, typů paliva a způsobů dodávky
- Analýza vývoje cen v čase
- Porovnání cen mezi různými lokalitami a kraji
- Analýza vlivu typu paliva na cenu tepla

## Struktura projektu

- `src/` - zdrojové kódy
  - `data_extraction/` - skripty pro extrakci dat z PDF souborů
  - `database/` - skripty pro práci s databází
  - `dashboard/` - kód pro interaktivní dashboard
- `data/` - složka pro ukládání dat
  - `pdf/` - původní PDF soubory
  - `csv/` - extrahovaná data v CSV formátu
- `docs/` - dokumentace
- `requirements.txt` - seznam závislostí

## Instalace a spuštění

### Požadavky

- Python 3.8+
- MySQL nebo jiná relační databáze
- Knihovny uvedené v `requirements.txt`

### Instalace

1. Naklonujte repozitář:
   ```
   git clone https://github.com/masserfx/vyvoj-cen-tepla.git
   cd vyvoj-cen-tepla
   ```

2. Vytvořte a aktivujte virtuální prostředí:
   ```
   python -m venv venv
   source venv/bin/activate  # Pro Windows: venv\Scripts\activate
   ```

3. Nainstalujte závislosti:
   ```
   pip install -r requirements.txt
   ```

4. Nastavte připojení k databázi v souboru `config.py`

### Použití

1. Extrakce dat z PDF souborů:
   ```
   python src/data_extraction/extract_pdf_data.py
   ```

2. Import dat do databáze:
   ```
   python src/database/import_data.py
   ```

3. Spuštění dashboardu:
   ```
   python src/dashboard/app.py
   ```

4. Otevřete prohlížeč na adrese `http://localhost:8050`

## Licence

Tento projekt je licencován pod MIT licencí - viz soubor [LICENSE](LICENSE) pro více informací.