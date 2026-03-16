# Tanzania Early Warning Bulletin System — Project Overview

This document describes what the project does, how it works, and how to run it locally.

---

## What It Does

This is a **Tanzania Early Warning Bulletin Generator** system. It supports:

1. **Web dashboard (Streamlit)** — Role-based access for multiple agencies to create and edit early-warning bulletins through forms and maps.
2. **Document pipeline** — Validates form/JSON data, generates Tanzania maps (region/district level), builds Word (DOCX) bulletins, and optionally converts them to PDF.
3. **Two bulletin types:**
   - **722E_4** — Five Days Severe Weather Impact-Based Forecast (TMA — Tanzania Meteorological Authority).
   - **Multirisk** — Three Days Impact-Based Forecast (PMO/DMD — Prime Minister’s Office / Disaster Management Division), combining inputs from TMA, MoW, GST, MoH, MoA, and NEMC.

### Main capabilities

- **Multi-agency dashboard:** TMA (Weather), MoW (Water/Flood), GST (Geological), MoH (Health), MoA (Agriculture), NEMC (Environment), and PMO/DMD (Multirisk).
- **Interactive maps:** Folium/Plotly maps with region or district selection; optional draw-on-map for custom areas.
- **Automatic map generation:** Pipeline draws Tanzania maps with alert-level colors (advisory/warning/major warning), region labels, water bodies, and warning icons.
- **Bilingual:** English and Swahili for labels and default texts.
- **Data bridges:** TMA and MoW data can be sent to the DMD page to pre-fill the multirisk bulletin.
- **History & audit:** Browse generated bulletins (PDF/DOCX) and view audit logs (admin).
- **PDF output:** DOCX → PDF using a Python backend (`docx2pdf` + Microsoft Word on supported platforms). DOCX generation works even if PDF is unavailable.

---

## How It Works

### High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard (Streamlit)                                            │
│  dashboard.py → auth → entity pages (TMA, MoW, GST, MoH, MoA,   │
│  NEMC, DMD) → forms, map widgets, validation, templates          │
└────────────────────────────┬────────────────────────────────────┘
                              │ JSON (form data)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Pipeline (src/)                                                  │
│  pipeline.py → validator → auto_maps → builder (722e4/multirisk)  │
│  → DOCX → pdf_converter (docx2pdf) → PDF                          │
└─────────────────────────────────────────────────────────────────┘
```

- **Dashboard:** Users log in (see `dashboard_config.yaml`), pick an entity (TMA, MoW, DMD, etc.), fill forms and maps, then trigger “Generate”. The app builds a JSON payload and calls the pipeline.
- **Pipeline:** Loads JSON → validates and parses into bulletin models → generates map images (if enabled) → builds DOCX with `python-docx` → optionally converts to PDF via `pdf_converter` (using `docx2pdf`).

### Main directories and modules

| Path | Purpose |
|------|--------|
| `dashboard.py` | Streamlit entry point; page config, sidebar entity selector, calls entity render functions. |
| `dashboard/` | Auth, config, entity pages (TMA, MoW, GST, MoH, MoA, NEMC, DMD), map widget, PDF viewer, validation, templates, data bridge, history, audit. |
| `src/` | Core pipeline and shared logic. |
| `src/models/` | Data models: `seven22e4.py` (722E_4), `multirisk.py` (Multirisk), `common.py` (AlertLevel, HazardType, etc.). |
| `src/validation/` | JSON → bulletin validation and parsing. |
| `src/builders/` | Document builders (`seven22e4_builder`, `multirisk_builder`), headers, tables, **map_generator** (Matplotlib + GeoPandas), auto_maps. |
| `src/converters/` | DOCX → PDF via `docx2pdf` (no LibreOffice dependency). |
| `src/pipeline.py` | `generate_722e4()` and `generate_multirisk()` orchestration. |
| `src/cli.py` | Click CLI for non-dashboard runs: `generate 722e4` and `generate multirisk`. |
| `assets/` | Logos, geodata (GADM regions/districts, Natural Earth lakes/rivers), icons. |
| `documents/` | Reference PDFs for comparison. |
| `output/` | Generated DOCX/PDF per entity (e.g. `output/tma/`, `output/dmd/`), maps, bridge files. |

### Data flow (dashboard → bulletin)

1. User selects regions/districts and alert levels on the entity page (and optionally draws shapes).
2. Form state is converted to the JSON schema expected by the pipeline (see `src/validation/`).
3. On “Generate”, the app calls `pipeline.generate_722e4(...)` or `pipeline.generate_multirisk(...)` with an input JSON path (often a temp file or a path under `output/`).
4. Pipeline: validate → generate maps (e.g. `src/builders/auto_maps.py` + `map_generator.py`) → build DOCX → save to `output/<entity>/` → optionally convert to PDF.
5. User can preview or download PDF/DOCX from the dashboard (e.g. history panels).

### Map generation

- **`src/builders/map_generator.py`:** Uses GeoPandas (GADM Tanzania regions/districts) and Matplotlib to draw:
  - Region or district polygons colored by alert level (yellow/orange/red/gray).
  - Region labels, country outline, lakes/rivers, optional warning icons.
- **`src/builders/auto_maps.py`:** Driven by bulletin content; calls the map generator and assigns map images to the bulletin (per day for 722E_4; per day and hazard for Multirisk).

### Authentication and roles

- **`dashboard/auth.py`** uses `streamlit-authenticator` and a YAML config.
- **`dashboard_config.yaml`** (project root) defines:
  - `credentials.usernames`: username, name, hashed password, `role`.
  - `cookie`: name, key, expiry.
- Roles (e.g. `tma`, `mow`, `dmd`, `gst`, `moh`, `moa`, `nemc`, `admin`) determine which entity view is default and which pages are available; `admin` can access all and the audit log.

---

## How to Run the Localhost Project

### Prerequisites

- **Python 3.10+** (project uses 3.12 in `venv`).
- **For PDF export (optional)**: `docx2pdf` and a compatible Microsoft Word installation (on Windows/macOS). Without this, the system still generates DOCX successfully; you can convert to PDF externally if needed.

### 1. Clone or open the project

Use the project root as working directory (e.g. `EW`).

### 2. Create a virtual environment and install dependencies

```bash
cd c:\Users\Daniel\Desktop\code\Masubi\Boni\EW
python -m venv venv
```

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (CMD):**

```cmd
venv\Scripts\activate.bat
pip install -r requirements.txt
```

**Linux/macOS:**

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure authentication

The app expects **`dashboard_config.yaml`** in the project root. A sample is already there with predefined users and bcrypt-hashed passwords. To add or change users:

- Edit `dashboard_config.yaml` (see `dashboard/auth.py` and streamlit-authenticator docs).
- Passwords must be hashed (e.g. with `bcrypt`). The sample users (e.g. `tma_user`, `dmd_user`, `admin`) can be used as-is for local testing.

Ensure the file exists:

```text
EW/
  dashboard_config.yaml   # credentials and cookie config
