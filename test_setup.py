#!/usr/bin/env python3
"""
Test script to verify data setup and libraries
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path

def test_data_access():
    """Test if shapefile is accessible and readable"""
    
    print("=" * 50)
    print("Testing Data Setup")
    print("=" * 50)
    
    # Check if data directory exists
    data_dir = Path("downloaded_data")
    if not data_dir.exists():
        print("❌ Error: downloaded_data directory not found")
        print("   Run ./setup.sh first!")
        return False
    
    print("✅ Data directory found")
    
    # List files in directory
    print("\nFiles in downloaded_data:")
    for file in data_dir.iterdir():
        print(f"  - {file.name}")
    
    # Try to find and read shapefile
    shapefiles = list(data_dir.glob("*.shp"))
    
    if not shapefiles:
        print("\n❌ No .shp files found")
        return False
    
    print(f"\n✅ Found {len(shapefiles)} shapefile(s)")
    
    # Read the first shapefile
    shapefile_path = shapefiles[0]
    print(f"\nReading: {shapefile_path.name}")
    
    try:
        gdf = gpd.read_file(shapefile_path)
        
        print(f"✅ Successfully loaded shapefile!")
        print(f"\nDataset Info:")
        print(f"  - Total features: {len(gdf):,}")
        print(f"  - CRS: {gdf.crs}")
        print(f"  - Bounds: {gdf.total_bounds}")
        print(f"\nColumns ({len(gdf.columns)}):")
        for col in gdf.columns:
            print(f"  - {col}")
        
        print(f"\nFirst row sample:")
        print(gdf.head(1).T)
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading shapefile: {e}")
        return False

if __name__ == "__main__":
    success = test_data_access()
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! Ready to build the app.")
    else:
        print("❌ Tests failed. Check setup.")
    print("=" * 50)
