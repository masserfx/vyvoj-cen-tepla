#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skript pro extrakci dat o cenách tepla z PDF souborů ERÚ.
"""

import os
import re
import pandas as pd
import pdfplumber
import logging
from pathlib import Path

# Nastavení loggeru
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def extrahuj_data_z_pdf(cesta_k_pdf, rok):
    """
    Extrahuje data o cenách tepla z PDF souboru pro konkrétní rok.
    
    Args:
        cesta_k_pdf (str): Cesta k PDF souboru
        rok (int): Rok, ke kterému se data vztahují
        
    Returns:
        pandas.DataFrame: DataFrame s extrahovanými daty
    """
    logger.info(f"Začínám extrakci dat z PDF souboru {cesta_k_pdf} pro rok {rok}")
    
    vsechny_radky = []
    
    try:
        with pdfplumber.open(cesta_k_pdf) as pdf:
            pocet_stranek = len(pdf.pages)
            logger.info(f"PDF má {pocet_stranek} stránek")
            
            for cislo_stranky, stranka in enumerate(pdf.pages, 1):
                logger.info(f"Zpracovávám stránku {cislo_stranky}/{pocet_stranek}")
                
                # Extrakce textu se zachováním rozložení
                text = stranka.extract_text()
                
                # Rozdělení na řádky a odstranění hlaviček
                radky = text.split('\n')
                datove_radky = []
                
                # Zpracování řádků - hledáme řádky začínající názvem lokality
                for radek in radky:
                    # Přeskočíme hlavičky a prázdné řádky
                    if not radek or "Cenová lokalita" in radek or "Dodávky" in radek:
                        continue
                    
                    # Pokud řádek začíná názvem lokality (začíná písmenem)
                    if re.match(r'^[A-Za-zÁ-Žá-ž]', radek.strip()):
                        datove_radky.append(radek)
                
                # Zpracování datových řádků
                for radek in datove_radky:
                    try:
                        # Rozdělení řádku na části
                        casti = radek.split()
                        
                        # Extrakce názvu lokality (může obsahovat více slov)
                        lokalita = ""
                        i = 0
                        while i < len(casti) and not re.match(r'^[A-Z]$', casti[i]):  # Hledáme kód kraje (jedno velké písmeno)
                            lokalita += casti[i] + " "
                            i += 1
                        
                        lokalita = lokalita.strip()
                        
                        # Pokud jsme nenašli validní lokalitu, přeskočíme řádek
                        if not lokalita or i >= len(casti):
                            continue
                        
                        # Kód kraje
                        kod_kraje = casti[i]
                        i += 1
                        
                        # Extrakce procentuálního zastoupení paliv
                        # Toto bude potřeba upravit podle přesného formátu dat
                        try:
                            uhli_procento = float(casti[i]) if i < len(casti) and re.match(r'^\d+(\.\d+)?$', casti[i]) else 0.0
                            i += 1
                            biomasa_procento = float(casti[i]) if i < len(casti) and re.match(r'^\d+(\.\d+)?$', casti[i]) else 0.0
                            i += 1
                            odpad_procento = float(casti[i]) if i < len(casti) and re.match(r'^\d+(\.\d+)?$', casti[i]) else 0.0
                            i += 1
                            zemni_plyn_procento = float(casti[i]) if i < len(casti) and re.match(r'^\d+(\.\d+)?$', casti[i]) else 0.0
                            i += 1
                            jina_paliva_procento = float(casti[i]) if i < len(casti) and re.match(r'^\d+(\.\d+)?$', casti[i]) else 0.0
                            i += 1
                        except (ValueError, IndexError):
                            # Pokud narazíme na problém s extrakcí, nastavíme výchozí hodnoty
                            uhli_procento = biomasa_procento = odpad_procento = zemni_plyn_procento = jina_paliva_procento = 0.0
                        
                        # Extrakce instalovaného výkonu, počtu odběrných míst a odběratelů
                        try:
                            instalovany_vykon = float(casti[i]) if i < len(casti) else None
                            i += 1
                            pocet_odbernych_mist = int(casti[i]) if i < len(casti) else None
                            i += 1
                            pocet_odberatelu = int(casti[i]) if i < len(casti) else None
                            i += 1
                        except (ValueError, IndexError):
                            instalovany_vykon = pocet_odbernych_mist = pocet_odberatelu = None
                        
                        # Extrakce cen a množství pro různé typy dodávek
                        typy_dodavek = [
                            "Dodávky z výroby při výkonu nad 10 MWt",
                            "Dodávky z výroby při výkonu do 10 MWt",
                            "Dodávky z primárního rozvodu",
                            "Dodávky z rozvodů z blokové kotelny",
                            "Dodávky ze sekundárních rozvodů",
                            "Dodávky z domovní předávací stanice",
                            "Dodávky z domovní kotelny",
                            "Dodávky pro centrální přípravu teplé vody na zdroji",
                            "Dodávky z centrální výměníkové stanice (CVS)",
                            "Dodávky pro centrální přípravu teplé vody na CVS"
                        ]
                        
                        # Pro každý typ dodávky extrahujeme cenu a množství
                        for typ_dodavky in typy_dodavek:
                            try:
                                cena = float(casti[i]) if i < len(casti) else None
                                i += 1
                                mnozstvi = float(casti[i]) if i < len(casti) else None
                                i += 1
                            except (ValueError, IndexError):
                                cena = mnozstvi = None
                            
                            # Přidáme záznam do seznamu
                            if cena is not None and mnozstvi is not None:
                                vsechny_radky.append({
                                    'Rok': rok,
                                    'Lokalita': lokalita,
                                    'Kod_kraje': kod_kraje,
                                    'Uhli_procento': uhli_procento,
                                    'Biomasa_procento': biomasa_procento,
                                    'Odpad_procento': odpad_procento,
                                    'Zemni_plyn_procento': zemni_plyn_procento,
                                    'Jina_paliva_procento': jina_paliva_procento,
                                    'Instalovany_vykon': instalovany_vykon,
                                    'Pocet_odbernych_mist': pocet_odbernych_mist,
                                    'Pocet_odberatelu': pocet_odberatelu,
                                    'Typ_dodavky': typ_dodavky,
                                    'Cena': cena,
                                    'Mnozstvi': mnozstvi
                                })
                    except Exception as e:
                        logger.error(f"Chyba při zpracování řádku: {radek}")
                        logger.error(f"Detaily chyby: {str(e)}")
    
    except Exception as e:
        logger.error(f"Chyba při otevírání PDF souboru: {str(e)}")
        return pd.DataFrame()
    
    # Vytvoření DataFrame z extrahovaných dat
    df = pd.DataFrame(vsechny_radky)
    
    logger.info(f"Extrakce dokončena. Získáno {len(df)} záznamů.")
    
    return df

def zpracuj_vsechny_pdf(adresar_pdf, adresar_csv):
    """
    Zpracuje všechny PDF soubory s cenami tepla v daném adresáři.
    
    Args:
        adresar_pdf (str): Cesta k adresáři s PDF soubory
        adresar_csv (str): Cesta k adresáři pro uložení CSV souborů
    """
    logger.info(f"Začínám zpracování všech PDF souborů v adresáři {adresar_pdf}")
    
    # Vytvoření adresáře pro CSV soubory, pokud neexistuje
    os.makedirs(adresar_csv, exist_ok=True)
    
    # Zpracování všech PDF souborů
    vsechna_data = pd.DataFrame()
    
    for soubor in os.listdir(adresar_pdf):
        if soubor.startswith("vyslednecenytepla") and soubor.endswith(".pdf"):
            # Extrakce roku z názvu souboru
            rok_match = re.search(r'vyslednecenytepla(\d{4})\.pdf', soubor)
            if rok_match:
                rok = int(rok_match.group(1))
                cesta_k_souboru = os.path.join(adresar_pdf, soubor)
                logger.info(f"Zpracovávám soubor {soubor} pro rok {rok}...")
                
                # Extrakce dat z PDF
                data_roku = extrahuj_data_z_pdf(cesta_k_souboru, rok)
                
                # Uložení dat pro konkrétní rok do CSV
                if not data_roku.empty:
                    nazev_csv = f"ceny_tepla_{rok}.csv"
                    cesta_k_csv = os.path.join(adresar_csv, nazev_csv)
                    data_roku.to_csv(cesta_k_csv, index=False, encoding='utf-8')
                    logger.info(f"Data pro rok {rok} byla uložena do souboru {nazev_csv}")
                
                # Přidání dat do celkového DataFrame
                vsechna_data = pd.concat([vsechna_data, data_roku])
    
    # Uložení všech dat do jednoho CSV souboru
    if not vsechna_data.empty:
        cesta_k_csv = os.path.join(adresar_csv, "ceny_tepla_vsechny_roky.csv")
        vsechna_data.to_csv(cesta_k_csv, index=False, encoding='utf-8')
        logger.info(f"Všechna data byla uložena do souboru {cesta_k_csv}")
    
    logger.info("Zpracování všech PDF souborů dokončeno.")

def main():
    """Hlavní funkce pro spuštění extrakce dat."""
    # Cesty k adresářům
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    PDF_DIR = BASE_DIR / "data" / "pdf"
    CSV_DIR = BASE_DIR / "data" / "csv"
    
    # Vytvoření adresářů, pokud neexistují
    os.makedirs(PDF_DIR, exist_ok=True)
    
    # Zpracování všech PDF souborů
    zpracuj_vsechny_pdf(PDF_DIR, CSV_DIR)

if __name__ == "__main__":
    main()