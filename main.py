from fastapi import FastAPI
import rasterio
import numpy as np
import math
from pyproj import Transformer

app = FastAPI(title="Wind Exposure API")

NLCD_PATH = "https://s3-us-west-2.amazonaws.com/mrlc/nlcd_2021_land_cover_l48_20210604.tif"
transformer = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

def roughness_from_nlcd(code):
    if code in [21,22,23,24,41,42,43,90]:
        return "B"
    if code == 11:
        return "D"
    return "C"

def destination_point(x, y, bearing_deg, dist_m):
    a = math.radians(bearing_deg)
    return x + dist_m * math.sin(a), y + dist_m * math.cos(a)

@app.get("/exposure")
def exposure(lat: float, lon: float, height_ft: float):
    directions = [
        ("N",0),("NE",45),("E",90),("SE",135),
        ("S",180),("SW",225),("W",270),("NW",315)
    ]

    x0, y0 = transformer.transform(lon, lat)
    output = []

    with rasterio.open(NLCD_PATH) as src:
        for name, bearing in directions:
            samples = []
            for d in [300,600,1200,2500]:
                xs, ys = destination_point(x0, y0, bearing, d)
                row, col = src.index(xs, ys)
                samples.append(src.read(1)[row, col])

            dominant = int(np.bincount(samples).argmax())
            rough = roughness_from_nlcd(dominant)

            exposure = "C"
            if rough == "B":
                exposure = "B"
            if rough == "D":
                exposure = "D"

            output.append({
                "direction": name,
                "roughness": rough,
                "exposure": exposure
            })

    return {"results": output}
