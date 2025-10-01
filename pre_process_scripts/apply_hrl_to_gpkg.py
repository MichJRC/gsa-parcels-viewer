import geopandas as gpd
import pandas as pd
import numpy as np

print("=" * 80)
print("APPLYING HRL CODES TO GEOPACKAGE")
print("=" * 80)

# ==============================================================================
# STEP 1: Load the final GSA → HRL mapping
# ==============================================================================
print("\n=== STEP 1: LOAD HRL MAPPING ===")
mapping = pd.read_csv('pre_process_scripts/GSA_to_HRL_mapping_FINAL_v2.csv')
print(f"✓ Loaded mapping: {len(mapping)} unique GSA codes")

# Show mapping statistics
mapped = mapping['HRL_Code'].notna().sum()
excluded = mapping['Is_Excluded'].sum()
unmapped = len(mapping) - mapped - excluded

print(f"  Mapped to HRL: {mapped}")
print(f"  Excluded (non-agricultural): {excluded}")
print(f"  Unmapped: {unmapped}")

# Create a lookup dictionary: DESC_SUOLO → HRL_Code
hrl_lookup = {}
for _, row in mapping.iterrows():
    desc_suolo = row['DESC_SUOLO']
    hrl_code = row['HRL_Code']
    hrl_name = row['HRL_Name']
    
    # Store even if NaN (will use 0 or special code)
    hrl_lookup[desc_suolo] = {
        'hrl_code': hrl_code if pd.notna(hrl_code) else 0,
        'hrl_name': hrl_name if pd.notna(hrl_name) else 'Unmapped',
        'is_excluded': row['Is_Excluded']
    }

print(f"✓ Created lookup dictionary with {len(hrl_lookup)} entries")

# ==============================================================================
# STEP 2: Load the geopackage
# ==============================================================================
print("\n=== STEP 2: LOAD GEOPACKAGE ===")
gpkg = gpd.read_file('downloaded_data/parcels_cleaned.gpkg')
print(f"✓ Loaded geopackage: {len(gpkg):,} features")
print(f"  Columns: {len(gpkg.columns)}")
print(f"  CRS: {gpkg.crs}")

# ==============================================================================
# STEP 3: Apply HRL codes to the geopackage
# ==============================================================================
print("\n=== STEP 3: APPLY HRL CODES ===")

# Add new columns for HRL data
gpkg['hrl_code'] = 0  # Default to 0 (unmapped)
gpkg['hrl_name'] = 'Unknown'

# Apply the mapping based on DESC_SUOLO
for idx, row in gpkg.iterrows():
    desc_suolo = row['DESC_SUOLO']
    
    if desc_suolo in hrl_lookup:
        lookup_data = hrl_lookup[desc_suolo]
        gpkg.at[idx, 'hrl_code'] = lookup_data['hrl_code']
        gpkg.at[idx, 'hrl_name'] = lookup_data['hrl_name']

print("✓ Applied HRL codes to all features")

# ==============================================================================
# STEP 4: Statistics and validation
# ==============================================================================
print("\n=== STEP 4: VALIDATION ===")

# Count features per HRL code
hrl_distribution = gpkg['hrl_code'].value_counts().sort_index()

print("\nHRL distribution in geopackage:")
total_features = len(gpkg)

# Show all HRL codes including 0 (unmapped)
print(f"\n{'HRL Code':<10} {'HRL Name':<30} {'Features':<12} {'Percentage'}")
print("-" * 70)

for hrl_code in sorted(gpkg['hrl_code'].unique()):
    if hrl_code == 0:
        name = "Unmapped/Unknown"
    else:
        # Get name from first occurrence
        name = gpkg[gpkg['hrl_code'] == hrl_code]['hrl_name'].iloc[0]
    
    count = hrl_distribution.get(hrl_code, 0)
    percentage = (count / total_features) * 100
    
    print(f"{int(hrl_code):<10} {name:<30} {count:<12,} {percentage:>6.2f}%")

