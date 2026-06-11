# Trail catalog

Full route lists per land value, OSM trail IDs, deferred & future candidates.

## Routes by land value

| `land`     | Country        | Activity | Routes |
|------------|----------------|----------|--------|
| `ch-hike`  | Switzerland    | Hiking   | SchweizMobil national/regional hiking routes (1-7, 10-99) |
| `ch-cycle` | Switzerland    | Cycling  | SchweizMobil national/regional cycling routes (1-7, 10-99) |
| `uk`       | UK             | Hiking   | SWCP (53 stages), WHW (8), ODP (12), South Downs Way (9), Cotswold Way (15), Hadrian's Wall Path (6), Pembrokeshire Coast Path (15), Cape Wrath (1), Pennine Way (OSM), John O'Groats Trail (14, OSM), John Muir Way (10, OSM), Skye Trail (7, OSM), England Coast Path (44, OSM), Ulster Way (14, OSM), Coast to Coast (14, scraper_websites.py) |
| `fr-hike`  | France         | Hiking   | GR20 (16 stages, Corsica), GR65 Via Podiensis (32), GR70 Chemin de Stevenson (13), HRP (41, OSM), Voie de Tours (15, OSM), Du Jura à la Méditerranée (36, OSM), La Routo (7, OSM), Sur les Pas des Huguenots en Cévennes (24, OSM), Via Arverna (22, OSM), GR 300 Chemin de Saint-Michel (19, OSM), GR 367 Sentier Cathare (13, OSM), L'Echappée Jurassienne (5, OSM), Grand Tour de la Gervanne (7, OSM) |
| `it-hike`  | Italy          | Hiking   | Alta Via 1 (11 stages, Dolomites), Italia Coast to Coast (18, scraper_websites.py), Sentiero della Pace (7, OSM), Cammino Celeste (11, OSM), Cammino Materano Via Peuceta (7, OSM), Cammino della Pace (29, OSM), Cammino delle Pievi (20, OSM), Grande Escursione Appenninica (25, OSM), Grande Traversata delle Alpi (25, OSM), Cammino di Santu Jacu (24, OSM), Sentiero Italia Sardegna (30, OSM), Alta Via n. 2 della Valle d'Aosta (14, OSM), Magna Via Francigena (9, OSM), Il Cammino di Dante (OSM), Basilicata Coast to Coast (OSM), Grande Circuito della Romagna (OSM), Sentiero Balcone Mediterraneo (OSM), Sentiero delle Foreste Sacre (OSM), Sentiero dei Celti e dei Liguri (OSM), Cammino del beato Enrico (OSM), Il Cammino di Sant'Antonio ×2 (OSM), Cammino del Lago Maggiore (OSM), Cammino di Don Tonino (OSM), Cammino del Beato Claudio (OSM), Sentiero Lago di Lugano (OSM), Cammino di San Giacomo Caltagirone (OSM), Cammino di Santu Jacu del Nord (OSM), Sentiero Italia Abruzzo (OSM), Sentiero Italia Molise (OSM), Alta Via n. 1 della Valle d'Aosta (OSM), Cammino di San Jacopo (OSM), Via degli Abati (OSM), Tour del Parco Alpi Liguri (OSM), Viae Misericordiae (OSM), Regio Tratturo Magno (OSM), Via degli Dei (OSM), Via della Lana e della Seta (OSM), Via Fabaria Iblea (OSM), Via Lucana (OSM), Via della Costa (OSM), Via Francesca della Sambuca (OSM), ViaSett (OSM) — routes 1–43 |
| `de-hike`  | Germany        | Hiking   | Malerweg (8), Westweg (9, schwarzwaldverein.de), Goldsteig Nord+Süd (OSM), Heidschnuckenweg (OSM), Lutherweg 1521 (OSM), Rheinburgenweg (OSM), Märchenlandweg (OSM), ViaJacobi (OSM), Rheinsteig (OSM), Lahnwanderweg (OSM), Hünenweg (OSM), Sauerland-Waldroute (OSM+website), Paul-Gerhardt-Weg (OSM), Lahn-Camino (OSM), Ulrikaweg (OSM), Kammweg Erzgebirge-Vogtland (website), Schwarzwaldverein Fernwanderwege ×22 (route_ids 10–31), Albverein Hauptwanderwege ×10 (route_ids 33–41, 52), Eifelsteig (49), Linksrheinischer Jakobsweg (50), WestfalenWanderWeg (51), Stormarnweg (53), Oberlausitzer Bergweg (54), Werra-Burgen-Steig Hessen (55), König-Ludwig-Weg (56), X27 Friedrich-Wilhelm-Grimme-Weg (57), Vulkanring Vogelsberg (58), Ith-Hils-Wanderweg (59), Westerwaldsteig (60), Bergischer Panoramasteig (61), X19 Schlösserweg (62), Ederhöhenweg (63), Herkulesweg (64), X22 Kurkölner Weg (65), Sieghöhenweg (66), X12 Richard-Schirrmann-Weg (67), Straße der Arbeit (68), X11 Lenne-Sieg-Weg (69), X30 Neandertalweg (70) |
| `es-hike`  | Spain          | Hiking   | GR11 (37, OSM), Camino Primitivo (11, OSM), GR221 (8, OSM), GR7 (41, OSM), Sulayr (19, OSM), GR109 Asturias Interior (27, OSM), Camí del Llobregat (9, OSM), Sendero de la Alpujarra (12, OSM), Camí dels bons homes (5, OSM), Gran Senda del Guadalhorce (4, OSM), Camino de la Frontera (11, scraper_websites.py), Camino Espiritual del Sur (14, scraper_websites.py) |
| `ie-hike`  | Ireland        | Hiking   | Wicklow Way, Kerry Way, Dingle Way, Causeway Coast Way, Beara Way, Western Way (all OSM single-stage) |
| `pt-hike`  | Portugal       | Hiking   | Rota Vicentina Trilho dos Pescadores (13, OSM), Grande Rota Peneda-Gerês (19, scraper_websites.py), Camino Portugués (25, scraper_websites.py, Lisboa→Santiago) |
| `at-hike`  | Austria        | Hiking   | Jakobsweg Österreich (17, OSM), BergeSeen Trail (23, OSM), Panoramaweg Südalpen (20, OSM) |
| `hu-hike`  | Hungary        | Hiking   | Országos Kéktúra (27, OSM) |
| `cz-hike`  | Czech Republic | Hiking   | Via Czechia Severní stezka (15, OSM), Centrální stezka (12, OSM), Jižní stezka (12, OSM) |
| `si-hike`  | Slovenia       | Hiking   | Julius Kugy Alpine Trail (30, OSM) |
| `nl-hike`  | Netherlands    | Hiking   | Pieterpad deel 1+2, Zuiderzeepad, Pelgrimspad deel 1+2, Westerborkpad, Trekvogelpad, Maarten van Rossumpad, Noaberpad, Waterliniepad, Grenslandpad, Marskramerpad, Groot Frieslandpad (all OSM) |
| `be-hike`  | Belgium        | Hiking   | Via Brabantica (7, OSM) |
| `hr-hike`  | Croatia        | Hiking   | Via Apsyrtides (11, OSM, Rijeka→Pula) |
| `se-hike`  | Sweden         | Hiking   | Hälsingeleden (22), Bohusleden (27), St. Olavsleden (29), Stockholm Archipelago Trail (19), Kungsleden (31), Skåneleden SL1–SL7 (7 routes), Hallandsleden (13), Blekingeleden (14), Södra Kungsleden (15), Tjustleden (16), Ostkustleden (17), Ingegerdsleden (18), Höga Kusten-leden (19), Dalkarlsvägen (20), Solanderleden (21) — all OSM |
| `no-hike`  | Norway         | Hiking   | Fjordruta på Nordmøre (14), Nordland trekking trail (43), Lofoten Long Crossing (11), Jotunheimstien (4), Signatur Stølsheimen (5), Signatur Omveien (6), Signatur Trollheimen (7), Signatur Lysefjorden rundt (8), Signatur Helt på grensen (9), Gullruta i Etnefjellene (10), Ryger (11), Saga (12), Massiv Trail (13) — all OSM |
| `dk-hike`  | Denmark        | Hiking   | Hærvejen (30, OSM), Øhavsstien (7, OSM) |
| `lt-hike`  | Lithuania      | Hiking   | E11 Lithuania (36, OSM 6519670, Lazdijai→Skuodas) |
| `ee-hike`  | Estonia        | Hiking   | Euroopa matkarada E9 (31, OSM), Peraküla-Aegviidu-Ähijärve haru (11, OSM), Camino Estonia (10, OSM) |
| `sk-hike`  | Slovakia       | Hiking   | SNP Trail (27, scraper_websites.py, Dukla Pass→Devín Castle) |
| `eu-hike`  | Europe (multi) | Hiking   | Via Alpina (116, OSM, Monaco→Trieste), Alpe Adria Trail (43, OSM, Salzburg→Trieste), Tour du Mont Blanc (11, OSM, circular FR/IT/CH), Sultan's Trail (120, OSM, Vienna→Istanbul), E1 (425, scraper_e1.py, North Cape→Sicily), Nordkalottruta (43, OSM, Sulitjelma→Buletjávri, NO/SE/FI) |

