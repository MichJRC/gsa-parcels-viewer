import geopandas as gpd
import pandas as pd
import numpy as np

print("=" * 80)
print("DIRECT GSA CODE → HRL MAPPING")
print("Building from your actual data: parcels_cleaned.gpkg")
print("=" * 80)

# ==============================================================================
# STEP 1: Load your geopackage
# ==============================================================================
print("\n=== STEP 1: LOAD GEOPACKAGE ===")
gpkg = gpd.read_file('downloaded_data/parcels_cleaned.gpkg')

print(f"✓ Total features: {len(gpkg):,}")
print(f"✓ Columns: {gpkg.columns.tolist()}")
print(f"✓ CRS: {gpkg.crs}")

# ==============================================================================
# STEP 2: Extract unique GSA codes and Italian names
# ==============================================================================
print("\n=== STEP 2: EXTRACT UNIQUE GSA CODES ===")

# Get unique combinations of GSA code and Italian name
gsa_unique = gpkg[['COD_SUOLO', 'DESC_SUOLO']].drop_duplicates().copy()
print(f"✓ Unique GSA code-name combinations: {len(gsa_unique)}")

# Show distribution
print(f"\nMost common crops (by feature count):")
top_crops = gpkg['DESC_SUOLO'].value_counts().head(15)
for crop, count in top_crops.items():
    print(f"  {crop}: {count:,} features")

# ==============================================================================
# STEP 3: Load your Italian-English translation
# ==============================================================================
print("\n=== STEP 3: LOAD ITALIAN-ENGLISH TRANSLATION ===")
italian_english = pd.read_csv('data/ItalianCropNamemaincrop-CorrectedEnglishCropName.csv')
print(f"✓ Translations loaded: {len(italian_english)}")

# ==============================================================================
# STEP 4: Merge GSA data with English translations
# ==============================================================================
print("\n=== STEP 4: MERGE GSA WITH ENGLISH TRANSLATIONS ===")

gsa_with_english = gsa_unique.merge(
    italian_english,
    left_on='DESC_SUOLO',
    right_on='Italian Crop Name (main_crop)',
    how='left'
)

matched = gsa_with_english['Corrected English Crop Name'].notna().sum()
unmatched = gsa_with_english['Corrected English Crop Name'].isna().sum()

print(f"✓ Matched with English: {matched}")
print(f"⚠ Not matched: {unmatched}")

if unmatched > 0:
    print("\nCrops without English translation:")
    print(gsa_with_english[gsa_with_english['Corrected English Crop Name'].isna()]['DESC_SUOLO'].tolist())

# ==============================================================================
# STEP 5: Define HRL categories and mapping rules
# ==============================================================================
print("\n=== STEP 5: DEFINE HRL MAPPING RULES ===")

