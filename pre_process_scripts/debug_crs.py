import geopandas as gpd
import rasterio
from shapely.geometry import box
from rasterio.mask import mask
import numpy as np
from pyproj import Transformer

GPKG_PATH = '/workspaces/gsa-parcels-viewer/downloaded_data/parcels_with_HRL_codes.gpkg'
GEOTIFF_PATH = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_croptype_2021_mosaic_compress.tif'

print("="*70)
print("🔍 DEBUGGING CRS AND DATA ALIGNMENT")
print("="*70)

# 1. Check GeoPackage
print("\n📦 GEOPACKAGE INFO:")
gdf = gpd.read_file(GPKG_PATH)
print(f"Total parcels: {len(gdf):,}")
print(f"CRS: {gdf.crs}")
print(f"Bounds: {gdf.total_bounds}")

if gdf.crs.to_epsg() != 4326:
    print(f"⚠️  Converting to WGS84...")
    gdf_wgs84 = gdf.to_crs('EPSG:4326')
    print(f"WGS84 Bounds: {gdf_wgs84.total_bounds}")
else:
    gdf_wgs84 = gdf

# 2. Check GeoTIFF
print("\n🗺️  GEOTIFF INFO:")
with rasterio.open(GEOTIFF_PATH) as src:
    print(f"CRS: {src.crs}")
    print(f"Bounds: {src.bounds}")
    print(f"Size: {src.width}x{src.height}")

# 3. Test sample parcel
print("\n🧪 TESTING FIRST PARCEL:")
sample = gdf.iloc[0]
print(f"HRL Class: {sample.get('hrl_name', 'N/A')}")

with rasterio.open(GEOTIFF_PATH) as src:
    sample_gdf = gpd.GeoDataFrame([sample], geometry='geometry', crs=gdf.crs)
    if sample_gdf.crs != src.crs:
        print(f"Transforming {sample_gdf.crs} -> {src.crs}")
        sample_gdf = sample_gdf.to_crs(src.crs)
    
    geometry = [sample_gdf.iloc[0].geometry.__geo_interface__]
    
    try:
        out_image, _ = mask(src, geometry, crop=True, all_touched=False)
        pixels = out_image[0]
        pixels_valid = pixels[pixels != 0]
        
        print(f"Extracted pixels: {pixels.size}")
        print(f"Valid pixels: {len(pixels_valid)}")
        
        if len(pixels_valid) > 0:
            unique, counts = np.unique(pixels_valid, return_counts=True)
            print(f"Pixel classes: {dict(zip(unique, counts))}")
            print("✓ SUCCESS!")
        else:
            print("❌ NO VALID PIXELS!")
    except Exception as e:
        print(f"❌ ERROR: {e}")

print("="*70)