# Summary statistics
print("\n" + "=" * 70)
print("SUMMARY:")
mapped_features = gpkg[gpkg['hrl_code'] > 0]
print(f"Total features: {total_features:,}")
print(f"Mapped to HRL codes: {len(mapped_features):,} ({len(mapped_features)/total_features*100:.1f}%)")
print(f"Unmapped (code 0): {(gpkg['hrl_code'] == 0).sum():,} ({(gpkg['hrl_code'] == 0).sum()/total_features*100:.1f}%)")

# Check critical HRL codes
print("\nCritical HRL codes recovered:")
critical_codes = {
    1110: 'Wheat',
    1130: 'Maize', 
    1320: 'Sugar Beet',
    1420: 'Soybeans',
    2100: 'Grapes'
}

for code, name in critical_codes.items():
    count = (gpkg['hrl_code'] == code).sum()
    status = "✓" if count > 0 else "❌"
    print(f"{status} HRL {code} ({name}): {count:,} features")

# ==============================================================================
# STEP 5: Save the updated geopackage
# ==============================================================================
print("\n=== STEP 5: SAVE UPDATED GEOPACKAGE ===")

# Save with HRL codes
output_file = 'downloaded_data/parcels_with_HRL_codes.gpkg'
gpkg.to_file(output_file, driver='GPKG')
print(f"✓ Saved: {output_file}")

print(f"\nNew columns added:")
print(f"  - hrl_code: HRL classification code (0 = unmapped, 1110-3200 = specific classes)")
print(f"  - hrl_name: Human-readable HRL class name")

# Also save a summary CSV
summary_df = gpkg.groupby(['hrl_code', 'hrl_name']).agg({
    'COD_SUOLO': 'count',
    'SUP_APPEZ': 'sum'
}).reset_index()
summary_df.columns = ['HRL_Code', 'HRL_Name', 'Feature_Count', 'Total_Area']
summary_df = summary_df.sort_values('HRL_Code')
summary_df.to_csv('pre_process_scripts/HRL_distribution_summary.csv', index=False)
print(f"✓ Saved: pre_process_scripts/HRL_distribution_summary.csv")

# ==============================================================================
# STEP 6: Create visualization data
# ==============================================================================
print("\n=== STEP 6: CREATE VISUALIZATION SUMMARY ===")

# Top 10 crops by area
top_crops = gpkg.groupby(['DESC_SUOLO', 'hrl_code', 'hrl_name']).agg({
    'SUP_APPEZ': 'sum',
    'COD_SUOLO': 'count'
}).reset_index()
top_crops.columns = ['Crop_Name', 'HRL_Code', 'HRL_Name', 'Total_Area_ha', 'Feature_Count']
top_crops = top_crops.sort_values('Total_Area_ha', ascending=False).head(20)
top_crops.to_csv('pre_process_scripts/top_20_crops_by_area.csv', index=False)
print(f"✓ Saved: pre_process_scripts/top_20_crops_by_area.csv")

print("\nTop 10 crops by area:")
for idx, row in top_crops.head(10).iterrows():
    print(f"  {row['Crop_Name']}: {row['Total_Area_ha']:.1f} ha (HRL {int(row['HRL_Code'])})")

print("\n" + "=" * 80)
print("SUCCESS! HRL CODES APPLIED TO GEOPACKAGE")
print("=" * 80)
print("\nOutput files created:")
print("  1. downloaded_data/parcels_with_HRL_codes.gpkg - Main output")
print("  2. pre_process_scripts/HRL_distribution_summary.csv - Statistics")
print("  3. pre_process_scripts/top_20_crops_by_area.csv - Top crops")
print("\nYou can now use these HRL codes for:")
print("  - Visualization in QGIS/GIS software")
print("  - Statistical analysis")
print("  - Comparison with other European datasets")
print("  - Integration with Copernicus HRL Croplands")
print("=" * 80)