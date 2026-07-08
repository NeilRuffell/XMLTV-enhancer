# XMLTV Enhancer

Provider-agnostic XMLTV enrichment service for Kodi IPTV Simple and `skin.estuary.pvr.plus.omega`.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn xmltv_enricher.app:app --host 0.0.0.0 --port 8765
```

## Environment

```bash
INPUT_MODE=xmltv_url
XMLTV_URL=https://example.com/guide.xml
XMLTV_FILE=/data/input.xml
TMDB_TOKEN=
TMDB_LANGUAGE=en-US
TMDB_REGION=CA
PORT=8765
REFRESH_SECONDS=21600
DATA_DIR=/data
```

Use `INPUT_MODE=xmltv_url` with `XMLTV_URL` for a remote guide, or switch back to `INPUT_MODE=xmltv_file` to read a local file from `XMLTV_FILE`.

## Endpoints

- `/health`
- `/refresh`
- `/refresh?clear=1`
- `/stats`
- `/epg.xml`
- `/genres.xml`
- `/inspect?title=...`
- `/audit`