```

### 4. Run the Streamlit dashboard

From the **project root** (where `dashboard.py` lives):

```bash
streamlit run dashboard.py
```

Or with explicit host/port:

```bash
streamlit run dashboard.py --server.port 8501 --server.address localhost
```

- Default URL: **http://localhost:8501**
- Log in with one of the users in `dashboard_config.yaml` (e.g. `admin` / password as set in the sample).
- Use the sidebar to switch between entities (TMA, MoW, GST, MoH, MoA, NEMC, PMO/DMD).
- Generate bulletins from the forms; outputs go to `output/tma/`, `output/dmd/`, etc.

### 5. Run the pipeline from the command line (no dashboard)

Without the web UI you can still generate bulletins from JSON files:

```bash
# From project root, with venv activated
pip install -e .   # if the project is set up as a package; otherwise ensure src is on PYTHONPATH

# 722E_4 Five Days Severe Weather (use examples/722e4_example.json for a sample)
python -m src.cli generate-722e4 -i path/to/input.json -o ./output -f both

# Multirisk Three Days (use examples/multirisk_sw_example.json for a sample)
python -m src.cli generate-multirisk -i path/to/input.json -o ./output -f both
```

If `python -m src.cli` fails (e.g. module not found), run from the project root with `PYTHONPATH` set:

**Windows (PowerShell):**

```powershell
$env:PYTHONPATH = (Get-Location).Path; python -m src.cli generate-722e4 -i examples/722e4_example.json -o ./output -f both
```

**Linux/macOS:**

```bash
PYTHONPATH=. python -m src.cli generate-722e4 -i examples/722e4_example.json -o ./output -f both
```

Sample input JSON files are in the **`examples/`** folder (e.g. `722e4_example.json`, `multirisk_sw_example.json`).

CLI options (for both commands):

- `-i` / `--input`: Input JSON file.
- `-o` / `--output-dir`: Output directory (default `./output`).
- `-f` / `--format`: `docx`, `pdf`, or `both`.
- `--no-maps`: Skip automatic map generation.
- `-m` / `--maps-dir`: Use pre-made map images from this directory.

### 6. Geodata and assets

- Map generation expects **`assets/geodata/`** with GADM and Natural Earth data (e.g. `gadm41_TZA_1.json.zip`, `gadm41_TZA_2.json.zip`, `ne_10m_lakes.zip`, `ne_10m_rivers.zip`). If these are missing, map generation may fail; add the expected files or adjust paths in `dashboard/config.py` and `src/builders/map_generator.py`.
- Logos and icons are referenced under `assets/` (see `config.py` and builder code).

---

## Summary

| Question | Answer |
|----------|--------|
| **What it does** | Multi-agency early warning bulletin system: web forms + maps → JSON → DOCX/PDF (722E_4 and Multirisk). |
| **How it works** | Streamlit dashboard for data entry and generation; `src` pipeline for validation, map generation, and document building; optional `docx2pdf` backend for PDF. |
| **Run locally** | Install deps from `requirements.txt`, configure `dashboard_config.yaml`, run `streamlit run dashboard.py`, open http://localhost:8501. |
| **CLI only** | Use `python -m src.cli generate-722e4` / `generate-multirisk` with JSON input and output options. |

For more detail, see the docstrings in `dashboard.py`, `src/pipeline.py`, `src/builders/map_generator.py`, and the various `dashboard/*_page.py` modules.
