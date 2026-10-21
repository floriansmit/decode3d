"""Build the lightweight public heat-market overlay used by the web preview."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "apps" / "web" / "public" / "data" / "cultural-data.json"
NETWORKS = ROOT / "data" / "cultural" / "raw" / "district-heating-networks.xlsx"
WFS_URL = (
    "https://geoserver.plandata.dk/geoserver/wfs?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=pdk:theme_pdk_forsyningomraade_vedtaget_v"
    "&outputFormat=application/json&srsName=EPSG:4326"
    "&bbox=9.2,56.3,10.7,56.9,EPSG:4326"
)
PRTR_URL = "https://miljoeoplysningerservice.mst.dk/v1/virksomheder?regnskabsaar=2019"


def fetch_json(url: str):
    request = Request(url, headers={"User-Agent": "DECODE geothermal research preview/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=90) as response:
        return json.load(response)


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"\b(a/s|amba|aps|i/s|fjernvarmeforsyning|fjernvarmevaerk|varmevaerk|fjernvarme|kraftvarmevaerk|kraftvarme)\b", " ", value)
    return " ".join(re.findall(r"[a-z0-9]+", value))


def network_rows() -> list[dict]:
    frame = pd.read_excel(NETWORKS, sheet_name="125% metode", header=1)
    frame = frame[frame.iloc[:, 2] == 2024]
    rows = []
    for _, row in frame.iterrows():
        rows.append({
            "id": str(row.iloc[0]),
            "name": str(row.iloc[1]),
            "heat_tj": round(float(row.iloc[3]), 2),
            "co2_kg_gj": round(float(row.iloc[4]), 2),
            "normalised": normalise(row.iloc[1]),
        })
    return rows


def best_network(names: list[str], networks: list[dict]):
    best, best_score = None, 0.0
    for raw_name in names:
        name = normalise(raw_name)
        if not name:
            continue
        for candidate in networks:
            other = candidate["normalised"]
            score = SequenceMatcher(None, name, other).ratio()
            if name in other or other in name:
                score = max(score, min(len(name), len(other)) / max(len(name), len(other)) + 0.18)
            if score > best_score:
                best, best_score = candidate, score
    return (best, round(best_score, 3)) if best_score >= 0.72 else (None, round(best_score, 3))


def district_heating_areas() -> list[dict]:
    collection = fetch_json(WFS_URL)
    grouped = defaultdict(list)
    labels = defaultdict(set)
    for feature in collection["features"]:
        props = feature.get("properties", {})
        if props.get("vaerdi1203") != "Fjernvarme":
            continue
        label = props.get("forsytekst") or props.get("navn1203") or "District-heating area"
        key = normalise(label) or feature.get("id", label)
        grouped[key].append(shape(feature["geometry"]))
        labels[key].update(str(v) for v in (label, props.get("navn1203")) if v)

    networks = network_rows()
    output = []
    for index, (key, geometries) in enumerate(grouped.items()):
        geometry = unary_union(geometries).simplify(0.00018, preserve_topology=True)
        centre = geometry.representative_point()
        match, score = best_network(sorted(labels[key]), networks)
        output.append({
            "id": f"dh-{index}",
            "name": sorted(labels[key], key=len)[0],
            "lon": round(centre.x, 6),
            "lat": round(centre.y, 6),
            "geometry": mapping(geometry),
            "heat_delivery_tj_2024": match["heat_tj"] if match else None,
            "co2_kg_gj_2024": match["co2_kg_gj"] if match else None,
            "statistics_name": match["name"] if match else None,
            "match_score": score if match else None,
        })
    return output


def prtr_sites() -> list[dict]:
    # The service publishes XML by default. These are the ten records returned
    # inside the study bbox, enriched from each record's official activity call.
    rows = [
        (185914, 9.513842, 56.347392, "Arla Foods Amba Rødkærsbro Mejeri", "F 105", "Dairy processing"),
        (186778, 10.042098, 56.375173, "Leca Danmark A/S", "B 103", "Ceramic and lightweight aggregate production"),
        (187800, 9.670764, 56.381224, "GRUNDFOS A/S", "A 205", "Metal processing"),
        (189471, 10.045706, 56.428846, "Midtjydsk Fornikling og Forchromning A/S", "A 109", "Metal surface treatment"),
        (189811, 9.621375, 56.710066, "Nørager Mejeri A/S", "F 105", "Dairy processing"),
        (189955, 9.792911, 56.639374, "Takeda Pharma A/S", "D 202", "Pharmaceutical production"),
        (190422, 10.047445, 56.458472, "Verdo Produktion A/S", "G 101", "Large heat and power plant"),
        (190533, 9.840727, 56.716030, "ROCKWOOL A/S", "B 102", "Glass and mineral-wool production"),
        (191986, 9.414805, 56.473761, "Energi Viborg Kraftvarme A/S", "G 101", "Large heat and power plant"),
        (192123, 9.779614, 56.636574, "Arla Foods Amba Hobro Mejericenter", "F 105", "Dairy processing"),
    ]
    return [{
        "id": f"prtr-{company_id}", "name": name, "lon": lon, "lat": lat,
        "kind": "heat_plant" if code == "G 101" else "industry",
        "activity_code": code, "activity": activity, "source_year": 2019,
    } for company_id, lon, lat, name, code, activity in rows]


def main() -> None:
    areas = district_heating_areas()
    sites = prtr_sites()
    payload = {
        "model_version": "Cultural overlay v1 · generated from official Danish public data",
        "district_heating_areas": areas,
        "sites": sites,
        "summary": {
            "district_heating_areas": len(areas),
            "areas_with_2024_statistics": sum(a["heat_delivery_tj_2024"] is not None for a in areas),
            "industrial_candidates": sum(s["kind"] == "industry" for s in sites),
            "heat_plants": sum(s["kind"] == "heat_plant" for s in sites),
        },
        "sources": [
            {"name": "Plandata.dk adopted supply areas", "url": WFS_URL, "year": "current public WFS"},
            {"name": "Danish Energy Agency district-heating declaration", "year": 2024},
            {"name": "Danish EPA PRTR production units", "url": PRTR_URL, "year": 2019},
        ],
        "notes": "Heat delivery is a network-level market proxy, not a building-level BBR heat-demand model. PRTR sites are screening candidates and require project-specific demand validation.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
