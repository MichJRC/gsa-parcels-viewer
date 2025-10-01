import pandas as pd

print("=" * 80)
print("APPLYING MANUAL HRL CORRECTIONS")
print("=" * 80)

# Load the current mapping
mapping = pd.read_csv('pre_process_scripts/GSA_to_HRL_mapping_FINAL.csv')
print(f"\nOriginal mapping: {len(mapping)} GSA codes")
print(f"  Mapped: {mapping['HRL_Code'].notna().sum()}")
print(f"  Unmapped: {mapping['HRL_Code'].isna().sum()}")

# Define manual corrections based on your classification
manual_corrections = {
    # 3100 - Unclassified arable crop (forage, herbs, aromatic plants)
    'SEMINATIVI': 3100,
    'ERBA MEDICA': 3100,
    'ERBA MEDICA  (SP. MEDICAGO SATIVA L. (VARIETA\'))': 3100,  # Exact match with extra spaces
    'TRIFOGLIO': 3100,
    'FACELIA': 3100,
    'SALVIA': 3100,
    'ORTICA': 3100,
    'PASSIFLORA': 3100,
    'PREZZEMOLO': 3100,
    'LAVANDA': 3100,
    'TIMO': 3100,
    'ECHINACEA PALLIDA': 3100,
    'ECHINACEA PURPUREA': 3100,
    'MAGGIORANA': 3100,
    'EUCALIPTO': 3100,
    'ORIGANO': 3100,
    'ROSMARINO': 3100,
    'MALVA': 3100,
    'BASILICO': 3100,
    'LOTO': 3100,
    'ZAFFERANO': 3100,
    'SENAPE': 3100,
    'FIORI EDULI': 3100,
    'MIZUNA O BRASSICA RAPA': 3100,
    'CICORIA': 3100,
    'TARTUFO': 3100,
    'PIANTE AROMATICHE E MEDICINALI E SPEZIE': 3100,
    'PIANTE ORNAMENTALI': 3100,
    'CANNA CINESE': 3100,
    'RAFANO': 3100,
    'RUCOLA': 3100,
    'CORIANDOLO': 3100,
    'CAMOMILLA': 3100,
    'BAMBU': 3100,
    'BAMBU GIGANTE': 3100,
    'MENTA': 3100,
    'SENAPE NERA': 3100,
    'CHENOPODIUM QUINOA': 3100,
    'LUPPOLO': 3100,
    'SALICE': 3100,
    'GERANIO': 3100,
    'FESTUCA': 3100,
    'CRISANTEMO': 3100,
    'POINSETTIA': 3100,
    'BORRAGINE': 3100,
    'RUSCUS': 3100,
    'PEONIA': 3100,
    
    # 3200 - Unclassified permanent crop (generic tree categories)
    'COLTIVAZIONI ARBOREE SPECIALIZZATE': 3200,
    'COLTIVAZIONI ARBOREE PROMISCUE': 3200,
    'COLTIVAZIONI ARBOREE PROMISCUE (PIU\' SPECIE ARBOREE)': 3200,  # With parentheses
    'COLTIVAZIONI ARBOREE PERMANENTI SOGGETTE A DIVIETO DI FERTILIZZAZIONE': 3200,
    'COLTIVAZIONI ARBOREE PERMANENTI SOGGETTE A DIVIETO DI FERTILIZZAZIONE E DI TRATTAMENTO FITOSANITARIO  LUNGO I CORSI D?ACQUA': 3200,  # Full version
    'MISCUGLIO DI AZOTOFISSATRICI': 3200,
    'ARBORICOLTURA': 3200,
    'COLTIVAZIONI ARBOREE': 3200,
    
    # 1210 - Fresh Vegetables
    'ZUCCA': 1210,
    'RAVANELLO': 1210,
    'CAVOLFIORE': 1210,
    'CETRIOLO': 1210,
    'SENAPE BRUNA': 1210,
    'RADICCHIO': 1210,
    'PORRO': 1210,
    'SCALOGNO': 1210,
    
    # 2310 - Fruits
    'COTOGNO': 2310,
    'NESPOLO': 2310,
    'MIRTILLI ROSSI': 2310,
    'MIRTILLI ROSSI, MIRTILLI NERI ED ALTRI FRUTTI DEL GENERE "VACCINIUM"': 2310,  # Full version with quotes
    'MORE': 2310,
    'GIUGGIOLO': 2310,
    'LOTO (KAKI)': 2310,
    'LOTO (KAKI) (COMPRESO IL CACO MELA)': 2310,  # Full version
    'OLIVELLO': 2310,
    'OLIVELLO O OLIVELLO SPINOSO': 2310,  # Full version
    'ARONIA NERA': 2310,
    
    # 2320 - Nuts
    'FRUTTA A GUSCIO': 2320
}

print(f"\n=== APPLYING {len(manual_corrections)} MANUAL CORRECTIONS ===")

# HRL names lookup
hrl_names = {
    1210: 'Fresh Vegetables',
    2310: 'Fruits',
    2320: 'Nuts',
    3100: 'Unclassified arable crop',
    3200: 'Unclassified permanent crop'
}

