#!/usr/bin/env python3
"""
Enrich hikes.json stages with country and admin1 (sub-national region) codes.

For OSM-based stages (those with _osm_id): fetches stage geometry from Waymarked
Trails, finds the stage midpoint, then does a point-in-polygon lookup against
Natural Earth admin-1 boundaries to determine country + region.

For website-scraped stages (no _osm_id): uses ROUTE_DEFAULTS, a hardcoded lookup
of the known geographic region for each route.

Usage:
    python3 enrich_regions.py              # enrich all stages not yet enriched
    python3 enrich_regions.py --refresh    # re-enrich all stages (overwrite existing)
    python3 enrich_regions.py --dry-run    # print what would change, don't save
"""

import argparse
import json
import math
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HIKES_JSON     = "hikes.json"
NE_CACHE       = ".ne_admin1.json"
NE_URL         = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_50m_admin_1_states_provinces.geojson"
)
WT_BASE        = "https://hiking.waymarkedtrails.org/api/v1/details/relation"
WT_DELAY       = 1.8   # seconds between Waymarked Trails requests
USER_AGENT     = "HikingTracker/1.0 (https://github.com/jclift-dev/hiking-tracker)"

# Lands to enrich (all European non-Swiss)
EU_LANDS = {
    "eu-hike", "fr-hike", "de-hike", "it-hike", "es-hike", "ie-hike", "uk",
    "pt-hike", "at-hike", "hu-hike", "cz-hike", "si-hike",
    "nl-hike", "be-hike", "se-hike", "no-hike", "ee-hike",
    "hr-hike", "sk-hike", "dk-hike", "lt-hike", "lv-hike",
}

# ---------------------------------------------------------------------------
# Hardcoded defaults for website-scraped routes (no _osm_id on stages).
# These routes are each within a small number of well-known regions.
# Format: (land, route_id) → list of (stage_range_start, stage_range_end, country, admin1)
# Use stage_range_end=None to mean "all remaining stages".
# admin1 should match the iso_3166_2 code (lowercase) used by make_europe_svg.py.
# ---------------------------------------------------------------------------

