#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skript pro import dat o cenách tepla do databáze.
"""

import os
import pandas as pd
import mysql.connector
from mysql.connector import Error
import logging
from pathlib import Path
import dotenv
import sys

# Načtení proměnných prostředí z .env souboru
dotenv.load_dotenv()

# Nastavení loggeru
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("database_import.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def vytvor_spojeni_s_databazi():
    """
    Vytvoří spojení s MySQL databází.
    
    Returns:
        mysql.connector.connection.MySQLConnection: Spojení s databází nebo None v případě chyby
    """
    try:
        spojeni = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'ceny_tepla_db'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '')
        )
        if spojeni.is_connected():
            logger.info(f"Připojeno k MySQL databázi: {os.getenv('DB_NAME', 'ceny_tepla_db')}")
            return spojeni
    except Error as e:
        logger.error(f"Chyba při připojení k MySQL databázi: {e}")
    return None

def vytvor_databazove_tabulky(spojeni):
    """
    Vytvoří potřebné tabulky v databázi.
    
    Args:
        spojeni (mysql.connector.connection.MySQLConnection): Spojení s databází
    """
    if not spojeni:
        return
    
    kurzor = spojeni.cursor()
    
    try:
        # Vytvoření tabulky Kraje
        kurzor.execute("""
        CREATE TABLE IF NOT EXISTS Kraje (
            KodKraje CHAR(1) PRIMARY KEY,
            NazevKraje VARCHAR(100) NOT NULL
        )
        """)
        
        # Vytvoření tabulky Lokality
        kurzor.execute("""
        CREATE TABLE IF NOT EXISTS Lokality (
            LokalitaID INT PRIMARY KEY AUTO_INCREMENT,
            NazevLokality VARCHAR(255) NOT NULL,
            KodKraje CHAR(1),
            FOREIGN KEY (KodKraje) REFERENCES Kraje(KodKraje)
        )
        """)
        
        # Vytvoření tabulky Roky
        kurzor.execute("""
        CREATE TABLE IF NOT EXISTS Roky (
            RokID INT PRIMARY KEY AUTO_INCREMENT,
            Rok INT NOT NULL UNIQUE
        )
        """)
        
        # Vytvoření tabulky TypyDodavek
        kurzor.execute("""
        CREATE TABLE IF NOT EXISTS TypyDodavek (
            TypDodavkyID INT PRIMARY KEY AUTO_INCREMENT,
            NazevTypuDodavky VARCHAR(255) NOT NULL UNIQUE,
            Popis TEXT
        )
        """)
        
        # Vytvoření hlavní datové tabulky
        kurzor.execute("""
        CREATE TABLE IF NOT EXISTS CenyTepla (
            DataID INT PRIMARY KEY AUTO_INCREMENT,
            LokalitaID INT,
            RokID INT,
            TypDodavkyID INT,
            InstalovanyVykon DECIMAL(10,3),
            PocetOdbernychMist INT,
            PocetOdberatelu INT,
            Cena DECIMAL(10,2),
            Mnozstvi DECIMAL(10,2),
            UhliProcento DECIMAL(5,2),
            BiomasaProcento DECIMAL(5,2),
            OdpadProcento DECIMAL(5,2),
            ZemniPlynProcento DECIMAL(5,2),
            JinaPalivaProcento DECIMAL(5,2),
            FOREIGN KEY (LokalitaID) REFERENCES Lokality(LokalitaID),
            FOREIGN KEY (RokID) REFERENCES Roky(RokID),
            FOREIGN KEY (TypDodavkyID) REFERENCES TypyDodavek(TypDodavkyID)
        )
        """)
        
        # Vytvoření indexů pro zrychlení dotazů
        kurzor.execute("CREATE INDEX IF NOT EXISTS idx_lokalita_rok ON CenyTepla(LokalitaID, RokID)")
        kurzor.execute("CREATE INDEX IF NOT EXISTS idx_typ_dodavky ON CenyTepla(TypDodavkyID)")
        kurzor.execute("CREATE INDEX IF NOT EXISTS idx_cena ON CenyTepla(Cena)")
        kurzor.execute("CREATE INDEX IF NOT EXISTS idx_mnozstvi ON CenyTepla(Mnozstvi)")
        
        spojeni.commit()
        logger.info("Databázové tabulky byly úspěšně vytvořeny")
    except Error as e:
        logger.error(f"Chyba při vytváření databázových tabulek: {e}")
        spojeni.rollback()
    finally:
        kurzor.close()

def inicializuj_databazi(spojeni):
    """
    Inicializuje databázi - naplní základní tabulky.
    
    Args:
        spojeni (mysql.connector.connection.MySQLConnection): Spojení s databází
    """
    if not spojeni:
        return
    
    kurzor = spojeni.cursor()
    
    try:
        # Vložení krajů
        kraje = [
            ('B', 'Jihomoravský kraj'),
            ('C', 'Jihočeský kraj'),
            ('E', 'Pardubický kraj'),
            ('H', 'Královéhradecký kraj'),
            ('J', 'Vysočina'),
            ('K', 'Karlovarský kraj'),
            ('L', 'Liberecký kraj'),
            ('M', 'Olomoucký kraj'),
            ('P', 'Plzeňský kraj'),
            ('S', 'Středočeský kraj'),
            ('T', 'Moravskoslezský kraj'),
            ('U', 'Ústecký kraj'),
            ('Z', 'Zlínský kraj')
        ]
        
        kurzor.executemany(
            "INSERT IGNORE INTO Kraje (KodKraje, NazevKraje) VALUES (%s, %s)",
            kraje
        )
        
        # Vložení typů dodávek
        typy_dodavek = [
            ("Dodávky z výroby při výkonu nad 10 MWt", "Dodávky tepelné energie z výrobních zařízení s instalovaným výkonem nad 10 MWt"),
            ("Dodávky z výroby při výkonu do 10 MWt", "Dodávky tepelné energie z výrobních zařízení s instalovaným výkonem do 10 MWt"),
            ("Dodávky z primárního rozvodu", "Dodávky tepelné energie z primárního rozvodu"),
            ("Dodávky z rozvodů z blokové kotelny", "Dodávky tepelné energie z rozvodů z blokové kotelny"),
            ("Dodávky ze sekundárních rozvodů", "Dodávky tepelné energie ze sekundárních rozvodů"),
            ("Dodávky z domovní předávací stanice", "Dodávky tepelné energie z domovní předávací stanice"),
            ("Dodávky z domovní kotelny", "Dodávky tepelné energie z domovní kotelny"),
            ("Dodávky pro centrální přípravu teplé vody na zdroji", "Dodávky tepelné energie pro centrální přípravu teplé vody na zdroji"),
            ("Dodávky z centrální výměníkové stanice (CVS)", "Dodávky tepelné energie z centrální výměníkové stanice"),
            ("Dodávky pro centrální přípravu teplé vody na CVS", "Dodávky tepelné energie pro centrální přípravu teplé vody na centrální výměníkové stanici")
        ]
        
        kurzor.executemany(
            "INSERT IGNORE INTO TypyDodavek (NazevTypuDodavky, Popis) VALUES (%s, %s)",
            typy_dodavek
        )
        
        spojeni.commit()
        logger.info("Základní data byla úspěšně vložena do databáze")
    except Error as e:
        logger.error(f"Chyba při inicializaci databáze: {e}")
        spojeni.rollback()
    finally:
        kurzor.close()

def importuj_data_do_databaze(spojeni, csv_soubor):
    """
    Importuje data z CSV souboru do databáze.
    
    Args:
        spojeni (mysql.connector.connection.MySQLConnection): Spojení s databází
        csv_soubor (str): Cesta k CSV souboru s daty
    """
    if not spojeni:
        return
    
    logger.info(f"Začínám import dat z CSV souboru: {csv_soubor}")
    
    try:
        # Načtení dat z CSV
        data = pd.read_csv(csv_soubor, encoding='utf-8')
        logger.info(f"Načteno {len(data)} záznamů z CSV souboru")
    except Exception as e:
        logger.error(f"Chyba při načítání CSV souboru: {e}")
        return
    
    kurzor = spojeni.cursor()
    
    try:
        # Vložení roků
        unikatni_roky = data['Rok'].unique()
        for rok in unikatni_roky:
            kurzor.execute(
                "INSERT IGNORE INTO Roky (Rok) VALUES (%s)",
                (int(rok),)
            )
        
        # Získání ID roků
        kurzor.execute("SELECT RokID, Rok FROM Roky")
        roky_mapping = {rok: rok_id for rok_id, rok in kurzor.fetchall()}
        
        # Vložení lokalit a získání jejich ID
        unikatni_lokality = data[['Lokalita', 'Kod_kraje']].drop_duplicates()
        for _, row in unikatni_lokality.iterrows():
            kurzor.execute(
                "INSERT IGNORE INTO Lokality (NazevLokality, KodKraje) VALUES (%s, %s)",
                (row['Lokalita'], row['Kod_kraje'])
            )
        
        # Získání ID lokalit
        kurzor.execute("SELECT LokalitaID, NazevLokality FROM Lokality")
        lokality_mapping = {nazev: lokalita_id for lokalita_id, nazev in kurzor.fetchall()}
        
        # Získání ID typů dodávek
        kurzor.execute("SELECT TypDodavkyID, NazevTypuDodavky FROM TypyDodavek")
        typy_dodavek_mapping = {nazev: typ_id for typ_id, nazev in kurzor.fetchall()}
        
        # Vložení hlavních dat
        pocet_vlozenych = 0
        for _, row in data.iterrows():
            lokalita_id = lokality_mapping.get(row['Lokalita'])
            rok_id = roky_mapping.get(row['Rok'])
            typ_dodavky_id = typy_dodavek_mapping.get(row['Typ_dodavky'])
            
            if lokalita_id and rok_id and typ_dodavky_id:
                kurzor.execute(
                    """
                    INSERT INTO CenyTepla (
                        LokalitaID, RokID, TypDodavkyID, InstalovanyVykon, 
                        PocetOdbernychMist, PocetOdberatelu, Cena, Mnozstvi,
                        UhliProcento, BiomasaProcento, OdpadProcento, 
                        ZemniPlynProcento, JinaPalivaProcento
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        lokalita_id, rok_id, typ_dodavky_id, row['Instalovany_vykon'],
                        row['Pocet_odbernych_mist'], row['Pocet_odberatelu'], 
                        row['Cena'], row['Mnozstvi'],
                        row['Uhli_procento'], row['Biomasa_procento'], row['Odpad_procento'],
                        row['Zemni_plyn_procento'], row['Jina_paliva_procento']
                    )
                )
                pocet_vlozenych += 1
        
        spojeni.commit()
        logger.info(f"Data byla úspěšně importována do databáze. Vloženo {pocet_vlozenych} záznamů.")
    except Error as e:
        logger.error(f"Chyba při importu dat do databáze: {e}")
        spojeni.rollback()
    finally:
        kurzor.close()

def main():
    """Hlavní funkce pro spuštění importu dat do databáze."""
    # Cesty k adresářům
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    CSV_DIR = BASE_DIR / "data" / "csv"
    
    # Kontrola existence CSV souborů
    csv_soubor = CSV_DIR / "ceny_tepla_vsechny_roky.csv"
    if not csv_soubor.exists():
        logger.error(f"CSV soubor {csv_soubor} neexistuje. Nejprve spusťte extrakci dat z PDF.")
        sys.exit(1)
    
    # Vytvoření spojení s databází
    spojeni = vytvor_spojeni_s_databazi()
    if not spojeni:
        logger.error("Nelze pokračovat bez připojení k databázi.")
        sys.exit(1)
    
    try:
        # Vytvoření databázových tabulek
        vytvor_databazove_tabulky(spojeni)
        
        # Inicializace databáze
        inicializuj_databazi(spojeni)
        
        # Import dat
        importuj_data_do_databaze(spojeni, str(csv_soubor))
    finally:
        if spojeni.is_connected():
            spojeni.close()
            logger.info("Spojení s databází bylo uzavřeno.")

if __name__ == "__main__":
    main()