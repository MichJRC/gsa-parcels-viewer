#!/usr/bin/env python3
"""
Simple script: Count parcels in viewport and show hrl_name distribution
"""

import geopandas as gpd

# Load parcels
parcels = gpd.read_file('downloaded_data/parcels_with_HRL_codes.gpkg')

# Your viewport bbox
min_lon, min_lat = 11.668082343105075, 44.83770289320065
max_lon, max_lat = 11.755972968105075, 44.848413809087354

# Filter parcels in viewport
viewport_parcels = parcels.cx[min_lon:max_lon, min_lat:max_lat]

# Print results
print(f"\n{'='*60}")
print(f"Parcels in viewport: {len(viewport_parcels):,}")
print(f"Bounding box: {min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}")
print(f"{'='*60}")

# Show hrl_name distribution
print(f"\nDistribution by hrl_name (farmer-declared crops):")
print(f"{'-'*60}")
for crop, count in viewport_parcels['hrl_name'].value_counts().items():
    pct = (count / len(viewport_parcels)) * 100
    print(f"{crop:<30} {count:5,} parcels ({pct:5.1f}%)")

print(f"\nTotal crop types: {viewport_parcels['hrl_name'].nunique()}")