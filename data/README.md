# Datová složka

Tato složka obsahuje data pro analýzu cen tepelné energie.

## Struktura

- `pdf/` - složka pro ukládání původních PDF souborů z ERÚ
  - Soubory by měly být pojmenovány ve formátu `vyslednecenytepla{rok}.pdf`
  - Například: `vyslednecenytepla2023.pdf`

- `csv/` - složka pro ukládání extrahovaných dat v CSV formátu
  - Soubory jsou generovány automaticky skriptem pro extrakci dat
  - Pro každý rok je vytvořen samostatný soubor `ceny_tepla_{rok}.csv`
  - Souhrnný soubor `ceny_tepla_vsechny_roky.csv` obsahuje data ze všech let

## Použití

1. Umístěte PDF soubory do složky `pdf/`
2. Spusťte skript pro extrakci dat: `python src/data_extraction/extract_pdf_data.py`
3. Extrahovaná data budou uložena do složky `csv/`

## Poznámky

- PDF soubory a CSV soubory nejsou verzovány v Gitu (jsou uvedeny v `.gitignore`)
- Pro zachování struktury složek jsou v repozitáři pouze prázdné `.gitkeep` soubory