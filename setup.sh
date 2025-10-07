#!/bin/bash
set -e  # Exit on any error

echo "Setting up GSA Parcels Viewer data..."

# Create data directories
mkdir -p downloaded_data
mkdir -p data/hrl_tiles

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
echo "Downloading HRL tiles..."
wget -q --show-progress -O data/hrl_tiles/hrl_tiles_mosaic.tar.gz \
  https://github.com/MichJRC/gsa-parcels-viewer/releases/download/v1.0.0/hrl_tiles_mosaic.tar.gz

# Extract the tiles using tar
echo "Extracting HRL tiles..."
cd data/hrl_tiles
tar -xzf hrl_tiles_mosaic.tar.gz

# Fix nested folder structure if present
# The tar might extract to data/hrl_tiles/hrl_tiles_mosaic or just hrl_tiles_mosaic
if [ -d "data/hrl_tiles/hrl_tiles_mosaic" ]; then
    echo "Fixing nested folder structure..."
    mv data/hrl_tiles/hrl_tiles_mosaic ./
    rm -rf data
elif [ ! -d "hrl_tiles_mosaic" ]; then
    echo "⚠️  Warning: Unexpected tile structure after extraction"
    ls -la
fi

cd ../..

# Verify all files were downloaded
echo ""
echo "Verifying downloads..."
FILES=(
    "downloaded_data/Appe_Azi_PCG_2021_FE.zip"
    "downloaded_data/parcels_cleaned.gpkg"
    "downloaded_data/parcels_with_HRL_codes.gpkg"
    "data/hrl_tiles/hrl_tiles_mosaic.tar.gz"
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

# Check if tiles were extracted
if [ -d "data/hrl_tiles/hrl_tiles_mosaic" ]; then
    TILE_COUNT=$(find data/hrl_tiles/hrl_tiles_mosaic -name "*.png" 2>/dev/null | wc -l)
    if [ "$TILE_COUNT" -gt 0 ]; then
        echo "✓ HRL tiles extracted ($TILE_COUNT tiles)"
    else
        echo "⚠️  HRL tiles folder exists but no PNG files found"
        echo "   Checking folder structure:"
        ls -la data/hrl_tiles/hrl_tiles_mosaic/ | head -10
        ALL_PRESENT=false
    fi
else
    echo "✗ HRL tiles not extracted properly"
    echo "   Expected: data/hrl_tiles/hrl_tiles_mosaic/"
    echo "   Found in data/hrl_tiles/:"
    ls -la data/hrl_tiles/
    ALL_PRESENT=false
fi

echo ""
if [ "$ALL_PRESENT" = true ]; then
    echo "✅ Data setup complete!"
    echo ""
    echo "Available datasets:"
    echo "  1. Appe_Azi_PCG_2021_FE/ - Original shapefile"
    echo "  2. parcels_cleaned.gpkg - Cleaned parcels"
    echo "  3. parcels_with_HRL_codes.gpkg - HRL-classified parcels (ready to use)"
    echo "  4. hrl_tiles_mosaic/ - HRL raster tiles (ready to use)"
    echo ""
    echo "You can now run: python3 pre_process_scripts/app.py"
else
    echo "❌ Setup incomplete - some files are missing"
    exit 1
fi