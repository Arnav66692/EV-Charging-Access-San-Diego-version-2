# Public web map

A single self-contained static page showing modeled DCFC fast-charging access,
equity (disadvantaged-community) context, and derived grid-feasibility tiers for
San Diego, Orange, and Los Angeles counties.

## Files

```
web/
├── index.html                  # the whole app: Leaflet + UI, no build step
└── data/
    ├── block_groups.geojson    # per-bg derived values (access, rel_access, pctile, is_dac, low_pop)
    ├── counties.geojson        # county boundaries
    └── candidates.geojson      # derived candidate feasibility tiers (lazy-loaded on toggle)
```

Regenerate the data files from the processed parquet with:

```bash
python scripts/build_web_data.py
```

## SDG&E firewall (legal boundary)

San Diego is in SDG&E territory and SDG&E prohibits redistributing its ICA load
layer. **No SDG&E load-capacity value, raw or rounded, ships in any file the
browser loads.** The map carries only derived outputs: modeled access, per-county
relative access, percentile rank, the DAC flag, and feasibility *tiers* (not MW).
The builder asserts the forbidden field names are absent before writing, and
`tests/test_web_firewall.py` is the release gate:

```bash
pytest tests/test_web_firewall.py -q
```

## Hosting

Pure static files, no backend, no API, no browser storage. Serve the `web/`
directory from any static host:

- **Local preview:** `python -m http.server 8011 --directory web` → http://localhost:8011
- **GitHub Pages / Netlify / Cloudflare Pages / S3+CloudFront:** publish the
  `web/` folder as-is. The only external requests are the Leaflet library and the
  CARTO basemap tiles (both CDN, neither carries project data). Drop the tile
  layer in `index.html` for a fully offline build.

Total payload on first load is ~4 MB (block groups + counties); the 3.2 MB
candidate layer is fetched only when its toggle is switched on.
