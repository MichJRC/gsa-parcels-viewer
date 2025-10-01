import geopandas as gpd
import pandas as pd
import numpy as np

print("=" * 80)
print("DIRECT GSA CODE → HRL MAPPING (IMPROVED MERGE)")
print("Building from your actual data: downloaded_data/parcels_cleaned.gpkg")
print("=" * 80)

# ==============================================================================
# STEP 1: Load your geopackage
# ==============================================================================
print("\n=== STEP 1: LOAD GEOPACKAGE ===")
gpkg = gpd.read_file('downloaded_data/parcels_cleaned.gpkg')

print(f"✓ Total features: {len(gpkg):,}")
print(f"✓ CRS: {gpkg.crs}")

# ==============================================================================
# STEP 2: Extract unique GSA codes and Italian names
# ==============================================================================
print("\n=== STEP 2: EXTRACT UNIQUE GSA CODES ===")

# Get unique combinations - create normalized key for matching
gsa_unique = gpkg[['COD_SUOLO', 'DESC_SUOLO']].drop_duplicates().copy()
# Create normalized version for matching (lowercase, stripped)
gsa_unique['DESC_SUOLO_NORMALIZED'] = gsa_unique['DESC_SUOLO'].str.strip().str.lower()

print(f"✓ Unique GSA code-name combinations: {len(gsa_unique)}")

# Show distribution
print(f"\nMost common crops (by feature count):")
top_crops = gpkg['DESC_SUOLO'].value_counts().head(15)
for crop, count in top_crops.items():
    print(f"  {crop}: {count:,} features")

# ==============================================================================
# STEP 3: Load and normalize Italian-English translation
# ==============================================================================
print("\n=== STEP 3: LOAD ITALIAN-ENGLISH TRANSLATION (WITH NORMALIZATION) ===")
italian_english = pd.read_csv('data/ITCrops_translated.csv')
print(f"✓ Translations loaded: {len(italian_english)}")

# Create normalized version for matching
italian_english['Italian_Normalized'] = italian_english['Italian Crop Name (main_crop)'].str.strip().str.lower()

print(f"Original columns: {italian_english.columns.tolist()}")

# ==============================================================================
# STEP 4: Merge using NORMALIZED keys with PARTIAL MATCHING fallback
# ==============================================================================
print("\n=== STEP 4: MERGE USING NORMALIZED KEYS ===")

# First: Try exact match
gsa_with_english = gsa_unique.merge(
    italian_english,
    left_on='DESC_SUOLO_NORMALIZED',
    right_on='Italian_Normalized',
    how='left'
)

matched_exact = gsa_with_english['Corrected English Crop Name'].notna().sum()
print(f"✓ Exact matches: {matched_exact}")

# Second: For unmatched, try partial matching (contains)
print("Attempting partial matching for remaining crops...")

def find_partial_match(gsa_name, translation_df):
    """Find translation where GSA name is contained in translation or vice versa"""
    gsa_norm = str(gsa_name).lower().strip()
    
    for _, trans_row in translation_df.iterrows():
        trans_norm = str(trans_row['Italian_Normalized']).lower().strip()
        
        # Check if one contains the other (with minimum length to avoid false positives)
        if len(gsa_norm) >= 4 and len(trans_norm) >= 4:
            # GSA name contained in translation (e.g., "BARBABIETOLA" in "BARBABIETOLA - RAPA...")
            if gsa_norm in trans_norm and gsa_norm != trans_norm:
                return trans_row['Corrected English Crop Name']
            # Translation contained in GSA name
            if trans_norm in gsa_norm and gsa_norm != trans_norm:
                return trans_row['Corrected English Crop Name']
    
    return None

# Apply partial matching to unmatched rows
unmatched_mask = gsa_with_english['Corrected English Crop Name'].isna()
for idx in gsa_with_english[unmatched_mask].index:
    gsa_name = gsa_with_english.at[idx, 'DESC_SUOLO_NORMALIZED']
    partial_match = find_partial_match(gsa_name, italian_english)
    if partial_match:
        gsa_with_english.at[idx, 'Corrected English Crop Name'] = partial_match

