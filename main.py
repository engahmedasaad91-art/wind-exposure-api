from fastapi import FastAPI, Query
import requests
import math

app = FastAPI(
    title="Wind Exposure API (ASCE 7)",
    description="Direction-by-direction wind exposure classification using ASCE 7 with NLCD REST fallback",
    version="1.0.0"
)

# ==============================
# Constants
# ==============================

NLCD_REST_URL = (
    "https://landfire.cr.usgs.gov/arcgis/rest/services/NLCD/"
    "Land_Cover_L48/MapServer/0/query"
)

HEADERS = {
    "User-Agent": "wind-exposure-api/1.0"
}

# ASCE 7 roughness mapping (simplified, conservative)
NLCD_TO_EXPOSURE = {
    # Developed
    21: "B", 22: "B", 23: "B", 24: "B",
    # Forest / Shrub
    41: "B", 42: "B", 43: "B",
    # Grass / Crops
    71: "C", 81: "C", 82: "C",
    # Wetlands / Open
    90: "C", 95: "C",
    # Water
    11: "D"
}

DIRECTIONS = [
    ("N", 315, 360),
    ("N", 0, 45),
    ("NE", 45, 90),
    ("E", 90, 135),
    ("SE", 135, 180),
    ("S", 180, 225),
    ("SW", 225, 270),
    ("W", 270, 315),
    ("NW", 315, 360),
]

# ==============================
# Helper functions
# ==============================

def query_nlcd_rest(lat: float, lon: float):
    """
    Uses NLCD REST Identify (robust, cloud-safe)
    """
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Value",
        "returnGeometry": "false"
    }

    try:
        r = requests.get(NLCD_REST_URL, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()

        features = data.get("features", [])
        if not features:
            return None

        return features[0]["attributes"].get("Value")

    except Exception:
        return None


def classify_exposure(nlcd_code):
    if nlcd_code is None:
        return "C", "NLCD unavailable → conservative Exposure C applied"

    exposure = NLCD_TO_EXPOSURE.get(nlcd_code, "C")
    return exposure, f"NLCD code {nlcd_code} → Exposure {exposure}"


# ==============================
# API Endpoint
# ==============================

@app.get("/exposure")
def exposure(
    lat: float = Query(...),
    lon: float = Query(...),
    height_ft: float = Query(...)
):
    directions_output = []
    governing = "B"

    for d in DIRECTIONS:
        name, start, end = d
        nlcd_code = query_nlcd_rest(lat, lon)
        exposure_class, note = classify_exposure(nlcd_code)

        if exposure_class == "D":
            governing = "D"
        elif exposure_class == "C" and governing != "D":
            governing = "C"

        directions_output.append({
            "direction": name,
            "sector_degrees": f"{start}–{end}",
            "nlcd_code": nlcd_code,
            "surface_roughness": exposure_class,
            "exposure": exposure_class,
            "engineering_note": note
        })

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "building_height_ft": height_ft
        },
        "asce_reference": [
            "ASCE 7-16 Section 26.7.2 (Surface Roughness)",
            "ASCE 7-16 Section 26.7.3 (Exposure Categories)"
        ],
        "governing_exposure": governing,
        "directions": directions_output,
        "status": "success"
    }
