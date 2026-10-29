#!/usr/bin/env python3
"""Build data.json for HCC Finder.

Sources (via pip):
  hccinfhir        CMS ICD-10 -> HCC mappings, labels, hierarchies, coefficients
                   (generated from CMS risk adjustment model software)
  simple_icd_10_cm Official ICD-10-CM tabular descriptors and inclusion terms

Usage:
  pip install -U hccinfhir simple_icd_10_cm
  python3 build/build.py            # writes data.json next to index.html

To update for a new year, change MAP_YEAR / COEF_YEAR below after upgrading
the packages, then rebuild and spot-check a few codes against the CMS files.
"""
import csv, json, os, re, sys, datetime
import simple_icd_10_cm as icd
import hccinfhir

MODEL = "CMS-HCC Model V28"
MAP_YEAR = 2027      # CMS mapping year (payment year; dates of service the prior year)
COEF_YEAR = 2026     # final published coefficients
COEF_PREFIX = "CNA_HCC"  # community, non-dual, aged
DATA_DATE = "14MAY2026"  # Last-Modified of the CMS mappings zip for MAP_YEAR, shown as "Updated" on the page

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data.json")
D = os.path.join(os.path.dirname(hccinfhir.__file__), "data")

def rows(name):
    with open(os.path.join(D, name), newline="") as f:
        yield from csv.DictReader(f)

# --- mapping
dx = {}
for r in rows(f"ra_dx_to_cc_{MAP_YEAR}.csv"):
    if r["model_name"] == MODEL:
        dx.setdefault(r["diagnosis_code"], set()).add(int(r["cc"]))

# --- labels, weights, hierarchy
labels = {r["cc"][3:]: r["label"] for r in rows("ra_labels_2026.csv") if r["model_version"] == "V28"}
weights = {}
for r in rows(f"ra_coefficients_{COEF_YEAR}.csv"):
    if r["model_version"] == "C28" and r["coefficient"].startswith(COEF_PREFIX):
        weights[r["coefficient"][len(COEF_PREFIX):]] = float(r["value"])
trumps, trumped = {}, {}
for r in rows(f"ra_hierarchies_{COEF_YEAR}.csv"):
    if r["model_version"] == "V28":
        trumps.setdefault(r["cc_parent"], []).append(int(r["cc_child"]))
        trumped.setdefault(r["cc_child"], []).append(int(r["cc_parent"]))

edits = {}
for r in rows("ra_dx_edits.csv"):
    if r["model_name"] != MODEL:
        continue
    if r["edit_type"] == "sex":
        who = "female" if r["sex"] == "2" else "male"
        t = f"{who}: " + ("no HCC" if r["action"] != "override" else f"HCC {r['cc_override']}")
    else:
        rng = f"age {r['age_min'] or '0'}-{r['age_max'] or '+'}"
        t = f"valid only {rng}" if r["action"] != "override" else f"{rng}: HCC {r['cc_override']}"
    edits.setdefault(r["icd10"], []).append(t)

hcc = {}
used = sorted({c for v in dx.values() for c in v})
for c in used:
    k = str(c)
    hcc[k] = {
        "l": labels.get(k, f"HCC {k}"),
        "w": weights.get(k),
        "t": sorted(trumps.get(k, [])),
        "b": sorted(trumped.get(k, [])),
    }

# --- codes: every billable code in any 3-char category that has an HCC code
def dot(k):
    return k if len(k) <= 3 else k[:3] + "." + k[3:]

cats = {k[:3] for k in dx}
codes = []
for k in icd.get_all_codes(with_dots=False):
    if "-" in k or not icd.is_leaf(k) or not k[:1].isalpha():
        continue
    d = dot(k)
    desc = icd.get_description(d)
    try:
        incl = icd.get_inclusion_term(d) or []
    except Exception:
        incl = []
    row = [k, desc, sorted(dx.get(k, []))]
    extra = "; ".join(incl)
    if extra or k in edits:
        row.append(extra)
    if k in edits:
        row.append("; ".join(edits[k]))
    codes.append(row)

missing = [k for k in dx if not icd.is_valid_item(dot(k))]
if missing:
    print(f"WARNING: {len(missing)} mapped codes lack descriptors: {missing[:20]}", file=sys.stderr)

# --- clinical layer + validation
clin = json.load(open(os.path.join(HERE, "clinical.json")))
STOP = {"of", "the", "and", "a", "an", "to", "in", "for", "or", "with", "nos"}
def stem(t):
    if len(t) > 5 and t.endswith("es"): return t[:-2]
    if len(t) > 6 and t.endswith("ic"): return t[:-2]
    if len(t) > 4 and t.endswith("s") and not t.endswith("ss"): return t[:-1]
    return t
def toks(s):
    return [stem(t) for t in re.split(r"[^a-z0-9]+", s.lower()) if t and t not in STOP]
idx = [(r, " " + " ".join(re.split(r"[^a-z0-9]+", (r[1] + " " + (r[3] if len(r) > 3 else "")).lower())) + " ") for r in codes]
def hits(q):
    ts = toks(q)
    return [r for r, t in idx if r[2] and all((" " + x) in t for x in ts)]
bad = []
for s in clin["symptoms"]:
    for c in s["consider"]:
        if not hits(c["q"]):
            bad.append(c["q"])
for k, exps in clin["synonyms"].items():
    if not any(hits(e) for e in exps):
        bad.append(f"syn:{k}")
if bad:
    print("WARNING: queries with no HCC hits:", bad, file=sys.stderr)

out = {
    "meta": {
        "model": "CMS-HCC V28",
        "mapping": f"CMS {MAP_YEAR} ICD-10 to HCC mappings (payment year {MAP_YEAR}, {MAP_YEAR-1} dates of service)",
        "weights": f"Payment year {COEF_YEAR} final, community non-dual aged",
        "icd": "ICD-10-CM " + next((f[len("icd10c-tabular-"):-4].replace("-1-", " ") for f in os.listdir(os.path.join(os.path.dirname(icd.__file__), "data")) if f.startswith("icd10c-tabular")), "tabular"),
        "built": datetime.date.today().strftime("%d%b%Y").upper(),
        "updated": DATA_DATE,
        "counts": {"hccCodes": len(dx), "codes": len(codes), "hccs": len(hcc)},
    },
    "hcc": hcc,
    "codes": codes,
    "syn": clin["synonyms"],
    "symptoms": clin["symptoms"],
    "notes": clin["notes"],
    "tips": clin["tips"],
}
with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
print(f"wrote {OUT}: {os.path.getsize(OUT)/1e6:.2f} MB, {len(codes)} codes, {len(dx)} HCC codes, {len(hcc)} HCCs")
