#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Webový dashboard pro vizualizaci vývoje cen tepla.
"""

import os
import pandas as pd
import numpy as np
import json
from pathlib import Path
import dash
from dash import dcc, html, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go

# Import AI forecasting module
try:
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from src.ai.forecasting import forecast_heat_prices, detect_anomalies, analyze_trends, analyze_correlations
    AI_FORECASTING_AVAILABLE = True
    print("AI forecasting module successfully imported.")
except ImportError as e:
    AI_FORECASTING_AVAILABLE = False
    print(f"AI forecasting module not available: {e}. AI features will be disabled.")

# Pokus o import geopandas - volitelný
try:
    import geopandas as gpd
    GEOPANDAS_AVAILABLE = True
    print("Knihovna geopandas byla úspěšně importována.")
except ImportError as e:
    print(f"Knihovna geopandas není k dispozici: {e}. Mapa nebude zobrazena.")
    print(f"Cesta k Pythonu: {os.sys.executable}")
    print(f"Cesta k knihovnám: {os.sys.path}")
    GEOPANDAS_AVAILABLE = False

# Cesty k adresářům
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CSV_DIR = BASE_DIR / "data" / "csv"
GRAPHS_DIR = BASE_DIR / "data" / "graphs"
GEO_DIR = BASE_DIR / "data" / "geo"

# Cesta k CSV souboru se všemi daty
CSV_SOUBOR = CSV_DIR / "ceny_tepla_vsechny_roky.csv"
GEOJSON_SOUBOR = GEO_DIR / "kraje_cr.geojson"
MAPOVANI_LOKALIT_SOUBOR = GEO_DIR / "mapovani_lokalit.json"

# Inicializace aplikace
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server

# Načtení dat
def nacti_data():
    """Načte data o cenách tepla z CSV souboru."""
    try:
        print("Načítám data z CSV souboru:", CSV_SOUBOR)
        df = pd.read_csv(CSV_SOUBOR)
        print("Data načtena, počet řádků:", len(df))
        
        # Přidání sloupce Typ_ceny, pokud neexistuje nebo obsahuje NaN hodnoty
        if 'Typ_ceny' not in df.columns:
            df['Typ_ceny'] = 'Výsledná'
        else:
            # Nahrazení NaN hodnot ve sloupci Typ_ceny hodnotou 'Výsledná'
            df['Typ_ceny'] = df['Typ_ceny'].fillna('Výsledná')
        
        # Označení předběžných cen pro rok 2024
        mask = df['Rok'] == 2024
        if mask.any():
            df.loc[mask, 'Typ_ceny'] = 'Předběžná'
        
        # Čištění dat
        df = df.dropna(subset=['Rok', 'Cena'])
        df['Rok'] = pd.to_numeric(df['Rok'], errors='coerce')
        df = df.dropna(subset=['Rok'])
        df['Rok'] = df['Rok'].astype(int)
        df['Cena'] = pd.to_numeric(df['Cena'], errors='coerce')
        df = df.dropna(subset=['Cena'])
        
        # Důkladné zpracování sloupce Instalovany_vykon
        print("Zpracovávám sloupec Instalovany_vykon")
        if 'Instalovany_vykon' in df.columns:
            # Převod na numerické hodnoty
            df['Instalovany_vykon'] = pd.to_numeric(df['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            df['Instalovany_vykon'] = df['Instalovany_vykon'].fillna(0)
            print("Počet chybějících hodnot v Instalovany_vykon po zpracování:", df['Instalovany_vykon'].isna().sum())
        else:
            # Pokud sloupec neexistuje, vytvoříme ho s výchozí hodnotou 0
            print("Sloupec Instalovany_vykon neexistuje, vytvářím ho")
            df['Instalovany_vykon'] = 0
        
        # Kontrola, zda máme sloupec Typ_dodavky
        if 'Typ_dodavky' not in df.columns:
            df['Typ_dodavky'] = 'Neznámý'
        
        print("Data úspěšně zpracována")
        return df
    except Exception as e:
        print(f"Chyba při načítání dat: {e}")
        # Vytvoření prázdného DataFrame se všemi potřebnými sloupci
        empty_df = pd.DataFrame(columns=['Rok', 'Lokalita', 'Kod_kraje', 'Uhli_procento', 
                                         'Biomasa_procento', 'Odpad_procento', 'Zemni_plyn_procento',
                                         'Jina_paliva_procento', 'Instalovany_vykon', 
                                         'Pocet_odbernych_mist', 'Pocet_odberatelu', 
                                         'Typ_dodavky', 'Cena', 'Mnozstvi', 'Typ_ceny'])
        return empty_df

# Načtení dat
df = nacti_data()

# Definice cest k souborům
GEO_DIR = Path(__file__).parent.parent.parent / 'data' / 'geo'
GEOJSON_SOUBOR = GEO_DIR / "kraje_cr.geojson"
MAPOVANI_LOKALIT_SOUBOR = GEO_DIR / "mapovani_lokalit.json"

# Načtení GeoJSON dat
try:
    # Cesta k GeoJSON souboru
    geojson_path = Path(__file__).parent.parent.parent / 'data' / 'geo' / 'kraje_cr.geojson'
    print(f"Pokus o načtení GeoJSON souboru: {geojson_path}")
    print(f"Soubor existuje: {geojson_path.exists()}")
    
    if not geojson_path.exists():
        print(f"GeoJSON soubor nebyl nalezen: {geojson_path}")
        geojson_data = None
    else:
        # Načtení GeoJSON souboru
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        print(f"GeoJSON soubor úspěšně načten, počet prvků: {len(geojson_data['features'])}")
except Exception as e:
    print(f"Chyba při načítání GeoJSON souboru: {e}")
    geojson_data = None

# Načtení mapování lokalit na souřadnice
def nacti_mapovani_lokalit():
    """Načte mapování lokalit na souřadnice z JSON souboru."""
    try:
        # Cesta k souboru s mapováním lokalit
        mapovani_path = Path(__file__).parent.parent.parent / 'data' / 'geo' / 'mapovani_lokalit.json'
        print(f"Pokus o načtení mapování lokalit: {mapovani_path}")
        
        if not mapovani_path.exists():
            print(f"Soubor s mapováním lokalit nebyl nalezen: {mapovani_path}")
            # Vytvoříme prázdné mapování
            return {}
        else:
            # Načtení souboru s mapováním
            with open(mapovani_path, 'r', encoding='utf-8') as f:
                mapovani_lokalit = json.load(f)
            
            print(f"Mapování lokalit úspěšně načteno, počet lokalit: {len(mapovani_lokalit)}")
            return mapovani_lokalit
    except Exception as e:
        print(f"Chyba při načítání mapování lokalit: {e}")
        # Vytvoříme prázdné mapování
        return {}

# Načtení mapování lokalit
mapovani_lokalit = nacti_mapovani_lokalit()

# Vytvoření rozšířeného mapování lokalit s informací o kraji
def vytvor_rozsirene_mapovani_lokalit(df, mapovani_lokalit):
    """
    Vytvoří rozšířené mapování lokalit, které obsahuje informaci o kraji.
    Klíč ve formátu 'lokalita|kod_kraje' -> {lat, lon}
    """
    # Vytvoření prázdného slovníku pro rozšířené mapování
    rozsirene_mapovani = {}
    
    # Kontrola, zda máme data
    if df.empty or 'Lokalita' not in df.columns or 'Kod_kraje' not in df.columns:
        print("Nelze vytvořit rozšířené mapování lokalit - chybí potřebná data")
        return rozsirene_mapovani
    
    # Získání unikátních kombinací lokalita-kraj
    unikatni_kombinace = df[['Lokalita', 'Kod_kraje']].drop_duplicates()
    
    # Vytvoření rozšířeného mapování
    for _, row in unikatni_kombinace.iterrows():
        lokalita = row['Lokalita']
        kod_kraje = row['Kod_kraje']
        
        # Vytvoříme klíč ve formátu 'lokalita|kod_kraje'
        klic = f"{lokalita}|{kod_kraje}"
        
        # Pokud lokalita existuje v původním mapování, použijeme její souřadnice
        if lokalita in mapovani_lokalit:
            rozsirene_mapovani[klic] = mapovani_lokalit[lokalita]
    
    print(f"Vytvořeno rozšířené mapování lokalit, počet položek: {len(rozsirene_mapovani)}")
    return rozsirene_mapovani

# Vytvoření rozšířeného mapování lokalit
rozsirene_mapovani_lokalit = vytvor_rozsirene_mapovani_lokalit(df, mapovani_lokalit)

# Získání všech typů dodávky z dat
typy_dodavky = ['Celkový průměr']
if 'Typ_dodavky' in df.columns:
    typy_dodavky.extend(sorted(df['Typ_dodavky'].unique().tolist()))

# Získání minimální a maximální ceny tepla z dat
cena_sloupec = 'Cena_tepla' if 'Cena_tepla' in df.columns else 'Cena'
min_cena = df[cena_sloupec].min() if not df.empty else 0
max_cena = df[cena_sloupec].max() if not df.empty else 1000

# Ošetření extrémních hodnot - nastavení rozumného maxima
if max_cena > 5000:  # Pokud je maximální cena nereálně vysoká
    print(f"Detekována extrémně vysoká cena: {max_cena} Kč/GJ. Nastavuji rozumné maximum.")
    # Filtrujeme extrémní hodnoty a hledáme druhou nejvyšší cenu
    rozumne_ceny = df[df[cena_sloupec] < 5000][cena_sloupec]
    if not rozumne_ceny.empty:
        max_cena = rozumne_ceny.max()
    else:
        max_cena = 2500  # Defaultní maximum, pokud nemáme jiné rozumné hodnoty

# Zaokrouhlení pro lepší zobrazení
min_cena = int(min_cena) if not pd.isna(min_cena) else 0
max_cena = int(max_cena) + 100 if not pd.isna(max_cena) else 1000

# Definice barev a stylů pro konzistentní vzhled
COLORS = {
    'primary': '#3a86ff',       # Modrá - hlavní barva
    'secondary': '#8338ec',     # Fialová - sekundární barva
    'accent': '#ff006e',        # Růžová - zvýrazňující barva
    'light': '#ffffff',         # Bílá - světlé prvky
    'dark': '#14213d',          # Tmavě modrá - text
    'success': '#06d6a0',       # Tyrkysová - pozitivní hodnoty
    'warning': '#ffd166',       # Žlutá - varování
    'background': 'rgba(236, 240, 243, 0.8)',  # Světlé pozadí s průhledností
    'glass': 'rgba(255, 255, 255, 0.25)'       # Skleněný efekt
}

# Výpočet agregovaných dat
def vypocet_agregace():
    """Vypočítá agregovaná data pro grafy."""
    global df
    
    # Kontrola, zda máme data
    if df.empty:
        return None
    
    # Vytvoření kopie dat
    data = df.copy()
    
    # Kontrola, zda existuje sloupec Typ_ceny
    if 'Typ_ceny' not in data.columns:
        data['Typ_ceny'] = 'Výsledná'
    
    # Výpočet průměrných cen podle roku a typu ceny
    agregace = data.groupby(['Rok', 'Typ_ceny'])['Cena'].mean().reset_index()
    
    # Výpočet meziročního nárůstu cen
    # Nejprve vytvoříme pivot tabulku s roky jako indexem a typy cen jako sloupci
    pivot = agregace.pivot(index='Rok', columns='Typ_ceny', values='Cena')
    
    # Výpočet meziročního nárůstu pro výsledné ceny
    if 'Výsledná' in pivot.columns:
        pivot['Meziroční_nárůst'] = pivot['Výsledná'].pct_change() * 100
    
    # Resetování indexu
    pivot = pivot.reset_index()
    
    # Převedení zpět na formát s Typ_ceny jako sloupcem (unpivot)
    # Toto je důležité pro funkce, které očekávají sloupec Typ_ceny
    result = agregace.copy()
    
    return result

# Funkce pro vytvoření popisu filtrů
def vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range=None, predbezne_ceny=None):
    """Vytvoří popis aktuálně vybraných filtrů."""
    filtry_info = []
    
    # Přidání informace o typu dodávky
    if typ_dodavky and typ_dodavky != 'Celkový průměr':
        filtry_info.append(f"Typ dodávky: {typ_dodavky}")
    
    # Přidání informace o kraji
    if kraj_nazev:
        filtry_info.append(f"Kraj: {kraj_nazev}")
    
    # Přidání informace o lokalitě
    if lokalita:
        filtry_info.append(f"Lokalita: {lokalita}")
    
    # Přidání informace o výkonu
    if vykon_range and vykon_range != [0, 6324]:
        filtry_info.append(f"Výkon: {vykon_range[0]}-{vykon_range[1]} MW")
    
    # Přidání informace o cenách
    if cena_range and cena_range != [0, 2500]:
        filtry_info.append(f"Cena: {cena_range[0]}-{cena_range[1]} Kč/GJ")
    
    # Přidání informace o palivech
    if vybrana_paliva and len(vybrana_paliva) < 5:
        filtry_info.append(f"Paliva: {', '.join(vybrana_paliva)}")
    
    # Přidání informace o předběžných cenách
    if predbezne_ceny:
        if predbezne_ceny == 'ano':
            filtry_info.append("Včetně předběžných cen")
        elif predbezne_ceny == 'vysledne':
            filtry_info.append("Pouze výsledné ceny")
    
    # Sestavení výsledného textu
    if filtry_info:
        return f"Filtry: {'; '.join(filtry_info)}"
    else:
        return "Všechna data bez filtrování"

# Získání seznamu unikátních typů dodávek pro dropdown
typy_dodavek = ['Celkový průměr']
if not df.empty:
    nejcastejsi_typy = df.groupby('Typ_dodavky').size().sort_values(ascending=False).head(10).index.tolist()
    typy_dodavek.extend([typ for typ in nejcastejsi_typy if typ != 'Celkový průměr'])

# Získání seznamu krajů pro dropdown
kraje = []
if not df.empty and 'Kod_kraje' in df.columns:
    # Platné kódy krajů v ČR
    platne_kody_kraju = ['A', 'B', 'C', 'E', 'H', 'J', 'K', 'L', 'M', 'P', 'S', 'T', 'U', 'Z']
    
    # Filtrování pouze platných kódů krajů
    platne_kody = sorted([kod for kod in df['Kod_kraje'].dropna().unique() if kod in platne_kody_kraju])
    
    # Mapování kódů krajů na celé názvy
    nazvy_kraju = {
        'A': 'Hlavní město Praha',
        'B': 'Jihomoravský kraj',
        'C': 'Jihočeský kraj',
        'E': 'Pardubický kraj',
        'H': 'Královéhradecký kraj',
        'J': 'Kraj Vysočina',
        'K': 'Karlovarský kraj',
        'L': 'Liberecký kraj',
        'M': 'Olomoucký kraj',
        'P': 'Plzeňský kraj',
        'S': 'Středočeský kraj',
        'T': 'Moravskoslezský kraj',
        'U': 'Ústecký kraj',
        'Z': 'Zlínský kraj'
    }
    
    # Vytvoření seznamu možností pro dropdown s celými názvy krajů
    kraje = [{'label': nazvy_kraju.get(kod, kod), 'value': nazvy_kraju.get(kod, kod)} for kod in platne_kody]
    
    # Vytvoření mapování názvů krajů zpět na kódy pro použití v callbacku
    nazvy_na_kody = {nazev: kod for kod, nazev in nazvy_kraju.items()}

# Získání seznamu typů paliv pro multi-dropdown
typy_paliv = ['Všechna paliva']
if not df.empty:
    paliva_sloupce = [col for col in df.columns if col.endswith('_procento')]
    nazvy_paliv = {
        'Uhli_procento': 'Uhlí',
        'Biomasa_procento': 'Biomasa',
        'Odpad_procento': 'Odpad',
        'Zemni_plyn_procento': 'Zemní plyn',
        'Jina_paliva_procento': 'Jiná paliva'
    }
    typy_paliv.extend([nazvy_paliv.get(col, col.replace('_procento', '')) for col in paliva_sloupce])

# Získání seznamu lokalit pro dropdown s automatickým doplňováním
lokality = []
if not df.empty and 'Lokalita' in df.columns:
    lokality = sorted(df['Lokalita'].dropna().unique().tolist())



# Mapování kódů krajů na jejich názvy
kody_na_nazvy = {
    'A': 'Hlavní město Praha',
    'S': 'Středočeský kraj',
    'C': 'Jihočeský kraj',
    'P': 'Plzeňský kraj',
    'K': 'Karlovarský kraj',
    'U': 'Ústecký kraj',
    'L': 'Liberecký kraj',
    'H': 'Královéhradecký kraj',
    'E': 'Pardubický kraj',
    'J': 'Kraj Vysočina',
    'B': 'Jihomoravský kraj',
    'M': 'Olomoucký kraj',
    'Z': 'Zlínský kraj',
    'T': 'Moravskoslezský kraj'
}

# Mapování názvů krajů na jejich kódy
nazvy_na_kody = {v: k for k, v in kody_na_nazvy.items()}

# Definice barev a stylů pro konzistentní vzhled
COLORS = {
    'primary': '#3a86ff',       # Modrá - hlavní barva
    'secondary': '#8338ec',     # Fialová - sekundární barva
    'accent': '#ff006e',        # Růžová - zvýrazňující barva
    'light': '#ffffff',         # Bílá - světlé prvky
    'dark': '#14213d',          # Tmavě modrá - text
    'success': '#06d6a0',       # Tyrkysová - pozitivní hodnoty
    'warning': '#ffd166',       # Žlutá - varování
    'background': 'rgba(236, 240, 243, 0.8)',  # Světlé pozadí s průhledností
    'glass': 'rgba(255, 255, 255, 0.25)'       # Skleněný efekt
}

# Styly pro glassmorphic design
STYLES = {
    'glass_card': {
        'backgroundColor': 'rgba(255, 255, 255, 0.25)',
        'backdropFilter': 'blur(10px)',
        'WebkitBackdropFilter': 'blur(10px)',
        'borderRadius': '16px',
        'border': '1px solid rgba(255, 255, 255, 0.18)',
        'boxShadow': '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
        'padding': '20px',
        'marginBottom': '20px'
    },
    'header': {
        'color': COLORS['dark'],
        'fontWeight': '600',
        'marginBottom': '20px',
        'textAlign': 'center',
        'fontSize': '24px',
        'letterSpacing': '0.5px'
    },
    'subheader': {
        'color': COLORS['dark'],
        'fontWeight': '500',
        'marginBottom': '15px',
        'textAlign': 'center',
        'fontSize': '18px',
        'letterSpacing': '0.3px'
    },
    'label': {
        'fontWeight': '500',
        'marginTop': '10px',
        'marginBottom': '5px',
        'color': COLORS['dark'],
        'letterSpacing': '0.2px'
    },
    'dropdown': {
        'marginBottom': '15px',
        'borderRadius': '8px',
        'border': '1px solid rgba(255, 255, 255, 0.3)',
        'backgroundColor': 'rgba(255, 255, 255, 0.2)',
        'boxShadow': '0 2px 5px rgba(0, 0, 0, 0.05)'
    },
    'container': {
        'maxWidth': '1400px',
        'margin': '0 auto',
        'padding': '20px'
    },
    'button': {
        'backgroundColor': COLORS['primary'],
        'color': 'white',
        'border': 'none',
        'borderRadius': '8px',
        'padding': '8px 16px',
        'cursor': 'pointer',
        'fontWeight': '500',
        'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.1)',
        'transition': 'all 0.3s ease'
    },
    'input': {
        'backgroundColor': 'rgba(255, 255, 255, 0.2)',
        'border': '1px solid rgba(255, 255, 255, 0.3)',
        'borderRadius': '8px',
        'padding': '8px 12px',
        'boxShadow': '0 2px 5px rgba(0, 0, 0, 0.05)'
    }
}

# Vytvoření layoutu aplikace
app.layout = html.Div([
    # Navigační lišta
    html.Div([
        html.Div([
            html.H1("Vývoj cen tepla v ČR", style={'margin': '0', 'color': COLORS['light'], 'fontWeight': '600', 'letterSpacing': '1px'}),
            html.P("Interaktivní dashboard pro analýzu cen tepla", style={'margin': '0', 'color': 'rgba(255, 255, 255, 0.8)', 'letterSpacing': '0.5px'})
        ], style={'display': 'flex', 'flexDirection': 'column', 'justifyContent': 'center'})
    ], style={
        'backgroundColor': COLORS['primary'],
        'backgroundImage': 'linear-gradient(135deg, ' + COLORS['primary'] + ' 0%, ' + COLORS['secondary'] + ' 100%)',
        'padding': '20px 30px',
        'boxShadow': '0 4px 30px rgba(0, 0, 0, 0.1)',
        'marginBottom': '30px',
        'borderRadius': '0 0 16px 16px'
    }),
    
    # Hlavní obsah
    html.Div([
        # První řádek - filtry a mapa
        html.Div([
            # Filtry
            html.Div([
                html.Div([
                    html.H3("Filtry", style=STYLES['header']),
                    
                    html.Div([
                        html.Label("Typ dodávky:", style=STYLES['label']),
                        dcc.Dropdown(
                            id='typ-dodavky-dropdown',
                            options=[{'label': typ, 'value': typ} for typ in typy_dodavek],
                            value='Celkový průměr',
                            style=STYLES['dropdown'],
                            clearable=False
                        ),
                    ]),
                    
                    html.Div([
                        html.Label("Kraj:", style=STYLES['label']),
                        dcc.Dropdown(
                            id='kraj-dropdown',
                            options=[{'label': nazev, 'value': nazev} for nazev in kody_na_nazvy.values()],
                            value=None,
                            style=STYLES['dropdown'],
                            placeholder="Vyberte kraj"
                        ),
                    ]),
                    
                    html.Div([
                        html.Label("Paliva:", style=STYLES['label']),
                        dcc.Checklist(
                            id='paliva-checklist',
                            options=[
                                {'label': ' Uhlí', 'value': 'Uhlí'},
                                {'label': ' Biomasa', 'value': 'Biomasa'},
                                {'label': ' Odpad', 'value': 'Odpad'},
                                {'label': ' Zemní plyn', 'value': 'Zemní plyn'},
                                {'label': ' Jiná paliva', 'value': 'Jiná paliva'}
                            ],
                            value=['Uhlí', 'Biomasa', 'Odpad', 'Zemní plyn', 'Jiná paliva'],
                            inline=True,
                            style={'marginBottom': '15px'},
                            inputStyle={"marginRight": "5px"},
                            labelStyle={"marginRight": "15px", "color": COLORS['dark']}
                        ),
                    ]),
                    
                    html.Div([
                        html.Label("Lokalita:", style=STYLES['label']),
                        dcc.Dropdown(
                            id='lokalita-dropdown',
                            options=[],
                            value=None,
                            style=STYLES['dropdown'],
                            placeholder="Vyberte lokalitu"
                        ),
                    ]),
                    
                    html.Div([
                        html.Label("Instalovaný tepelný výkon [MW]:", style=STYLES['label']),
                        html.Div([
                            html.Div(id='vykon-min-hodnota', style={'display': 'inline-block', 'marginRight': '10px', 'fontSize': '12px', 'color': COLORS['secondary']}),
                            html.Div(id='vykon-max-hodnota', style={'display': 'inline-block', 'fontSize': '12px', 'color': COLORS['secondary']})
                        ]),
                        dcc.RangeSlider(
                            id='vykon-range-slider',
                            min=0,
                            max=6324,
                            step=10,
                            marks={
                                0: {'label': '0', 'style': {'color': COLORS['dark']}},
                                100: {'label': '100', 'style': {'color': COLORS['dark']}},
                                500: {'label': '500', 'style': {'color': COLORS['dark']}},
                                1000: {'label': '1000', 'style': {'color': COLORS['dark']}},
                                3000: {'label': '3000', 'style': {'color': COLORS['dark']}},
                                6324: {'label': '6324', 'style': {'color': COLORS['dark']}}
                            },
                            value=[0, 6324],
                            allowCross=False,
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        html.Div([
                            html.Div(id='vykon-min-display', style={'display': 'inline-block', 'marginRight': '10px', 'fontSize': '12px', 'color': COLORS['secondary']}),
                            html.Div(id='vykon-max-display', style={'display': 'inline-block', 'fontSize': '12px', 'color': COLORS['secondary']})
                        ], style={'marginTop': '5px', 'marginBottom': '15px'}),
                        
                        # Přidání manuálních vstupů pro rozsah výkonu
                        html.Div([
                            html.Label("Zadat rozsah ručně:", style={'fontSize': '13px', 'fontWeight': 'bold', 'marginBottom': '5px', 'color': COLORS['dark']}),
                            html.Div([
                                html.Div([
                                    html.Label("Min:", style={'fontSize': '12px', 'marginRight': '5px', 'color': COLORS['dark']}),
                                    dcc.Input(
                                        id='vykon-min-input',
                                        type='number',
                                        min=0,
                                        max=6324,
                                        step=1,
                                        value=0,
                                        style={
                                            'width': '80px',
                                            'height': '30px',
                                            'borderRadius': '8px',
                                            'border': '1px solid rgba(255, 255, 255, 0.3)',
                                            'backgroundColor': 'rgba(255, 255, 255, 0.2)',
                                            'padding': '5px',
                                            'marginRight': '10px',
                                            'boxShadow': '0 2px 5px rgba(0, 0, 0, 0.05)'
                                        }
                                    )
                                ], style={'display': 'inline-block', 'marginRight': '15px'}),
                                html.Div([
                                    html.Label("Max:", style={'fontSize': '12px', 'marginRight': '5px', 'color': COLORS['dark']}),
                                    dcc.Input(
                                        id='vykon-max-input',
                                        type='number',
                                        min=0,
                                        max=6324,
                                        step=1,
                                        value=6324,
                                        style={
                                            'width': '80px',
                                            'height': '30px',
                                            'borderRadius': '8px',
                                            'border': '1px solid rgba(255, 255, 255, 0.3)',
                                            'backgroundColor': 'rgba(255, 255, 255, 0.2)',
                                            'padding': '5px',
                                            'boxShadow': '0 2px 5px rgba(0, 0, 0, 0.05)'
                                        }
                                    )
                                ], style={'display': 'inline-block'}),
                                html.Button(
                                    'Použít',
                                    id='vykon-apply-button',
                                    style={
                                        'backgroundColor': COLORS['primary'],
                                        'color': 'white',
                                        'border': 'none',
                                        'borderRadius': '8px',
                                        'padding': '5px 15px',
                                        'marginLeft': '10px',
                                        'cursor': 'pointer',
                                        'height': '30px',
                                        'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.1)',
                                        'transition': 'all 0.3s ease'
                                    }
                                )
                            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '15px'})
                        ]),
                    ]),
                    
                    # Přidání filtru pro rozsah cen tepla
                    html.Div([
                        html.Label("Rozsah cen tepla [Kč/GJ]:", style=STYLES['label']),
                        dcc.RangeSlider(
                            id='cena-range-slider',
                            min=min_cena,
                            max=max_cena,
                            step=10,
                            marks={
                                min_cena: {'label': str(min_cena), 'style': {'color': COLORS['dark']}},
                                int(min_cena + (max_cena - min_cena) * 0.25): {'label': str(int(min_cena + (max_cena - min_cena) * 0.25)), 'style': {'color': COLORS['dark']}},
                                int(min_cena + (max_cena - min_cena) * 0.5): {'label': str(int(min_cena + (max_cena - min_cena) * 0.5)), 'style': {'color': COLORS['dark']}},
                                int(min_cena + (max_cena - min_cena) * 0.75): {'label': str(int(min_cena + (max_cena - min_cena) * 0.75)), 'style': {'color': COLORS['dark']}},
                                max_cena: {'label': str(max_cena), 'style': {'color': COLORS['dark']}}
                            },
                            value=[min_cena, max_cena],
                            allowCross=False,
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                        html.Div([
                            html.Div(id='cena-min-display', style={'display': 'inline-block', 'marginRight': '10px', 'fontSize': '12px', 'color': COLORS['secondary']}),
                            html.Div(id='cena-max-display', style={'display': 'inline-block', 'fontSize': '12px', 'color': COLORS['secondary']})
                        ], style={'marginTop': '5px', 'marginBottom': '15px'})
                    ]),
                    
                    html.Div([
                        html.Label("Zobrazit předběžné ceny:", style=STYLES['label']),
                        dcc.RadioItems(
                            id='predbezne-ceny-radio',
                            options=[
                                {'label': ' Ano', 'value': 'ano'},
                                {'label': ' Ne', 'value': 'vysledne'}
                            ],
                            value='ano',
                            inline=True,
                            inputStyle={"marginRight": "5px"},
                            labelStyle={"marginRight": "15px", "color": COLORS['dark']}
                        )
                    ]),
                ], style=STYLES['glass_card'])
            ], style={'width': '25%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            # Mapa
            html.Div([
                html.Div([
                    html.H3("Mapa cen tepla v ČR", style=STYLES['header']),
                    dcc.Graph(
                        id='mapa-cr',
                        config={'displayModeBar': True, 'scrollZoom': True},
                        style={'height': '600px', 'borderRadius': '8px', 'overflow': 'hidden'}
                    )
                ], style=STYLES['glass_card'])
            ], style={'width': '73%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),
        
        # Druhý řádek - grafy
        html.Div([
            # Vývoj cen
            html.Div([
                html.Div([
                    html.H3("Vývoj cen tepla v čase", style=STYLES['header']),
                    dcc.Graph(id='vyvoj-cen-graf', style={'borderRadius': '8px', 'overflow': 'hidden'})
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            # Meziroční nárůst
            html.Div([
                html.Div([
                    html.H3("Meziroční nárůst cen tepla", style=STYLES['header']),
                    dcc.Graph(id='mezirocni-narust-graf', style={'borderRadius': '8px', 'overflow': 'hidden'})
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
        ], style={'display': 'flex', 'flexWrap': 'wrap', 'marginTop': '20px'}),
        
        # Třetí řádek - podíl paliv a tabulka
        html.Div([
            # Podíl paliv
            html.Div([
                html.Div([
                    html.H3("Podíl paliv na výrobě tepla", style=STYLES['header']),
                    dcc.Graph(id='paliva-podil-graf', style={'borderRadius': '8px', 'overflow': 'hidden'})
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            # Tabulka cen
            html.Div([
                html.Div([
                    html.H3("Tabulka cen tepla", style=STYLES['header']),
                    html.Div(id='tabulka-cen', style={'overflowX': 'auto'})
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
        ], style={'display': 'flex', 'flexWrap': 'wrap', 'marginTop': '20px'}),
        
        # Čtvrtý řádek - AI prognózy a analýzy (návrh rozšíření)
        html.Div([
            html.Div([
                html.Div([
                    html.H3("AI Prognóza vývoje cen", style=STYLES['header']),
                    html.Div([
                        html.P("Predikce budoucího vývoje cen tepla pomocí pokročilých AI modelů.", 
                               style={'textAlign': 'center', 'color': COLORS['dark'], 'marginBottom': '15px'}),
                        dcc.Dropdown(
                            id='forecast-method-dropdown',
                            options=[
                                {'label': 'Prophet (Facebook)', 'value': 'prophet'},
                                {'label': 'ARIMA', 'value': 'arima'},
                                {'label': 'SARIMAX', 'value': 'sarimax'}
                            ],
                            value='prophet',
                            style=STYLES['dropdown'],
                            clearable=False
                        ),
                        dcc.Graph(id='forecast-graph', style={'borderRadius': '8px', 'overflow': 'hidden'})
                    ]) if AI_FORECASTING_AVAILABLE else html.Div([
                        html.P("Pro zobrazení AI prognózy je potřeba nainstalovat dodatečné knihovny.", 
                               style={'textAlign': 'center', 'color': COLORS['dark'], 'marginBottom': '15px'}),
                        html.Img(src='https://via.placeholder.com/600x300?text=AI+Prognóza+vývoje+cen', 
                                style={'width': '100%', 'borderRadius': '8px', 'marginBottom': '15px'})
                    ])
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            
            html.Div([
                html.Div([
                    html.H3("Analýza anomálií a trendů", style=STYLES['header']),
                    html.Div([
                        html.P("Automatická detekce anomálií a analýza trendů pomocí pokročilých algoritmů.", 
                               style={'textAlign': 'center', 'color': COLORS['dark'], 'marginBottom': '15px'}),
                        dcc.Tabs([
                            dcc.Tab(label='Detekce anomálií', children=[
                                dcc.Graph(id='anomalies-graph', style={'borderRadius': '8px', 'overflow': 'hidden'})
                            ], style={'padding': '15px', 'backgroundColor': 'rgba(255, 255, 255, 0.1)'},
                               selected_style={'padding': '15px', 'backgroundColor': 'rgba(255, 255, 255, 0.2)', 'borderTop': f'3px solid {COLORS["primary"]}'}),
                            dcc.Tab(label='Analýza trendů', children=[
                                dcc.Graph(id='trends-graph', style={'borderRadius': '8px', 'overflow': 'hidden'})
                            ], style={'padding': '15px', 'backgroundColor': 'rgba(255, 255, 255, 0.1)'},
                               selected_style={'padding': '15px', 'backgroundColor': 'rgba(255, 255, 255, 0.2)', 'borderTop': f'3px solid {COLORS["primary"]}'})
                        ], style={'marginTop': '15px'})
                    ]) if AI_FORECASTING_AVAILABLE else html.Div([
                        html.P("Pro zobrazení analýzy anomálií a trendů je potřeba nainstalovat dodatečné knihovny.", 
                               style={'textAlign': 'center', 'color': COLORS['dark'], 'marginBottom': '15px'}),
                        html.Img(src='https://via.placeholder.com/600x300?text=Analýza+anomálií+a+trendů', 
                                style={'width': '100%', 'borderRadius': '8px', 'marginBottom': '15px'})
                    ])
                ], style=STYLES['glass_card'])
            ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top', 'marginLeft': '2%'})
        ], style={'display': 'flex', 'flexWrap': 'wrap', 'marginTop': '20px'})
    ], style=STYLES['container']),
    
    # Patička
    html.Footer([
        html.P("© 2024 Dashboard vývoje cen tepla v ČR", style={'margin': '0', 'textAlign': 'center', 'color': COLORS['light'], 'letterSpacing': '0.5px'})
    ], style={
        'backgroundColor': COLORS['primary'],
        'backgroundImage': 'linear-gradient(135deg, ' + COLORS['primary'] + ' 0%, ' + COLORS['secondary'] + ' 100%)',
        'padding': '15px',
        'marginTop': '30px',
        'boxShadow': '0 -4px 30px rgba(0, 0, 0, 0.1)',
        'borderRadius': '16px 16px 0 0'
    })
], style={
    'backgroundColor': COLORS['background'],
    'backgroundImage': 'linear-gradient(135deg, rgba(236, 240, 243, 0.8) 0%, rgba(250, 250, 250, 0.8) 100%)',
    'minHeight': '100vh', 
    'fontFamily': '"Poppins", "Segoe UI", Arial, sans-serif'
})

# Callback pro aktualizaci grafu vývoje cen
@callback(
    Output('vyvoj-cen-graf', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_graf_vyvoje_cen(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, predbezne_ceny):
    """Aktualizuje graf vývoje cen tepla v čase."""
    try:
        # Filtrování dat podle vybraných filtrů
        filtrovana_data = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování podle lokality
        if lokalita:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
        
        # Filtrování podle instalovaného výkonu
        if vykon_range:
            min_vykon, max_vykon = vykon_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
            # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                 (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
        
        # Filtrování podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            # Mapování názvů paliv na sloupce v datech
            nazvy_paliv_reverse = {
                'Uhlí': 'Uhli_procento',
                'Biomasa': 'Biomasa_procento',
                'Odpad': 'Odpad_procento',
                'Zemní plyn': 'Zemni_plyn_procento',
                'Jiná paliva': 'Jina_paliva_procento'
            }
            
            # Vytvoříme masku pro filtrování
            maska = pd.Series(False, index=filtrovana_data.index)
            
            for palivo in vybrana_paliva:
                palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                if palivo_sloupec in df.columns:
                    maska = maska | (filtrovana_data[palivo_sloupec] > 50)
            
            filtrovana_data = filtrovana_data[maska]
        
        # Filtrování předběžných cen
        if predbezne_ceny == 'vysledne':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_ceny'] != 'Předběžná']
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, None, predbezne_ceny)
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Vývoj cen tepla v čase<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Rok",
                yaxis_title="Cena tepla [Kč/GJ]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Žádná data k zobrazení pro vybrané filtry",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark'])
            )
            return fig
        
        # Agregace dat podle roku a typu ceny
        agregace = filtrovana_data.groupby(['Rok', 'Typ_ceny'])['Cena'].mean().reset_index()
        
        # Pivot tabulka pro zobrazení
        pivot_data = agregace.pivot(index='Rok', columns='Typ_ceny', values='Cena').reset_index()
        
        # Seřazení podle roku
        pivot_data = pivot_data.sort_values('Rok')
        
        # Vytvoření grafu
        fig = go.Figure()
        
        # Přidání čáry pro výsledné ceny
        if 'Výsledná' in pivot_data.columns:
            fig.add_trace(go.Scatter(
                x=pivot_data['Rok'],
                y=pivot_data['Výsledná'],
                mode='lines+markers',
                name='Výsledná cena tepla',
                line=dict(color=COLORS['primary'], width=3),
                marker=dict(size=8, color=COLORS['primary']),
                hovertemplate='%{x}: %{y:.2f} Kč/GJ<extra></extra>'
            ))
        
        # Přidání čáry pro předběžné ceny
        if 'Předběžná' in pivot_data.columns and predbezne_ceny == 'ano':
            fig.add_trace(go.Scatter(
                x=pivot_data['Rok'],
                y=pivot_data['Předběžná'],
                mode='lines+markers',
                name='Předběžná cena tepla',
                line=dict(color=COLORS['accent'], width=2, dash='dash'),
                marker=dict(size=8, color=COLORS['accent']),
                hovertemplate='%{x}: %{y:.2f} Kč/GJ<extra></extra>'
            ))
        
        # Přidání oblasti pro zvýraznění trendu
        if 'Výsledná' in pivot_data.columns:
            fig.add_trace(go.Scatter(
                x=pivot_data['Rok'],
                y=pivot_data['Výsledná'],
                mode='none',
                fill='tozeroy',
                fillcolor='rgba(58, 134, 255, 0.2)',
                hoverinfo='none',
                showlegend=False
            ))
        
        # Nastavení layoutu grafu
        fig.update_layout(
            title={
                'text': "Vývoj cen tepla v čase<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Rok",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20},
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                tickmode='linear',
                dtick=1
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.2)',
                zerolinewidth=1
            )
        )
        
        return fig
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci grafu vývoje cen: {e}")
        traceback.print_exc()
        
        # Vytvoření prázdného grafu v případě chyby
        fig = go.Figure()
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, None, predbezne_ceny)
        
        fig.update_layout(
            title={
                'text': "Chyba při zobrazení grafu vývoje cen<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Rok",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20}
        )
        fig.add_annotation(
            text=f"Došlo k chybě: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=COLORS['accent'])
        )
        return fig

# Callback pro aktualizaci grafu meziročního nárůstu
@callback(
    Output('mezirocni-narust-graf', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_graf_mezirocniho_narustu(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, predbezne_ceny):
    """Aktualizuje graf meziročního nárůstu cen tepla."""
    try:
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, None, predbezne_ceny)
        
        if df.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Meziroční nárůst cen tepla<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Rok",
                yaxis_title="Meziroční nárůst [%]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Žádná data k zobrazení",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark'])
            )
            return fig
        
        # Vytvoření kopie dat pro filtrování
        filtrovana_data = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování podle lokality
        if lokalita:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
        
        # Filtrování podle instalovaného výkonu
        if vykon_range:
            min_vykon, max_vykon = vykon_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
            # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                 (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
        
        # Filtrování podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            # Mapování názvů paliv na sloupce v datech
            nazvy_paliv_reverse = {
                'Uhlí': 'Uhli_procento',
                'Biomasa': 'Biomasa_procento',
                'Odpad': 'Odpad_procento',
                'Zemní plyn': 'Zemni_plyn_procento',
                'Jiná paliva': 'Jina_paliva_procento'
            }
            
            # Vytvoříme masku pro filtrování
            maska = pd.Series(False, index=filtrovana_data.index)
            
            for palivo in vybrana_paliva:
                palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                if palivo_sloupec in df.columns:
                    maska = maska | (filtrovana_data[palivo_sloupec] > 50)
            
            filtrovana_data = filtrovana_data[maska]
        
        # Filtrování předběžných cen
        if predbezne_ceny == 'vysledne':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_ceny'] != 'Předběžná']
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Meziroční nárůst cen tepla<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Rok",
                yaxis_title="Meziroční nárůst [%]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Žádná data k zobrazení pro vybrané filtry",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark'])
            )
            return fig
        
        # Vytvoření grafu
        fig = go.Figure()
        
        # Pokud je vybrána konkrétní lokalita, zobrazíme vývoj cen pro tuto lokalitu
        if lokalita:
            try:
                # Výpočet průměrných cen podle roku a typu ceny
                agregace = filtrovana_data.groupby(['Rok', 'Typ_ceny'])['Cena'].mean().reset_index()
                
                # Vytvoření pivot tabulky s roky jako indexem a typy cen jako sloupci
                pivot = agregace.pivot(index='Rok', columns='Typ_ceny', values='Cena')
                
                # Výpočet meziročního nárůstu pro výsledné ceny
                if 'Výsledná' in pivot.columns:
                    pivot['Meziroční_nárůst'] = pivot['Výsledná'].pct_change() * 100
                else:
                    # Pokud nemáme sloupec 'Výsledná', použijeme první dostupný sloupec
                    if not pivot.empty and len(pivot.columns) > 0:
                        first_col = pivot.columns[0]
                        pivot['Meziroční_nárůst'] = pivot[first_col].pct_change() * 100
                    else:
                        # Pokud nemáme žádná data, vytvoříme prázdný graf
                        fig = go.Figure()
                        fig.update_layout(
                            title={
                                'text': f"Meziroční nárůst cen tepla - {lokalita}<br><sup>" + popis_filtru + "</sup>",
                                'x': 0.5,
                                'xanchor': 'center',
                                'font': {'size': 16, 'color': COLORS['dark']}
                            },
                            xaxis_title="Rok",
                            yaxis_title="Meziroční nárůst [%]",
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            height=400,
                            margin={"r": 20, "t": 60, "l": 20, "b": 20}
                        )
                        fig.add_annotation(
                            text="Nedostatek dat pro výpočet meziročního nárůstu",
                            xref="paper", yref="paper",
                            x=0.5, y=0.5,
                            showarrow=False,
                            font=dict(size=14, color=COLORS['dark'])
                        )
                        return fig
                
                # Resetování indexu
                pivot = pivot.reset_index()
                
                # Vytvoříme dva samostatné grafy místo jednoho s dvěma osami
                # Použijeme subplots pro vytvoření dvou grafů nad sebou
                from plotly.subplots import make_subplots
                
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                                   subplot_titles=(f"Meziroční nárůst cen tepla", f"Vývoj cen tepla"))
                
                # Přidáme graf meziročního nárůstu (sloupcový)
                fig.add_trace(
                    go.Bar(
                        x=pivot['Rok'],
                        y=pivot['Meziroční_nárůst'],
                        name='Meziroční nárůst [%]',
                        marker_color=COLORS['accent'],
                        hovertemplate='Rok: %{x}<br>Meziroční nárůst: %{y:.2f}%<extra></extra>'
                    ),
                    row=1, col=1
                )
                
                # Přidáme graf vývoje cen (čárový)
                if 'Výsledná' in pivot.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=pivot['Rok'],
                            y=pivot['Výsledná'],
                            name='Cena tepla [Kč/GJ]',
                            mode='lines+markers',
                            marker=dict(color=COLORS['primary']),
                            line=dict(color=COLORS['primary'], width=2),
                            hovertemplate='Rok: %{x}<br>Cena: %{y:.2f} Kč/GJ<extra></extra>'
                        ),
                        row=2, col=1
                    )
                
                # Nastavení layoutu
                fig.update_layout(
                    title={
                        'text': f"Analýza cen tepla - {lokalita}<br><sup>" + popis_filtru + "</sup>",
                        'x': 0.5,
                        'xanchor': 'center',
                        'font': {'size': 16, 'color': COLORS['dark']}
                    },
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=600,  # Zvětšíme výšku pro dva grafy
                    margin=dict(l=50, r=50, t=80, b=50),
                    showlegend=True,
                    legend=dict(
                        orientation='h',
                        yanchor='bottom',
                        y=1.02,
                        xanchor='right',
                        x=1
                    )
                )
                
                # Nastavení os
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)', row=1, col=1)
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)', title_text="Rok", row=2, col=1)
                
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)', 
                                title_text="Meziroční nárůst [%]", row=1, col=1)
                
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.1)', 
                                title_text="Cena tepla [Kč/GJ]", row=2, col=1)
                
            except Exception as e:
                import traceback
                print(f"Chyba při vytváření grafu pro lokalitu: {e}")
                traceback.print_exc()
                
                # Vytvoření prázdného grafu v případě chyby
                fig = go.Figure()
                fig.update_layout(
                    title={
                        'text': f"Chyba při zobrazení grafu pro lokalitu {lokalita}<br><sup>" + popis_filtru + "</sup>",
                        'x': 0.5,
                        'xanchor': 'center',
                        'font': {'size': 16, 'color': COLORS['dark']}
                    },
                    xaxis_title="Rok",
                    yaxis_title="Meziroční nárůst [%]",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    height=400,
                    margin={"r": 20, "t": 60, "l": 20, "b": 20}
                )
                fig.add_annotation(
                    text=f"Došlo k chybě: {str(e)}",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=14, color=COLORS['accent'])
                )
        else:
            # Pokud není vybrána konkrétní lokalita, zobrazíme informační zprávu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Meziroční nárůst cen tepla<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Rok",
                yaxis_title="Meziroční nárůst [%]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Pro zobrazení meziročního nárůstu cen vyberte konkrétní lokalitu",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark']),
                bgcolor="rgba(255, 255, 255, 0.7)",
                bordercolor=COLORS['accent'],
                borderwidth=1,
                borderpad=4
            )
        
        return fig
    
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci grafu meziročního nárůstu: {e}")
        traceback.print_exc()
        
        # Vytvoření prázdného grafu v případě chyby
        fig = go.Figure()
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, None, predbezne_ceny)
        
        fig.update_layout(
            title={
                'text': "Chyba při zobrazení grafu meziročního nárůstu<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Rok",
            yaxis_title="Meziroční nárůst [%]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20}
        )
        fig.add_annotation(
            text=f"Došlo k chybě: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=COLORS['accent'])
        )
        return fig

# Callback pro aktualizaci grafu podílu paliv
@callback(
    Output('paliva-podil-graf', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value')]
)
def aktualizuj_graf_podilu_paliv(typ_dodavky, kraj_nazev, lokalita, vykon_range):
    """Aktualizuje graf podílu paliv."""
    try:
        if df.empty:
            return go.Figure().update_layout(title="Žádná data k dispozici")
        
        # Kontrola, zda máme sloupce s podíly paliv
        paliva_sloupce = [col for col in df.columns if col.endswith('_procento')]
        if not paliva_sloupce:
            return go.Figure().update_layout(
                title="Chybí data o podílech paliv",
                annotations=[dict(
                    text="Chybí data o podílech paliv",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=14)
                )]
            )
        
        # Začneme s původními daty
        filtrovana_data = df.copy()
        
        # Převod názvu kraje na kód
        kraj = None
        if kraj_nazev and 'Kod_kraje' in df.columns:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování dat podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování dat podle lokality
        if lokalita and 'Lokalita' in df.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
        
        # Filtrování dat podle instalovaného výkonu
        if vykon_range and 'Instalovany_vykon' in df.columns:
            min_vykon, max_vykon = vykon_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
            # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                             (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            return go.Figure().update_layout(
                title="Po aplikaci filtrů nezbyly žádné záznamy",
                annotations=[dict(
                    text="Po aplikaci filtrů nezbyly žádné záznamy",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5,
                    showarrow=False,
                    font=dict(size=14)
                )]
            )
        
        # Výpočet průměrných podílů paliv podle roku
        podily_paliv = filtrovana_data.groupby('Rok')[paliva_sloupce].mean().reset_index()
        
        # Přejmenování sloupců pro lepší zobrazení
        nazvy_paliv = {
            'Uhli_procento': 'Uhlí',
            'Biomasa_procento': 'Biomasa',
            'Odpad_procento': 'Odpad',
            'Zemni_plyn_procento': 'Zemní plyn',
            'Jina_paliva_procento': 'Jiná paliva'
        }
        
        # Převod dat do formátu pro stacked bar chart
        podily_paliv_melted = pd.melt(
            podily_paliv, 
            id_vars=['Rok'], 
            value_vars=paliva_sloupce,
            var_name='Palivo', 
            value_name='Podíl'
        )
        
        # Přejmenování paliv
        podily_paliv_melted['Palivo'] = podily_paliv_melted['Palivo'].map(
            lambda x: nazvy_paliv.get(x, x.replace('_procento', ''))
        )
        
        # Vytvoření grafu
        fig = px.bar(
            podily_paliv_melted, 
            x='Rok', 
            y='Podíl',
            color='Palivo',
            title=f'Podíl paliv v čase - {typ_dodavky}' + 
                  (f' (Kraj: {kraj_nazev})' if kraj_nazev else '') +
                  (f' (Lokalita: {lokalita})' if lokalita else '') +
                  (f' (Výkon: {vykon_range[0]}-{vykon_range[1]} MW)' if vykon_range and vykon_range != [0, 6324] else ''),
            labels={'Podíl': 'Podíl [%]', 'Rok': 'Rok', 'Palivo': 'Palivo'},
            color_discrete_sequence=px.colors.qualitative.Set1
        )
        
        # Úprava vzhledu grafu
        fig.update_layout(
            xaxis=dict(tickmode='array', tickvals=sorted(podily_paliv['Rok'].unique())),
            yaxis=dict(title='Podíl [%]'),
            legend=dict(title='Palivo'),
            barmode='stack',
            plot_bgcolor='white',
            font=dict(size=12)
        )
        
        return fig
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci grafu podílu paliv: {e}")
        traceback.print_exc()
        return go.Figure().update_layout(
            title=f"Došlo k chybě při generování grafu: {str(e)}",
            annotations=[dict(
                text=f"Došlo k chybě při generování grafu: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14)
            )]
        )

# Callback pro aktualizaci tabulky cen
@callback(
    Output('tabulka-cen', 'children'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_tabulku_cen(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, predbezne_ceny):
    """Aktualizuje tabulku průměrných cen tepla."""
    try:
        print(f"Aktualizuji tabulku cen s parametry: typ_dodavky={typ_dodavky}, kraj_nazev={kraj_nazev}, vybrana_paliva={vybrana_paliva}, lokalita={lokalita}, vykon_range={vykon_range}, predbezne_ceny={predbezne_ceny}")
        
        if df.empty:
            print("DataFrame je prázdný")
            return html.Div([
                html.P("Žádná data k dispozici", 
                       style={'textAlign': 'center', 'color': COLORS['dark'], 'padding': '20px'})
            ])
        
        # Začneme s původními daty
        filtrovana_data = df.copy()
        print(f"Počet řádků před filtrováním: {len(filtrovana_data)}")
        print(f"Sloupce v datech: {filtrovana_data.columns.tolist()}")
        
        # Převod názvu kraje na kód
        kraj = None
        if kraj_nazev and 'Kod_kraje' in filtrovana_data.columns:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
                print(f"Počet řádků po filtrování podle kraje: {len(filtrovana_data)}")
        
        # Filtrování dat podle typu dodávky
        if typ_dodavky != 'Celkový průměr' and 'Typ_dodavky' in filtrovana_data.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
            print(f"Počet řádků po filtrování podle typu dodávky: {len(filtrovana_data)}")
        
        # Filtrování dat podle lokality
        if lokalita and 'Lokalita' in filtrovana_data.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
            print(f"Počet řádků po filtrování podle lokality: {len(filtrovana_data)}")
        
        # Filtrování dat podle instalovaného výkonu
        if vykon_range and 'Instalovany_vykon' in filtrovana_data.columns:
            try:
                min_vykon, max_vykon = vykon_range
                # Ujistíme se, že sloupec obsahuje numerické hodnoty
                filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
                # Nahrazení chybějících hodnot nulou
                filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
                # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
                filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
                # Filtrujeme podle rozsahu
                filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                     (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
                print(f"Počet řádků po filtrování podle výkonu: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle výkonu: {e}")
        
        # Filtrování dat podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            try:
                # Mapování názvů paliv na sloupce v datech
                nazvy_paliv_reverse = {
                    'Uhlí': 'Uhli_procento',
                    'Biomasa': 'Biomasa_procento',
                    'Odpad': 'Odpad_procento',
                    'Zemní plyn': 'Zemni_plyn_procento',
                    'Jiná paliva': 'Jina_paliva_procento'
                }
                
                # Vytvoříme masku pro filtrování
                maska = pd.Series(False, index=filtrovana_data.index)
                
                for palivo in vybrana_paliva:
                    palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                    if palivo_sloupec in filtrovana_data.columns:
                        maska = maska | (filtrovana_data[palivo_sloupec] > 50)
                
                filtrovana_data = filtrovana_data[maska]
                print(f"Počet řádků po filtrování podle paliv: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle paliv: {e}")
        
        # Filtrování předběžných cen
        if predbezne_ceny == 'vysledne' and 'Typ_ceny' in filtrovana_data.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_ceny'] != 'Předběžná']
            print(f"Počet řádků po filtrování podle typu ceny: {len(filtrovana_data)}")
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            print("Po aplikaci filtrů nezbyly žádné záznamy")
            return html.Div([
                html.P("Po aplikaci filtrů nezbyly žádné záznamy.", 
                       style={'textAlign': 'center', 'color': COLORS['dark'], 'padding': '20px'})
            ])
        
        # Agregace dat podle roku a typu ceny
        if 'Rok' in filtrovana_data.columns and 'Typ_ceny' in filtrovana_data.columns and 'Cena' in filtrovana_data.columns:
            agregace = filtrovana_data.groupby(['Rok', 'Typ_ceny'])['Cena'].mean().reset_index()
            print(f"Počet řádků po agregaci: {len(agregace)}")
            
            # Pivot tabulka pro zobrazení
            pivot_data = agregace.pivot(index='Rok', columns='Typ_ceny', values='Cena').reset_index()
            
            # Seřazení podle roku
            pivot_data = pivot_data.sort_values('Rok')
            
            # Formátování hodnot
            for col in pivot_data.columns:
                if col != 'Rok':
                    pivot_data[col] = pivot_data[col].apply(lambda x: f"{x:.2f} Kč/GJ" if not pd.isna(x) else "-")
            
            # Styly pro glassmorphic tabulku
            table_header_style = {
                'backgroundColor': 'rgba(58, 134, 255, 0.8)',
                'color': 'white',
                'fontWeight': '600',
                'textAlign': 'center',
                'padding': '12px 15px',
                'borderBottom': '2px solid rgba(255, 255, 255, 0.3)',
                'letterSpacing': '0.5px',
                'backdropFilter': 'blur(10px)',
                'WebkitBackdropFilter': 'blur(10px)',
            }
            
            table_cell_style = {
                'padding': '10px 15px',
                'textAlign': 'center',
                'borderBottom': '1px solid rgba(255, 255, 255, 0.2)',
                'backdropFilter': 'blur(5px)',
                'WebkitBackdropFilter': 'blur(5px)',
                'transition': 'all 0.3s ease',
            }
            
            year_cell_style = {
                'padding': '10px 15px',
                'textAlign': 'center',
                'fontWeight': '600',
                'backgroundColor': 'rgba(131, 56, 236, 0.8)',
                'color': 'white',
                'borderBottom': '1px solid rgba(255, 255, 255, 0.2)',
                'letterSpacing': '0.5px',
            }
            
            # Vytvoření tabulky s glassmorphic stylem
            tabulka = html.Table([
                html.Thead(
                    html.Tr([
                        html.Th("Rok", style=table_header_style)
                    ] + [
                        html.Th(col, style=table_header_style) for col in pivot_data.columns if col != 'Rok'
                    ])
                ),
                html.Tbody([
                    html.Tr([
                        html.Td(row['Rok'], style=year_cell_style)
                    ] + [
                        html.Td(
                            row[col], 
                            style={
                                **table_cell_style,
                                'backgroundColor': 'rgba(255, 255, 255, 0.15)' if i % 2 == 0 else 'rgba(255, 255, 255, 0.05)',
                                'color': COLORS['dark']
                            }
                        ) for col in pivot_data.columns if col != 'Rok'
                    ]) for i, (_, row) in enumerate(pivot_data.iterrows())
                ])
            ], style={
                'width': '100%',
                'borderCollapse': 'separate',
                'borderSpacing': '0',
                'boxShadow': '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
                'borderRadius': '16px',
                'overflow': 'hidden',
                'marginTop': '15px',
                'border': '1px solid rgba(255, 255, 255, 0.18)',
                'backdropFilter': 'blur(10px)',
                'WebkitBackdropFilter': 'blur(10px)',
            })
            
            # Přidání informace o filtrech
            filtry_info = []
            if typ_dodavky != 'Celkový průměr':
                filtry_info.append(f"Typ dodávky: {typ_dodavky}")
            if kraj_nazev:
                filtry_info.append(f"Kraj: {kraj_nazev}")
            if lokalita:
                filtry_info.append(f"Lokalita: {lokalita}")
            if vykon_range and vykon_range != [0, 6324]:
                filtry_info.append(f"Výkon: {vykon_range[0]}-{vykon_range[1]} MW")
            if vybrana_paliva and len(vybrana_paliva) < 5:
                filtry_info.append(f"Paliva: {', '.join(vybrana_paliva)}")
            
            filtry_text = "Průměrné ceny tepla"
            if filtry_info:
                filtry_text += f" ({'; '.join(filtry_info)})"
            
            return html.Div([
                html.P(filtry_text, style={
                    'fontSize': '14px',
                    'fontStyle': 'italic',
                    'color': COLORS['dark'],
                    'marginBottom': '15px',
                    'textAlign': 'center',
                    'letterSpacing': '0.3px'
                }),
                tabulka
            ])
        else:
            print("Chybí některý z potřebných sloupců pro agregaci")
            return html.Div([
                html.P("Nelze vytvořit tabulku - chybí potřebná data", 
                       style={'textAlign': 'center', 'color': COLORS['dark'], 'padding': '20px'})
            ])
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci tabulky cen: {e}")
        traceback.print_exc()
        return html.Div([
            html.P(f"Došlo k chybě při generování tabulky: {str(e)}", 
                   style={'textAlign': 'center', 'color': COLORS['accent'], 'padding': '20px'})
        ])

# Callback pro aktualizaci seznamu lokalit v dropdown
@callback(
    Output('lokalita-dropdown', 'options'),
    [Input('kraj-dropdown', 'value'),
     Input('typ-dodavky-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('vykon-range-slider', 'value')]
)
def aktualizuj_lokalita_dropdown(kraj_nazev, typ_dodavky, vybrana_paliva, vykon_range):
    """Aktualizuje seznam lokalit v dropdown podle vybraných filtrů."""
    try:
        print(f"Aktualizuji seznam lokalit s parametry: kraj_nazev={kraj_nazev}, typ_dodavky={typ_dodavky}, vybrana_paliva={vybrana_paliva}, vykon_range={vykon_range}")
        
        if df.empty:
            print("DataFrame je prázdný")
            return []
            
        if 'Lokalita' not in df.columns:
            print("Sloupec Lokalita neexistuje")
            return []
        
        # Začneme s původními daty
        filtrovana_data = df.copy()
        print(f"Počet řádků před filtrováním: {len(filtrovana_data)}")
        
        # Filtrování podle kraje
        if kraj_nazev and 'Kod_kraje' in filtrovana_data.columns:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
                print(f"Počet řádků po filtrování podle kraje: {len(filtrovana_data)}")
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr' and 'Typ_dodavky' in filtrovana_data.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
            print(f"Počet řádků po filtrování podle typu dodávky: {len(filtrovana_data)}")
        
        # Filtrování podle paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            try:
                # Mapování názvů paliv na sloupce v datech
                nazvy_paliv_reverse = {
                    'Uhlí': 'Uhli_procento',
                    'Biomasa': 'Biomasa_procento',
                    'Odpad': 'Odpad_procento',
                    'Zemní plyn': 'Zemni_plyn_procento',
                    'Jiná paliva': 'Jina_paliva_procento'
                }
                
                # Vytvoříme masku pro filtrování
                maska = pd.Series(False, index=filtrovana_data.index)
                
                for palivo in vybrana_paliva:
                    palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                    if palivo_sloupec in filtrovana_data.columns:
                        maska = maska | (filtrovana_data[palivo_sloupec] > 50)
                
                filtrovana_data = filtrovana_data[maska]
                print(f"Počet řádků po filtrování podle paliv: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle paliv: {e}")
        
        # Filtrování podle výkonu
        if vykon_range and 'Instalovany_vykon' in filtrovana_data.columns:
            try:
                min_vykon, max_vykon = vykon_range
                # Ujistíme se, že sloupec obsahuje numerické hodnoty
                filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
                # Nahrazení chybějících hodnot nulou
                filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
                # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
                filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
                # Filtrujeme podle rozsahu
                filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                     (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
                print(f"Počet řádků po filtrování podle výkonu: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle výkonu: {e}")
        
        # Získání unikátních lokalit
        unikatni_lokality = sorted(filtrovana_data['Lokalita'].unique())
        print(f"Počet unikátních lokalit: {len(unikatni_lokality)}")
        
        # Vytvoření seznamu možností pro dropdown
        options = [{'label': lokalita, 'value': lokalita} for lokalita in unikatni_lokality]
        
        return options
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci seznamu lokalit: {e}")
        traceback.print_exc()
        return []

# Callback pro aktualizaci zobrazení vybraného rozsahu výkonu
@callback(
    [Output('vykon-min-display', 'children'),
     Output('vykon-max-display', 'children')],
    [Input('vykon-range-slider', 'value')]
)
def aktualizuj_vykon_display(vykon_range):
    """Aktualizuje zobrazení vybraného rozsahu výkonu."""
    min_vykon, max_vykon = vykon_range
    return f"Od: {min_vykon} MW", f"Do: {max_vykon} MW"

# Callback pro zobrazení mezních hodnot instalovaného výkonu
@callback(
    [Output('vykon-min-hodnota', 'children'),
     Output('vykon-max-hodnota', 'children')],
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value')]
)
def aktualizuj_mezni_hodnoty_vykonu(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita):
    """Aktualizuje zobrazení mezních hodnot instalovaného výkonu."""
    try:
        print("Aktualizuji mezní hodnoty výkonu")
        
        # Kontrola, zda DataFrame není prázdný a zda obsahuje sloupec Instalovany_vykon
        if df.empty:
            print("DataFrame je prázdný")
            return "Min: 0 MW", "Max: 6324 MW"
            
        if 'Instalovany_vykon' not in df.columns:
            print("Sloupec Instalovany_vykon neexistuje")
            return "Min: 0 MW", "Max: 6324 MW"
        
        # Filtrování dat podle vybraných filtrů
        filtrovana_data = df.copy()
        print("Počet řádků před filtrováním:", len(filtrovana_data))
        
        # Ujistíme se, že sloupec obsahuje numerické hodnoty
        filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
        filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
        
        # Převod názvu kraje na kód
        kraj = None
        if kraj_nazev and 'Kod_kraje' in df.columns:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
                print(f"Filtrováno podle kraje {kraj_nazev} (kód: {kraj}), počet řádků:", len(filtrovana_data))
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
            print(f"Filtrováno podle typu dodávky {typ_dodavky}, počet řádků:", len(filtrovana_data))
        
        # Filtrování podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0:
            nazvy_paliv_reverse = {
                'Uhlí': 'Uhli_procento',
                'Biomasa': 'Biomasa_procento',
                'Odpad': 'Odpad_procento',
                'Zemní plyn': 'Zemni_plyn_procento',
                'Jiná paliva': 'Jina_paliva_procento'
            }
            
            # Vytvoříme masku pro filtrování
            maska = pd.Series(False, index=filtrovana_data.index)
            
            for palivo in vybrana_paliva:
                palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                if palivo_sloupec in df.columns:
                    maska = maska | (filtrovana_data[palivo_sloupec] > 50)
            
            filtrovana_data = filtrovana_data[maska]
            print(f"Filtrováno podle paliv {vybrana_paliva}, počet řádků:", len(filtrovana_data))
        
        # Filtrování podle lokality
        if lokalita and 'Lokalita' in df.columns:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
            print(f"Filtrováno podle lokality {lokalita}, počet řádků:", len(filtrovana_data))
        
        # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
        filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
        print("Počet řádků po odstranění NaN hodnot v Instalovany_vykon:", len(filtrovana_data))
        
        # Výpočet mezních hodnot
        if filtrovana_data.empty:
            print("Po filtrování nezbyly žádné řádky")
            return "Min: 0 MW", "Max: 6324 MW"
        
        if 'Instalovany_vykon' not in filtrovana_data.columns:
            print("Sloupec Instalovany_vykon není v filtrovaných datech")
            return "Min: 0 MW", "Max: 6324 MW"
        
        # Kontrola, zda sloupec obsahuje nějaké hodnoty
        if filtrovana_data['Instalovany_vykon'].count() == 0:
            print("Sloupec Instalovany_vykon neobsahuje žádné hodnoty")
            return "Min: 0 MW", "Max: 6324 MW"
        
        min_vykon = filtrovana_data['Instalovany_vykon'].min()
        max_vykon = filtrovana_data['Instalovany_vykon'].max()
        
        print(f"Vypočtené mezní hodnoty: min={min_vykon}, max={max_vykon}")
        
        # Ošetření případu, kdy nejsou data
        if pd.isna(min_vykon) or pd.isna(max_vykon):
            print("Vypočtené hodnoty obsahují NaN")
            return "Min: 0 MW", "Max: 6324 MW"
            
        return f"Min: {min_vykon:.2f} MW", f"Max: {max_vykon:.2f} MW"
    except Exception as e:
        print(f"Chyba při výpočtu mezních hodnot: {e}")
        import traceback
        traceback.print_exc()
        return "Min: 0 MW", "Max: 6324 MW"

# Callback pro aktualizaci zobrazení rozsahu cen
@callback(
    [Output('cena-min-display', 'children'),
     Output('cena-max-display', 'children')],
    [Input('cena-range-slider', 'value')]
)
def aktualizuj_cena_display(cena_range):
    """Aktualizuje zobrazení vybraného rozsahu cen."""
    min_cena, max_cena = cena_range
    return f"Min: {min_cena} Kč/GJ", f"Max: {max_cena} Kč/GJ"

# Upravený callback pro mapu, který zahrnuje filtr cen
@callback(
    Output('mapa-cr', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('cena-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_mapu_cr(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny):
    """Aktualizuje mapu ČR s cenami tepla."""
    try:
        print(f"Aktualizuji mapu s parametry: typ_dodavky={typ_dodavky}, kraj_nazev={kraj_nazev}, vybrana_paliva={vybrana_paliva}, lokalita={lokalita}, vykon_range={vykon_range}, cena_range={cena_range}, predbezne_ceny={predbezne_ceny}")
        
        # Vytvoření prázdné mapy
        fig = go.Figure()
        
        if df.empty:
            print("DataFrame je prázdný")
            # Vytvoření prázdné mapy
            fig.update_layout(
                mapbox=dict(
                    style="carto-positron",
                    zoom=5.5,
                    center={"lat": 49.8, "lon": 15.5},
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin={"r": 0, "t": 30, "l": 0, "b": 0},
                height=600,
                title={
                    'text': "Mapa cen tepla v ČR<br><sup>Žádná data k dispozici</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                }
            )
            return fig
        
        # Vytvoření kopie dat pro filtrování
        filtrovana_data = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            # Mapování názvů paliv na sloupce v datech
            nazvy_paliv_reverse = {
                'Uhlí': 'Uhli_procento',
                'Biomasa': 'Biomasa_procento',
                'Odpad': 'Odpad_procento',
                'Zemní plyn': 'Zemni_plyn_procento',
                'Jiná paliva': 'Jina_paliva_procento'
            }
            
            # Vytvoříme masku pro filtrování
            maska = pd.Series(False, index=filtrovana_data.index)
            
            for palivo in vybrana_paliva:
                palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                if palivo_sloupec in df.columns:
                    maska = maska | (filtrovana_data[palivo_sloupec] > 50)
            
            filtrovana_data = filtrovana_data[maska]
            print(f"Počet řádků po filtrování podle paliv: {len(filtrovana_data)}")
        
        # Filtrování podle lokality
        if lokalita:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
            print(f"Počet řádků po filtrování podle lokality: {len(filtrovana_data)}")
        
        # Filtrování podle výkonu
        if vykon_range and 'Instalovany_vykon' in filtrovana_data.columns:
            try:
                min_vykon, max_vykon = vykon_range
                # Nahrazení chybějících hodnot nulou
                filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
                # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
                filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
                # Filtrujeme podle rozsahu
                filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                     (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
                print(f"Počet řádků po filtrování podle výkonu: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle výkonu: {e}")
        
        # Filtrování podle rozsahu cen
        if cena_range:
            try:
                min_cena, max_cena = cena_range
                cena_sloupec = 'Cena_tepla' if 'Cena_tepla' in filtrovana_data.columns else 'Cena'
                filtrovana_data = filtrovana_data[(filtrovana_data[cena_sloupec] >= min_cena) & 
                                                 (filtrovana_data[cena_sloupec] <= max_cena)]
                print(f"Počet řádků po filtrování podle ceny: {len(filtrovana_data)}")
            except Exception as e:
                print(f"Chyba při filtrování podle ceny: {e}")
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            print("Po filtrování nezbyly žádné záznamy")
            # Vytvoření prázdné mapy
            fig.update_layout(
                mapbox=dict(
                    style="carto-positron",
                    zoom=5.5,
                    center={"lat": 49.8, "lon": 15.5},
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin={"r": 0, "t": 30, "l": 0, "b": 0},
                height=600,
                title={
                    'text': "Mapa cen tepla v ČR<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                }
            )
            
            return fig
        
        # Definice barev pro kraje
        kraje_barvy = {
            'A': '#3a86ff',      # Hlavní město Praha
            'S': '#1f77b4',      # Středočeský kraj
            'C': '#ff7f0e',      # Jihočeský kraj
            'P': '#2ca02c',      # Plzeňský kraj
            'K': '#d62728',      # Karlovarský kraj
            'U': '#9467bd',      # Ústecký kraj
            'L': '#8c564b',      # Liberecký kraj
            'H': '#e377c2',      # Královéhradecký kraj
            'E': '#7f7f7f',      # Pardubický kraj
            'J': '#bcbd22',      # Kraj Vysočina
            'B': '#17becf',      # Jihomoravský kraj
            'M': '#aec7e8',      # Olomoucký kraj
            'Z': '#ffbb78',      # Zlínský kraj
            'T': '#98df8a'       # Moravskoslezský kraj
        }
        
        # Určení sloupce s cenou
        cena_sloupec = 'Cena_tepla' if 'Cena_tepla' in filtrovana_data.columns else 'Cena'
        
        # Agregace dat podle lokalit
        if 'Lokalita' in filtrovana_data.columns and 'Kod_kraje' in filtrovana_data.columns:
            try:
                lokality_data = filtrovana_data.groupby(['Lokalita', 'Kod_kraje'])[cena_sloupec].mean().reset_index()
                print(f"Počet lokalit po agregaci: {len(lokality_data)}")
                
                # Přidání souřadnic lokalit
                lokality_data['lat'] = None
                lokality_data['lon'] = None
                
                # Přidání souřadnic z mapování
                for idx, row in lokality_data.iterrows():
                    lokalita_name = row['Lokalita']
                    kod_kraje = row['Kod_kraje']
                    klic = f"{lokalita_name}|{kod_kraje}"
                    
                    # Pokud existuje mapování pro tuto kombinaci lokalita-kraj
                    if rozsirene_mapovani_lokalit and klic in rozsirene_mapovani_lokalit:
                        lokality_data.at[idx, 'lat'] = rozsirene_mapovani_lokalit[klic].get('lat')
                        lokality_data.at[idx, 'lon'] = rozsirene_mapovani_lokalit[klic].get('lon')
                    # Pokud neexistuje mapování pro tuto kombinaci, ale existuje pro lokalitu
                    elif mapovani_lokalit and lokalita_name in mapovani_lokalit:
                        lokality_data.at[idx, 'lat'] = mapovani_lokalit[lokalita_name].get('lat')
                        lokality_data.at[idx, 'lon'] = mapovani_lokalit[lokalita_name].get('lon')
                
                # Filtrujeme pouze lokality, pro které máme souřadnice
                lokality_data = lokality_data.dropna(subset=['lat', 'lon'])
                print(f"Počet lokalit se souřadnicemi: {len(lokality_data)}")
                
                if not lokality_data.empty:
                    # Ošetření extrémních hodnot cen
                    max_zobrazena_cena = 2500  # Maximální zobrazovaná cena
                    lokality_data[cena_sloupec] = lokality_data[cena_sloupec].apply(
                        lambda x: min(x, max_zobrazena_cena)
                    )
                    
                    # Vytvoření seznamů pro souřadnice a texty
                    lats = []
                    lons = []
                    texts = []
                    colors = []
                    sizes = []
                    lokalita_names = []  # Seznam pro ukládání názvů lokalit
                    
                    for _, row in lokality_data.iterrows():
                        lats.append(row['lat'])
                        lons.append(row['lon'])
                        lokalita_names.append(row['Lokalita'])  # Uložení názvu lokality
                        
                        # Přidání informace o původní ceně, pokud byla omezena
                        puvodni_cena = row[cena_sloupec]
                        zobrazena_cena = min(puvodni_cena, max_zobrazena_cena)
                        
                        if puvodni_cena > max_zobrazena_cena:
                            text = f"{row['Lokalita']} ({zobrazena_cena:.2f} Kč/GJ, původní: {puvodni_cena:.2f} Kč/GJ)"
                        else:
                            text = f"{row['Lokalita']} ({zobrazena_cena:.2f} Kč/GJ)"
                            
                        texts.append(text)
                        colors.append(kraje_barvy.get(row['Kod_kraje'], '#3a86ff'))
                        
                        # Zvýrazníme vybranou lokalitu větším bodem
                        if row['Lokalita'] == lokalita:
                            sizes.append(15)  # Větší velikost pro vybranou lokalitu
                        else:
                            sizes.append(10)  # Standardní velikost pro ostatní lokality
                    
                    # Přidání bodů na mapu s customdata pro identifikaci lokality při kliknutí
                    fig.add_trace(go.Scattermapbox(
                        lat=lats,
                        lon=lons,
                        mode='markers',
                        marker=dict(
                            size=sizes,
                            color=colors,
                            opacity=0.8
                        ),
                        text=texts,
                        hoverinfo='text',
                        customdata=lokalita_names,  # Přidání názvů lokalit jako customdata
                    ))
                    
                    print("Body lokalit úspěšně přidány na mapu")
                else:
                    print("Žádné lokality se souřadnicemi")
            except Exception as e:
                print(f"Chyba při zpracování lokalit: {e}")
                import traceback
                traceback.print_exc()
        
        # Nastavení layoutu mapy
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",
                zoom=5.5,
                center={"lat": 49.8, "lon": 15.5},
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin={"r": 0, "t": 30, "l": 0, "b": 0},
            height=600,
            showlegend=False,
            title={
                'text': "Mapa cen tepla v ČR<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            clickmode='event+select',  # Povolení klikání na body
        )
        
        print("Mapa úspěšně vytvořena")
        return fig
    
    except Exception as e:
        print(f"Chyba při aktualizaci mapy: {e}")
        import traceback
        traceback.print_exc()
        # Vytvoření prázdné mapy v případě chyby
        fig = go.Figure()
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        # Přidání mapového podkladu
        fig.update_layout(
            mapbox=dict(
                style="carto-positron",
                zoom=5.5,
                center={"lat": 49.8, "lon": 15.5},
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin={"r": 0, "t": 30, "l": 0, "b": 0},
            height=600,
            title={
                'text': "Chyba při zobrazení mapy<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            }
        )
        
        return fig

# Callback pro aktualizaci dropdown menu po kliknutí na bod v mapě
@callback(
    Output('lokalita-dropdown', 'value'),
    [Input('mapa-cr', 'clickData')],
    [State('lokalita-dropdown', 'options')]
)
def aktualizuj_lokalitu_z_mapy(clickData, options):
    """Aktualizuje vybranou lokalitu po kliknutí na bod v mapě."""
    if clickData is None:
        # Pokud uživatel neklikl na žádný bod, necháme hodnotu beze změny
        raise dash.exceptions.PreventUpdate
    
    try:
        # Získání názvu lokality z customdata kliknutého bodu
        lokalita_name = clickData['points'][0]['customdata']
        
        # Kontrola, zda je lokalita v seznamu možností
        dostupne_lokality = [opt['value'] for opt in options] if options else []
        
        if lokalita_name in dostupne_lokality:
            print(f"Vybrána lokalita z mapy: {lokalita_name}")
            return lokalita_name
        else:
            print(f"Lokalita {lokalita_name} není v seznamu dostupných lokalit")
            raise dash.exceptions.PreventUpdate
    
    except Exception as e:
        print(f"Chyba při aktualizaci lokality z mapy: {e}")
        import traceback
        traceback.print_exc()
        raise dash.exceptions.PreventUpdate

# Přidání callbacku pro synchronizaci mezi slidery a manuálními vstupy
@callback(
    [Output('vykon-range-slider', 'value'),
     Output('vykon-min-input', 'value'),
     Output('vykon-max-input', 'value')],
    [Input('vykon-apply-button', 'n_clicks'),
     Input('vykon-range-slider', 'value')],
    [State('vykon-min-input', 'value'),
     State('vykon-max-input', 'value')]
)
def synchronizuj_vykon_vstupy(n_clicks, slider_value, min_input, max_input):
    """Synchronizuje hodnoty mezi sliderem a manuálními vstupy pro výkon."""
    ctx = dash.callback_context
    
    # Zjištění, který vstup vyvolal callback
    if not ctx.triggered:
        # Pokud callback nebyl vyvolán žádným vstupem, vrátíme výchozí hodnoty
        return [0, 6324], 0, 6324
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'vykon-apply-button':
        # Pokud byl stisknut tlačítko "Použít", aktualizujeme slider podle manuálních vstupů
        # Zajistíme, že min je menší než max
        min_val = min(min_input or 0, max_input or 6324)
        max_val = max(min_input or 0, max_input or 6324)
        return [min_val, max_val], min_val, max_val
    else:
        # Pokud byl změněn slider, aktualizujeme manuální vstupy
        return slider_value, slider_value[0], slider_value[1]

# Callback pro AI prognózu
@callback(
    Output('forecast-graph', 'figure'),
    [Input('forecast-method-dropdown', 'value'),
     Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value')]
)
def aktualizuj_ai_prognozu(forecast_method, typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range):
    """Aktualizuje AI prognózu vývoje cen tepla."""
    if not AI_FORECASTING_AVAILABLE:
        # Vytvoření náhradního grafu
        fig = go.Figure()
        fig.update_layout(
            title="AI prognóza není k dispozici",
            xaxis={'visible': False},
            yaxis={'visible': False},
            annotations=[{
                'text': "Pro zobrazení AI prognózy je potřeba nainstalovat dodatečné knihovny",
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 16, 'color': COLORS['dark']}
            }],
            plot_bgcolor='rgba(255, 255, 255, 0.0)',
            paper_bgcolor='rgba(255, 255, 255, 0.0)'
        )
        return fig
    
    try:
        # Filtrování dat podle vybraných parametrů
        filtered_df = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtered_df = filtered_df[filtered_df['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev is not None and kraj_nazev != 'Všechny kraje':
            # Zkontrolujeme, zda existuje sloupec 'Kraj_nazev' nebo 'Kod_kraje'
            if 'Kraj_nazev' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Kraj_nazev'] == kraj_nazev]
            elif 'Kod_kraje' in filtered_df.columns:
                # Převod názvu kraje na kód
                kraj_kod = nazvy_na_kody.get(kraj_nazev)
                if kraj_kod:
                    filtered_df = filtered_df[filtered_df['Kod_kraje'] == kraj_kod]
        
        # Filtrování podle paliv
        if vybrana_paliva and 'Všechna paliva' not in vybrana_paliva:
            # Zkontrolujeme, zda existuje sloupec 'Palivo'
            if 'Palivo' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Palivo'].isin(vybrana_paliva)]
            else:
                # Mapování názvů paliv na sloupce v datech
                nazvy_paliv_reverse = {
                    'Uhlí': 'Uhli_procento',
                    'Biomasa': 'Biomasa_procento',
                    'Odpad': 'Odpad_procento',
                    'Zemní plyn': 'Zemni_plyn_procento',
                    'Jiná paliva': 'Jina_paliva_procento'
                }
                
                # Vytvoříme masku pro filtrování
                maska = pd.Series(False, index=filtered_df.index)
                
                for palivo in vybrana_paliva:
                    palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                    if palivo_sloupec in filtered_df.columns:
                        maska = maska | (filtered_df[palivo_sloupec] > 50)
                
                filtered_df = filtered_df[maska]
        
        # Filtrování podle lokality
        if lokalita is not None and lokalita != 'Všechny lokality':
            if 'Lokalita' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['Lokalita'] == lokalita]
        
        # Filtrování podle výkonu
        min_vykon, max_vykon = vykon_range
        if 'Instalovany_vykon' in filtered_df.columns:
            filtered_df = filtered_df[(filtered_df['Instalovany_vykon'] >= min_vykon) & 
                                    (filtered_df['Instalovany_vykon'] <= max_vykon)]
        
        # Kontrola, zda máme data po filtrování
        if filtered_df.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title="Po aplikaci filtrů nezbyly žádné záznamy pro AI prognózu",
                xaxis={'visible': False},
                yaxis={'visible': False},
                annotations=[{
                    'text': "Po aplikaci filtrů nezbyly žádné záznamy pro AI prognózu",
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 16, 'color': COLORS['dark']}
                }],
                plot_bgcolor='rgba(255, 255, 255, 0.0)',
                paper_bgcolor='rgba(255, 255, 255, 0.0)'
            )
            return fig
        
        # Výpočet průměrných cen podle roku
        # Zkontrolujeme, zda existuje sloupec 'Cena_tepla' nebo 'Cena'
        cena_sloupec = 'Cena_tepla' if 'Cena_tepla' in filtered_df.columns else 'Cena'
        avg_prices = filtered_df.groupby('Rok')[cena_sloupec].mean().reset_index()
        
        # Přejmenování sloupců pro AI prognózu
        forecast_data = avg_prices.rename(columns={cena_sloupec: 'Cena'})
        
        # Generování AI prognózy
        forecast_fig, _ = forecast_heat_prices(forecast_data, forecast_periods=5, method=forecast_method)
        
        return forecast_fig
    
    except Exception as e:
        print(f"Chyba při aktualizaci AI prognózy: {e}")
        # Vytvoření prázdného grafu v případě chyby
        fig = go.Figure()
        fig.update_layout(
            title="Nepodařilo se vygenerovat AI prognózu",
            xaxis={'visible': False},
            yaxis={'visible': False},
            annotations=[{
                'text': f"Chyba: {str(e)}",
                'xref': 'paper',
                'yref': 'paper',
                'showarrow': False,
                'font': {'size': 14, 'color': COLORS['accent']}
            }],
            plot_bgcolor='rgba(255, 255, 255, 0.0)',
            paper_bgcolor='rgba(255, 255, 255, 0.0)'
        )
        return fig

@callback(
    Output('porovnani-cen-graf', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('cena-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_graf_porovnani_cen(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny):
    """Aktualizuje graf porovnání cen tepla podle typu dodávky."""
    try:
        # Filtrování dat podle vybraných filtrů
        filtrovana_data = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování podle lokality
        if lokalita:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
        
        # Filtrování podle instalovaného výkonu
        if vykon_range:
            min_vykon, max_vykon = vykon_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
            # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                 (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
        
        # Filtrování podle ceny
        if cena_range:
            min_cena, max_cena = cena_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Cena'] = pd.to_numeric(filtrovana_data['Cena'], errors='coerce')
            # Filtrujeme pouze řádky, kde Cena není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Cena'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Cena'] >= min_cena) & 
                                 (filtrovana_data['Cena'] <= max_cena)]
        
        # Filtrování podle vybraných paliv
        if vybrana_paliva and len(vybrana_paliva) > 0 and vybrana_paliva != ['Všechna paliva']:
            # Mapování názvů paliv na sloupce v datech
            nazvy_paliv_reverse = {
                'Uhlí': 'Uhli_procento',
                'Biomasa': 'Biomasa_procento',
                'Odpad': 'Odpad_procento',
                'Zemní plyn': 'Zemni_plyn_procento',
                'Jiná paliva': 'Jina_paliva_procento'
            }
            
            # Vytvoříme masku pro filtrování
            maska = pd.Series(False, index=filtrovana_data.index)
            
            for palivo in vybrana_paliva:
                palivo_sloupec = nazvy_paliv_reverse.get(palivo, palivo.replace(' ', '_') + '_procento')
                if palivo_sloupec in df.columns:
                    maska = maska | (filtrovana_data[palivo_sloupec] > 50)
            
            filtrovana_data = filtrovana_data[maska]
        
        # Filtrování předběžných cen
        if predbezne_ceny == 'vysledne':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_ceny'] != 'Předběžná']
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Porovnání cen tepla podle typu dodávky<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Typ dodávky",
                yaxis_title="Cena tepla [Kč/GJ]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Žádná data k zobrazení pro vybrané filtry",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark'])
            )
            return fig
        
        # Získání posledního roku v datech
        posledni_rok = filtrovana_data['Rok'].max()
        
        # Filtrování dat pouze pro poslední rok
        data_posledni_rok = filtrovana_data[filtrovana_data['Rok'] == posledni_rok]
        
        # Agregace dat podle typu dodávky
        agregace = data_posledni_rok.groupby('Typ_dodavky')['Cena'].agg(['mean', 'count']).reset_index()
        
        # Seřazení podle průměrné ceny
        agregace = agregace.sort_values('mean', ascending=False)
        
        # Vytvoření grafu
        fig = go.Figure()
        
        # Přidání sloupců pro každý typ dodávky
        fig.add_trace(go.Bar(
            x=agregace['Typ_dodavky'],
            y=agregace['mean'],
            text=agregace['mean'].round(2).astype(str) + ' Kč/GJ',
            textposition='auto',
            marker_color=COLORS['primary'],
            hovertemplate='%{x}<br>Průměrná cena: %{y:.2f} Kč/GJ<br>Počet lokalit: %{customdata}<extra></extra>',
            customdata=agregace['count']
        ))
        
        # Nastavení layoutu grafu
        fig.update_layout(
            title={
                'text': f"Porovnání cen tepla podle typu dodávky ({posledni_rok})<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Typ dodávky",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20},
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.2)',
                zerolinewidth=1
            )
        )
        
        return fig
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci grafu porovnání cen: {e}")
        traceback.print_exc()
        
        # Vytvoření prázdného grafu v případě chyby
        fig = go.Figure()
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        fig.update_layout(
            title={
                'text': "Chyba při zobrazení grafu porovnání cen<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Typ dodávky",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20}
        )
        fig.add_annotation(
            text=f"Došlo k chybě: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=COLORS['accent'])
        )
        return fig

@callback(
    Output('porovnani-paliv-graf', 'figure'),
    [Input('typ-dodavky-dropdown', 'value'),
     Input('kraj-dropdown', 'value'),
     Input('paliva-checklist', 'value'),
     Input('lokalita-dropdown', 'value'),
     Input('vykon-range-slider', 'value'),
     Input('cena-range-slider', 'value'),
     Input('predbezne-ceny-radio', 'value')]
)
def aktualizuj_graf_porovnani_paliv(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny):
    """Aktualizuje graf porovnání cen tepla podle převažujícího paliva."""
    try:
        # Filtrování dat podle vybraných filtrů
        filtrovana_data = df.copy()
        
        # Filtrování podle typu dodávky
        if typ_dodavky != 'Celkový průměr':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_dodavky'] == typ_dodavky]
        
        # Filtrování podle kraje
        if kraj_nazev:
            kraj = nazvy_na_kody.get(kraj_nazev)
            if kraj:
                filtrovana_data = filtrovana_data[filtrovana_data['Kod_kraje'] == kraj]
        
        # Filtrování podle lokality
        if lokalita:
            filtrovana_data = filtrovana_data[filtrovana_data['Lokalita'] == lokalita]
        
        # Filtrování podle instalovaného výkonu
        if vykon_range:
            min_vykon, max_vykon = vykon_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Instalovany_vykon'] = pd.to_numeric(filtrovana_data['Instalovany_vykon'], errors='coerce')
            # Nahrazení chybějících hodnot nulou
            filtrovana_data['Instalovany_vykon'] = filtrovana_data['Instalovany_vykon'].fillna(0)
            # Filtrujeme pouze řádky, kde Instalovany_vykon není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Instalovany_vykon'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Instalovany_vykon'] >= min_vykon) & 
                                 (filtrovana_data['Instalovany_vykon'] <= max_vykon)]
        
        # Filtrování podle ceny
        if cena_range:
            min_cena, max_cena = cena_range
            # Ujistíme se, že sloupec obsahuje numerické hodnoty
            filtrovana_data['Cena'] = pd.to_numeric(filtrovana_data['Cena'], errors='coerce')
            # Filtrujeme pouze řádky, kde Cena není NaN
            filtrovana_data = filtrovana_data[filtrovana_data['Cena'].notna()]
            # Filtrujeme podle rozsahu
            filtrovana_data = filtrovana_data[(filtrovana_data['Cena'] >= min_cena) & 
                                 (filtrovana_data['Cena'] <= max_cena)]
        
        # Filtrování předběžných cen
        if predbezne_ceny == 'vysledne':
            filtrovana_data = filtrovana_data[filtrovana_data['Typ_ceny'] != 'Předběžná']
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        # Kontrola, zda máme data po filtrování
        if filtrovana_data.empty:
            # Vytvoření prázdného grafu
            fig = go.Figure()
            fig.update_layout(
                title={
                    'text': "Porovnání cen tepla podle převažujícího paliva<br><sup>" + popis_filtru + "</sup>",
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 16, 'color': COLORS['dark']}
                },
                xaxis_title="Převažující palivo",
                yaxis_title="Cena tepla [Kč/GJ]",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=400,
                margin={"r": 20, "t": 60, "l": 20, "b": 20}
            )
            fig.add_annotation(
                text="Žádná data k zobrazení pro vybrané filtry",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color=COLORS['dark'])
            )
            return fig
        
        # Získání posledního roku v datech
        posledni_rok = filtrovana_data['Rok'].max()
        
        # Filtrování dat pouze pro poslední rok
        data_posledni_rok = filtrovana_data[filtrovana_data['Rok'] == posledni_rok]
        
        # Určení převažujícího paliva pro každý záznam
        paliva_sloupce = ['Uhli_procento', 'Biomasa_procento', 'Odpad_procento', 'Zemni_plyn_procento', 'Jina_paliva_procento']
        
        # Vytvoření sloupce s převažujícím palivem
        def najdi_prevazujici_palivo(row):
            max_palivo = None
            max_procento = 0
            for palivo_sloupec in paliva_sloupce:
                if palivo_sloupec in row and pd.notna(row[palivo_sloupec]) and row[palivo_sloupec] > max_procento:
                    max_procento = row[palivo_sloupec]
                    max_palivo = palivo_sloupec
            
            if max_palivo:
                # Převod názvu sloupce na čitelný název paliva
                nazvy_paliv = {
                    'Uhli_procento': 'Uhlí',
                    'Biomasa_procento': 'Biomasa',
                    'Odpad_procento': 'Odpad',
                    'Zemni_plyn_procento': 'Zemní plyn',
                    'Jina_paliva_procento': 'Jiná paliva'
                }
                return nazvy_paliv.get(max_palivo, max_palivo.replace('_procento', ''))
            else:
                return 'Neurčeno'
        
        data_posledni_rok['Prevazujici_palivo'] = data_posledni_rok.apply(najdi_prevazujici_palivo, axis=1)
        
        # Agregace dat podle převažujícího paliva
        agregace = data_posledni_rok.groupby('Prevazujici_palivo')['Cena'].agg(['mean', 'count']).reset_index()
        
        # Seřazení podle průměrné ceny
        agregace = agregace.sort_values('mean', ascending=False)
        
        # Vytvoření grafu
        fig = go.Figure()
        
        # Přidání sloupců pro každý typ paliva
        fig.add_trace(go.Bar(
            x=agregace['Prevazujici_palivo'],
            y=agregace['mean'],
            text=agregace['mean'].round(2).astype(str) + ' Kč/GJ',
            textposition='auto',
            marker_color=COLORS['primary'],
            hovertemplate='%{x}<br>Průměrná cena: %{y:.2f} Kč/GJ<br>Počet lokalit: %{customdata}<extra></extra>',
            customdata=agregace['count']
        ))
        
        # Nastavení layoutu grafu
        fig.update_layout(
            title={
                'text': f"Porovnání cen tepla podle převažujícího paliva ({posledni_rok})<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Převažující palivo",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20},
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=True,
                zerolinecolor='rgba(0,0,0,0.2)',
                zerolinewidth=1
            )
        )
        
        return fig
    except Exception as e:
        import traceback
        print(f"Chyba při aktualizaci grafu porovnání paliv: {e}")
        traceback.print_exc()
        
        # Vytvoření prázdného grafu v případě chyby
        fig = go.Figure()
        
        # Vytvoření popisu filtrů
        popis_filtru = vytvor_popis_filtru(typ_dodavky, kraj_nazev, vybrana_paliva, lokalita, vykon_range, cena_range, predbezne_ceny)
        
        fig.update_layout(
            title={
                'text': "Chyba při zobrazení grafu porovnání paliv<br><sup>" + popis_filtru + "</sup>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'color': COLORS['dark']}
            },
            xaxis_title="Převažující palivo",
            yaxis_title="Cena tepla [Kč/GJ]",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin={"r": 20, "t": 60, "l": 20, "b": 20}
        )
        fig.add_annotation(
            text=f"Došlo k chybě: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=14, color=COLORS['accent'])
        )
        return fig

# Spuštění aplikace
if __name__ == '__main__':
    app.run_server(debug=True, port=8051) 