matched_total = gsa_with_english['Corrected English Crop Name'].notna().sum()
matched_partial = matched_total - matched_exact
unmatched = gsa_with_english['Corrected English Crop Name'].isna().sum()

print(f"✓ Partial matches: {matched_partial}")
print(f"✓ Total matched: {matched_total} ({matched_total/len(gsa_unique)*100:.1f}%)")
print(f"⚠ Still unmatched: {unmatched} ({unmatched/len(gsa_unique)*100:.1f}%)")

if unmatched > 0:
    print(f"\n⚠ Crops still without English translation (first 10):")
    unmatched_crops = gsa_with_english[gsa_with_english['Corrected English Crop Name'].isna()]['DESC_SUOLO'].head(10).tolist()
    for crop in unmatched_crops:
        print(f"  - {crop}")

# ==============================================================================
# STEP 5: Define HRL categories with comprehensive keywords
# ==============================================================================
print("\n=== STEP 5: DEFINE HRL MAPPING RULES ===")

hrl_mapping_rules = {
    1110: {
        'name': 'Wheat',
        'keywords_italian': ['frumento', 'grano'],
        'keywords_english': ['wheat'],
        'priority': 1
    },
    1120: {
        'name': 'Barley',
        'keywords_italian': ['orzo'],
        'keywords_english': ['barley'],
        'priority': 1
    },
    1130: {
        'name': 'Maize',
        'keywords_italian': ['mais', 'granturco', 'granoturco'],
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
        'keywords_italian': ['avena', 'segale', 'sorgo', 'miglio', 'farro', 'spelta', 'triticale'],
        'keywords_english': ['oat', 'rye', 'sorghum', 'millet', 'spelt', 'triticale'],
        'priority': 2
    },
    1210: {
        'name': 'Fresh Vegetables',
        'keywords_italian': ['pomodoro', 'ortaggi', 'verdura', 'cavolo', 'lattuga', 
                             'melanzana', 'peperone', 'zucchina', 'cipolla', 'aglio',
                             'carota', 'sedano', 'finocchio', 'spinaci', 'asparago',
                             'carciofo', 'melone', 'anguria', 'cocomero', 'fragola',
                             'bietola'],  # Chard is a vegetable
        'keywords_english': ['tomato', 'vegetable', 'cabbage', 'lettuce', 'eggplant',
                            'pepper', 'zucchini', 'onion', 'garlic', 'carrot',
                            'celery', 'fennel', 'spinach', 'asparagus', 'artichoke',
                            'melon', 'watermelon', 'strawberry', 'chard', 'swiss chard'],
        'priority': 1
    },
    1220: {
        'name': 'Dry pulses',
        'keywords_italian': ['fagiolo', 'pisello', 'lenticchia', 'cece', 'fava', 'favino', 'lupino'],
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
        'keywords_italian': ['barbabietola'],  # This will catch BARBABIETOLA
        'keywords_english': ['beet', 'beetroot'],  # Will catch Beetroot
        'priority': 1
    },
    1410: {
        'name': 'Sunflower',
        'keywords_italian': ['girasole'],
        'keywords_english': ['sunflower'],
        'priority': 1
    },
    1420: {
        'name': 'Soybeans',
        'keywords_italian': ['soia', 'soja'],
        'keywords_english': ['soy', 'soybean'],
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
        'keywords_italian': ['vite', 'uva', 'vigneto', 'vitigno'],
        'keywords_english': ['grape', 'vine', 'grapevine', 'vineyard'],
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
                             'mirtillo', 'lampone', 'ribes', 'frutteto', 'marasca',
                             'visciola', 'amarena'],
        'keywords_english': ['apple', 'pear', 'peach', 'apricot', 'cherry',
                            'plum', 'citrus', 'orange', 'lemon', 'mandarin',
                            'grapefruit', 'fig', 'kiwi', 'blueberry', 'raspberry',
                            'currant', 'fruit tree', 'orchard', 'morello'],
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
# STEP 6: Define non-agricultural categories to EXCLUDE
# ==============================================================================
print("\n=== STEP 6: DEFINE NON-AGRICULTURAL CATEGORIES ===")

non_agricultural_keywords = {
    'uso non agricolo', 'non agricultural', 'fabbricati', 'buildings',
    'tare', 'margini', 'margins', 'field margins', 'fossati', 'canali', 'ditches',
    'siepi', 'hedges', 'fasce tampone', 'buffer strips', 'buffer',
    'ritirate dalla produzione', 'withdrawn', 'maceri', 'stagni', 'laghetti', 'ponds',
    'serre', 'greenhouse', 'vivai', 'nursery', 'orti familiari', 'family garden'
}

def is_non_agricultural(italian_name, english_name):
    """Check if this is non-agricultural land that should be excluded"""
    search_text = f"{str(italian_name).lower()} {str(english_name).lower()}"
    return any(keyword in search_text for keyword in non_agricultural_keywords)

# ==============================================================================
# STEP 7: Assign HRL codes with improved logic and MANUAL OVERRIDES
# ==============================================================================
print("\n=== STEP 7: ASSIGN HRL CODES ===")

# Define manual overrides for problematic crops
manual_overrides = {
    'SOIA': 1420,  # Soybeans
    'BARBABIETOLA': 1320,  # Sugar Beet (even if translation says Sugarcane)
    'VITE': 2100,  # Grapes
    'UVA': 2100,  # Grapes (alternative)
    'GRANTURCO (MAIS)': 1130,  # Maize
    'GRANO (FRUMENTO) TENERO': 1110,  # Wheat
    'GRANO (FRUMENTO) DURO': 1110,  # Wheat
}

def assign_hrl_code(italian_name, english_name):
    """
    Assign HRL code based on Italian and English crop names.
    Returns (hrl_code, confidence, matched_by, is_excluded)
    """
    if pd.isna(italian_name):
        return None, 'none', 'no_name', False
    
    # Check manual overrides FIRST
    italian_upper = str(italian_name).upper().strip()
    if italian_upper in manual_overrides:
        hrl = manual_overrides[italian_upper]
        return hrl, 'very_high', 'manual_override', False
    
    # Check if non-agricultural (should be excluded)
    if is_non_agricultural(italian_name, english_name):
        return None, 'excluded', 'non_agricultural', True
    
    italian_lower = str(italian_name).lower()
    english_lower = str(english_name).lower() if pd.notna(english_name) else ''
    
    # Try to match with specific crops first (priority 1), then broader categories
    for priority in [1, 2]:
        for hrl_code, rules in hrl_mapping_rules.items():
            if rules['priority'] != priority:
                continue
            
            # Check Italian keywords
            for keyword in rules['keywords_italian']:
                if keyword in italian_lower:
                    return hrl_code, 'high', f'italian:{keyword}', False
            
            # Check English keywords
            if english_lower:
                for keyword in rules['keywords_english']:
                    if keyword in english_lower:
                        return hrl_code, 'high', f'english:{keyword}', False
    
    # No match found
    return None, 'none', 'no_match', False

# Apply the mapping
print("Applying mapping rules...")
results = []

for idx, row in gsa_with_english.iterrows():
    hrl_code, confidence, matched_by, is_excluded = assign_hrl_code(
        row['DESC_SUOLO'], 
        row['Corrected English Crop Name']
    )
    
    results.append({
        'COD_SUOLO': row['COD_SUOLO'],
        'DESC_SUOLO': row['DESC_SUOLO'],
        'English_Name': row['Corrected English Crop Name'],
        'HRL_Code': hrl_code,
        'HRL_Name': hrl_mapping_rules[hrl_code]['name'] if hrl_code else None,
        'Confidence': confidence,
        'Matched_By': matched_by,
        'Is_Excluded': is_excluded
    })

results_df = pd.DataFrame(results)

# ==============================================================================
# STEP 8: Analyze results
# ==============================================================================
print("\n=== STEP 8: MAPPING RESULTS ===")

total = len(results_df)
mapped = results_df['HRL_Code'].notna().sum()
excluded = results_df['Is_Excluded'].sum()
unmapped = total - mapped - excluded

print(f"Total unique GSA codes: {total}")
print(f"✓ Successfully mapped to HRL: {mapped} ({mapped/total*100:.1f}%)")
print(f"✓ Excluded (non-agricultural): {excluded} ({excluded/total*100:.1f}%)")
print(f"⚠ Still need review: {unmapped} ({unmapped/total*100:.1f}%)")

# Show distribution by HRL code
print("\n=== HRL CODE DISTRIBUTION ===")
hrl_counts = results_df['HRL_Code'].value_counts().sort_index()

target_hrls = [1110, 1120, 1130, 1140, 1150, 1210, 1220, 1310, 1320,
               1410, 1420, 1430, 1440, 2100, 2200, 2310, 2320]

print("\nTarget HRL codes (17 specific crop classes):")
for hrl_code in target_hrls:
    if hrl_code in hrl_counts.index:
        count = hrl_counts[hrl_code]
        hrl_name = hrl_mapping_rules[hrl_code]['name']
        # Highlight the 3 that were originally missing
        status = "⭐" if hrl_code in [1110, 1130, 1320] else "✓"
        print(f"{status} HRL {hrl_code} ({hrl_name}): {count} GSA codes")
    else:
        hrl_name = hrl_mapping_rules[hrl_code]['name']
        print(f"❌ HRL {hrl_code} ({hrl_name}): 0 GSA codes")

# ==============================================================================
# STEP 9: Save results
# ==============================================================================
print("\n=== STEP 9: SAVE RESULTS ===")

# Save complete mapping
results_df.to_csv('downloaded_data/GSA_to_HRL_mapping_FINAL.csv', index=False)
print("✓ Saved: downloaded_data/GSA_to_HRL_mapping_FINAL.csv")

# Save only agricultural crops (mapped + unmapped, excluding non-agricultural)
agricultural = results_df[~results_df['Is_Excluded']].copy()
agricultural.to_csv('downloaded_data/GSA_to_HRL_AGRICULTURAL_ONLY.csv', index=False)
print(f"✓ Saved: downloaded_data/GSA_to_HRL_AGRICULTURAL_ONLY.csv ({len(agricultural)} agricultural crops)")

# Save crops that still need review
needs_review = results_df[(results_df['HRL_Code'].isna()) & (~results_df['Is_Excluded'])].copy()
if len(needs_review) > 0:
    needs_review.to_csv('downloaded_data/GSA_codes_STILL_NEED_REVIEW.csv', index=False)
    print(f"⚠ Saved: downloaded_data/GSA_codes_STILL_NEED_REVIEW.csv ({len(needs_review)} codes)")
    
    print("\nTop unmapped agricultural crops:")
    for idx, row in needs_review.head(10).iterrows():
        eng = f"({row['English_Name']})" if pd.notna(row['English_Name']) else "(no translation)"
        print(f"  - {row['DESC_SUOLO']} {eng}")
else:
    print("✅ All agricultural crops successfully mapped!")

# Save summary by HRL
hrl_summary = results_df[results_df['HRL_Code'].notna()].groupby('HRL_Code').agg({
    'COD_SUOLO': 'count',
    'HRL_Name': 'first'
}).reset_index()
hrl_summary.columns = ['HRL_Code', 'Number_of_GSA_Codes', 'HRL_Name']
hrl_summary = hrl_summary.sort_values('HRL_Code')
hrl_summary.to_csv('downloaded_data/HRL_summary.csv', index=False)
print("✓ Saved: downloaded_data/HRL_summary.csv")

print("\n" + "=" * 80)
print("IMPROVED MAPPING COMPLETE!")
print("=" * 80)
print("\nKEY IMPROVEMENTS:")
print("✓ Normalized string matching (case-insensitive, trimmed)")
print("✓ Non-agricultural land automatically excluded")
print("✓ Better keyword coverage for Italian crops")
print("✓ Should now match: BARBABIETOLA, SOIA, VITE, etc.")
print("\nCheck if HRL 1130, 1320, 1420, 2100 are now recovered!")
print("=" * 80)