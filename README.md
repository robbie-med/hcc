# HCC Finder

Search a diagnosis, symptom, abbreviation, ICD-10 code, or `bmi 42` and get the matching ICD-10-CM codes that map to a CMS-HCC (V28), with the official descriptor ready to copy.

Runs entirely in the browser. Nothing is sent anywhere; the selection list and color settings stay in local storage.

## Deploy

GitHub Pages: Settings > Pages > Deploy from a branch > `main` / root.

## Data

| What | Source |
|---|---|
| ICD-10 to HCC mapping | CMS 2027 mappings, CMS-HCC V28 (`hccinfhir`) |
| HCC labels, hierarchies | CMS V28 model software |
| RAF weights | Payment year 2026 final, community non-dual aged |
| Descriptors, inclusion terms | ICD-10-CM tabular, April 2026 (`simple_icd_10_cm`) |
| Synonyms, symptoms, notes, tips | `build/clinical.json` |

## Rebuild data

```
pip install -U hccinfhir simple_icd_10_cm
python3 build/build.py
node build/check.mjs   # smoke test: search, typo correction, RAF total
```

For a new payment year, change `MAP_YEAR`, `COEF_YEAR`, and `DATA_DATE` (the CMS mappings file date) in `build/build.py`.

Reference only. Code what the note supports.
