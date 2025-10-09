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
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px

print("Libraries loaded!")

# %%
# Matplotlib example
data = pd.DataFrame({
    'x': [1, 2, 3, 4, 5],
    'y': [2, 4, 6, 8, 10]
})

plt.figure(figsize=(10, 6))
plt.plot(data['x'], data['y'], marker='o')
plt.title('My Plot')
plt.xlabel('X axis')
plt.ylabel('Y axis')
plt.grid(True)
plt.show()

# %%
# Plotly interactive plot
fig = px.scatter(data, x='x', y='y', title='Interactive Plot')
fig.show()

# %%
# GeoPandas map example (when you have geodata)
# world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
# world.plot(figsize=(15, 10))
# plt.title('World Map')
# plt.show()



