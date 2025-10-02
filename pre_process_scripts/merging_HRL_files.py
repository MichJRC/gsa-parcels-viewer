import rasterio
from rasterio.merge import merge
import glob

# Get all your TIF files
tif_files = glob.glob('data/hrl_tiles/*.tif')

# Open all tiles
src_files_to_mosaic = []
for fp in tif_files:
    src = rasterio.open(fp)
    src_files_to_mosaic.append(src)

# Merge tiles
mosaic, out_trans = merge(src_files_to_mosaic)

# Save mosaic
out_meta = src.meta.copy()
out_meta.update({
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_trans
})

with rasterio.open('downloaded_data/hrl_croptype_2021_mosaic.tif', 'w', **out_meta) as dest:
    dest.write(mosaic)

# Close files
for src in src_files_to_mosaic:
    src.close()