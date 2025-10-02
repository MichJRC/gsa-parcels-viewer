import geopandas as gpd
import matplotlib.pyplot as plt

df = gpd.read_file("downloaded_data/parcels_with_HRL_codes.gpkg")
geo = df[['hrl_code','geometry']].copy()
geoLatLong = geo.to_crs(4326)

geoLatLong['Location'] = geoLatLong.centroid

geoLatLong["Lat"] = geoLatLong.Location.y  # Simpler syntax
geoLatLong["Long"] = geoLatLong.Location.x

# Use scatter instead of plot
plt.figure(figsize=(10, 8))  # Optional: makes the plot larger
plt.scatter(geoLatLong["Long"], geoLatLong["Lat"], c='darkgreen', marker='p', s=20)
plt.xlabel('Longitude')  # Fixed: Long on x-axis
plt.ylabel('Latitude')   # Fixed: Lat on y-axis
plt.xlim(9, 14)   # Longitude range
plt.ylim(42, 47) 
plt.title('Location Plot')
plt.grid(True, alpha=0.3)  # Optional: adds a grid
plt.savefig('pre_process_scripts/plot.png', dpi=150, bbox_inches='tight')
plt.close()  # Good practice to close the figure
print("Plot saved!")