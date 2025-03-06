#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dashboard pro vizualizaci dat o cenách tepla.
"""

import os
import pandas as pd
import mysql.connector
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import logging
from pathlib import Path
import dotenv

# Načtení proměnných prostředí z .env souboru
dotenv.load_dotenv()

# Nastavení loggeru
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dashboard.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Načtení dat z databáze
def nacti_data_z_databaze():
    """
    Načte data z databáze.
    
    Returns:
        pandas.DataFrame: DataFrame s daty nebo prázdný DataFrame v případě chyby
    """
    try:
        spojeni = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'ceny_tepla_db'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', '')
        )
        
        if not spojeni.is_connected():
            logger.error("Nelze se připojit k databázi")
            return pd.DataFrame()
        
        dotaz = """
        SELECT 
            r.Rok, 
            k.NazevKraje, 
            l.NazevLokality, 
            td.NazevTypuDodavky,
            ct.InstalovanyVykon,
            ct.PocetOdbernychMist,
            ct.PocetOdberatelu,
            ct.Cena,
            ct.Mnozstvi,
            ct.UhliProcento,
            ct.BiomasaProcento,
            ct.OdpadProcento,
            ct.ZemniPlynProcento,
            ct.JinaPalivaProcento
        FROM 
            CenyTepla ct
            JOIN Lokality l ON ct.LokalitaID = l.LokalitaID
            JOIN Kraje k ON l.KodKraje = k.KodKraje
            JOIN Roky r ON ct.RokID = r.RokID
            JOIN TypyDodavek td ON ct.TypDodavkyID = td.TypDodavkyID
        """
        
        data = pd.read_sql(dotaz, spojeni)
        spojeni.close()
        
        logger.info(f"Načteno {len(data)} záznamů z databáze")
        return data
    except Exception as e:
        logger.error(f"Chyba při načítání dat z databáze: {e}")
        return pd.DataFrame()

# Načtení dat z CSV, pokud není dostupná databáze
def nacti_data_z_csv():
    """
    Načte data z CSV souboru, pokud není dostupná databáze.
    
    Returns:
        pandas.DataFrame: DataFrame s daty nebo prázdný DataFrame v případě chyby
    """
    try:
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        CSV_DIR = BASE_DIR / "data" / "csv"
        csv_soubor = CSV_DIR / "ceny_tepla_vsechny_roky.csv"
        
        if not csv_soubor.exists():
            logger.error(f"CSV soubor {csv_soubor} neexistuje")
            return pd.DataFrame()
        
        data = pd.read_csv(csv_soubor, encoding='utf-8')
        
        # Přejmenování sloupců pro kompatibilitu s databázovým formátem
        data = data.rename(columns={
            'Kod_kraje': 'NazevKraje',  # Dočasné řešení, ve skutečnosti by bylo potřeba mapování
            'Lokalita': 'NazevLokality',
            'Typ_dodavky': 'NazevTypuDodavky',
            'Instalovany_vykon': 'InstalovanyVykon',
            'Pocet_odbernych_mist': 'PocetOdbernychMist',
            'Pocet_odberatelu': 'PocetOdberatelu',
            'Uhli_procento': 'UhliProcento',
            'Biomasa_procento': 'BiomasaProcento',
            'Odpad_procento': 'OdpadProcento',
            'Zemni_plyn_procento': 'ZemniPlynProcento',
            'Jina_paliva_procento': 'JinaPalivaProcento'
        })
        
        logger.info(f"Načteno {len(data)} záznamů z CSV souboru")
        return data
    except Exception as e:
        logger.error(f"Chyba při načítání dat z CSV souboru: {e}")
        return pd.DataFrame()

# Načtení dat
data = nacti_data_z_databaze()
if data.empty:
    logger.warning("Data nebyla načtena z databáze, zkouším načíst z CSV")
    data = nacti_data_z_csv()

if data.empty:
    logger.error("Nepodařilo se načíst data ani z databáze, ani z CSV")
    # Vytvoření prázdného DataFrame s potřebnými sloupci
    data = pd.DataFrame(columns=[
        'Rok', 'NazevKraje', 'NazevLokality', 'NazevTypuDodavky',
        'InstalovanyVykon', 'PocetOdbernychMist', 'PocetOdberatelu',
        'Cena', 'Mnozstvi', 'UhliProcento', 'BiomasaProcento',
        'OdpadProcento', 'ZemniPlynProcento', 'JinaPalivaProcento'
    ])

# Inicializace Dash aplikace
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"}
    ]
)
app.title = "Analýza cen tepelné energie v ČR"

# Layout aplikace
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Analýza cen tepelné energie v ČR", className="text-center my-4")
        ])
    ]),
    
    # Filtry
    dbc.Row([
        dbc.Col([
            html.H4("Filtry", className="mb-3"),
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Rok:"),
                            dcc.Dropdown(
                                id='rok-dropdown',
                                options=[{'label': str(rok), 'value': rok} for rok in sorted(data['Rok'].unique())] if not data.empty else [],
                                value=max(data['Rok'].unique()) if not data.empty and len(data['Rok'].unique()) > 0 else None,
                                multi=True
                            )
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("Kraj:"),
                            dcc.Dropdown(
                                id='kraj-dropdown',
                                options=[{'label': kraj, 'value': kraj} for kraj in sorted(data['NazevKraje'].unique())] if not data.empty else [],
                                multi=True
                            )
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("Typ dodávky:"),
                            dcc.Dropdown(
                                id='typ-dodavky-dropdown',
                                options=[{'label': typ, 'value': typ} for typ in sorted(data['NazevTypuDodavky'].unique())] if not data.empty else [],
                                multi=True
                            )
                        ], width=4)
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("Lokalita:"),
                            dcc.Dropdown(
                                id='lokalita-dropdown',
                                options=[{'label': lokalita, 'value': lokalita} for lokalita in sorted(data['NazevLokality'].unique())] if not data.empty else [],
                                multi=True
                            )
                        ], width=6),
                        
                        dbc.Col([
                            html.Label("Rozsah cen [Kč/GJ]:"),
                            dcc.RangeSlider(
                                id='cena-slider',
                                min=data['Cena'].min() if not data.empty else 0,
                                max=data['Cena'].max() if not data.empty else 2000,
                                step=50,
                                marks={i: str(i) for i in range(0, int(data['Cena'].max()) + 1, 500)} if not data.empty else {0: '0', 2000: '2000'},
                                value=[data['Cena'].min() if not data.empty else 0, data['Cena'].max() if not data.empty else 2000]
                            )
                        ], width=6)
                    ], className="mt-3")
                ])
            ])
        ])
    ], className="mb-4"),
    
    # Grafy
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Vývoj průměrné ceny tepla v čase"),
                dbc.CardBody([
                    dcc.Graph(id='vyvoj-ceny-graf')
                ])
            ])
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Porovnání cen podle krajů"),
                dbc.CardBody([
                    dcc.Graph(id='ceny-podle-kraju-graf')
                ])
            ])
        ], width=6)
    ], className="mb-4"),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Rozložení paliv"),
                dbc.CardBody([
                    dcc.Graph(id='rozlozeni-paliv-graf')
                ])
            ])
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Cena vs. množství"),
                dbc.CardBody([
                    dcc.Graph(id='cena-vs-mnozstvi-graf')
                ])
            ])
        ], width=6)
    ], className="mb-4"),
    
    # Tabulka s detailními údaji
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Detailní údaje"),
                dbc.CardBody([
                    dash_table.DataTable(
                        id='detailni-tabulka',
                        columns=[
                            {'name': 'Lokalita', 'id': 'NazevLokality'},
                            {'name': 'Kraj', 'id': 'NazevKraje'},
                            {'name': 'Rok', 'id': 'Rok'},
                            {'name': 'Typ dodávky', 'id': 'NazevTypuDodavky'},
                            {'name': 'Cena [Kč/GJ]', 'id': 'Cena'},
                            {'name': 'Množství [GJ]', 'id': 'Mnozstvi'},
                            {'name': 'Instalovaný výkon [MWt]', 'id': 'InstalovanyVykon'}
                        ],
                        page_size=10,
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left'},
                        style_header={
                            'backgroundColor': 'rgb(230, 230, 230)',
                            'fontWeight': 'bold'
                        }
                    )
                ])
            ])
        ])
    ]),
    
    # Footer
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P("© 2025 Analýza cen tepelné energie v ČR", className="text-center")
        ])
    ])
], fluid=True)

# Callback pro aktualizaci dropdown lokalit podle vybraného kraje
@app.callback(
    Output('lokalita-dropdown', 'options'),
    [Input('kraj-dropdown', 'value')]
)
def aktualizuj_lokality_dropdown(vybrany_kraj):
    if not vybrany_kraj:
        return [{'label': lokalita, 'value': lokalita} for lokalita in sorted(data['NazevLokality'].unique())]
    
    filtrovana_data = data[data['NazevKraje'].isin(vybrany_kraj)]
    return [{'label': lokalita, 'value': lokalita} for lokalita in sorted(filtrovana_data['NazevLokality'].unique())]

# Callback pro aktualizaci grafů
@app.callback(
    [
        Output('vyvoj-ceny-graf', 'figure'),
        Output('ceny-podle-kraju-graf', 'figure'),
        Output('rozlozeni-paliv-graf', 'figure'),
        Output('cena-vs-mnozstvi-graf', 'figure'),
        Output('detailni-tabulka', 'data')
    ],
    [
        Input('rok-dropdown', 'value'),
        Input('kraj-dropdown', 'value'),
        Input('typ-dodavky-dropdown', 'value'),
        Input('lokalita-dropdown', 'value'),
        Input('cena-slider', 'value')
    ]
)
def aktualizuj_grafy(vybrany_rok, vybrany_kraj, vybrany_typ_dodavky, vybrana_lokalita, rozsah_cen):
    # Filtrování dat
    filtrovana_data = data.copy()
    
    if vybrany_rok:
        if isinstance(vybrany_rok, list):
            filtrovana_data = filtrovana_data[filtrovana_data['Rok'].isin(vybrany_rok)]
        else:
            filtrovana_data = filtrovana_data[filtrovana_data['Rok'] == vybrany_rok]
    
    if vybrany_kraj:
        filtrovana_data = filtrovana_data[filtrovana_data['NazevKraje'].isin(vybrany_kraj)]
    
    if vybrany_typ_dodavky:
        filtrovana_data = filtrovana_data[filtrovana_data['NazevTypuDodavky'].isin(vybrany_typ_dodavky)]
    
    if vybrana_lokalita:
        filtrovana_data = filtrovana_data[filtrovana_data['NazevLokality'].isin(vybrana_lokalita)]
    
    if rozsah_cen:
        filtrovana_data = filtrovana_data[(filtrovana_data['Cena'] >= rozsah_cen[0]) & (filtrovana_data['Cena'] <= rozsah_cen[1])]
    
    # Pokud nemáme žádná data po filtrování, vrátíme prázdné grafy
    if filtrovana_data.empty:
        prazdny_graf = px.scatter(title="Žádná data neodpovídají vybraným filtrům")
        prazdny_graf.update_layout(
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": "Žádná data neodpovídají vybraným filtrům",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 20}
                }
            ]
        )
        return prazdny_graf, prazdny_graf, prazdny_graf, prazdny_graf, []
    
    # Graf vývoje průměrné ceny v čase
    prumerne_ceny_podle_roku = filtrovana_data.groupby('Rok')['Cena'].mean().reset_index()
    vyvoj_ceny_graf = px.line(
        prumerne_ceny_podle_roku, 
        x='Rok', 
        y='Cena',
        title='Vývoj průměrné ceny tepla v čase',
        labels={'Cena': 'Průměrná cena [Kč/GJ]', 'Rok': 'Rok'}
    )
    vyvoj_ceny_graf.update_layout(xaxis_tickangle=-45)
    
    # Graf porovnání cen podle krajů
    prumerne_ceny_podle_kraju = filtrovana_data.groupby('NazevKraje')['Cena'].mean().reset_index()
    ceny_podle_kraju_graf = px.bar(
        prumerne_ceny_podle_kraju.sort_values('Cena'), 
        x='NazevKraje', 
        y='Cena',
        title='Průměrná cena tepla podle krajů',
        labels={'Cena': 'Průměrná cena [Kč/GJ]', 'NazevKraje': 'Kraj'}
    )
    ceny_podle_kraju_graf.update_layout(xaxis_tickangle=-45)
    
    # Graf rozložení paliv
    paliva_data = filtrovana_data[['UhliProcento', 'BiomasaProcento', 'OdpadProcento', 'ZemniPlynProcento', 'JinaPalivaProcento']].mean().reset_index()
    paliva_data.columns = ['Palivo', 'Procento']
    paliva_data['Palivo'] = paliva_data['Palivo'].map({
        'UhliProcento': 'Uhlí',
        'BiomasaProcento': 'Biomasa a OZE',
        'OdpadProcento': 'Odpady',
        'ZemniPlynProcento': 'Zemní plyn',
        'JinaPalivaProcento': 'Jiná paliva'
    })
    rozlozeni_paliv_graf = px.pie(
        paliva_data, 
        values='Procento', 
        names='Palivo',
        title='Průměrné rozložení paliv'
    )
    
    # Graf cena vs. množství
    cena_vs_mnozstvi_graf = px.scatter(
        filtrovana_data, 
        x='Mnozstvi', 
        y='Cena',
        color='NazevKraje',
        hover_name='NazevLokality',
        title='Vztah mezi cenou a množstvím dodaného tepla',
        labels={'Cena': 'Cena [Kč/GJ]', 'Mnozstvi': 'Množství [GJ]'}
    )
    
    # Detailní tabulka
    detailni_data = filtrovana_data[['NazevLokality', 'NazevKraje', 'Rok', 'NazevTypuDodavky', 'Cena', 'Mnozstvi', 'InstalovanyVykon']].to_dict('records')
    
    return vyvoj_ceny_graf, ceny_podle_kraju_graf, rozlozeni_paliv_graf, cena_vs_mnozstvi_graf, detailni_data

# Spuštění aplikace
if __name__ == '__main__':
    app.run_server(debug=True)