# Based on official HRL Croplands manual - 17 specific crop classes
hrl_mapping_rules = {
    1110: {
        'name': 'Wheat',
        'keywords_italian': ['frumento', 'grano', 'triticum'],
        'keywords_english': ['wheat', 'triticum'],
        'priority': 1
    },
    1120: {
        'name': 'Barley',
        'keywords_italian': ['orzo'],
        'keywords_english': ['barley', 'hordeum'],
        'priority': 1
    },
    1130: {
        'name': 'Maize',
        'keywords_italian': ['mais', 'granoturco', 'granturco'],
        'keywords_english': ['maize', 'corn'],
        'priority': 1
    },
    1140: {
        'name': 'Rice',
        'keywords_italian': ['riso', 'risone'],
        'keywords_english': ['rice', 'paddy'],
        'priority': 1
    },
    1150: {
        'name': 'Other cereals',
        'keywords_italian': ['avena', 'segale', 'sorgo', 'miglio', 'farro', 'spelta'],
        'keywords_english': ['oat', 'rye', 'sorghum', 'millet', 'spelt'],
        'priority': 2  # Lower priority - catch remaining cereals
    },
    1210: {
        'name': 'Fresh Vegetables',
        'keywords_italian': ['pomodoro', 'ortaggi', 'verdura', 'cavolo', 'lattuga', 
                             'melanzana', 'peperone', 'zucchina', 'cipolla', 'aglio',
                             'carota', 'sedano', 'finocchio', 'spinaci', 'asparago',
                             'carciofo', 'melone', 'anguria', 'cocomero', 'fragola'],
        'keywords_english': ['tomato', 'vegetable', 'cabbage', 'lettuce', 'eggplant',
                            'pepper', 'zucchini', 'onion', 'garlic', 'carrot',
                            'celery', 'fennel', 'spinach', 'asparagus', 'artichoke',
                            'melon', 'watermelon', 'strawberry'],
        'priority': 1
    },
    1220: {
        'name': 'Dry pulses',
        'keywords_italian': ['fagiolo', 'pisello', 'lenticchia', 'cece', 'fava', 'lupino'],
        'keywords_english': ['bean', 'pea', 'lentil', 'chickpea', 'fava', 'lupin'],
        'priority': 1
    },
    1310: {
        'name': 'Potatoes',
        'keywords_italian': ['patata'],
        'keywords_english': ['potato'],
        'priority': 1
    },
    1320: {
        'name': 'Sugar Beet',
        'keywords_italian': ['barbabietola da zucchero', 'barbabietola zuccherina'],
        'keywords_english': ['sugar beet', 'sugar-beet'],
        'priority': 1
    },
    1410: {
        'name': 'Sunflower',
        'keywords_italian': ['girasole'],
        'keywords_english': ['sunflower', 'helianthus'],
        'priority': 1
    },
    1420: {
        'name': 'Soybeans',
        'keywords_italian': ['soia'],
        'keywords_english': ['soy', 'soybean', 'soja'],
        'priority': 1
    },
    1430: {
        'name': 'Rapeseed',
        'keywords_italian': ['colza'],
        'keywords_english': ['rapeseed', 'rape', 'canola'],
        'priority': 1
    },
    1440: {
        'name': 'Flax, cotton and hemp',
        'keywords_italian': ['lino', 'cotone', 'canapa'],
        'keywords_english': ['flax', 'cotton', 'hemp', 'linseed'],
        'priority': 1
    },
    2100: {
        'name': 'Grapes',
        'keywords_italian': ['vite', 'uva', 'vigneto'],
        'keywords_english': ['grape', 'vine', 'vineyard'],
        'priority': 1
    },
    2200: {
        'name': 'Olives',
        'keywords_italian': ['olivo', 'oliva', 'oliveto'],
        'keywords_english': ['olive'],
        'priority': 1
    },
    2310: {
        'name': 'Fruits',
        'keywords_italian': ['melo', 'pero', 'pesco', 'albicocco', 'ciliegio', 
                             'prugno', 'susino', 'agrumi', 'arancio', 'limone',
                             'mandarino', 'pompelmo', 'fico', 'kiwi', 'actinidia',
                             'mirtillo', 'lampone', 'ribes', 'frutteto'],
        'keywords_english': ['apple', 'pear', 'peach', 'apricot', 'cherry',
                            'plum', 'citrus', 'orange', 'lemon', 'mandarin',
                            'grapefruit', 'fig', 'kiwi', 'blueberry', 'raspberry',
                            'currant', 'fruit tree', 'orchard'],
        'priority': 1
    },
    2320: {
        'name': 'Nuts',
        'keywords_italian': ['mandorlo', 'noce', 'nocciolo', 'nocciola', 'pistacchio', 'castagno'],
        'keywords_english': ['almond', 'walnut', 'hazelnut', 'pistachio', 'chestnut'],
        'priority': 1
    }
}

print(f"✓ Defined mapping rules for {len(hrl_mapping_rules)} HRL categories")

# ==============================================================================
# STEP 6: Apply mapping rules to assign HRL codes
# ==============================================================================
print("\n=== STEP 6: ASSIGN HRL CODES TO GSA CODES ===")

def assign_hrl_code(italian_name, english_name):
    """
    Assign HRL code based on Italian and English crop names.
    Returns (hrl_code, confidence, matched_by)
    """
    if pd.isna(italian_name):
        return None, 'none', 'no_name'
    
    italian_lower = str(italian_name).lower()
    english_lower = str(english_name).lower() if pd.notna(english_name) else ''
    
    # Try to match with priority 1 rules first (specific crops)
    for priority in [1, 2]:
        for hrl_code, rules in hrl_mapping_rules.items():
            if rules['priority'] != priority:
                continue
            
            # Check Italian keywords
            for keyword in rules['keywords_italian']:
                if keyword in italian_lower:
                    return hrl_code, 'high', f'italian:{keyword}'
            
            # Check English keywords
            if english_lower:
                for keyword in rules['keywords_english']:
                    if keyword in english_lower:
                        return hrl_code, 'high', f'english:{keyword}'
    
    # No match found
    return None, 'none', 'no_match'

