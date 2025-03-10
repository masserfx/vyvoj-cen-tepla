#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Skript pro analýzu dat pro mapu.
"""

import pandas as pd
import json
from pathlib import Path

# Načtení dat
df_path = Path('data/csv/ceny_tepla_vsechny_roky.csv')
df = pd.read_csv(df_path)
print(f"Počet řádků v datech: {len(df)}")
print(f"Počet unikátních lokalit v datech: {df['Lokalita'].nunique()}")
print(f"Počet unikátních krajů v datech: {df['Kod_kraje'].nunique()}")
print(f"Unikátní kódy krajů: {sorted(df['Kod_kraje'].unique())}")

# Načtení mapování lokalit
map_path = Path('data/geo/mapovani_lokalit.json')
with open(map_path, 'r', encoding='utf-8') as f:
    mapovani_lokalit = json.load(f)
print(f"Počet lokalit v mapování: {len(mapovani_lokalit)}")

# Vytvoření rozšířeného mapování
unikatni_kombinace = df[['Lokalita', 'Kod_kraje']].drop_duplicates()
print(f"Počet unikátních kombinací lokalita-kraj: {len(unikatni_kombinace)}")

rozsirene_mapovani = {}
for _, row in unikatni_kombinace.iterrows():
    lokalita = row['Lokalita']
    kod_kraje = row['Kod_kraje']
    klic = f"{lokalita}|{kod_kraje}"
    
    if lokalita in mapovani_lokalit:
        rozsirene_mapovani[klic] = mapovani_lokalit[lokalita]

print(f"Počet položek v rozšířeném mapování: {len(rozsirene_mapovani)}")
print(f"Procento pokrytí: {len(rozsirene_mapovani) / len(unikatni_kombinace) * 100:.2f}%")

# Analýza chybějících souřadnic
chybejici_lokality = []
for _, row in unikatni_kombinace.iterrows():
    lokalita = row['Lokalita']
    kod_kraje = row['Kod_kraje']
    klic = f"{lokalita}|{kod_kraje}"
    
    if klic not in rozsirene_mapovani and lokalita not in mapovani_lokalit:
        chybejici_lokality.append((lokalita, kod_kraje))

print(f"Počet lokalit bez souřadnic: {len(chybejici_lokality)}")
if chybejici_lokality:
    print("Ukázka prvních 10 lokalit bez souřadnic:")
    for lokalita, kod_kraje in chybejici_lokality[:10]:
        print(f"  - {lokalita} (kraj: {kod_kraje})")

# Analýza filtrů
print("\nAnalýza filtrů:")
print(f"Počet unikátních typů dodávky: {df['Typ_dodavky'].nunique()}")
print(f"Unikátní typy dodávky: {sorted(df['Typ_dodavky'].unique())}")

if 'Palivo' in df.columns:
    print(f"Počet unikátních paliv: {df['Palivo'].nunique()}")
    print(f"Unikátní paliva: {sorted(df['Palivo'].unique())}")
else:
    print("Sloupec 'Palivo' není v datech.")
    print("Dostupné sloupce s procenty paliv:")
    for col in df.columns:
        if 'procento' in col.lower():
            print(f"  - {col}")

# Analýza výkonu
print("\nAnalýza instalovaného výkonu:")
print(f"Minimální výkon: {df['Instalovany_vykon'].min()}")
print(f"Maximální výkon: {df['Instalovany_vykon'].max()}")
print(f"Průměrný výkon: {df['Instalovany_vykon'].mean():.2f}")
print(f"Medián výkonu: {df['Instalovany_vykon'].median():.2f}")

# Analýza cen
print("\nAnalýza cen:")
print(f"Minimální cena: {df['Cena'].min():.2f}")
print(f"Maximální cena: {df['Cena'].max():.2f}")
print(f"Průměrná cena: {df['Cena'].mean():.2f}")
print(f"Medián ceny: {df['Cena'].median():.2f}")

# Analýza dat pro mapu
print("\nAnalýza dat pro mapu:")
# Filtrování dat podle výchozích filtrů
filtrovana_data = df.copy()
# Agregace dat podle lokalit
lokality_data = filtrovana_data.groupby(['Lokalita', 'Kod_kraje'])['Cena'].mean().reset_index()
# Přidání souřadnic
lokality_data['lat'] = None
lokality_data['lon'] = None
for idx, row in lokality_data.iterrows():
    lokalita = row['Lokalita']
    kod_kraje = row['Kod_kraje']
    klic = f"{lokalita}|{kod_kraje}"
    
    if klic in rozsirene_mapovani:
        lokality_data.at[idx, 'lat'] = rozsirene_mapovani[klic].get('lat')
        lokality_data.at[idx, 'lon'] = rozsirene_mapovani[klic].get('lon')
    elif lokalita in mapovani_lokalit:
        lokality_data.at[idx, 'lat'] = mapovani_lokalit[lokalita].get('lat')
        lokality_data.at[idx, 'lon'] = mapovani_lokalit[lokalita].get('lon')

# Filtrování pouze lokalit, pro které máme souřadnice
lokality_s_souradnicemi = lokality_data.dropna(subset=['lat', 'lon'])
print(f"Počet lokalit s cenami: {len(lokality_data)}")
print(f"Počet lokalit s cenami a souřadnicemi: {len(lokality_s_souradnicemi)}")
print(f"Procento lokalit s cenami a souřadnicemi: {len(lokality_s_souradnicemi) / len(lokality_data) * 100:.2f}%")

# Analýza podle krajů
print("\nAnalýza podle krajů:")
kraje_stats = lokality_data.groupby('Kod_kraje').agg(
    pocet_lokalit=('Lokalita', 'nunique'),
    pocet_lokalit_s_souradnicemi=('lat', lambda x: x.notna().sum()),
    prumerna_cena=('Cena', 'mean')
).reset_index()
kraje_stats['procento_pokryti'] = kraje_stats['pocet_lokalit_s_souradnicemi'] / kraje_stats['pocet_lokalit'] * 100
print(kraje_stats.sort_values('procento_pokryti', ascending=False).to_string(index=False)) 