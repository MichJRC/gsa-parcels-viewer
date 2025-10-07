cat > data/hrl_tiles/README.md << 'EOF'
# HRL Crop Type Tiles

This folder contains HRL (High Resolution Layer) crop classification data for 2021.

## Files tracked in Git:
- `hrl_colors.txt` - Color mapping for HRL classification codes
- `README.md` - This file

## Files NOT tracked (auto-downloaded):
- `hrl_tiles_mosaic/` - Pre-generated map tiles (~500MB-1GB)
- `hrl_tiles_mosaic.tar.gz` - Compressed tiles archive
- `hrl_colored.tif` - Intermediate colored GeoTIFF
- `temp.vrt` - Temporary GDAL virtual raster

## Setup:
To download pre-generated tiles, run:
```bash
./setup.sh