ROUTE_DEFAULTS = {
    # France — uses ISO 3166-2 département codes (fr-NN / fr-2a / fr-2b)
    ("fr-hike", 1):  [                                   # GR20 — Corsica, north→south
        (1,  9,  "fr", "fr-2b"),   # Haute-Corse (northern half)
        (10, None, "fr", "fr-2a"), # Corse-du-Sud (southern half)
    ],
    ("fr-hike", 2):  [                                   # GR65 Via Podiensis
        (1,  3,  "fr", "fr-43"),   # Haute-Loire
        (4,  5,  "fr", "fr-48"),   # Lozère
        (6,  9,  "fr", "fr-12"),   # Aveyron
        (10, 14, "fr", "fr-46"),   # Lot
        (15, 18, "fr", "fr-82"),   # Tarn-et-Garonne / Gers
        (19, 27, "fr", "fr-32"),   # Gers
        (28, None, "fr", "fr-64"), # Pyrénées-Atlantiques
    ],
    ("fr-hike", 3):  [                                   # GR70 Chemin de Stevenson
        (1,  3,  "fr", "fr-43"),   # Haute-Loire
        (4,  8,  "fr", "fr-48"),   # Lozère
        (9,  11, "fr", "fr-07"),   # Ardèche
        (12, None, "fr", "fr-30"), # Gard
    ],
    # Mercantour/Alpi Marittime — Italian side (all in Cuneo province, Piedmont)
    ("it-hike", 44): [(1, None, "it", "it-cn")],         # Alto Tanaro Tour
    ("it-hike", 45): [(1, None, "it", "it-cn")],         # Alta Via dei Re
    ("it-hike", 46): [(1, None, "it", "it-cn")],         # Grand Tour de l'Argentera et des Merveilles
    ("it-hike", 47): [(1, None, "it", "it-cn")],         # Le trekking du loup
    ("it-hike", 48): [(1, None, "it", "it-cn")],         # Giro del Marguareis
    ("it-hike", 49): [(1, None, "it", "it-cn")],         # Tour du parc naturel du Marguareis
    # Mercantour — French side
    ("fr-hike", 25): [(1, None, "fr", "fr-06")],         # La randonnée des couleurs (Alpes-Maritimes)
    ("fr-hike", 26): [(1, None, "fr", "fr-06")],         # Le sentier d'Azur (Alpes-Maritimes)
    # Vanoise — all in Savoie
    ("fr-hike", 15): [(1, None, "fr", "fr-73")],         # Tour des glaciers de la Vanoise
    ("fr-hike", 16): [(1, None, "fr", "fr-73")],         # Tour de la Grande Casse
    ("fr-hike", 17): [(1, None, "fr", "fr-73")],         # Tour de Méan Martin
    ("fr-hike", 18): [(1, None, "fr", "fr-73")],         # Tour de la Vallaisonnay
    ("fr-hike", 19): [(1, None, "fr", "fr-73")],         # GTT3
    ("fr-hike", 20): [(1, None, "fr", "fr-73")],         # GTT5
    ("fr-hike", 21): [(1, None, "fr", "fr-73")],         # GTT6
    ("fr-hike", 22): [(1, None, "fr", "fr-73")],         # GTT Tour La Plagne
    ("fr-hike", 23): [(1, None, "fr", "fr-73")],         # Tour du Mont Pourri
    ("fr-hike", 24): [(1, None, "fr", "fr-73")],         # GTT1
    ("fr-hike", 27): [(1, None, "fr", "fr-73")],         # Tour de la Pointe de l'Échelle (Savoie)
    ("eu-hike", 7):  [                                   # Grande traversée Alpi Marittime (Col de Larche → Grimaldi)
        (1,  1,  "fr", "fr-04"),   # Alpes-de-Haute-Provence: Col de Larche
        (2,  13, "it", "it-cn"),   # Cuneo / Piedmont: Maritime Alps
        (14, None, "it", "it-im"), # Imperia / Liguria: towards the Mediterranean
    ],
    ("eu-hike", 8):  [                                   # La boucle des 4 vallées (Pontebernardo → Pontebernardo)
        (1,  2,  "it", "it-cn"),   # Cuneo: Pontebernardo → Col de Larche
        (3,  None, "fr", "fr-06"), # Alpes-Maritimes: Bousieyas → back to Italy
    ],
    ("eu-hike", 9):  [                                   # Tour du Mont Ténibre (Refuge Talarico circular)
        (1,  2,  "fr", "fr-06"),   # Alpes-Maritimes: crosses to French side
        (3,  None, "it", "it-cn"), # Cuneo: back on Italian side
    ],
    ("eu-hike", 10): [                                   # Sur l'Alta Via Ligure (Menton → Imperia)
        (1,  1,  "fr", "fr-06"),   # Alpes-Maritimes: Menton start
        (2,  None, "it", "it-im"), # Imperia / Liguria: Italian Riviera
    ],
    ("eu-hike", 11): [                                   # Tour franco-italien du Mont Gramondo (alternates FR/IT)
        (1,  1,  "fr", "fr-06"),   # Alpes-Maritimes
        (2,  2,  "it", "it-im"),   # Imperia
        (3,  None, "fr", "fr-06"), # Alpes-Maritimes
    ],
    ("eu-hike", 12): [                                   # High Scardus Trail (MK/XK/AL — Šar Planina)
        (1,  1,  "mk", "mk"),   # Staro Selo → Ljuboten: North Macedonia start
        (2,  9,  "xk", "xk"),   # Kosovo section (Brezovica, Prevalla, Restelica…)
        (10, 13, "al", "al"),   # Albania section (Radomirë → Stanet e Hinoskes)
        (14, 15, "mk", "mk"),   # North Macedonia (Bitushe area)
        (16, 17, "al", "al"),   # Albania (Jablanica → Qafa e Kryqit)
        (18, None, "mk", "mk"), # North Macedonia (Vevcani → Sveti Naum)
    ],
    ("it-hike", 50): [(1, None, "it", "it-im")],         # Les plus beaux villages Ligures (Imperia)
    ("fr-hike", 14): [                                   # GR54 Tour de l'Oisans (circular)
        (1,  2,  "fr", "fr-38"),   # Isère: Bourg d'Oisans → Mizoën
        (3,  9,  "fr", "fr-05"),   # Hautes-Alpes: Villar d'Arène → Valgaudemar
        (10, None, "fr", "fr-38"), # Isère: Valjouffrey → Bourg d'Oisans
    ],
    # Italy — uses ISO 3166-2 province codes
    ("it-hike", 1):  [                                   # Alta Via 1
        (1,  5,  "it", "it-bz"),   # South Tyrol / Bolzano province
        (6,  None, "it", "it-bl"), # Belluno province (Veneto)
    ],
    # UK — county-level codes matching europePaths (make_europe_svg.py)
    ("uk", 1):  [                                        # South West Coast Path
        (1,  1,  "gb", "gb-som"),  # Somerset: Minehead → Porlock Weir
        (2,  9,  "gb", "gb-dev"),  # Devon (north coast): Lynmouth → Hartland Quay
        (10, 34, "gb", "gb-con"),  # Cornwall: Bude → Polperro
        (35, 35, "gb", "gb-con"),  # Rame Peninsula (Cornwall) → Plymouth ferry
        (36, 45, "gb", "gb-dev"),  # Devon (south coast): Yealm → Sidmouth
        (46, None, "gb", "gb-dor"), # Dorset: Seaton → Poole
    ],
    ("uk", 2):  [                                        # West Highland Way
        (1,  5,  "gb", "gb-stg"),  # Stirling (Milngavie → Bridge of Orchy)
        (6,  None, "gb", "gb-hld"), # Highland (Rannoch Moor → Fort William)
    ],
    ("uk", 3):  [                                        # Offa's Dyke Path
        (1,  2,  "gb", "gb-mon"),  # Monmouthshire
        (3,  5,  "gb", "gb-pow"),  # Powys
        (6,  8,  "gb", "gb-shr"),  # Shropshire
        (9,  None, "gb", "gb-den"), # Denbighshire → Prestatyn
    ],
    ("uk", 5):  [                                        # South Downs Way
        (1,  3,  "gb", "gb-ham"),  # Hampshire: Winchester → Buriton
        (4,  6,  "gb", "gb-wsx"),  # West Sussex: Cocking → River Adur
        (7,  None, "gb", "gb-esx"), # East Sussex: Lewes → Eastbourne
    ],
    ("uk", 6):  [                                        # Cotswold Way
        (1,  13, "gb", "gb-gls"),  # Gloucestershire
        (14, None, "gb", "gb-bas"), # Bath and North East Somerset
    ],
    ("uk", 7):  [                                        # Hadrian's Wall Path
        (1,  5,  "gb", "gb-nbl"),  # Northumberland
        (6,  None, "gb", "gb-cma"), # Cumbria: Birdoswald → Bowness-on-Solway
    ],
    ("uk", 8):  [(1, None, "gb", "gb-pem")],             # Pembrokeshire Coast Path
    # Germany — Schwarzwaldverein Fernwanderwege (route_ids 10–31), all in Baden-Württemberg
    ("de-hike", 10): [(1, None, "de", "de-bw")],  # Mittelweg
    ("de-hike", 11): [(1, None, "de", "de-bw")],  # Ostweg
    ("de-hike", 12): [(1, None, "de", "de-bw")],  # Querweg Freiburg-Bodensee
    ("de-hike", 13): [(1, None, "de", "de-bw")],  # Markgräfler Wiiwegli
    ("de-hike", 14): [(1, None, "de", "de-bw")],  # Schluchtensteig
    ("de-hike", 15): [(1, None, "de", "de-bw")],  # Kandelhöhenweg
    ("de-hike", 16): [(1, None, "de", "de-bw")],  # Schwarzwald-Jura-Bodensee
    ("de-hike", 17): [(1, None, "de", "de-bw")],  # ZweiTälerSteig
    ("de-hike", 18): [(1, None, "de", "de-bw")],  # Breisgauer Weinweg
    ("de-hike", 19): [(1, None, "de", "de-bw")],  # Gäurandweg
    ("de-hike", 20): [(1, None, "de", "de-bw")],  # Hochrhein-Höhenweg
    ("de-hike", 21): [(1, None, "de", "de-bw")],  # Interregio-Wanderweg
    ("de-hike", 22): [(1, None, "de", "de-bw")],  # Murgleiter
    ("de-hike", 23): [(1, None, "de", "de-bw")],  # Ortenauer Weinpfad
    ("de-hike", 24): [(1, None, "de", "de-bw")],  # Querweg Gengenbach-Alpirsbach
    ("de-hike", 25): [(1, None, "de", "de-bw")],  # Querweg Lahr-Rottweil
    ("de-hike", 26): [(1, None, "de", "de-bw")],  # Querweg Schwarzwald-Kaiserstuhl-Rhein
    ("de-hike", 27): [(1, None, "de", "de-bw")],  # Renchtalsteig
    ("de-hike", 28): [(1, None, "de", "de-bw")],  # Rheinauenweg
    ("de-hike", 29): [(1, None, "de", "de-bw")],  # Schwarzwald-Nordrandweg
    ("de-hike", 30): [(1, None, "de", "de-bw")],  # Wasserweltensteig
    ("de-hike", 31): [(1, None, "de", "de-bw")],  # Hotzenwald-Querweg
    # Spain — gronze.com routes (no OSM IDs); uses ISO 3166-2 autonomous-community codes
    ("es-hike", 15): [                                   # Camino Francés (SJdPP → Santiago)
        (1,  6,  "es", "es-na"),   # Navarra: Roncesvalles → Los Arcos
        (7,  9,  "es", "es-ri"),   # La Rioja: Logroño → Santo Domingo de la Calzada
        (10, 26, "es", "es-cl"),   # Castilla y León: Belorado → Villafranca del Bierzo
        (27, None, "es", "es-ga"), # Galicia: O Cebreiro → Santiago
    ],
    ("es-hike", 16): [                                   # Via de la Plata / Camino Sanabrés (Sevilla → Santiago)
        (1,  3,  "es", "es-an"),   # Andalucía: Sevilla → Almadén de la Plata
        (4,  15, "es", "es-ex"),   # Extremadura: Monesterio → Aldeanueva del Camino
        (16, 28, "es", "es-cl"),   # Castilla y León: Béjar → Puebla de Sanabria
        (29, None, "es", "es-ga"), # Galicia: A Gudiña → Santiago
    ],
    ("es-hike", 17): [(1, None, "es", "es-ga")],         # Camino Inglés (all Galicia: A Coruña province)
    ("es-hike", 18): [                                   # Camino de Invierno (Ponferrada → Outeiro)
        (1, 1,    "es", "es-cl"),  # Castilla y León: Ponferrada → Médulas (León province)
        (2, None, "es", "es-ga"),  # Galicia: O Barco de Valdeorras → Outeiro
    ],
    ("es-hike", 19): [                                   # Camino Salvador (León → Grado)
        (1, 2,    "es", "es-cl"),  # Castilla y León: León → Poladura de la Tercia
        (3, None, "es", "es-as"),  # Asturias: Pajares → Grado
    ],
    ("es-hike", 20): [(1, None, "es", "es-ga")],         # Camino de Fisterra (Santiago → Faro de Fisterra, all Galicia)
    ("es-hike", 21): [                                   # Camino Aragonés (Somport → Estella, 7 stages)
        (1, 3, "es", "es-ar"),   # Aragón: Somport → Ruesta
        (4, None, "es", "es-na"), # Navarra: Sangüesa → Estella
    ],
    ("es-hike", 22): [                                   # Camino de Madrid (Madrid → Sahagún, 14 stages)
        (1, 3,    "es", "es-md"),  # Comunidad de Madrid: Madrid → Cercedilla
        (4, None, "es", "es-cl"),  # Castilla y León: Segovia → Sahagún
    ],
    ("es-hike", 23): [                                   # Camino Vasco (Irun → Burgos, 16 stages)
        (1, 6,    "es", "es-pv"),  # País Vasco: Irun → Vitoria-Gasteiz
        (7, None, "es", "es-cl"),  # Castilla y León: Puebla de Arganzón → Burgos/Belorado
    ],
    ("es-hike", 24): [                                   # Camino del Ebro (Deltebre → Nájera, 18 stages)
        (1,  4,  "es", "es-ct"),   # Cataluña: Deltebre → Gandesa
        (5,  12, "es", "es-ar"),   # Aragón: Fabara → Gallur
        (13, 13, "es", "es-na"),   # Navarra: Gallur → Tudela
        (14, None, "es", "es-ri"), # La Rioja: Alfaro → Nájera
    ],
    ("es-hike", 25): [                                   # Camino Vadiniense (San Vicente → León, 11 stages)
        (1, 4,    "es", "es-cb"),  # Cantabria: San Vicente → Potes/Espinama
        (5, None, "es", "es-cl"),  # Castilla y León: Portilla de la Reina → León
    ],
    ("es-hike", 26): [(1, None, "es", "es-ga")],         # Ría de Muros-Noia (all Galicia)
    ("es-hike", 27): [                                   # Camino Baztán (Bayonne → Puente la Reina, 6 stages)
        (1, 2, "fr", "fr-64"),   # Pyrénées-Atlantiques: Bayonne → Amaiur-Maya
        (3, None, "es", "es-na"), # Navarra: Berroeta → Puente la Reina
    ],
    ("es-hike", 28): [                                   # Camino Catalán (Barcelona → Jaca, 27 stages)
        (1,  10, "es", "es-ct"),   # Cataluña: Barcelona → Lleida
        (11, None, "es", "es-ar"), # Aragón: Fraga → Jaca
    ],
    ("es-hike", 29): [                                   # Camino Olvidado (Bilbao → O Cebreiro, 28 stages)
        (1,  2,  "es", "es-pv"),   # País Vasco: Bilbao → Mimetiz/Zalla
        (3,  27, "es", "es-cl"),   # Castilla y León: Villasana de Mena → Villafranca del Bierzo
        (28, None, "es", "es-ga"), # Galicia: O Cebreiro
    ],
    ("es-hike", 30): [                                   # Camino de Levante (Valencia → Zamora, 29 stages)
        (1,  4,  "es", "es-vc"),   # Comunitat Valenciana: Valencia → Font de la Figuera
        (5,  18, "es", "es-cm"),   # Castilla-La Mancha: Almansa → Escalona/Toledo
        (19, None, "es", "es-cl"), # Castilla y León: San Martín de Valdeiglesias → Zamora
    ],
    ("es-hike", 31): [                                   # Ruta de la Lana (Alicante → Burgos, 30 stages)
        (1,  3,  "es", "es-vc"),   # Comunitat Valenciana: Alicante → Villena
        (4,  22, "es", "es-cm"),   # Castilla-La Mancha: Caudete → Sigüenza/Atienza
        (23, None, "es", "es-cl"), # Castilla y León: Soria → Burgos
    ],
    ("es-hike", 32): [                                   # Camino Mozárabe (multi-start → Mérida, 38 stages)
        (1,  31, "es", "es-an"),   # Andalucía: all southern branches → Córdoba
        (32, None, "es", "es-ex"), # Extremadura: Monterrubio → Mérida/Alcuéscar
    ],
    ("pt-hike", 4): [                                    # Camino Portugués da Costa (Porto → Pontevedra, 13 stages)
        (1,  2,  "pt", "pt-13"),   # Porto district: Porto → Póvoa de Varzim
        (3,  4,  "pt", "pt-03"),   # Braga district: Marinhas → Viana do Castelo
        (5,  5,  "pt", "pt-16"),   # Viana do Castelo district: Viana → Caminha
        (6,  None, "es", "es-ga"), # Galicia (Spain): A Guarda → Pontevedra
    ],
    ("fr-hike", 30): [                                   # Camino de Vézelay (Vézelay → Saint-Jean-Pied-de-Port, 51 stages)
        (1,  11, "fr", "fr-89"),   # Yonne/Nièvre/Berry: Vézelay → Argenton
        (12, 23, "fr", "fr-58"),   # Nièvre/Cher/Creuse: Nevers branch → Gargilesse
        (24, 30, "fr", "fr-87"),   # Haute-Vienne: Crozant → Limoges
        (31, 37, "fr", "fr-24"),   # Dordogne: Coquille → Bergerac
        (38, 44, "fr", "fr-33"),   # Gironde/Landes: Sainte-Foy → Bazas → Captieux
        (45, None, "fr", "fr-64"), # Pyrénées-Atlantiques: Roquefort → Saint-Jean-Pied-de-Port
    ],
    ("eu-hike", 13): [                                   # Via Gebennensis (Geneva → Le Puy, 17 stages; CH/FR)
        (1,  1,  "ch", "ch-ge"),   # Geneva canton: start
        (2,  9,  "fr", "fr-74"),   # Haute-Savoie / Ain / Isère: Frangy → Saint-Romain
        (10, None, "fr", "fr-42"), # Loire / Haute-Loire: Chavanay → Le Puy
    ],
    ("eu-hike", 14): [                                   # Camino de Arles (Arles → Jaca, 34 stages; FR/ES)
        (1,  5,  "fr", "fr-30"),   # Gard/Hérault: Arles → Montpellier
        (6,  14, "fr", "fr-34"),   # Hérault/Aveyron/Tarn: Saint-Guilhem → Castres
        (15, 20, "fr", "fr-81"),   # Tarn / Haute-Garonne: Dourgne → Toulouse
        (21, 28, "fr", "fr-32"),   # Gers: Léguevin → Morlaàs
        (29, 33, "fr", "fr-64"),   # Pyrénées-Atlantiques: Lescar → Somport
        (34, None, "es", "es-ar"), # Aragón: Somport → Jaca
    ],
    ("eu-hike", 15): [                                   # Camino del Piamonte (Carcassonne → Roncesvalles, 23 stages; FR/ES)
        (1,  7,  "fr", "fr-11"),   # Aude/Ariège: Carcassonne → Saint-Lizier
        (8,  14, "fr", "fr-09"),   # Ariège/Haute-Garonne: Castillon → Bagnères
        (15, 22, "fr", "fr-65"),   # Hautes-Pyrénées/Pyrénées-Atlantiques: Lourdes → Saint-Jean-Pied-de-Port
        (23, None, "es", "es-na"), # Navarra: Saint-Jean-Pied-de-Port → Roncesvalles
    ],
    ("eu-hike", 16): [                                   # Via Francígena (Lausanne → Roma, 51 stages; CH/IT)
        (1,  2,  "ch", "ch-vd"),   # Vaud: Lausanne → Vevey → Aigle
        (3,  7,  "ch", "ch-vs"),   # Valais: Saint-Maurice → Grand-Saint-Bernard
        (8,  12, "it", "it-ao"),   # Valle d'Aosta: Étroubles → Pont-Saint-Martin
        (13, 21, "it", "it-to"),   # Piedmont: Ivrea → Pavia
        (22, 27, "it", "it-pc"),   # Emilia-Romagna: Piacenza → Berceto
        (28, 33, "it", "it-ms"),   # Tuscany (Massa-Carrara / Liguria): Pontremoli → Lucca
        (34, 42, "it", "it-si"),   # Tuscany: Altopascio → Siena
        (43, None, "it", "it-vt"), # Lazio: Acquapendente → Roma
    ],
    ("it-hike", 53): [                                   # Camino di San Francesco (Roma → La Verna, 23 stages)
        (1,  2,  "it", "it-rm"),   # Roma province: Roma → Monterotondo
        (3,  7,  "it", "it-ri"),   # Rieti province: Ponticelli → Piediluco
        (8,  14, "it", "it-tr"),   # Terni province (Umbria): Ferentillo → Assisi
        (15, 19, "it", "it-pg"),   # Perugia province (Umbria): Valfabbrica → Città di Castello
        (20, None, "it", "it-ar"), # Arezzo province (Tuscany): Citerna → La Verna
    ],
}


