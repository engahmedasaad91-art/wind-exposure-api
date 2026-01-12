from fastapi import FastAPI, Query
import rasterio
import numpy as np
from pyproj import Transformer
from math import cos, sin, radians

# ============================================================
# CONFIG
# ============================================================

NLCD_PATH = r"C:\wind_exposure_local\nlcd\nlcd_2021_conus.tif"

# ASCE directional sectors (±45°)
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

FETCH_DISTANCE_M = 800      # conservative ASCE fetch
SAMPLE_STEP_M = 30          # NLCD resolution

# ============================================================
# NLCD → ASCE EXPOSURE MAP
# ============================================================

NLCD_TO_EXPOSURE = {
    11: "D",   # Open water
    12: "D",
    21: "B",   # Developed
    22: "B",
    23: "B",
    24: "B",
    31: "C",   # Barren
    41: "B",   # Forest
    42: "B",
    43: "B",
    52: "C",
    71: "C",
    72: "C",
    73: "C",
    74: "C",
    81: "C",   # Agriculture
    82: "C",
}

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Local ASCE 7 Wind Exposure Tool",
    version="1.0"
)

# ============================================================
# HELPERS
# ============================================================

def sample_nlcd(lat, lon, src, transformer):
    x, y = transformer.transform(lon, lat)
    row, col = src.index(x, y)
    return int(src.read(1)[row, col])

def direction_vector(angle_deg):
    return cos(radians(angle_deg)), sin(radians(angle_deg))

# ============================================================
# API
# ============================================================

@app.get("/exposure")
def exposure(
    lat: float = Query(...),
    lon: float = Query(...),
    height_ft: float = Query(...)
):
    with rasterio.open(NLCD_PATH) as src:
        transformer = Transformer.from_crs(
            "EPSG:4326", src.crs, always_xy=True
        )

        results = []
        governing = "B"

        for name, start_deg, end_deg in DIRECTIONS:
            exposures = []

            angles = (
                [start_deg] if start_deg == end_deg else
                list(range(start_deg, end_deg, 5))
            )

            for angle in angles:
                dx, dy = direction_vector(angle)

                for d in range(0, FETCH_DISTANCE_M, SAMPLE_STEP_M):
                    lat_s = lat + (dy * d / 111000)
                    lon_s = lon + (dx * d / (111000 * cos(radians(lat))))

                    try:
                        nlcd = sample_nlcd(lat_s, lon_s, src, transformer)
                        exp = NLCD_TO_EXPOSURE.get(nlcd, "C")
                        exposures.append(exp)
                    except Exception:
                        continue

            # majority rule
            final_exp = max(set(exposures), key=exposures.count) if exposures else "C"
            governing = max(governing, final_exp)

            results.append({
                "direction": name,
                "exposure": final_exp
            })

    return {
        "location": {"lat": lat, "lon": lon, "height_ft": height_ft},
        "governing_exposure": governing,
        "directions": results,
        "asce_reference": [
            "ASCE 7-16 Section 26.7.2",
            "ASCE 7-16 Section 26.7.3"
        ]
    }

# ============================================================
# LOCAL RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
