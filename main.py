from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import requests
import math

app = FastAPI(
    title="Wind Exposure API (ASCE 7)",
    description="Direction-by-direction wind exposure classification using NLCD",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# ASCE REFERENCES
# =========================
ASCE_REFS = [
    "ASCE 7-16 Section 26.7.2 (Surface Roughness)",
    "ASCE 7-16 Section 26.7.3 (Exposure Categories)"
]

# =========================
# NLCD → Exposure Mapping
# =========================
NLCD_EXPOSURE_MAP = {
    # Open water, barren, grassland → C
    11: "C",  # Open Water
    12: "C",  # Perennial Ice/Snow
    31: "C",  # Barren
    71: "C",  # Grassland
    72: "C",
    73: "C",
    74: "C",
    90: "C",  # Woody Wetlands
    95: "C",

    # Developed / Forest → B
    21: "B",  # Developed Open Space
    22: "B",
    23: "B",
    24: "B",
    41: "B",  # Forest
    42: "B",
    43: "B"
}

# =========================
# DIRECTION SECTORS (±45°)
# =========================
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

# =========================
# NLCD QUERY (WMS)
# =========================
def query_nlcd(lat: float, lon: float) -> int | None:
    """
    Queries NLCD WMS for a single pixel.
    IMPORTANT: WMS 1.3.0 with EPSG:4326 requires lon,lat axis order.
    """
    delta = 0.00005  # ~5 m

    lon_min = lon - delta
    lon_max = lon + delta
    lat_min = lat - delta
    lat_max = lat + delta

    url = "https://www.mrlc.gov/geoserver/mrlc_display/NLCD_2021_Land_Cover_L48/wms"

    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetFeatureInfo",
        "layers": "NLCD_2021_Land_Cover_L48",
        "query_layers": "NLCD_2021_Land_Cover_L48",
        "crs": "EPSG:4326",
        # 🚨 CORRECT AXIS ORDER (lon,lat)
        "bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "width": 3,
        "height": 3,
        "i": 1,
        "j": 1,
        "info_format": "application/json"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        features = data.get("features", [])
        if not features:
            return None
        return int(features[0]["properties"]["NLCD_Land_Cover"])
    except Exception:
        return None

# =========================
# EXPOSURE ENDPOINT
# =========================
@app.get("/exposure")
def exposure(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    height_ft: float = Query(..., description="Building height in feet")
):
    directions_out = []
    exposures_found = []

    nlcd_code = query_nlcd(lat, lon)

    exposure_class = NLCD_EXPOSURE_MAP.get(nlcd_code, "C") if nlcd_code else "C"

    for d in DIRECTIONS:
        directions_out.append({
            "direction": d[0],
            "sector_degrees": f"{d[1]}–{d[2]}",
            "nlcd_code": nlcd_code,
            "surface_roughness": exposure_class,
            "exposure": exposure_class,
            "engineering_note": (
                "Derived from NLCD land cover"
                if nlcd_code else
                "NLCD unavailable → conservative Exposure C applied"
            )
        })
        exposures_found.append(exposure_class)

    governing = "C"
    if "D" in exposures_found:
        governing = "D"
    elif "C" in exposures_found:
        governing = "C"
    else:
        governing = "B"

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "building_height_ft": height_ft
        },
        "asce_reference": ASCE_REFS,
        "governing_exposure": governing,
        "directions": directions_out,
        "status": "success"
    }