# Apply the mapping
print("Applying mapping rules...")
gsa_with_english['HRL_Code'] = None
gsa_with_english['HRL_Name'] = None
gsa_with_english['Confidence'] = None
gsa_with_english['Matched_By'] = None

for idx, row in gsa_with_english.iterrows():
    hrl_code, confidence, matched_by = assign_hrl_code(
        row['DESC_SUOLO'], 
        row['Corrected English Crop Name']
    )
    
    gsa_with_english.at[idx, 'HRL_Code'] = hrl_code
    if hrl_code:
        gsa_with_english.at[idx, 'HRL_Name'] = hrl_mapping_rules[hrl_code]['name']
    gsa_with_english.at[idx, 'Confidence'] = confidence
    gsa_with_english.at[idx, 'Matched_By'] = matched_by

# ==============================================================================
# STEP 7: Analyze results
# ==============================================================================
print("\n=== STEP 7: MAPPING RESULTS ===")

total_gsa_codes = len(gsa_with_english)
mapped_codes = gsa_with_english['HRL_Code'].notna().sum()
unmapped_codes = gsa_with_english['HRL_Code'].isna().sum()

print(f"Total unique GSA codes: {total_gsa_codes}")
print(f"Successfully mapped: {mapped_codes} ({mapped_codes/total_gsa_codes*100:.1f}%)")
print(f"Need manual assignment: {unmapped_codes} ({unmapped_codes/total_gsa_codes*100:.1f}%)")

# Show distribution by HRL code
print("\n=== HRL CODE DISTRIBUTION ===")
hrl_counts = gsa_with_english['HRL_Code'].value_counts().sort_index()

target_hrls = [1110, 1120, 1130, 1140, 1150, 1210, 1220, 1310, 1320,
               1410, 1420, 1430, 1440, 2100, 2200, 2310, 2320]

for hrl_code in target_hrls:
    if hrl_code in hrl_counts.index:
        count = hrl_counts[hrl_code]
        hrl_name = hrl_mapping_rules[hrl_code]['name']
        status = "✓"
        # Highlight the 3 that were missing
        if hrl_code in [1110, 1130, 1320]:
            status = "⭐"
        print(f"{status} HRL {hrl_code} ({hrl_name}): {count} GSA codes")
    else:
        hrl_name = hrl_mapping_rules[hrl_code]['name']
        print(f"❌ HRL {hrl_code} ({hrl_name}): 0 GSA codes")

# ==============================================================================
# STEP 8: Save results
# ==============================================================================
print("\n=== STEP 8: SAVE RESULTS ===")

# Save complete mapping
output_columns = ['COD_SUOLO', 'DESC_SUOLO', 'Corrected English Crop Name', 
                  'HRL_Code', 'HRL_Name', 'Confidence', 'Matched_By']
gsa_with_english[output_columns].to_csv('pre_process_scripts/GSA_to_HRL_mapping_complete.csv', index=False)
print("✓ Saved: GSA_to_HRL_mapping_complete.csv")

# Save crops needing manual review
needs_review = gsa_with_english[gsa_with_english['HRL_Code'].isna()].copy()
if len(needs_review) > 0:
    needs_review[output_columns].to_csv('pre_process_scripts/GSA_codes_NEED_MANUAL_HRL.csv', index=False)
    print(f"⚠ Saved: GSA_codes_NEED_MANUAL_HRL.csv ({len(needs_review)} codes to review)")
    print("\nTop unmapped crops:")
    for _, row in needs_review.head(10).iterrows():
        print(f"  - {row['DESC_SUOLO']} ({row['Corrected English Crop Name']})")
else:
    print("✅ All GSA codes successfully mapped!")

# Save summary statistics
summary = gsa_with_english.groupby('HRL_Code').agg({
    'COD_SUOLO': 'count',
    'HRL_Name': 'first'
}).reset_index()
summary.columns = ['HRL_Code', 'Number_of_GSA_Codes', 'HRL_Name']
summary = summary.sort_values('HRL_Code')
summary.to_csv('pre_process_scripts/HRL_summary_statistics.csv', index=False)
print("✓ Saved: HRL_summary_statistics.csv")

print("\n" + "=" * 80)
print("MAPPING COMPLETE!")
print("=" * 80)
print("\nNEXT STEPS:")
print("1. Review 'GSA_to_HRL_mapping_complete.csv'")
if len(needs_review) > 0:
    print("2. Complete manual assignments in 'GSA_codes_NEED_MANUAL_HRL.csv'")
    print("3. Re-run with completed manual assignments")
print("4. Apply the final mapping to your geopackage!")
print("=" * 80)