FROM python:3.11-slim

# Install GDAL
RUN apt-get update && \
    apt-get install -y gdal-bin libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

# Set GDAL env vars
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