# ---------------------------------------------------------------------------
# Waymarked Trails API
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


def fetch_relation(osm_id):
    """Fetch Waymarked Trails relation details. Returns JSON dict or None."""
    url = f"{WT_BASE}/{osm_id}"
    for attempt in range(2):
        try:
            time.sleep(WT_DELAY)
            r = SESSION.get(url, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code >= 500 and attempt == 0:
                time.sleep(10)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 0:
                time.sleep(10)
                continue
            print(f"   [warn] failed {osm_id}: {e}")
    return None


# ---------------------------------------------------------------------------
# Coordinate helpers (copied from scraper_osm.py)
# ---------------------------------------------------------------------------

def merc_to_wgs84(x, y):
    """EPSG:3857 Web Mercator (metres) → (lat_deg, lng_deg)."""
    lng = x / 20037508.34 * 180.0
    lat = math.degrees(
        2 * math.atan(math.exp(math.radians(y / 20037508.34 * 180.0))) - math.pi / 2
    )
    return lat, lng


def extract_coords_wgs84(route_node):
    """Recursively collect WGS84 (lat, lon) pairs from a route node's geometry."""
    coords = []
    for child in route_node.get("main", []):
        if "ways" in child:
            for way in child["ways"]:
                geom = way.get("geometry", {})
                if geom.get("type") == "LineString":
                    for xy in geom["coordinates"]:
                        coords.append(merc_to_wgs84(xy[0], xy[1]))
        else:
            coords.extend(extract_coords_wgs84(child))
    return coords


def midpoint_wgs84(route_node):
    """Return the midpoint (lat, lon) of a route's geometry, or None."""
    pts = extract_coords_wgs84(route_node)
    if not pts:
        return None
    mid = pts[len(pts) // 2]
    return mid  # (lat, lon)


# ---------------------------------------------------------------------------
# Natural Earth point-in-polygon
# ---------------------------------------------------------------------------

def load_ne_geojson():
    if os.path.exists(NE_CACHE):
        with open(NE_CACHE) as f:
            return json.load(f)
    print("[info] Downloading Natural Earth admin-1 (50m)…")
    r = requests.get(NE_URL, timeout=120)
    r.raise_for_status()
    data = r.json()
    with open(NE_CACHE, "w") as f:
        json.dump(data, f)
    return data


def build_spatial_index(features):
    """
    Build a list of (bbox, iso_a2, admin1_code, polygon_rings) entries.
    bbox = (lon_min, lat_min, lon_max, lat_max).
    """
    index = []
    for feat in features:
        props  = feat.get("properties", {})
        iso_a2 = (props.get("iso_a2") or "").upper().strip()
        if not iso_a2 or iso_a2 == "-99":
            continue

        # Derive admin1 code: prefer iso_3166_2
        iso2 = (props.get("iso_3166_2") or "").strip()
        if iso2 and iso2 != "-99" and "-" in iso2:
            admin1 = iso2.lower()
        else:
            # Use adm1_code slug
            adm1 = (props.get("adm1_code") or "").strip()
            if adm1:
                slug = adm1.split("-")[-1].lower()
                admin1 = f"{iso_a2.lower()}-{slug}"
            else:
                admin1 = iso_a2.lower()

        # Single-polygon countries: keep country-level code
        if iso_a2 in ("CH", "MC", "LI", "SI"):
            admin1 = iso_a2.lower()

        # Ireland: map county-level codes to the 4 provinces used by make_europe_svg.py.
        # NB: Cork county ISO is IE-CO, which collides with the europePaths province code
        # ie-co (Connacht), so we match by name not by ISO code.
        if iso_a2 == "IE":
            name_lc = (props.get("name") or "").lower()
            leinster = {"wicklow","wexford","carlow","kilkenny","laois","laoighis",
                        "offaly","kildare","meath","westmeath","longford","louth",
                        "dublin","fingal","south dublin","dún laoghaire–rathdown"}
            munster  = {"cork","kerry","limerick","clare","waterford",
                        "tipperary","north tipperary","south tipperary"}
            connacht = {"galway","mayo","sligo","leitrim","roscommon"}
            if   any(c in name_lc for c in leinster): admin1 = "ie-le"
            elif any(c in name_lc for c in munster):  admin1 = "ie-mu"
            elif any(c in name_lc for c in connacht): admin1 = "ie-co"
            else:                                      admin1 = "ie-ul"  # Ulster + fallback

        geom  = feat.get("geometry", {})
        gtype = geom.get("type", "")

        def add_polygon(rings):
            outer = rings[0]
            lons = [c[0] for c in outer]
            lats = [c[1] for c in outer]
            bbox = (min(lons), min(lats), max(lons), max(lats))
            index.append((bbox, iso_a2.lower(), admin1, outer))

        if gtype == "Polygon":
            add_polygon(geom["coordinates"])
        elif gtype == "MultiPolygon":
            for poly in geom["coordinates"]:
                add_polygon(poly)

    return index


def point_in_polygon(lon, lat, ring):
    """Ray casting point-in-polygon test. Ring is list of [lon, lat]."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def find_region(lat, lon, spatial_index):
    """
    Return (country_iso2, admin1_code) for the given WGS84 coordinate,
    or (None, None) if not found.
    """
    for bbox, country, admin1, ring in spatial_index:
        lon_min, lat_min, lon_max, lat_max = bbox
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            continue
        if point_in_polygon(lon, lat, ring):
            return country, admin1
    return None, None


# ---------------------------------------------------------------------------
# Route default lookup
# ---------------------------------------------------------------------------

def default_region(land, route_id, stage_nr):
    """
    Return (country, admin1) from ROUTE_DEFAULTS for website-scraped stages,
    or (None, None) if not found.
    """
    key = (land, route_id)
    ranges = ROUTE_DEFAULTS.get(key)
    if not ranges:
        return None, None
    for start, end, country, admin1 in ranges:
        if stage_nr >= start and (end is None or stage_nr <= end):
            return country, admin1
    return None, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh",  action="store_true", help="Re-enrich already-enriched stages")
    parser.add_argument("--dry-run",  action="store_true", help="Print changes without saving")
    args = parser.parse_args()

    with open(HIKES_JSON) as f:
        hikes = json.load(f)

    ne_data = load_ne_geojson()
    spatial_index = build_spatial_index(ne_data["features"])
    print(f"[info] Spatial index: {len(spatial_index)} polygons")

    total_enriched = 0
    total_skipped  = 0
    total_failed   = 0
    changed = False

    for route in hikes:
        land     = route.get("land", "")
        route_id = route.get("route_id")
        if land not in EU_LANDS:
            continue

        osm_stages = [s for s in route["stages"] if s.get("_osm_id")]
        static_stages = [s for s in route["stages"] if not s.get("_osm_id")]

        needs_osm = [
            s for s in osm_stages
            if args.refresh or not s.get("country")
        ]
        needs_static = [
            s for s in static_stages
            if args.refresh or not s.get("country")
        ]

        if not needs_osm and not needs_static:
            total_skipped += len(route["stages"])
            continue

        if needs_osm:
            print(f"\n{route['name']} ({land}) — {len(needs_osm)} OSM stages to enrich…")

        for stage in needs_osm:
            osm_id = stage["_osm_id"]
            nr = stage["stage_nr"]
            print(f"  Stage {nr:3d} (OSM {osm_id})…", end=" ", flush=True)

            data = fetch_relation(osm_id)
            if not data:
                print("fetch failed")
                total_failed += 1
                continue

            mid = midpoint_wgs84(data.get("route", {}))
            if not mid:
                print("no geometry")
                total_failed += 1
                continue

            lat, lon = mid
            country, admin1 = find_region(lat, lon, spatial_index)

            if country:
                print(f"{country} / {admin1}  ({lat:.3f}, {lon:.3f})")
                stage["country"] = country
                stage["admin1"]  = admin1
                total_enriched += 1
                changed = True
            else:
                print(f"no match  ({lat:.3f}, {lon:.3f})")
                total_failed += 1

        for stage in needs_static:
            nr = stage["stage_nr"]
            country, admin1 = default_region(land, route_id, nr)
            if country:
                stage["country"] = country
                stage["admin1"]  = admin1
                total_enriched += 1
                changed = True
            else:
                total_failed += 1

    print(f"\n[done] enriched={total_enriched} skipped={total_skipped} failed={total_failed}")

    if changed and not args.dry_run:
        with open(HIKES_JSON, "w") as f:
            json.dump(hikes, f, ensure_ascii=False, separators=(",", ":"))
        print(f"[info] Saved {HIKES_JSON}")
    elif args.dry_run:
        print("[dry-run] No changes saved.")
    else:
        print("[info] Nothing changed.")


if __name__ == "__main__":
    main()
