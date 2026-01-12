from fastapi import FastAPI, Query, HTTPException
from typing import Optional
import math

app = FastAPI(
    title="Wind Exposure API (ASCE 7)",
    description="Direction-by-direction exposure classification per ASCE 7",
    version="1.0.0"
)

# ---------------------------------------------------------
# Utility: wind directions (±45° sectors)
# ---------------------------------------------------------
DIRECTIONS = [
    ("N", 315, 45),
    ("NE", 0, 90),
    ("E", 45, 135),
    ("SE", 90, 180),
    ("S", 135, 225),
    ("SW", 180, 270),
    ("W", 225, 315),
    ("NW", 270, 360),
]


# ---------------------------------------------------------
# Health check (important for Render)
# ---------------------------------------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Wind Exposure API is running"}


# ---------------------------------------------------------
# Main exposure endpoint
# ---------------------------------------------------------
@app.get("/exposure")
def exposure(
    lat: Optional[float] = Query(None, description="Latitude (decimal degrees)"),
    latitude: Optional[float] = Query(None, description="Latitude (alternate name)"),
    lon: Optional[float] = Query(None, description="Longitude (decimal degrees)"),
    lng: Optional[float] = Query(None, description="Longitude (alternate name)"),
    longitude: Optional[float] = Query(None, description="Longitude (alternate name)"),
    height_ft: float = Query(..., gt=0, description="Building height in feet"),
):
    """
    Returns direction-by-direction exposure classification.
    Land-cover logic is currently a placeholder and can be upgraded
    to NLCD / ESA without changing the API.
    """

    # -----------------------------
    # Resolve latitude / longitude
    # -----------------------------
    latitude_val = lat if lat is not None else latitude
    longitude_val = lon if lon is not None else lng if lng is not None else longitude

    if latitude_val is None or longitude_val is None:
        raise HTTPException(
            status_code=400,
            detail="Provide latitude (lat or latitude) and longitude (lon, lng, or longitude)",
        )

    # -----------------------------
    # Basic sanity checks
    # -----------------------------
    if not (-90 <= latitude_val <= 90):
        raise HTTPException(status_code=400, detail="Latitude out of range")

    if not (-180 <= longitude_val <= 180):
        raise HTTPException(status_code=400, detail="Longitude out of range")

    # ---------------------------------------------------------
    # PLACEHOLDER exposure logic (engineering-safe default)
    # ---------------------------------------------------------
    # NOTE:
    # This is intentionally conservative and transparent.
    # Replace this block later with NLCD / ESA land-cover logic.
    # ---------------------------------------------------------

    results = []

    for name, start_deg, end_deg in DIRECTIONS:
        results.append({
            "direction": name,
            "sector_degrees": f"{start_deg}°–{end_deg}°",
            "dominant_land_cover": "Unknown (placeholder)",
            "surface_roughness": "C",
            "exposure": "C",
            "engineering_note": (
                "Defaulted to Exposure C pending land-cover fetch. "
                "Upgrade with NLCD / ESA for site-specific classification."
            )
        })

    return {
        "location": {
            "latitude": latitude_val,
            "longitude": longitude_val,
            "building_height_ft": height_ft,
        },
        "asce_reference": [
            "ASCE 7-16 Section 26.7.2 (Surface Roughness)",
            "ASCE 7-16 Section 26.7.3 (Exposure Categories)",
        ],
        "governing_exposure": "C",
        "directions": results,
        "status": "success",
    }
