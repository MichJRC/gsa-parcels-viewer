#!/bin/bash

# Create data directory
mkdir -p downloaded_data

# Download shapefile from your release
echo "Downloading shapefile data (50 MB)..."
wget -q --show-progress -O downloaded_data/your-shapefile-data.zip \
  https://github.com/YOUR-USERNAME/YOUR-REPO-NAME/releases/download/v1.0.0/your-shapefile-data.zip

# Unzip the shapefile data
echo "Extracting shapefile data..."
cd downloaded_data && unzip -q your-shapefile-data.zip && cd ..

# Download the merged geodata
echo "Downloading merged geodata..."
wget -q --show-progress -O downloaded_data/merged_geodata.gpkg \
  https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/merged_geodata.gpkg

echo "✅ Data setup complete!"
