from fastapi import FastAPI, Query, HTTPException
from typing import Optional, List
import math
import rasterio
from pyproj import Transformer
from pathlib import Path
import requests

# =========================================================
# App metadata
# =========================================================
app = FastAPI(
    title="Wind Exposure API (ASCE 7 – NLCD)",
    description="Direction-by-direction wind exposure classification using USGS NLCD",
    version="2.0.0"
)

# =========================================================
# Constants
# =========================================================

# NLCD 2021 CONUS (authoritative USGS / MRLC dataset)
NLCD_URL = (
    "https://prd-tnm.s3.amazonaws.com/StagedProducts/NLCD/"
    "data/land_cover/2021/nlcd_2021_land_cover_l48_20210604.img"
)

# Render allows /tmp for runtime cache
NLCD_CACHE = Path("/tmp/nlcd_2021.img")

# NLCD pixel size ≈ 30 m
PIXEL_SIZE_M = 30.0

# Wind directions (ASCE ±45° sectors)
DIRECTIONS = [
    ("N", 0),
    ("NE", 45),
    ("E", 90),
    ("SE", 135),
    ("S", 180),
    ("SW", 225),
    ("W", 270),
    ("NW", 315),
]

# =========================================================
# Health check (important for Render)
# =========================================================
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Wind Exposure API is running"}

# =========================================================
# NLCD utilities
# =========================================================
def load_nlcd():
    """
    Download NLCD once and cache locally.
    """
    if not NLCD_CACHE.exists():
        r = requests.get(NLCD_URL, stream=True, timeout=60)
        r.raise_for_status()
        with open(NLCD_CACHE, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return rasterio.open(NLCD_CACHE)


def nlcd_to_roughness(value: int) -> str:
    """
    Map NLCD land-cover class to ASCE surface roughness.
    Conservative mapping per ASCE intent.
    """
    if value == 11:  # Open water
        return "D"
    if value in (21, 22, 23, 24, 41, 42, 43):  # Developed / Forest
        return "B"
    return "C"  # Default open terrain


def sample_upwind_roughness(
    lat: float,
    lon: float,
    bearing_deg: float,
    fetch_ft: float
) -> List[str]:
    """
    Sample NLCD roughness values along upwind direction.
    """
    dataset = load_nlcd()

    transformer = Transformer.from_crs("EPSG:4326", dataset.crs, always_xy=True)
    x0, y0 = transformer.transform(lon, lat)

    fetch_m = fetch_ft * 0.3048
    steps = int(fetch_m / PIXEL_SIZE_M)

    roughness_values = []

    for i in range(1, steps + 1):
        dx = PIXEL_SIZE_M * i * math.sin(math.radians(bearing_deg))
        dy = PIXEL_SIZE_M * i * math.cos(math.radians(bearing_deg))

        try:
            row, col = dataset.index(x0 + dx, y0 + dy)
            val = int(dataset.read(1)[row, col])
            roughness_values.append(nlcd_to_roughness(val))
        except Exception:
            continue

    return roughness_values


def determine_exposure(roughness: List[str], height_ft: float) -> str:
    """
    Determine governing exposure per ASCE 7-16 §26.7.3
    """
    req_B = max(2600.0, 20.0 * height_ft)
    req_D = max(5000.0, 20.0 * height_ft)

    length_ft = len(roughness) * PIXEL_SIZE_M * 3.281

    if roughness.count("D") * PIXEL_SIZE_M * 3.281 >= req_D:
        return "D"
    if roughness.count("B") * PIXEL_SIZE_M * 3.281 >= req_B:
        return "B"
    return "C"

# =========================================================
# Exposure endpoint
# =========================================================
@app.get("/exposure")
def exposure(
    lat: Optional[float] = Query(None),
    latitude: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    longitude: Optional[float] = Query(None),
    height_ft: float = Query(..., gt=0),
):
    # Resolve coordinates
    latitude_val = lat if lat is not None else latitude
    longitude_val = lon if lon is not None else lng if lng is not None else longitude

    if latitude_val is None or longitude_val is None:
        raise HTTPException(
            status_code=400,
            detail="Provide latitude (lat/latitude) and longitude (lon/lng/longitude)"
        )

    if not (-90 <= latitude_val <= 90):
        raise HTTPException(status_code=400, detail="Latitude out of range")

    if not (-180 <= longitude_val <= 180):
        raise HTTPException(status_code=400, detail="Longitude out of range")

    results = []
    governing = "C"

    for name, bearing in DIRECTIONS:
        fetch_ft = max(20.0 * height_ft, 5000.0)
        roughness_vals = sample_upwind_roughness(
            latitude_val, longitude_val, bearing, fetch_ft
        )
        exposure_cat = determine_exposure(roughness_vals, height_ft)

        if exposure_cat == "D":
            governing = "D"
        elif exposure_cat == "B" and governing != "D":
            governing = "B"

        results.append({
            "direction": name,
            "bearing_deg": bearing,
            "exposure": exposure_cat,
            "sample_count": len(roughness_vals),
            "engineering_note": (
                "Computed from USGS NLCD land cover "
                "per ASCE 7-16 §§26.7.2–26.7.3"
            )
        })

    return {
        "location": {
            "latitude": latitude_val,
            "longitude": longitude_val,
            "building_height_ft": height_ft,
        },
        "governing_exposure": governing,
        "directions": results,
        "data_source": "USGS NLCD 2021 (MRLC)",
        "asce_reference": [
            "ASCE 7-16 Section 26.7.2 (Surface Roughness)",
            "ASCE 7-16 Section 26.7.3 (Exposure Categories)",
        ],
        "status": "success",
    }
