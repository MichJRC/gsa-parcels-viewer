#!/usr/bin/env python3
"""
Script to inspect GPKG fields and count parcels in viewport
Run this in a new terminal while Flask app is running
"""

import geopandas as gpd

print("="*60)
print("STEP 1: Loading and Inspecting GPKG")
print("="*60)

# Load parcels
parcels = gpd.read_file('downloaded_data/parcels_with_HRL_codes.gpkg')

print(f"\n✓ Loaded {len(parcels)} parcels")
print(f"✓ CRS: {parcels.crs}")

# Show all column names
print("\n📋 Available columns in GPKG:")
print("-" * 60)
for i, col in enumerate(parcels.columns, 1):
    print(f"{i:2d}. {col}")

# Show first row as example
print("\n📊 Example of first parcel data:")
print("-" * 60)
first_row = parcels.iloc[0]
for col in parcels.columns:
    if col != 'geometry':  # Skip geometry as it's long
        print(f"{col}: {first_row[col]}")

# Show unique values for likely crop field
print("\n🌾 Looking for crop/culture fields:")
print("-" * 60)
crop_candidates = [col for col in parcels.columns 
                   if any(keyword in col.lower() 
                   for keyword in ['crop', 'coltur', 'culture', 'cod', 'class'])]

for col in crop_candidates:
    n_unique = parcels[col].nunique()
    print(f"\n{col}:")
    print(f"  - Unique values: {n_unique}")
    if n_unique < 20:  # Only show if reasonable number
        print(f"  - Values: {sorted(parcels[col].unique())[:10]}")

print("\n" + "="*60)
print("STEP 2: Counting Parcels in Your Viewport")
print("="*60)

# Your bbox values (FIXED SYNTAX - added comma!)
min_lon, min_lat = 11.668082343105075, 44.83770289320065
max_lon, max_lat = 11.755972968105075, 44.848413809087354

# Filter parcels within viewport
viewport_parcels = parcels.cx[min_lon:max_lon, min_lat:max_lat]

print(f"\n✓ Number of parcels in viewport: {len(viewport_parcels)}")
print(f"✓ Bounding box: {min_lon},{min_lat},{max_lon},{max_lat}")

# Try to show crop diversity (adjust field name based on inspection above)
# Common field names: CODICE_COLTURA, crop_code, culture, hrl_code
for possible_crop_field in ['CODICE_COLTURA', 'crop_code', 'culture', 
                             'COLTURA', 'hrl_code', 'hrl_name']:
    if possible_crop_field in viewport_parcels.columns:
        n_crop_types = viewport_parcels[possible_crop_field].nunique()
        print(f"✓ Crop types ({possible_crop_field}): {n_crop_types}")
        
        # Show crop distribution
        print(f"\n📊 Crop distribution in viewport:")
        crop_counts = viewport_parcels[possible_crop_field].value_counts()
        for crop, count in crop_counts.head(10).items():
            pct = (count / len(viewport_parcels)) * 100
            print(f"  {crop}: {count} parcels ({pct:.1f}%)")
        break

print("\n" + "="*60)
print("DONE! Use the field name shown above for your analysis")
print("="*60)