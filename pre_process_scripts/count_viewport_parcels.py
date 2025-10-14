#!/usr/bin/env python3
"""
Simple script: Count parcels in viewport and show hrl_name distribution
FIXED: Handles CRS conversion from WGS84 bbox to EPSG:3003
"""

import geopandas as gpd

# Load parcels
print("Loading parcels...")
parcels = gpd.read_file('downloaded_data/parcels_with_HRL_codes.gpkg')
print(f"Original CRS: {parcels.crs}")
print(f"Total parcels: {len(parcels):,}")

# Convert parcels to WGS84 (same as your web map)
print("\nConverting to WGS84...")
parcels_wgs84 = parcels.to_crs(epsg=4326)

# Your viewport bbox from web app (in WGS84 degrees)
min_lon, min_lat = 11.668082343105075, 44.83770289320065
max_lon, max_lat = 11.755972968105075, 44.848413809087354

# Filter parcels in viewport
viewport_parcels = parcels_wgs84.cx[min_lon:max_lon, min_lat:max_lat]

# Print results
print(f"\n{'='*60}")
print(f"Parcels in viewport: {len(viewport_parcels):,}")
print(f"Bounding box: {min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}")
print(f"{'='*60}")

if len(viewport_parcels) > 0:
    # Show hrl_name distribution
    print(f"\nDistribution by hrl_name (farmer-declared crops):")
    print(f"{'-'*60}")
    for crop, count in viewport_parcels['hrl_name'].value_counts().items():
        pct = (count / len(viewport_parcels)) * 100
        print(f"{crop:<30} {count:5,} parcels ({pct:5.1f}%)")
    
    print(f"\nTotal crop types: {viewport_parcels['hrl_name'].nunique()}")
    
    # Calculate area
    total_area = viewport_parcels['SUP_APPEZ'].sum()
    print(f"Total agricultural area: {total_area:.1f} hectares")
else:
    print("\n⚠️  No parcels found in this viewport!")
    print("Check your bounding box coordinates.")