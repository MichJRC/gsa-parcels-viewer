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
