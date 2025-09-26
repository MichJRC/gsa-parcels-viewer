#!/bin/bash

# Create data directory
mkdir -p downloaded_data

# Download shapefile from your release
echo "Downloading shapefile data (50 MB)..."
wget -q --show-progress -O downloaded_data/Appe_Azi_PCG_2021_FE.zip \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/Appe_Azi_PCG_2021_FE.zip

# Unzip the shapefile data
echo "Extracting shapefile data..."
cd downloaded_data && unzip -q Appe_Azi_PCG_2021_FE.zip && cd ..

echo "✅ Data setup complete!"
