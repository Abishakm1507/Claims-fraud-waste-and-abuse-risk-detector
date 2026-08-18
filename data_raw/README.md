# data_raw — optional fallback only

**You do not normally need this folder.**

The assistant reads the ETL's curated tables (`data/curated/`), which it locates
automatically — at the repo root, above this module, or in a sibling project.
Check what it found:

```bash
python -c "from backend.data import warehouse as wh; print(wh.source())"
```

`curated` means it is reading ETL output. Nothing further is required.

## When this folder IS used

Only if no curated tables exist — for example running this module standalone,
before the ETL has been executed. In that case drop the source CSVs here and
run:

```bash
python scripts/build_data.py
```

The assistant then builds its own warehouse from them. This is a fallback: two
modules parsing the same CSVs independently can compute the same fact
differently, which is exactly what the ETL exists to prevent.

## Overriding the location

```
CURATED_DIR=/absolute/path/to/data/curated
```
