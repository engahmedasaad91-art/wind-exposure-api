from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import math
import requests

app = FastAPI(
    title="Wind Exposure API (ASCE 7)",
    description="Automatic wind exposure classification using NLCD land cover",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# ASCE REFERENCES
# ===============================
ASCE_REFS = [
    "ASCE 7-16 Section 26.7.2 (Surface Roughness)",
    "ASCE 7-16 Section 26.7.3 (Exposure Categories)"
]

# ===============================
# NLCD → Roughness Mapping
# ===============================
NLCD_TO_ROUGHNESS = {
    11: "C",  # Open Water
    12: "C",  # Perennial Ice/Snow
    21: "B",  # Developed, Open Space
    22: "B",  # Developed, Low Intensity
    23: "B",  # Developed, Medium Intensity
    24: "B",  # Developed, High Intensity
    31: "C",  # Barren Land
    41: "B",  # Deciduous Forest
    42: "B",  # Evergreen Forest
    43: "B",  # Mixed Forest
    52: "C",  # Shrub/Scrub
    71: "C",  # Grassland
    81: "C",  # Pasture/Hay
    82: "C",  # Cultivated Crops
    90: "B",  # Woody Wetlands
    95: "C",  # Emergent Herbaceous Wetlands
}

# ===============================
# NLCD WMS SERVICE
# ===============================
NLCD_WMS_URL = "https://www.mrlc.gov/geoserver/mrlc_display/NLCD_2021_Land_Cover_L48/wms"

def query_nlcd(lat: float, lon: float) -> int | None:
    """
    Query NLCD land cover at a single point via WMS GetFeatureInfo.
    """
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetFeatureInfo",
        "layers": "NLCD_2021_Land_Cover_L48",
        "query_layers": "NLCD_2021_Land_Cover_L48",
        "crs": "EPSG:4326",
        "bbox": f"{lat-0.0001},{lon-0.0001},{lat+0.0001},{lon+0.0001}",
        "width": 101,
        "height": 101,
        "i": 50,
        "j": 50,
        "info_format": "application/json"
    }

    try:
        r = requests.get(NLCD_WMS_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        if not features:
            return None
        return features[0]["properties"].get("NLCD_Land")
    except Exception:
        return None

# ===============================
# EXPOSURE LOGIC
# ===============================
def exposure_from_roughness(z0: str) -> str:
    if z0 == "B":
        return "B"
    return "C"

# ===============================
# API ENDPOINT
# ===============================
@app.get("/exposure")
def get_exposure(
    lat: float = Query(...),
    lon: float = Query(...),
    height_ft: float = Query(...)
):
    directions = [
        ("N", "315–45°"),
        ("NE", "0–90°"),
        ("E", "45–135°"),
        ("SE", "90–180°"),
        ("S", "135–225°"),
        ("SW", "180–270°"),
        ("W", "225–315°"),
        ("NW", "270–360°"),
    ]

    direction_results = []

    for d, sector in directions:
        nlcd = query_nlcd(lat, lon)
        roughness = NLCD_TO_ROUGHNESS.get(nlcd, "C")
        exposure = exposure_from_roughness(roughness)

        direction_results.append({
            "direction": d,
            "sector_degrees": sector,
            "nlcd_code": nlcd,
            "surface_roughness": roughness,
            "exposure": exposure,
            "engineering_note": (
                "Derived from NLCD land cover per ASCE 7-16 §26.7"
                if nlcd is not None else
                "NLCD unavailable → conservative Exposure C applied"
            )
        })

    governing = "C"
    if all(d["exposure"] == "B" for d in direction_results):
        governing = "B"

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "building_height_ft": height_ft
        },
        "asce_reference": ASCE_REFS,
        "governing_exposure": governing,
        "directions": direction_results,
        "status": "success"
    }
