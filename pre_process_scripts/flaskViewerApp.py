#!/usr/bin/env python3
"""
Flask app with dynamic parcel loading based on viewport
"""

from flask import Flask, jsonify, render_template_string, request
import geopandas as gpd
import json
from shapely.geometry import box
import warnings

warnings.filterwarnings('ignore')

app = Flask(__name__)

# Global variable for data
gdf_global = None

def load_data(file_path):
    """Load and filter shapefile"""
    global gdf_global
    
    print("=" * 50)
    print("Loading shapefile...")
    gdf = gpd.read_file(file_path)
    
    original_count = len(gdf)
    print(f"Original parcels: {original_count:,}")
    
    # Filter out tiny artifacts (< 10 m²)
    gdf = gdf[gdf.geometry.area > 10]
    filtered_count = len(gdf)
    
    print(f"After filtering: {filtered_count:,}")
    print(f"Removed: {original_count - filtered_count} artifacts")
    
    # Convert to WGS84 for web display
    if gdf.crs.to_epsg() != 4326:
        print("Converting to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    # Create spatial index for fast queries
    print("Creating spatial index...")
    gdf.sindex
    
    # Add centroids for faster filtering
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    gdf_global = gdf
    print("=" * 50)
    return gdf

@app.route('/')
def index():
    """Main page with map"""
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Agricultural Parcels Viewer</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #map { height: 100vh; width: 100%; }
        .info-box {
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 1000;
            max-width: 300px;
        }
        .info-box h3 { margin: 0 0 10px 0; }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            z-index: 2000;
            display: none;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="info-box">
        <h3>Agricultural Parcels</h3>
        <p><strong>Total parcels:</strong> {{ total_parcels }}</p>
        <p><strong>Visible:</strong> <span id="visible-count">0</span></p>
        <p><strong>Zoom level:</strong> <span id="zoom-level">10</span></p>
        <p style="font-size: 12px; color: #666; margin-top: 10px;">
            Pan and zoom to load parcels dynamically
        </p>
    </div>
    <div class="loading" id="loading">Loading parcels...</div>

    <script>
        // Initialize map centered on Northern Italy
        var map = L.map('map').setView([45.5, 9.5], 10);
        
        // Add base layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Layer for parcels
        var parcelLayer = L.layerGroup().addTo(map);
        
        // Function to load parcels based on current view
        function loadParcels() {
            var bounds = map.getBounds();
            var zoom = map.getZoom();
            
            // Update zoom display
            document.getElementById('zoom-level').textContent = zoom;
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            
            // Determine max features based on zoom
            var maxFeatures = zoom > 12 ? 2000 : zoom > 10 ? 1000 : 500;
            
            // Fetch parcels for current viewport
            fetch(`/api/parcels?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&max=${maxFeatures}`)
                .then(response => response.json())
                .then(data => {
                    // Clear existing parcels
                    parcelLayer.clearLayers();
                    
                    // Update visible count
                    document.getElementById('visible-count').textContent = data.count.toLocaleString();
                    
                    // Add new parcels
                    L.geoJSON(data.geojson, {
                        style: function(feature) {
                            return {
                                fillColor: '#3388ff',
                                weight: 1,
                                opacity: 1,
                                color: 'white',
                                fillOpacity: 0.6
                            };
                        },
                        onEachFeature: function(feature, layer) {
                            var props = feature.properties;
                            var popup = '<div style="max-width: 250px;">';
                            popup += '<h4 style="margin: 0 0 10px 0;">Parcel Info</h4>';
                            popup += '<strong>Crop:</strong> ' + (props.DESC_COLT || 'N/A') + '<br>';
                            popup += '<strong>Soil Code:</strong> ' + (props.COD_SUOLO || 'N/A') + '<br>';
                            popup += '<strong>Soil Desc:</strong> ' + (props.DESC_SUOLO || 'N/A') + '<br>';
                            popup += '<strong>Area:</strong> ' + (props.SUP_APPEZ || 'N/A') + ' ha<br>';
                            popup += '<strong>Province:</strong> ' + (props.SIGLA_PROV || 'N/A');
                            popup += '</div>';
                            layer.bindPopup(popup);
                        }
                    }).addTo(parcelLayer);
                    
                    // Hide loading
                    document.getElementById('loading').style.display = 'none';
                })
                .catch(error => {
                    console.error('Error loading parcels:', error);
                    document.getElementById('loading').style.display = 'none';
                });
        }
        
        // Load parcels on map move/zoom
        map.on('moveend', loadParcels);
        map.on('zoomend', loadParcels);
        
        // Initial load
        loadParcels();
    </script>
</body>
</html>
    """
    
    return render_template_string(
        html,
        total_parcels=f"{len(gdf_global):,}"
    )

@app.route('/api/parcels')
def get_parcels():
    """API endpoint to get parcels in bounding box"""
    try:
        # Get bounding box parameters
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))
        max_features = int(request.args.get('max', 1000))
        
        # Create bounding box
        bbox = box(west, south, east, north)
        
        # Fast pre-filter using centroids
        mask = (
            (gdf_global['centroid_x'] >= west) & 
            (gdf_global['centroid_x'] <= east) &
            (gdf_global['centroid_y'] >= south) & 
            (gdf_global['centroid_y'] <= north)
        )
        
        gdf_subset = gdf_global[mask]
        
        # Further filter with actual geometry intersection
        if len(gdf_subset) > 0:
            gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox)]
        else:
            gdf_filtered = gdf_subset
        
        # Limit results
        if len(gdf_filtered) > max_features:
            gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
        
        # Select columns and convert to GeoJSON
        columns_to_keep = ['COD_SUOLO', 'DESC_SUOLO', 'DESC_COLT', 'SIGLA_PROV', 
                           'SUP_APPEZ', 'geometry']
        gdf_clean = gdf_filtered[columns_to_keep].copy()
        
        geojson = json.loads(gdf_clean.to_json())
        
        return jsonify({
            'geojson': geojson,
            'count': len(gdf_filtered)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Path to your shapefile
    SHAPEFILE = "downloaded_data/parcels_cleaned.gpkg"

    print("\nStarting Agricultural Parcels Viewer")
    print("=" * 50)
    
    # Load data
    load_data(SHAPEFILE)
    
    print("\nStarting Flask server...")
    print("Access via the PORTS tab in Codespaces")
    print("=" * 50)
    
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)