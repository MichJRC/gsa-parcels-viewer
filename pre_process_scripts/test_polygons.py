#!/usr/bin/env python3
"""
Quick viewer to check shapefile geometries on a map
"""
import geopandas as gpd
import folium
import warnings
warnings.filterwarnings('ignore')

print("Loading shapefile...")
gdf = gpd.read_file('downloaded_data/Appe_Azi_PCG_2021_FE/Appe_Azi_PCG_2021_FE.shp')

# Convert to WGS84 for web display
print("Converting to WGS84...")
gdf = gdf.to_crs('EPSG:4326')

# Take a small sample from the center
print("Sampling 100 parcels...")
sample = gdf.sample(n=5000, random_state=42)

# Get center point
center_lat = sample.geometry.centroid.y.mean()
center_lon = sample.geometry.centroid.x.mean()

print(f"Creating map centered at: {center_lat:.4f}, {center_lon:.4f}")

# Create map
m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

# Add polygons
for idx, row in sample.iterrows():
    folium.GeoJson(
        row['geometry'],
        style_function=lambda x: {
            'fillColor': '#3388ff',
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5
        }
    ).add_to(m)

# Save map
m.save('pre_process_scripts/parcel_viewer.html')
print("Map saved to: parcel_viewer.html")
print("Opening in browser...")