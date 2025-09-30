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
sample = gdf.sample(n=2000, random_state=42)

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

############### checking the small parcels to see if there are legitimate or artefacts ##

import geopandas as gpd
import warnings
warnings.filterwarnings('ignore')

# Load shapefile
gdf = gpd.read_file('downloaded_data/Appe_Azi_PCG_2021_FE/Appe_Azi_PCG_2021_FE.shp')

# Calculate area for each parcel
gdf['area_m2'] = gdf.geometry.area

# Check for suspiciously small or thin parcels
print("Area statistics:")
print(gdf['area_m2'].describe())

print("\nSmallest 10 parcels (m²):")
print(gdf.nsmallest(10, 'area_m2')[['area_m2', 'DESC_COLT', 'COD_SUOLO']])

# Check for very thin polygons (low area-to-perimeter ratio)
gdf['perimeter_m'] = gdf.geometry.length
gdf['shape_index'] = gdf['perimeter_m'] / (2 * (3.14159 * gdf['area_m2']) ** 0.5)

print("\nMost elongated parcels (high shape index = thin/irregular):")
print(gdf.nlargest(10, 'shape_index')[['area_m2', 'shape_index', 'DESC_COLT']])

##### making some different shapes to visualise the difference between circonference and perimeter

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

fig, axes = plt.subplots(2, 2, figsize=(12, 10))

def draw_shape_comparison(ax, shape_type):
    if shape_type == 'circle':
        # Circle with area = 100
        radius = np.sqrt(100/np.pi)
        circle = patches.Circle((5, 5), radius, fill=False, edgecolor='blue', linewidth=3)
        ax.add_patch(circle)
        area = 100
        perimeter = 2 * np.pi * radius
        
    elif shape_type == 'square':
        # Square with area = 100
        side = 10
        square = patches.Rectangle((0, 0), side, side, fill=False, edgecolor='green', linewidth=3)
        ax.add_patch(square)
        area = 100
        perimeter = 4 * side
        
    elif shape_type == 'rectangle':
        # Elongated rectangle with area = 100
        width = 25
        height = 4
        rect = patches.Rectangle((0, 3), width, height, fill=False, edgecolor='orange', linewidth=3)
        ax.add_patch(rect)
        area = 100
        perimeter = 2 * (width + height)
        
    elif shape_type == 'sliver':
        # Very thin sliver with area = 1.5 (like your artifacts)
        width = 30
        height = 0.05
        sliver = patches.Rectangle((0, 5), width, height, fill=False, edgecolor='red', linewidth=3)
        ax.add_patch(sliver)
        area = 1.5
        perimeter = 2 * (width + height)
    
    # Calculate shape index
    shape_index = perimeter / (2 * np.sqrt(np.pi * area))
    
    # Draw the equivalent circle (dotted)
    equiv_radius = np.sqrt(area/np.pi)
    equiv_circle = patches.Circle((15, 5) if shape_type != 'sliver' else (15, 5), 
                                  equiv_radius, fill=False, 
                                  edgecolor='gray', linewidth=2, linestyle='--', alpha=0.5)
    ax.add_patch(equiv_circle)
    
    ax.set_xlim(-2, 32)
    ax.set_ylim(-2, 12)
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    
    title = f'{shape_type.upper()}\n'
    title += f'Area = {area:.1f} m²\n'
    title += f'Perimeter = {perimeter:.1f} m\n'
    title += f'Shape Index = {shape_index:.2f}\n'
    title += f'(Gray dotted = equivalent circle)'
    ax.set_title(title, fontsize=11, fontweight='bold')

draw_shape_comparison(axes[0,0], 'circle')
draw_shape_comparison(axes[0,1], 'square')
draw_shape_comparison(axes[1,0], 'rectangle')
draw_shape_comparison(axes[1,1], 'sliver')

plt.suptitle('Shape Index Comparison: How "stretched out" is the polygon?\n' +
             'Lower index = more compact (circular)\n' +
             'Higher index = more elongated/irregular', 
             fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('pre_process_scripts/shape_index_visual.png', dpi=150, bbox_inches='tight')
print("✅ Visualization saved to: shape_index_visual.png")
print("\nKey insight:")
print("- Circle (index ~1.0): Most compact shape possible")
print("- Square (index ~1.13): Slightly less compact")
print("- Rectangle (index ~2.3): Elongated but reasonable")
print("- Sliver (index 200+): Degenerate geometry - likely an error")

### check if id_appez and codice azienda are unique meaning that the real identifier is the combination of the twos##
import geopandas as gpd
gdf = gpd.read_file("downloaded_data/Appe_Azi_PCG_2021_FE/Appe_Azi_PCG_2021_FE.shp")

# Check if ID_APPEZ is unique within each farm
print("Checking ID_APPEZ uniqueness:")
print(f"Total records: {len(gdf):,}")
print(f"Unique ID_APPEZ: {gdf['ID_APPEZ'].nunique():,}")
print(f"Unique COD_AZI (farms): {gdf['COD_AZI'].nunique():,}")

# Check if ID_APPEZ is unique within each farm
grouped = gdf.groupby('COD_AZI')['ID_APPEZ'].apply(lambda x: x.duplicated().sum())
farms_with_dupes = (grouped > 0).sum()
print(f"\nFarms with duplicate ID_APPEZ: {farms_with_dupes}")

# there are no duplicates of ID_APPEZ within the farm

# Lets see how many polygons per ID_APPEZ and farm_ID with the same type of crop we would dissolve to clean the dataset
import geopandas as gpd

gdf = gpd.read_file("downloaded_data/Appe_Azi_PCG_2021_FE/Appe_Azi_PCG_2021_FE.shp")

print("=" * 70)
print("ANALYZING POTENTIAL MERGES")
print("=" * 70)

# Count polygons per unique combination of COD_AZI + ID_APPEZ + COD_SUOLO
counts = gdf.groupby(['COD_AZI', 'ID_APPEZ', 'COD_SUOLO']).size()

print("\nPolygons per unique (Farm + Parcel + Soil) combination:")
print(counts.describe())

multi_poly_count = (counts > 1).sum()
total_could_merge = (counts - 1).sum()

print(f"\nCombinations with multiple polygons: {multi_poly_count:,}")
print(f"Total polygons that could be merged: {total_could_merge:,}")
print(f"Potential reduction: {(total_could_merge / len(gdf) * 100):.2f}%")

# Show some examples
if multi_poly_count > 0:
    multi_poly = counts[counts > 1].head(10)
    print("\nExamples of combinations with multiple polygons:")
    print("(These will be merged during dissolve)")
    for (cod_azi, id_appez, cod_suolo), count in multi_poly.items():
        # Get the actual records to show more info
        sample = gdf[(gdf['COD_AZI'] == cod_azi) & 
                     (gdf['ID_APPEZ'] == id_appez) & 
                     (gdf['COD_SUOLO'] == cod_suolo)].iloc[0]
        print(f"\n  Farm: {cod_azi[:10]}... | Parcel: {id_appez} | Soil: {cod_suolo}")
        print(f"  Crop: {sample['DESC_COLT']}")
        print(f"  → {count} polygons will be merged into 1")
else:
    print("\nNo combinations found with multiple polygons!")
    print("The dissolve operation will not reduce the polygon count.")

print("\n" + "=" * 70)