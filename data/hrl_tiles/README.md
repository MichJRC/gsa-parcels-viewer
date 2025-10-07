markdown# HRL Crop Type Tiles

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
This will download and extract the tiles to data/hrl_tiles/hrl_tiles_mosaic/.
How the tiles were generated:
1. Create color mapping file
The hrl_colors.txt file maps HRL classification codes to RGB colors.
2. Apply color relief to the GeoTIFF
bashgdaldem color-relief hrl_croptype_2021_mosaic_compress.tif hrl_colors.txt hrl_colored.tif -alpha
This converts the original GeoTIFF from numeric values to a colored RGB image with transparency.
3. Generate map tiles
bashgdal2tiles.py -z 10-14 --processes=4 hrl_colored.tif hrl_tiles_mosaic
This creates web map tiles at zoom levels 10-14 using 4 CPU cores.
Tile structure:
hrl_tiles_mosaic/
├── 10/
├── 11/
├── 12/
├── 13/
└── 14/
    └── [x]/
        └── [y].png
Each zoom level contains tiles organized by X/Y coordinates following the Web Mercator tile scheme.
HRL Classification Codes:
See hrl_colors.txt for the complete mapping. Examples:

1110: Common wheat (yellow)
1410: Maize (cyan)
2100: Rice (orange)
2310: Legumes (gray)

