#!/usr/bin/env python3
"""
Simplified vector cleaning - focuses on geometry quality, not dissolve
"""

import geopandas as gpd
import warnings
warnings.filterwarnings('ignore')

def clean_shapefile(input_path, output_path):
    """Clean shapefile by fixing geometries and removing artifacts"""
    
    print("=" * 70)
    print("VECTOR CLEANING PROCESS")
    print("=" * 70)
    
    # Load shapefile
    print("\nSTEP 1: Loading shapefile...")
    gdf = gpd.read_file(input_path)
    original_count = len(gdf)
    print(f"   Loaded: {original_count:,} parcels")
    print(f"   CRS: {gdf.crs}")
    
    # STEP 2: Fix invalid geometries and topological errors with buffer(0)
    print("\nSTEP 2: Fixing invalid geometries and topological errors...")
    print("   Using buffer(0) - this fixes:")
    print("   • Invalid geometries (self-intersections, bow-ties)")
    print("   • Small topological gaps between adjacent polygons")
    print("   • Incorrect winding order")
    
    invalid_before = (~gdf.geometry.is_valid).sum()
    print(f"\n   Invalid geometries before: {invalid_before}")
    
    # Apply buffer(0) to all geometries
    gdf['geometry'] = gdf.geometry.buffer(0)
    
    invalid_after = (~gdf.geometry.is_valid).sum()
    print(f"   Invalid geometries after: {invalid_after}")
    print(f"   Fixed: {invalid_before - invalid_after}")
    
    # STEP 3: Simplify geometries to remove micro-artifacts
    print("\nSTEP 3: Simplifying geometries...")
    print("   Tolerance: 1.0 meter (preserving topology)")
    print("   This removes unnecessary vertices and micro-zigzags")
    
    def count_vertices(geom):
        if geom.geom_type == 'Polygon':
            return len(geom.exterior.coords)
        elif geom.geom_type == 'MultiPolygon':
            return sum(len(p.exterior.coords) for p in geom.geoms)
        return 0
    
    vertices_before = gdf.geometry.apply(count_vertices).sum()
    
    gdf['geometry'] = gdf.geometry.simplify(
        tolerance=1.0,  # Slightly higher tolerance for agricultural parcels
        preserve_topology=True
    )
    
    vertices_after = gdf.geometry.apply(count_vertices).sum()
    
    print(f"   Vertices before: {vertices_before:,}")
    print(f"   Vertices after:  {vertices_after:,}")
    print(f"   Reduction: {((vertices_before - vertices_after) / vertices_before * 100):.1f}%")
    
    # STEP 4: Analyze geometry quality
    print("\nSTEP 4: Analyzing geometry quality...")
    
    gdf['area_m2'] = gdf.geometry.area
    gdf['perimeter_m'] = gdf.geometry.length
    gdf['shape_index'] = gdf['perimeter_m'] / (2 * (3.14159 * gdf['area_m2']) ** 0.5)
    
    print(f"\n   Area statistics (m²):")
    print(f"   Min:    {gdf['area_m2'].min():.2f}")
    print(f"   Median: {gdf['area_m2'].median():.2f}")
    print(f"   Mean:   {gdf['area_m2'].mean():.2f}")
    print(f"   Max:    {gdf['area_m2'].max():.2f}")
    
    print(f"\n   Shape index statistics:")
    print(f"   Median: {gdf['shape_index'].median():.2f}")
    print(f"   Mean:   {gdf['shape_index'].mean():.2f}")
    print(f"   95%:    {gdf['shape_index'].quantile(0.95):.2f}")
    print(f"   Max:    {gdf['shape_index'].max():.2f}")
    
    # Count problem geometries
    tiny_5 = (gdf['area_m2'] < 5).sum()
    tiny_10 = (gdf['area_m2'] < 10).sum()
    slivers_50 = (gdf['shape_index'] > 50).sum()
    slivers_100 = (gdf['shape_index'] > 100).sum()
    
    print(f"\n   Problem geometries:")
    print(f"   Area < 5 m²:  {tiny_5:,}")
    print(f"   Area < 10 m²: {tiny_10:,}")
    print(f"   Shape index > 50:  {slivers_50:,}")
    print(f"   Shape index > 100: {slivers_100:,}")
    
    # STEP 5: Remove extreme slivers
    print("\nSTEP 5: Removing extreme slivers...")
    print("   Criteria: shape_index > 100 AND area < 100 m²")
    
    before_sliver = len(gdf)
    gdf = gdf[~((gdf['shape_index'] > 100) & (gdf['area_m2'] < 100))]
    after_sliver = len(gdf)
    
    print(f"   Removed: {before_sliver - after_sliver:,} extreme slivers")
    
    # STEP 6: Remove tiny artifacts
    print("\nSTEP 6: Removing tiny artifacts...")
    print("   Threshold: < 10 m²")
    
    before_tiny = len(gdf)
    gdf = gdf[gdf['area_m2'] >= 10]
    after_tiny = len(gdf)
    
    print(f"   Removed: {before_tiny - after_tiny:,} tiny parcels")
    print(f"   Remaining: {after_tiny:,} parcels")
    
    # Clean up temporary columns
    gdf = gdf.drop(columns=['area_m2', 'perimeter_m', 'shape_index'])
    
    # STEP 7: Final validation
    print("\nSTEP 7: Final validation...")
    
    final_invalid = (~gdf.geometry.is_valid).sum()
    final_null = gdf.geometry.isna().sum()
    final_empty = gdf.geometry.is_empty.sum()
    
    print(f"   Invalid: {final_invalid}, Null: {final_null}, Empty: {final_empty}")
    
    if final_invalid > 0 or final_null > 0 or final_empty > 0:
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.isna() & ~gdf.geometry.is_empty]
        print(f"   After cleanup: {len(gdf):,} parcels")
    
    # STEP 8: Save
    print(f"\nSTEP 8: Saving cleaned data...")
    print(f"   Output: {output_path}")
    
    if output_path.endswith('.gpkg'):
        gdf.to_file(output_path, driver='GPKG')
    else:
        gdf.to_file(output_path)
    
    print(f"   Saved: {len(gdf):,} parcels")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Original:  {original_count:,}")
    print(f"Cleaned:   {len(gdf):,}")
    print(f"Removed:   {original_count - len(gdf):,} ({((original_count - len(gdf)) / original_count * 100):.2f}%)")
    print("=" * 70)
    
    return gdf

if __name__ == '__main__':
    INPUT_SHAPEFILE = "downloaded_data/Appe_Azi_PCG_2021_FE/Appe_Azi_PCG_2021_FE.shp"
    OUTPUT_GPKG = "downloaded_data/parcels_cleaned.gpkg"
    
    clean_shapefile(INPUT_SHAPEFILE, OUTPUT_GPKG)