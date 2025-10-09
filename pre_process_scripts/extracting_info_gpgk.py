# %%

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas

# %%

gdf = gpd.read_file("/workspaces/gsa-parcels-viewer/downloaded_data/parcels_with_HRL_codes.gpkg")

# %%
col = gdf.columns
print(col)

# get the unique classes of hrl
unique_combinations = gdf[['hrl_code', 'hrl_name']].drop_duplicates()
print(f"Unique combinations:\n{unique_combinations}")

# %%