## OSM trail catalog (scraper_osm.py TRAILS list)

| OSM ID    | `land`    | route_id | Trail |
|-----------|-----------|----------|-------|
| 4080347   | `uk`      | 4        | Pennine Way |
| 77976     | `uk`      | 5        | South Downs Way — OSM fallback (superseded by scraper_nationaltrail.py) |
| 65239     | `uk`      | 6        | Cotswold Way — OSM fallback (superseded by scraper_nationaltrail.py) |
| 38791     | `uk`      | 7        | Hadrian's Wall Path — OSM fallback (superseded by scraper_nationaltrail.py) |
| 77964     | `uk`      | 8        | Pembrokeshire Coast Path — OSM fallback (superseded by scraper_nationaltrail.py) |
| 9327615   | `uk`      | 9        | Cape Wrath Trail (single stage) |
| 12622536  | `uk`      | 10       | John O'Groats Trail (14 stages) |
| 49215     | `uk`      | 11       | John Muir Way (10 stages) |
| 14421894  | `uk`      | 12       | Skye Trail (7 stages) |
| 3971851   | `uk`      | 13       | England Coast Path (44 sections) |
| 918951    | `uk`      | 14       | Ulster Way (14 stages) |
| 8386002   | `fr-hike` | 4        | Haute Randonnée Pyrénéenne (41 stages) |
| 187781    | `fr-hike` | 5        | Voie de Tours (15 stages) |
| 10670467  | `fr-hike` | 6        | Du Jura à la Méditerranée (36 stages) |
| 14234324  | `fr-hike` | 7        | La Routo (7 stages) |
| 15006813  | `fr-hike` | 8        | Sur les Pas des Huguenots en Cévennes (24 stages) |
| 3371115   | `fr-hike` | 9        | Via Arverna (22 stages) |
| 16195169  | `fr-hike` | 10       | GR 300 Chemin de Saint-Michel (19 stages) |
| 3394595   | `fr-hike` | 11       | GR 367 Sentier Cathare (13 stages) |
| 16234318  | `fr-hike` | 12       | L'Echappée Jurassienne (5 stages) |
| 17667253  | `fr-hike` | 13       | Grand Tour de la Gervanne (7 stages) |
| 61185     | `de-hike` | 3        | Goldsteig-Südroute |
| 3300718   | `de-hike` | 4        | Goldsteig-Nordroute |
| 19995501  | `de-hike` | 5        | Heidschnuckenweg |
| 3795969   | `de-hike` | 6        | Lutherweg 1521 |
| 11243633  | `de-hike` | 7        | Rheinburgenweg (13 stages) |
| 2717790   | `de-hike` | 8        | Märchenlandweg (33 stages) |
| 2927471   | `de-hike` | 9        | ViaJacobi (32 stages) |
| 2685      | `de-hike` | 32       | Rheinsteig (21 stages, Bonn→Wiesbaden) |
| 3718434   | `de-hike` | 42       | Lahnwanderweg (19 stages) |
| 13561380  | `de-hike` | 43       | Hünenweg (12 stages) |
| 89751     | `de-hike` | 44       | Sauerland-Waldroute (overwritten by scraper_websites.py with 7 stages) |
| 14988038  | `de-hike` | 45       | Paul-Gerhardt-Weg (10 stages) |
| 18138429  | `de-hike` | 46       | Lahn-Camino - Jakobsweg (6 stages) |
| 19221478  | `de-hike` | 47       | Ulrikaweg (6 stages) |
| 2153742   | `de-hike` | 48       | Kammweg Erzgebirge-Vogtland (overwritten by scraper_websites.py with 17 stages) |
| 7458271   | `de-hike` | 60       | Westerwaldsteig (16 stages) |
| 3535507   | `de-hike` | 61       | Bergischer Panoramasteig (12 stages) |
| 31758     | `de-hike` | 62       | X19 Schlösserweg (17 stages) |
| 66159     | `de-hike` | 63       | Ederhöhenweg (9 stages) |
| 227175    | `de-hike` | 64       | Herkulesweg (9 stages) |
| 69496     | `de-hike` | 65       | X22 Kurkölner Weg (13 stages) |
| 91600     | `de-hike` | 66       | Sieghöhenweg (12 stages) |
| 91604     | `de-hike` | 67       | X12 Richard-Schirrmann-Weg (7 stages) |
| 121147    | `de-hike` | 68       | Straße der Arbeit (17 stages) |
| 299338    | `de-hike` | 69       | X11 Lenne-Sieg-Weg (8 stages) |
| 31656     | `de-hike` | 70       | X30 Neandertalweg (12 stages) |
| 8865914   | `es-hike` | 1        | Senda Pirenaica (GR11) (37 stages) |
| 19298101  | `es-hike` | 2        | Camino Primitivo (11 stages) |
| 16358020  | `es-hike` | 3        | GR 221 Ruta de Pedra en Sec (8 stages) |
| 318027    | `es-hike` | 4        | GR 7: Andorra - Gibraltar (41 stages) |
| 8883098   | `es-hike` | 5        | Sulayr (19 stages) |
| 6544796   | `es-hike` | 6        | GR 109 Asturias Interior (27 stages) |
| 9681617   | `es-hike` | 7        | Camí del Llobregat (9 stages) |
| 9913208   | `es-hike` | 8        | Sendero de la Alpujarra (12 stages) |
| 1181120   | `es-hike` | 9        | Camí dels bons homes (5 stages) |
| 6390970   | `es-hike` | 10       | Gran Senda del Guadalhorce (4 stages) |
| 3477430   | `it-hike` | 2        | Sentiero della Pace (7 stages) |
| 12286842  | `it-hike` | 3        | Cammino Celeste (11 stages) |
| 14251864  | `it-hike` | 4        | Cammino Materano - Via Peuceta (7 stages) |
| 16944248  | `it-hike` | 5        | Cammino della Pace (29 stages) |
| 15956980  | `it-hike` | 6        | Cammino delle Pievi (20 stages) |
| 358901    | `it-hike` | 7        | Grande Escursione Appenninica (25 stages) |
| 3159979   | `it-hike` | 8        | Grande Traversata delle Alpi (25 stages) |
| 15651288  | `it-hike` | 9        | Cammino di Santu Jacu (24 stages) |
| 7011030   | `it-hike` | 10       | Sentiero Italia - Sardegna (30 stages) |
| 9898948   | `it-hike` | 11       | Alta Via n. 2 della Valle d'Aosta (14 stages) |
| 12116509  | `it-hike` | 12       | Magna Via Francigena (9 stages) |
| 12104446  | `it-hike` | 14       | Il Cammino di Dante |
| 17916506  | `it-hike` | 15       | Basilicata Coast to Coast |
| 10323589  | `it-hike` | 16       | Grande Circuito della Romagna |
| 5804593   | `it-hike` | 17       | Sentiero Balcone Mediterraneo |
| 5330693   | `it-hike` | 18       | Sentiero delle Foreste Sacre |
| 18187153  | `it-hike` | 19       | Sentiero dei Celti e dei Liguri |
| 6032965   | `it-hike` | 20       | Cammino del beato Enrico |
| 3446664   | `it-hike` | 21       | Il Cammino di Sant'Antonio |
| 10275750  | `it-hike` | 22       | Il Cammino di Sant'Antonio (Gemona - Padova) |
| 20388719  | `it-hike` | 23       | Cammino del Lago Maggiore |
| 16907774  | `it-hike` | 24       | Cammino di Don Tonino |
| 13836647  | `it-hike` | 25       | Cammino del Beato Claudio |
| 7132092   | `it-hike` | 26       | Sentiero Lago di Lugano |
| 15904861  | `it-hike` | 27       | Cammino di San Giacomo - Da Caltagirone a Capizzi |
| 15737206  | `it-hike` | 28       | Cammino di Santu Jacu del Nord |
| 7401588   | `it-hike` | 29       | Sentiero Italia - Abruzzo |
| 7220974   | `it-hike` | 30       | Sentiero Italia - Molise |
| 1706143   | `it-hike` | 31       | Alta Via n. 1 della Valle d'Aosta |
| 11156760  | `it-hike` | 32       | Cammino di San Jacopo |
| 18730553  | `it-hike` | 33       | Via degli Abati |
| 15955535  | `it-hike` | 34       | Tour del Parco Alpi Liguri |
| 9527949   | `it-hike` | 35       | Viae Misericordiae |
| 19542924  | `it-hike` | 36       | Regio Tratturo Magno |
| 222322    | `it-hike` | 37       | Via degli Dei |
| 12636375  | `it-hike` | 38       | Via della Lana e della Seta |
| 17654925  | `it-hike` | 39       | Via Fabaria Iblea |
| 19561857  | `it-hike` | 40       | Via Lucana |
| 11685878  | `it-hike` | 41       | Via della Costa |
| 12221576  | `it-hike` | 42       | Via Francesca della Sambuca |
| 7450464   | `it-hike` | 43       | ViaSett |
| 2740      | `ie-hike` | 1        | Wicklow Way (single stage) |
| 183744    | `ie-hike` | 2        | The Kerry Way (single stage) |
| 21664     | `ie-hike` | 3        | The Dingle Way (single stage) |
| 1085994   | `ie-hike` | 4        | Causeway Coast Way (single stage) |
| 2989585   | `ie-hike` | 5        | Beara Way (single stage) |
| 14702338  | `ie-hike` | 6        | Western Way (single stage) |
| 20810829  | `pt-hike` | 1        | Rota Vicentina - Trilho dos Pescadores (13 stages) |
| 2073724   | `at-hike` | 1        | Jakobsweg Österreich (17 stages) |
| 18013720  | `at-hike` | 2        | BergeSeen Trail (23 stages) |
| 2926132   | `at-hike` | 3        | Panoramaweg Südalpen (20 stages) |
| 6007494   | `hu-hike` | 1        | Országos Kéktúra (27 stages) |
| 16828381  | `cz-hike` | 1        | Via Czechia - Severní stezka (15 stages) |
| 16828379  | `cz-hike` | 2        | Via Czechia - Centrální stezka (12 stages) |
| 16828282  | `cz-hike` | 3        | Via Czechia - Jižní stezka (12 stages) |
| 10909145  | `si-hike` | 1        | Julius Kugy Alpine Trail (30 stages) |
| 312993    | `nl-hike` | 1        | Pieterpad deel 1 (13 stages) |
| 156951    | `nl-hike` | 2        | Pieterpad deel 2 (13 stages) |
| 1561342   | `nl-hike` | 3        | Zuiderzeepad (28 stages) |
| 9588884   | `nl-hike` | 4        | Pelgrimspad deel 1 (12 stages) |
| 8446574   | `nl-hike` | 5        | Pelgrimspad deel 2 (15 stages) |
| 8469244   | `nl-hike` | 6        | Westerborkpad (28 stages) |
| 532494    | `nl-hike` | 7        | Trekvogelpad (24 stages) |
| 8435936   | `nl-hike` | 8        | Maarten van Rossumpad (24 stages) |
| 1537463   | `nl-hike` | 9        | Noaberpad (23 stages) |
| 6715665   | `nl-hike` | 10       | Waterliniepad (21 stages) |
| 8463196   | `nl-hike` | 11       | Grenslandpad (20 stages) |
| 2801085   | `nl-hike` | 12       | Marskramerpad (20 stages) |
| 6662765   | `nl-hike` | 13       | Groot Frieslandpad (23 stages) |
| 18632711  | `be-hike` | 1        | Via Brabantica (7 stages) |
| 14368967  | `hr-hike` | 1        | Via Apsyrtides (11 stages, Rijeka→Pula) |
| 7128733   | `se-hike` | 1        | Hälsingeleden (22 stages) |
| 280016    | `se-hike` | 2        | Bohusleden (27 stages) |
| 10524322  | `se-hike` | 3        | St. Olavsleden (29 stages) |
| 19012437  | `se-hike` | 4        | Stockholm Archipelago Trail (19 stages) |
| 1657661   | `se-hike` | 5        | Kungsleden (31 stages, Abisko→Hemavan) |
| 23828     | `se-hike` | 6        | Skåneleden SL1 - Kust till kust (20 stages) |
| 415700    | `se-hike` | 7        | Skåneleden SL2 - Nord till syd (19 stages) |
| 68019     | `se-hike` | 8        | Skåneleden SL3 - Ås till ås (14 stages) |
| 408995    | `se-hike` | 9        | Skåneleden SL4 - Österlen (12 stages) |
| 399333    | `se-hike` | 10       | Skåneleden SL5 - Öresund (19 stages) |
| 11583146  | `se-hike` | 11       | Skåneleden SL6 - Vattenriket (10 stages) |
| 18194568  | `se-hike` | 12       | Skåneleden SL7 - Sydkust (5 stages) |
| 1673983   | `se-hike` | 13       | Hallandsleden |
| 297037    | `se-hike` | 14       | Blekingeleden |
| 254324    | `se-hike` | 15       | Södra Kungsleden |
| 3199983   | `se-hike` | 16       | Tjustleden |
| 3649216   | `se-hike` | 17       | Ostkustleden |
| 8436154   | `se-hike` | 18       | Ingegerdsleden |
| 1730468   | `se-hike` | 19       | Höga Kusten-leden |
| 2926839   | `se-hike` | 20       | Dalkarlsvägen |
| 9588658   | `se-hike` | 21       | Solanderleden |
| 14772115  | `no-hike` | 1        | Fjordruta på Nordmøre (14 stages) |
| 6364172   | `no-hike` | 2        | Nordland trekking trail (43 stages) |
| 19229749  | `no-hike` | 3        | Lofoten Long Crossing (11 stages) |
| 5620490   | `no-hike` | 4        | Jotunheimstien |
| 14770011  | `no-hike` | 5        | Signatur Stølsheimen |
| 14769947  | `no-hike` | 6        | Signatur Omveien |
| 14772116  | `no-hike` | 7        | Signatur Trollheimen |
| 14772110  | `no-hike` | 8        | Signatur Lysefjorden rundt |
| 14772117  | `no-hike` | 9        | Signatur Helt på grensen |
| 14772111  | `no-hike` | 10       | Gullruta i Etnefjellene |
| 7078769   | `no-hike` | 11       | Ryger |
| 14771926  | `no-hike` | 12       | Saga |
| 14769822  | `no-hike` | 13       | Massiv Trail |
| 1792585   | `dk-hike` | 1        | Hærvejen (30 stages) |
| 1202410   | `dk-hike` | 2        | Øhavsstien (7 stages) |
| 6519670   | `lt-hike` | 1        | E11 Lithuania (36 stages, Lazdijai→Skuodas) |
| 9645763   | `ee-hike` | 1        | Euroopa matkarada E9 (31 stages) |
| 13182780  | `ee-hike` | 2        | Peraküla-Aegviidu-Ähijärve haru (11 stages) |
| 15843108  | `ee-hike` | 3        | Camino Estonia (10 stages) |
| 20014200  | `eu-hike` | 1        | Via Alpina (116 stages, Monaco→Trieste) |
| 3176522   | `eu-hike` | 2        | Alpe Adria Trail (43 stages, Salzburg→Trieste) |
| 6436417   | `eu-hike` | 3        | Tour du Mont Blanc (11 stages, circular FR/IT/CH) |
| 16127693  | `eu-hike` | 4        | Sultan's Trail (120 stages, Vienna→Istanbul, AT/SK/HU/RS/HR/BG/GR/TR) |
| 2437984   | `eu-hike` | 6        | Nordkalottruta (43 stages, Sulitjelma→Buletjávri, NO/SE/FI) |

