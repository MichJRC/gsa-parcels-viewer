#!/bin/bash

set -e  # Exit on any error

echo "Setting up GSA Parcels Viewer data..."

# Create data directory
mkdir -p downloaded_data

# Download original shapefile from release
echo "Downloading original shapefile data (50 MB)..."
wget -q --show-progress -O downloaded_data/Appe_Azi_PCG_2021_FE.zip \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/Appe_Azi_PCG_2021_FE.zip

# Unzip the shapefile data
echo "Extracting shapefile data..."
cd downloaded_data && unzip -q -o Appe_Azi_PCG_2021_FE.zip && cd ..

# Download cleaned parcels (intermediate step)
echo "Downloading cleaned agricultural parcels data..."
wget -q --show-progress -O downloaded_data/parcels_cleaned.gpkg \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/parcels_cleaned.gpkg

# Download HRL-classified parcels (final product)
echo "Downloading HRL-classified parcels data..."
wget -q --show-progress -O downloaded_data/parcels_with_HRL_codes.gpkg \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/parcels_with_HRL_codes.gpkg

# Download HRL tiles
echo "Downloading HRL-tiles"
wget -q --show-progress -O downloaded_data/hrl_tiles_mosaic.tar.gz \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/hrl_tiles_mosaic.tar.gz

# Unzip the tiles
echo "Extracting the tiles..."
cd downloaded_data && unzip -q -o hrl_tiles_mosaic.tar.gz && cd ..

# Verify all files were downloaded
echo ""
echo "Verifying downloads..."
FILES=(
    "downloaded_data/Appe_Azi_PCG_2021_FE.zip"
    "downloaded_data/parcels_cleaned.gpkg"
    "downloaded_data/parcels_with_HRL_codes.gpkg"
    "downloaded_data/hrl_tiles_mosaic.tar.gz"
)

ALL_PRESENT=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        SIZE=$(du -h "$file" | cut -f1)
        echo "✓ $file ($SIZE)"
    else
        echo "✗ Missing: $file"
        ALL_PRESENT=false
    fi
done

echo ""
if [ "$ALL_PRESENT" = true ]; then
    echo "✅ Data setup complete!"
    echo ""
    echo "Available datasets:"
    echo "  1. Appe_Azi_PCG_2021_FE/ - Original shapefile"
    echo "  2. parcels_cleaned.gpkg - Cleaned parcels"
    echo "  3. parcels_with_HRL_codes.gpkg - HRL-classified parcels (ready to use)"
    echo "  4. hrl_tiles_mosaic.tar.gz - hrl_tiles_mosaic (ready to use)"
else
    echo "❌ Setup incomplete - some files are missing"
    exit 1
fi
