# Swiss ch-hike OSM Superroute Status

Audit run 2026-06-28 against Overpass (`operator=Wanderland Schweiz`, `type=superroute`) and Waymarked Trails child counts.

Routes 1–7 and 95 were already wired in. This covers the remaining 81 multi-stage routes.

---

## Count mismatch — OSM needs fixing

OSM has a superroute but the child sub-route count doesn't match SchweizMobil. Someone needs to add the missing sub-route relations in OSM.

| Route | Name | SM stages | OSM subroutes | OSM relation |
|-------|------|-----------|---------------|--------------|
| ch-hike 45 | Nationalpark-Panoramaweg | 7 | 6 | [1601223](https://www.openstreetmap.org/relation/1601223) |
| ch-hike 62 | Walserweg Gottardo | 14 | 11 | [20121021](https://www.openstreetmap.org/relation/20121021) |
| ch-hike 75 | Schanfigger Höhenweg | 6 | 4 | [20127293](https://www.openstreetmap.org/relation/20127293) |

---

## No OSM superroute — structure missing entirely

These routes have no `type=superroute` relation in OSM. The full hierarchy (one parent superroute + one child route relation per stage) needs to be created.

| Route | Name | SM stages |
|-------|------|-----------|
| ch-hike 22 | Kulturspur Appenzellerland | 6 |
| ch-hike 23 | Senda Scuol–Samnaun | 2 |
| ch-hike 26 | Panorama Rundweg Thunersee | 4 |
| ch-hike 27 | Swiss Tour Monte Rosa | 3 |
| ch-hike 28 | Chemin de la Sarine fribourgeoise | 2 |
| ch-hike 29 | Pragelpass-Weg | 3 |
| ch-hike 30 | ViaValtellina | 8 |
| ch-hike 33 | Via Albula/Bernina | 10 |
| ch-hike 36 | Chemin du vignoble | 4 |
| ch-hike 39 | Aletsch Panoramaweg | 3 |
| ch-hike 40 | ViaSbrinz | 5 |
| ch-hike 42 | Aargauer Weg | 6 |
| ch-hike 44 | Appenzeller Weg | 3 |
| ch-hike 48 | Toggenburger Höhenweg | 6 |
| ch-hike 49 | Vier-Quellen-Weg | 5 |
| ch-hike 50 | ViaSpluga | 4 |
| ch-hike 51 | Furka-Höhenweg | 2 |
| ch-hike 53 | Bernina-Tour | 5 |
| ch-hike 57 | Obwaldner Höhenweg | 6 |
| ch-hike 58 | Chemin des Bisses | 7 |
| ch-hike 59 | Sentiero Cristallina | 3 |
| ch-hike 65 | Grenzpfad Napfbergland | 6 |
| ch-hike 66 | Liechtensteiner Panoramaweg | 3 |
| ch-hike 69 | Züri Oberland-Höhenweg | 4 |
| ch-hike 70 | ViaFrancigena (CH) | 10 |
| ch-hike 71 | Chemin des Trois-Lacs | 3 |
| ch-hike 76 | Seeland-Solothurn-Weg | 4 |
| ch-hike 78 | Freiburger Voralpenweg | 5 |
| ch-hike 79 | Thurgauer Panoramaweg | 2 |
| ch-hike 81 | Fribourg en diagonale | 3 |
| ch-hike 82 | Sanetsch-Muveran-Weg | 3 |
| ch-hike 85 | Senda Sursilvana | 5 |
| ch-hike 86 | Rheintaler Höhenweg | 6 |
| ch-hike 87 | Via Engiadina | 12 |
| ch-hike 88 | Nidwaldner Höhenweg | 6 |
| ch-hike 90 | ViaStockalper | 3 |
| ch-hike 92 | Neckerweg | 2 |
| ch-hike 99 | Weg der Schweiz | 4 |
| ch-hike 261 | Sentier du Lac de la Gruyère | 3 |
| ch-hike 360 | Brienzersee Drei Wasserfälleweg | 2 |
| ch-hike 381 | Schwarzwasser-Sense-Schluchtenweg | 2 |
| ch-hike 478 | Weissenstein-Passwang-Weg | 2 |
| ch-hike 570 | Nidwaldner Zentrumsweg | 2 |
| ch-hike 599 | ViaUrschweiz | 2 |
| ch-hike 693 | Via Capricorn | 3 |
| ch-hike 712 | Sentiero Alpino Calanca | 3 |
| ch-hike 735 | Walserweg Safiental | 3 |
| ch-hike 737 | Via Calanca | 2 |
| ch-hike 757 | Alte Averserstrasse | 2 |
| ch-hike 980 | Appenzeller Alpenweg | 2 |

---

## What "correct structure" means in OSM

The pattern used by the already-wired routes (e.g. Au fil du Doubs):

- One parent `type=superroute` relation with `route=hiking`, `network=rwn`, `operator=Wanderland Schweiz`, `ref=<SM route number>`, `from`/`to`
- One child `type=route` relation per stage, each with `route=hiking`, `network=rwn`, `ref=<SM route number>`, `from`/`to` matching the stage endpoints, named `<Route Name> - Etappe N`

Once the OSM structure matches, add the parent relation ID to `CH_OSM_PARENTS` in `scraper_osm.py` and run `python3 scraper_osm.py --backfill-ch-osm-ids`, then `source .env && python3 scraper.py --import`.