## Website-only routes (scraper_websites.py)

| route_id | Trail | Land | Stages | Source |
|----------|-------|------|--------|--------|
| uk-15    | Coast to Coast (Wainwright's) | `uk` | 14 | wainwright.org.uk (hardcoded) |
| de-44    | Sauerland-Waldroute | `de-hike` | 7 | sauerland-waldroute.de (partial — JS-rendered, 19 actual stages) |
| de-48    | Kammweg Erzgebirge-Vogtland | `de-hike` | 17 | erzgebirge-tourismus.de (hardcoded, overwrites 3 OSM sections) |
| de-49    | Eifelsteig | `de-hike` | 15 | eifelsteig.de |
| de-50    | Linksrheinischer Jakobsweg | `de-hike` | 12 | linksrheinischer-jakobsweg.info |
| de-51    | WestfalenWanderWeg | `de-hike` | 11 | wildganz.com |
| de-53    | Stormarnweg | `de-hike` | 6 | wildganz.com (hardcoded) |
| de-54    | Oberlausitzer Bergweg | `de-hike` | 7 | oberlausitzer-bergweg.de (hardcoded) |
| de-55    | Werra-Burgen-Steig Hessen | `de-hike` | 6 | werra-burgen-steig-hessen.de (hardcoded) |
| de-56    | König-Ludwig-Weg | `de-hike` | 8 | koenig-ludwig-weg.de (hardcoded — JS-rendered) |
| de-57    | X27 Friedrich-Wilhelm-Grimme-Weg | `de-hike` | 11 | ich-geh-wandern.de (hardcoded) |
| de-58    | Vulkanring Vogelsberg | `de-hike` | 6 | vogelsberg-touristik.de (hardcoded) |
| de-59    | Ith-Hils-Wanderweg | `de-hike` | 7 | ith-hils.de (hardcoded) |
| es-11    | Camino de la Frontera | `es-hike` | 14 | caminodelafrontera.es (hardcoded) |
| es-12    | Camino Espiritual del Sur | `es-hike` | 14 | caminoespiritualdelsur.com (live scraper) |
| it-13    | Italia Coast to Coast | `it-hike` | 18 | italiacoast2coast.it |
| pt-2     | Grande Rota Peneda-Gerês | `pt-hike` | 19 | walkingpenedageres.pt |
| pt-3     | Camino Portugués | `pt-hike` | 25 | pilgrim.es (Lisboa→Santiago) |
| sk-1     | SNP Trail | `sk-hike` | 27 | snptrail.com (hardcoded, multi-page) |

## Deferred (no viable day-stage subroutes in OSM)

| Trail | Notes |
|---|---|
| GR10 Pyrenean Traverse | 9 sections ~100 km each — no day-stage breakdown at level-2 |
| GR5 Grande Traversée des Alpes | OSM 18308154, coarse sections only. Re-check periodically. |
| Camino Francés | OSM 2163573, flat (1 child × 163 km) |
| Via Francigena | Canterbury→Rome; Italian section may have subroutes now — check periodically |
| Lycian Way | Turkey; OSM structure flat. Needs website scraper (tr-hike) |
| High Scardus Trail | 31 stages, 215km, MK/XK/AL. high-scardus-trail.com — website scraper candidate |
| Stråsjöleden | 15 stages, 264km. paxwalk.se — Outdooractive JS-rendered |
| Via Dinarica (White Trail) | OSM 4690755, flat — no day-stage subroutes |
| Müritz-Nationalpark-Wanderweg | Flat OSM / Outdooractive JS-rendered |
| Georg-Fahrbach-Weg | Flat OSM (4 coarse sections) |
| Ruta del Ter | Flat OSM (4 coarse sections, ~55km each) |
| Kaiserweg | wandern-suedharz-kyffhaeuser.de repeatedly ECONNREFUSED |

## Future candidates

| Trail | Land | Notes |
|---|---|---|
| **Latvia** | `lv-hike` (new) | E9/E11 sections likely have day-stage OSM hierarchy — check Waymarked Trails |
| **More French GRs** | `fr-hike` | GR34 Chemin des Douaniers, GR54 Tour de l'Oisans — check OSM structure |
| **More Spanish** | `es-hike` | Camino del Norte, Via de la Plata — OSM may have day stages |
| **Ireland update** | `ie-hike` | All 6 routes are flat single-stage OSM — re-check if day stages added |
| Zentralalpenweg 02 | `at-hike` | 8 stages, 1146km. Coarse OSM sections. |

## Pending tasks

- **Westweg user_state alignment** — stages 5–9 renumbered when OSM replaced Schwarzwaldverein version. Any user completions for old stages 5–9 now map to wrong stages.
- **Sauerland-Waldroute** — 19 full stages on sauerland-waldroute.de but only 7 in static HTML (rest JS-rendered). Consider Playwright scrape.
- **Kammweg Erzgebirge-Vogtland** — website version has 17 stages but OSM only had 3 coarse sections.
- **`discover_trails.py --recheck-large-stages`** — run to get real day-stage counts for multi-section candidates.
