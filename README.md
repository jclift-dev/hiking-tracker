# Via — Long-Distance Trail Tracker

> Track your progress on hiking and cycling trails across Europe. Built for a small group of users.

[![Live Demo](https://img.shields.io/badge/Live_Demo-GitHub_Pages-327FC7?logo=github&logoColor=white)](https://jclift-dev.github.io/hiking-tracker/)

---

## Overview

**Via** is a web application for tracking progress on long-distance hiking and cycling trails. It started as a Swiss hiking tracker (April 2026) and has expanded to cover trails across **Switzerland, UK, France, Germany, Italy, Spain, and Ireland**.

- **Web App**: Single-file vanilla JS application (`index.html`)
- **Backend**: Supabase (PostgreSQL + Auth)
- **Data Sources**: SchweizMobil API, Waymarked Trails (OSM), and various national trail websites
- **Travel Times**: Swiss public transport (SBB) integration for planning

---

## Features

### For Users

| Feature | Description |
|---------|-------------|
| **Stage Tracking** | Mark stages as completed with dates |
| **Wishlist** | Heart icon to save trails for later |
| **Ratings & Notes** | Rate trails (1-5) and add personal notes |
| **Multi-Country** | Switch between CH, UK, FR, DE, IT, ES, IE |
| **Multi-Activity** | Toggle hiking/cycling modes |
| **SBB Travel Times** | See train times from Swiss stations to trailheads |
| **Elevation Profiles** | Visual elevation icons per stage |
| **Dark Mode** | Automatic based on system preference |
| **Responsive** | Works on mobile and desktop |
| **Offline-First** | State persists across sessions |

### For Trail Data

| Country | Trails | Scraper |
|---------|--------|---------|
| **Switzerland** | 479 routes, 1179+ stages | `scraper.py` (SchweizMobil API) |
| **UK** | SWCP, WHW, ODP, SDW, CW, HWP, PCP, Cape Wrath | `scraper_nationaltrail.py`, `scraper_swcp.py`, `scraper_whw.py`, `scraper_odd.py` |
| **France** | GR20, GR65, GR70, HRP | `scraper_gr20.py`, `scraper_gr.py` |
| **Italy** | Alta Via 1 (Dolomites) | `scraper_av1.py` |
| **Germany** | Malerweg, Westweg, Goldsteig, Heidschnuckenweg | `scraper_malerweg.py`, `scraper_osm.py` |
| **Spain** | GR11, Camino Primitivo, GR221 | `scraper_osm.py` |
| **Ireland** | Wicklow Way, Kerry Way, Dingle Way, Causeway Coast, Beara Way, Western Way | `scraper_osm.py` |

---

## Quick Start

### Using the Web App

1. **Live Version**: Visit [https://jclift-dev.github.io/hiking-tracker/](https://jclift-dev.github.io/hiking-tracker/)
2. **Sign In**: Use your invited email address (sign-ups are disabled; users must be invited via Supabase)
3. **Browse Trails**: Filter by country, difficulty, or search
4. **Track Progress**: Click on stages to mark them complete, add ratings, and notes

### Running Locally

```bash
# Clone the repo
git clone https://github.com/jclift-dev/hiking-tracker.git
cd hiking-tracker

# Start a local HTTP server (required - won't work with file://)
python3 -m http.server 8000

# Open in browser
# http://localhost:8000
```

> **Note**: The app requires Supabase credentials to load data. For local development with live data, you'll need `.env` file with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`.

---

## Project Structure

```
hiking-tracker/
├── index.html           # Single-page web application
├── LICENSE              # MIT License + data source notices
├── README.md            # This file
├── requirements.txt     # Python dependencies
├── scraper.py           # Swiss trails (SchweizMobil API) + SBB enrichment
├── scraper_swcp.py      # UK: South West Coast Path
├── scraper_whw.py       # UK: West Highland Way
├── scraper_odd.py       # UK: Offa's Dyke Path
├── scraper_gr20.py      # France: GR20 (Corsica)
├── scraper_gr.py        # France: GR65, GR70, GR20 distances
├── scraper_av1.py       # Italy: Alta Via 1
├── scraper_malerweg.py  # Germany: Malerweg
├── scraper_nationaltrail.py  # UK: South Downs Way, Cotswold Way, etc.
├── scraper_osm.py       # OpenStreetMap trails (Waymarked Trails API)
├── test_sbb.py          # SBB API connectivity test
├── discover_local.py    # Research tool (Playwright)
├── hikes.json           # Scraped trail data (output)
├── CLAUDE.md            # Technical documentation
├── DESIGN.md            # Design system specification
├── assets/              # Terrain icons (SVG)
│   ├── icon-1-meadow.svg
│   ├── icon-2-rolling-hills.svg
│   ├── icon-3-foothills.svg
│   ├── icon-4-alpine.svg
│   └── icon-5-summit.svg
├── .env                 # Supabase credentials (gitignored)
└── .gitlab-ci.yml       # CI configuration
```

---

## Data Flow

```
SchweizMobil API (CH routes)
    ↓
Waymarked Trails API (OSM routes)
    ↓
National Trail Websites (UK/FR/DE/IT/ES/IE)
    ↓
scraper.py + friends → hikes.json
    ↓
Supabase (PostgreSQL)
    ↓
index.html (Web App)
```

---

## Scraping Trail Data

### Prerequisites

```bash
# Install all dependencies
pip3 install -r requirements.txt

# Or install individually
pip3 install requests beautifulsoup4 cloudscraper
```

### Switzerland (SchweizMobil)

```bash
# Fetch all routes and stages (no SBB times)
python3 scraper.py --routes-only

# Fetch routes only for a specific land
python3 scraper.py --routes-only --land ch-hike

# Enrich with SBB travel times from a specific origin
python3 scraper.py --sbb-only --origin "Basel SBB"

# Process all planned SBB origins in sequence (for overnight runs)
python3 scraper.py --sbb-all

# Import to Supabase
python3 scraper.py --import
```

**Planned SBB Origins**: Basel SBB, Zürich HB, Bern, Lausanne, Genève, Luzern, St. Gallen, Interlaken Ost, Chur, Thun, Biel/Bienne, Lugano

### UK Trails

```bash
# South West Coast Path (53 stages)
python3 scraper_swcp.py
python3 scraper_swcp.py --refresh  # Force re-fetch

# West Highland Way (8 stages)
python3 scraper_whw.py

# Offa's Dyke Path (12 stages)
python3 scraper_odd.py

# UK National Trails (SDW, CW, HWP, PCP)
python3 scraper_nationaltrail.py
python3 scraper_nationaltrail.py --only sdw  # Specific trail
```

### France

```bash
# GR20 (Corsica, 16 stages)
python3 scraper_gr20.py

# GR65 (Via Podiensis) + GR70 (Chemin de Stevenson)
python3 scraper_gr.py
python3 scraper_gr.py --only gr65
```

### Italy

```bash
# Alta Via 1 (Dolomites, 11 stages)
python3 scraper_av1.py
```

### Germany

```bash
# Malerweg (Saxon Switzerland, 8 stages)
python3 scraper_malerweg.py
```

### OpenStreetMap (Multi-Country)

```bash
# All OSM trails in catalog
python3 scraper_osm.py

# Specific trail by OSM relation ID
python3 scraper_osm.py --only 4080347  # Pennine Way

# Skip elevation lookups (faster)
python3 scraper_osm.py --skip-elevation
```

### Import to Supabase

After scraping, import to Supabase:

```bash
# Set credentials in .env first
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_SERVICE_KEY=your-service-role-key

python3 scraper.py --import
```

---

## Land Values

The `land` field identifies country and activity:

| Land | Country | Activity | Routes |
|------|---------|----------|--------|
| `ch-hike` | Switzerland | Hiking | SchweizMobil |
| `ch-cycle` | Switzerland | Cycling | SchweizMobil |
| `uk` | United Kingdom | Hiking | SWCP, WHW, ODP, SDW, CW, HWP, PCP, Cape Wrath |
| `fr-hike` | France | Hiking | GR20, GR65, GR70, HRP |
| `de-hike` | Germany | Hiking | Malerweg, Westweg, Goldsteig, Heidschnuckenweg |
| `it-hike` | Italy | Hiking | Alta Via 1 |
| `es-hike` | Spain | Hiking | GR11, Camino Primitivo, GR221 |
| `ie-hike` | Ireland | Hiking | Wicklow Way, Kerry Way, Dingle Way, etc. |

---

## Supabase Schema

### Tables

| Table | Purpose | Key |
|-------|---------|-----|
| `routes` | Route metadata | `(id, land)` |
| `stages` | Per-stage data | `(route_id, land, stage_nr)` |
| `user_state` | User completions/ratings/notes | `(user_id, stage_key)` |
| `user_preferences` | User settings | `user_id` |

### Row-Level Security (RLS)

- `routes` and `stages`: Public read access
- `user_state` and `user_preferences`: Users can only read/write their own rows
- Scraper uses service role key (bypasses RLS) for imports

---

## Development

### Adding a New Trail

1. **Identify the data source** (website API or scraping)
2. **Create a new scraper** following existing patterns
3. **Add land value** if new country/activity
4. **Update Supabase CHECK constraints**:
   ```sql
   ALTER TABLE routes DROP CONSTRAINT routes_land_check;
   ALTER TABLE routes ADD CONSTRAINT routes_land_check
     CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike'));
   ALTER TABLE stages DROP CONSTRAINT stages_land_check;
   ALTER TABLE stages ADD CONSTRAINT stages_land_check
     CHECK (land IN ('ch-hike','ch-cycle','uk','fr-hike','de-hike','it-hike','es-hike','ie-hike'));
   ```
5. **Add to web app** (`index.html`): source labels, flags, maps

### Design System

See `DESIGN.md` for:
- Color palette (Forest Depth, Glacial Slate, Swiss Emergency Red)
- Typography (Manrope for display, Inter for body)
- Elevation and depth system (tonal layering, no 1px borders)
- Component specifications (buttons, cards, chips, inputs)

---

## Rate Limiting & Quotas

| API | Limit | Delay | Notes |
|-----|-------|-------|-------|
| SchweizMobil | ~polite crawling | 0.35s between requests | Required `Referer` header |
| transport.opendata.ch (SBB) | Daily quota | 2.0s between requests | ~600-1200 requests per origin |
| OpenTopoData | 1000 req/day | None | Used for elevation data |

---

## Deployment

### GitHub Pages

The web app is deployed at [https://jclift-dev.github.io/hiking-tracker/](https://jclift-dev.github.io/hiking-tracker/)

Pushes to `main` branch deploy automatically via GitHub Pages.

### Local Testing

```bash
# Run the web app locally
python3 -m http.server 8000

# Or use the Claude Code launch configuration
# (defined in .claude/launch.json)
```

---

## Troubleshooting

### Stuck Auth State

Append `?reset` to the URL to clear localStorage and sessionStorage:
```
https://jclift-dev.github.io/hiking-tracker/?reset
```

### Scraper Issues

- **Daily quota exceeded**: Wait until midnight Swiss time (quota resets daily)
- **403 Forbidden**: Ensure `Referer: https://www.schweizmobil.ch/` header is set
- **Corrupted hikes.json**: Backup created automatically to `hikes.json.bak`

### PC Sleep/Wake Issues

The app includes recovery logic for PC lock/sleep scenarios. If the app appears stuck after waking, try:
1. Wait 20+ seconds for auto-recovery
2. Use `?reset` escape hatch
3. Refresh the page

---

## Security

- **XSS Protection**: User content (notes, error messages) is escaped before rendering
- **Auth**: Email + password via Supabase Auth; sign-ups disabled (invite-only)
- **Session**: 1-week expiry with auto-refresh
- **Service Key**: Never committed to repo (gitignored in `.env`)

---

## Contributing

This is a private project for a small group of users. Contributions are not currently accepted from external contributors.

---

## License

The trail data includes content from:
- **SchweizMobil**: Used with permission for non-commercial purposes
- **OpenStreetMap**: © OpenStreetMap contributors, ODbL 1.0
- **Waymarked Trails**: © OpenStreetMap contributors, ODbL 1.0

The application code is proprietary.

---

## Changelog

### Latest Updates (June 2026)

- **2026-06-04**: Add elevation to UK National Trail stages via GPX split
- **2026-06-04**: Add UK National Trails scraper (South Downs Way, Cotswold Way, Hadrian's Wall Path, Pembrokeshire Coast Path)
- **2026-06-04**: Add UK/Ireland OSM trails with two-link stage cards
- **2026-05-27**: Complete Basel SBB travel times for all 1332 stages
- **2026-05-26**: Add GR65 + GR70 scrapers, backfill GR20 distances

### Project Start

- **2026-04-05**: Initial commit — Swiss hiking & cycling tracker with 479 routes, 1179 stages

---

## Related Files

- [`CLAUDE.md`](CLAUDE.md) — Detailed technical documentation for AI assistants and developers
- [`DESIGN.md`](DESIGN.md) — Design system specification (Modern Alpinist theme)
- [`scraper.py`](scraper.py) — Main scraper for Swiss trails
- [`index.html`](index.html) — Web application source
