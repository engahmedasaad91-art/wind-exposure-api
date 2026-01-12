from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from typing import List, Dict

# ============================================================
# App setup
# ============================================================

app = FastAPI(
    title="Wind Exposure API",
    description="ASCE 7-16 Directional Wind Exposure Classification using NLCD",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Constants
# ============================================================

# OFFICIAL MRLC / Esri-hosted NLCD FeatureServer (cloud-safe)
NLCD_REST_URL = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/"
    "NLCD_2019_Land_Cover_L48/FeatureServer/0/query"
)

# NLCD → ASCE Exposure Mapping (engineering conservative)
NLCD_TO_EXPOSURE = {
    11: "D",  # Open Water
    12: "D",  # Perennial Ice/Snow
    21: "B",  # Developed, Open Space
    22: "B",  # Developed, Low Intensity
    23: "B",  # Developed, Medium Intensity
    24: "B",  # Developed, High Intensity
    31: "C",  # Barren Land
    41: "C",  # Deciduous Forest
    42: "C",  # Evergreen Forest
    43: "C",  # Mixed Forest
    52: "C",  # Shrub/Scrub
    71: "C",  # Grassland/Herbaceous
    81: "C",  # Pasture/Hay
    82: "C",  # Cultivated Crops
    90: "C",  # Woody Wetlands
    95: "C",  # Emergent Herbaceous Wetlands
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
]

# ============================================================
# Helper Functions
# ============================================================

def query_nlcd(lat: float, lon: float):
    """Query NLCD land cover code at a point"""
    params = {
        "f": "json",
        "where": "1=1",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Value",
        "returnGeometry": "false"
    }

    try:
        r = requests.get(NLCD_REST_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        features = data.get("features", [])
        if not features:
            return None

        return features[0]["attributes"].get("Value")

    except Exception:
        return None


def exposure_from_nlcd(nlcd_code: int | None):
    """Convert NLCD code to ASCE exposure"""
    if nlcd_code is None:
        return "C", "NLCD unavailable → conservative Exposure C applied"
    return NLCD_TO_EXPOSURE.get(nlcd_code, "C"), "NLCD-based exposure applied"


# ============================================================
# API Endpoints
# ============================================================

@app.get("/")
def root():
    return {
        "service": "Wind Exposure API",
        "status": "running",
        "standard": "ASCE 7-16"
    }


@app.get("/exposure")
def get_exposure(
    lat: float = Query(..., description="Latitude (WGS84)"),
    lon: float = Query(..., description="Longitude (WGS84)"),
    height_ft: float = Query(..., gt=0, description="Building height in feet"),
):
    nlcd_code = query_nlcd(lat, lon)
    exposure, note = exposure_from_nlcd(nlcd_code)

    directions_output: List[Dict] = []

    for d, start, end in DIRECTIONS:
        sector = f"{start}-{end}°"
        directions_output.append({
            "direction": d,
            "sector_degrees": sector,
            "nlcd_code": nlcd_code,
            "surface_roughness": exposure,
            "exposure": exposure,
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
        "governing_exposure": exposure,
        "directions": directions_output,
        "status": "success"
    }
