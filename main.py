from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Wind Exposure API (ASCE 7)",
    description="Direction-by-direction wind exposure classification",
    version="1.0.0",
)

# Allow browser + frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "Wind Exposure API is running"}

@app.get("/exposure")
def exposure(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    height_ft: float = Query(..., gt=0, description="Building height in feet"),
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

    results = []
    for d, sector in directions:
        results.append({
            "direction": d,
            "sector_degrees": sector,
            "dominant_land_cover": "Placeholder",
            "surface_roughness": "C",
            "exposure": "C",
            "engineering_note": "Defaulted to Exposure C (no land-cover applied yet)"
        })

    return {
        "location": {
            "latitude": lat,
            "longitude": lon,
            "building_height_ft": height_ft
        },
        "asce_reference": [
            "ASCE 7-16 Section 26.7.2",
            "ASCE 7-16 Section 26.7.3"
        ],
        "governing_exposure": "C",
        "directions": results,
        "status": "success"
    }
