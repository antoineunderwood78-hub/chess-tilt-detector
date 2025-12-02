    FROM python:3.10-slim

    # Install system dependencies for geopandas and other libraries if needed
    # libspatialindex-dev is often needed for rtree, which geopandas might use
    RUN apt-get update && apt-get install -y \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

    WORKDIR /app

    COPY requirements.txt .

    RUN pip install --no-cache-dir -r requirements.txt

    # Default command to keep container running
    CMD ["tail", "-f", "/dev/null"]