# Apply corrections
corrections_applied = 0
for crop_name, hrl_code in manual_corrections.items():
    # Find matching rows
    mask = mapping['DESC_SUOLO'] == crop_name
    
    if mask.any():
        # Update HRL code
        mapping.loc[mask, 'HRL_Code'] = hrl_code
        mapping.loc[mask, 'HRL_Name'] = hrl_names[hrl_code]
        mapping.loc[mask, 'Confidence'] = 'manual'
        mapping.loc[mask, 'Matched_By'] = 'manual_correction'
        corrections_applied += 1
        print(f"✓ {crop_name} → HRL {hrl_code} ({hrl_names[hrl_code]})")
    else:
        print(f"⚠ {crop_name} not found in mapping")

print(f"\n✓ Applied {corrections_applied} corrections")

# Update statistics
print("\n=== UPDATED MAPPING STATISTICS ===")
print(f"Total GSA codes: {len(mapping)}")
mapped = mapping['HRL_Code'].notna().sum()
excluded = mapping['Is_Excluded'].sum()
unmapped = len(mapping) - mapped - excluded

print(f"✓ Mapped to HRL: {mapped} ({mapped/len(mapping)*100:.1f}%)")
print(f"✓ Excluded (non-agricultural): {excluded} ({excluded/len(mapping)*100:.1f}%)")
print(f"⚠ Still unmapped: {unmapped} ({unmapped/len(mapping)*100:.1f}%)")

# Show updated HRL distribution
print("\n=== UPDATED HRL CODE DISTRIBUTION ===")
hrl_counts = mapping['HRL_Code'].value_counts().sort_index()

all_hrl_names = {
    1110: 'Wheat', 1120: 'Barley', 1130: 'Maize', 1140: 'Rice', 1150: 'Other cereals',
    1210: 'Fresh Vegetables', 1220: 'Dry pulses',
    1310: 'Potatoes', 1320: 'Sugar Beet',
    1410: 'Sunflower', 1420: 'Soybeans', 1430: 'Rapeseed', 1440: 'Flax, cotton and hemp',
    2100: 'Grapes', 2200: 'Olives', 2310: 'Fruits', 2320: 'Nuts',
    3100: 'Unclassified arable crop', 3200: 'Unclassified permanent crop'
}

for hrl_code in sorted(all_hrl_names.keys()):
    if hrl_code in hrl_counts.index:
        count = hrl_counts[hrl_code]
        status = "⭐" if hrl_code in [1110, 1130, 1320, 1420, 2100] else "✓"
        print(f"{status} HRL {hrl_code} ({all_hrl_names[hrl_code]}): {count} GSA codes")
    else:
        print(f"  HRL {hrl_code} ({all_hrl_names[hrl_code]}): 0 GSA codes")

# Save updated mapping
mapping.to_csv('pre_process_scripts/GSA_to_HRL_mapping_FINAL_v2.csv', index=False)
print("\n✓ Saved: pre_process_scripts/GSA_to_HRL_mapping_FINAL_v2.csv")

# Update agricultural only file
agricultural = mapping[~mapping['Is_Excluded']].copy()
agricultural.to_csv('pre_process_scripts/GSA_to_HRL_AGRICULTURAL_ONLY_v2.csv', index=False)
print(f"✓ Saved: pre_process_scripts/GSA_to_HRL_AGRICULTURAL_ONLY_v2.csv ({len(agricultural)} crops)")

# Update still need review file
needs_review = mapping[(mapping['HRL_Code'].isna()) & (~mapping['Is_Excluded'])].copy()
if len(needs_review) > 0:
    needs_review.to_csv('pre_process_scripts/GSA_codes_STILL_NEED_REVIEW_v2.csv', index=False)
    print(f"⚠ Saved: pre_process_scripts/GSA_codes_STILL_NEED_REVIEW_v2.csv ({len(needs_review)} codes)")
    
    if len(needs_review) <= 20:
        print("\nRemaining unmapped crops:")
        for _, row in needs_review.iterrows():
            eng = f"({row['English_Name']})" if pd.notna(row['English_Name']) else ""
            print(f"  - {row['DESC_SUOLO']} {eng}")
else:
    print("✅ All agricultural crops now mapped!")

# Update summary
hrl_summary = mapping[mapping['HRL_Code'].notna()].groupby('HRL_Code').agg({
    'COD_SUOLO': 'count',
    'HRL_Name': 'first'
}).reset_index()
hrl_summary.columns = ['HRL_Code', 'Number_of_GSA_Codes', 'HRL_Name']
hrl_summary = hrl_summary.sort_values('HRL_Code')
hrl_summary.to_csv('pre_process_scripts/HRL_summary_v2.csv', index=False)
print("✓ Saved: pre_process_scripts/HRL_summary_v2.csv")

print("\n" + "=" * 80)
print("MANUAL CORRECTIONS COMPLETE!")
print("=" * 80)
print("\nYou can now apply this mapping to your geopackage!")
print("The mapping includes:")
print("  ✓ All 17 specific HRL crop classes (1110-2320)")
print("  ✓ Unclassified categories (3100, 3200)")
print("  ✓ Manual corrections for herbs, vegetables, fruits, nuts")
print("=" * 80)