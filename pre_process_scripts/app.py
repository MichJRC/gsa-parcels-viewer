#!/usr/bin/env python3
"""
GSA Parcels vs HRL Crop Type Comparison
Flask backend with GeoPandas + Rasterio for GeoTIFF analysis
"""

from flask import Flask, jsonify, render_template_string, request
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import box
import numpy as np
from functools import lru_cache
import time
import warnings
warnings.filterwarnings('ignore')

# Import rasterio for GeoTIFF handling
try:
    import rasterio
    from rasterio.mask import mask
    from rasterio.windows import from_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("⚠️  Warning: rasterio not installed. GeoTIFF comparison will be disabled.")
    print("   Install with: pip install rasterio")

app = Flask(__name__)

# Global variables
gdf_global = None
raster_dataset = None
crop_code_mapping = None
cod_uso_colors = None

def load_parcel_data(file_path):
    """
    Load and prepare the new GPKG data with COD_USO codes
    """
    global gdf_global, crop_code_mapping, cod_uso_colors
    
    print("🌾 Loading GSA Parcels Data...")
    
    # Load data
    gdf = gpd.read_file(file_path)
    print(f"Loaded {len(gdf)} agricultural parcels")
    
    # Convert to WGS84 for web display
    if gdf.crs.to_epsg() != 4326:
        print("Converting to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    # Create spatial index
    print("Creating spatial index...")
    gdf.sindex
    
    # Analyze COD_USO distribution
    if 'COD_USO' in gdf.columns:
        cod_uso_counts = gdf['COD_USO'].value_counts()
        print(f"Found {len(cod_uso_counts)} unique COD_USO codes")
        
        # Create color mapping for top codes
        top_codes = cod_uso_counts.head(20).index.tolist()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                  '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
                  '#AED6F1', '#F8B88B', '#ABEBC6', '#F5B7B1', '#D2B4DE']
        cod_uso_colors = {code: colors[i % len(colors)] for i, code in enumerate(top_codes)}
    else:
        print("⚠️  Warning: COD_USO column not found in data")
        cod_uso_colors = {}
    
    # Add centroids for faster queries
    print("Computing centroids...")
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    gdf_global = gdf
    print(f"✅ Parcel data loaded successfully!")
    return gdf

def load_raster_data(file_path):
    """
    Load and prepare the GeoTIFF raster data
    """
    global raster_dataset
    
    if not RASTERIO_AVAILABLE:
        print("⚠️  Skipping raster data - rasterio not available")
        return None
    
    print("🗺️  Loading HRL Crop Type GeoTIFF...")
    
    try:
        # Open raster dataset (keep it open for fast queries)
        raster_dataset = rasterio.open(file_path)
        
        print(f"Raster info:")
        print(f"  - CRS: {raster_dataset.crs}")
        print(f"  - Shape: {raster_dataset.shape}")
        print(f"  - Bounds: {raster_dataset.bounds}")
        print(f"  - Resolution: {raster_dataset.res}")
        
        print(f"✅ Raster data loaded successfully!")
        return raster_dataset
        
    except Exception as e:
        print(f"❌ Error loading raster: {e}")
        return None

@lru_cache(maxsize=100)
def get_features_in_bbox(north, south, east, west, max_features=1000):
    """
    Get parcel features within bounding box
    """
    bbox = box(west, south, east, north)
    
    # Fast pre-filter using centroids
    mask = (
        (gdf_global['centroid_x'] >= west) & 
        (gdf_global['centroid_x'] <= east) &
        (gdf_global['centroid_y'] >= south) & 
        (gdf_global['centroid_y'] <= north)
    )
    
    gdf_subset = gdf_global[mask]
    
    if len(gdf_subset) == 0:
        return gdf_subset
    
    # Further filter with geometry intersection
    gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox)]
    
    # Limit results
    if len(gdf_filtered) > max_features:
        gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
    
    return gdf_filtered

def get_raster_stats_in_bbox(north, south, east, west):
    """
    Extract raster pixel statistics within bounding box
    Returns COD_USO distribution from the raster
    """
    if raster_dataset is None or not RASTERIO_AVAILABLE:
        return None
    
    try:
        # Create bounding box geometry
        bbox_geom = box(west, south, east, north)
        
        # Convert bbox to raster CRS if needed
        if raster_dataset.crs.to_epsg() != 4326:
            import geopandas as gpd
            bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs='EPSG:4326')
            bbox_gdf = bbox_gdf.to_crs(raster_dataset.crs)
            bbox_geom = bbox_gdf.geometry.iloc[0]
        
        # Read raster data for the bbox
        out_image, out_transform = mask(raster_dataset, [bbox_geom], crop=True, all_touched=True)
        
        # Get the data (first band)
        data = out_image[0]
        
        # Remove nodata values
        nodata_value = raster_dataset.nodata
        if nodata_value is not None:
            data = data[data != nodata_value]
        
        # Count unique values (COD_USO codes)
        unique, counts = np.unique(data, return_counts=True)
        
        # Create distribution dictionary
        cod_uso_distribution = {int(code): int(count) for code, count in zip(unique, counts)}
        
        return {
            'distribution': cod_uso_distribution,
            'total_pixels': int(data.size),
            'unique_codes': len(unique)
        }
        
    except Exception as e:
        print(f"Error extracting raster stats: {e}")
        return None

@app.route('/')
def index():
    """
    Main page with interactive map and comparison
    """
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>GSA Parcels vs HRL Crop Type Comparison</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #container { display: flex; height: 100vh; }
        #map { flex: 2; }
        #sidebar { flex: 1; padding: 20px; background: #f5f5f5; overflow-y: auto; }
        #stats { background: white; padding: 15px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .info-box { background: white; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .chart-container { height: 350px; margin-top: 10px; }
        .loading { color: #666; font-style: italic; }
        h2 { margin-top: 0; color: #2c3e50; }
        h3 { margin-top: 0; color: #34495e; font-size: 16px; }
        .comparison-header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 15px;
            border-radius: 8px;
            margin-bottom: 15px;
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0; 
            border-bottom: 1px solid #ecf0f1;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { font-weight: 500; color: #7f8c8d; }
        .metric-value { font-weight: bold; color: #2c3e50; }
        .legend { background: white; padding: 10px; border-radius: 5px; margin-top: 10px; }
        .legend-item { display: flex; align-items: center; margin: 5px 0; font-size: 13px; }
        .legend-color { width: 20px; height: 15px; margin-right: 8px; border-radius: 3px; }
        .raster-disabled { color: #e74c3c; font-style: italic; }
        .custom-popup .leaflet-popup-content { margin: 12px 16px; }
        .custom-popup .leaflet-popup-content-wrapper { border-radius: 8px; }
    </style>
</head>
<body>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h2>🌾 GSA Parcels vs HRL</h2>
            
            <div class="comparison-header">
                <h3 style="margin: 0; color: white;">📊 Comparison Dashboard</h3>
                <div style="font-size: 12px; margin-top: 5px; opacity: 0.9;">
                    Vector Parcels vs Raster Classification
                </div>
            </div>
            
            <div id="stats" class="info-box">
                <h3>Current View Statistics</h3>
                <div id="parcel-count" class="loading">Move map to load data...</div>
                <div id="raster-count"></div>
            </div>
            
            <div class="info-box">
                <h3>📈 Parcels COD_USO Distribution</h3>
                <div id="parcel-chart" class="chart-container"></div>
            </div>
            
            <div class="info-box">
                <h3>🗺️ Raster COD_USO Distribution</h3>
                <div id="raster-chart" class="chart-container"></div>
                <div id="raster-status"></div>
            </div>
            
            <div class="info-box">
                <h3>⚖️ Side-by-Side Comparison</h3>
                <div id="comparison-chart" class="chart-container"></div>
            </div>
            
            <div class="legend">
                <h4 style="margin-top: 0;">🏷️ Top COD_USO Codes</h4>
                <div id="legend-content"></div>
            </div>
            
            <div class="info-box">
                <h4>💡 About</h4>
                <ul style="font-size: 13px; line-height: 1.6;">
                    <li><strong>{{ parcel_count }}</strong> parcels in dataset</li>
                    <li>Parcels: Vector GSA data (polygons)</li>
                    <li>Raster: HRL Crop Type 2021 (pixels)</li>
                    <li>Both share <strong>COD_USO</strong> attribute</li>
                    <li>Click parcels for details</li>
                    <li>Charts update with map view</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        var map = L.map('map').setView([45.5, 9.5], 10);
        
        // Base layers
        var baseLayers = {
            "OpenStreetMap": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }),
            "Satellite (ESRI)": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri'
            }),
            "Satellite (Google)": L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                attribution: '© Google'
            })
        };
        
        baseLayers["Satellite (ESRI)"].addTo(map);
        
        var parcelLayer = L.layerGroup().addTo(map);
        
        L.control.layers(baseLayers, {"Parcels": parcelLayer}, {
            position: 'topright'
        }).addTo(map);
        
        var codUsoColors = {{ cod_uso_colors | safe }};
        var rasterAvailable = {{ raster_available | tojson }};
        
        function updateLegend(topCodes) {
            var legendContent = document.getElementById('legend-content');
            legendContent.innerHTML = '';
            
            topCodes.slice(0, 15).forEach(function(item) {
                var code = item[0];
                var div = document.createElement('div');
                div.className = 'legend-item';
                div.innerHTML = `
                    <div class="legend-color" style="background-color: ${codUsoColors[code] || '#888888'}"></div>
                    <span>Code ${code}: ${item[1].toLocaleString()} parcels</span>
                `;
                legendContent.appendChild(div);
            });
        }
        
        function updateMapData() {
            var bounds = map.getBounds();
            var zoom = map.getZoom();
            
            document.getElementById('parcel-count').innerHTML = '<span class="loading">Loading...</span>';
            
            var maxFeatures = zoom > 12 ? 2000 : zoom > 10 ? 1000 : 500;
            
            fetch(`/api/features?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&max_features=${maxFeatures}`)
                .then(response => response.json())
                .then(data => {
                    parcelLayer.clearLayers();
                    
                    // Update parcel stats
                    document.getElementById('parcel-count').innerHTML = 
                        `<div class="metric">
                            <span class="metric-label">📍 Parcels in View:</span>
                            <span class="metric-value">${data.stats.total_parcels.toLocaleString()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">📏 Zoom Level:</span>
                            <span class="metric-value">${zoom}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">🎯 Unique COD_USO:</span>
                            <span class="metric-value">${Object.keys(data.stats.cod_uso_distribution || {}).length}</span>
                        </div>`;
                    
                    // Update raster stats
                    if (data.stats.raster_stats) {
                        document.getElementById('raster-count').innerHTML = 
                            `<div class="metric">
                                <span class="metric-label">🗺️ Raster Pixels:</span>
                                <span class="metric-value">${data.stats.raster_stats.total_pixels.toLocaleString()}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">🎯 Unique COD_USO:</span>
                                <span class="metric-value">${data.stats.raster_stats.unique_codes}</span>
                            </div>`;
                        document.getElementById('raster-status').innerHTML = '';
                    } else {
                        document.getElementById('raster-count').innerHTML = '';
                        document.getElementById('raster-status').innerHTML = 
                            '<p class="raster-disabled">⚠️ Raster comparison unavailable</p>';
                    }
                    
                    // Add parcels to map
                    data.features.forEach(function(feature) {
                        var codUso = feature.properties.COD_USO;
                        var color = codUsoColors[codUso] || '#888888';
                        
                        var layer = L.geoJSON(feature, {
                            style: {
                                fillColor: color,
                                weight: 1,
                                opacity: 1,
                                color: 'white',
                                fillOpacity: 0.6
                            }
                        });
                        
                        var popupContent = `
                            <div style="font-family: Arial, sans-serif;">
                                <h4 style="margin: 0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
                                    Agricultural Parcel
                                </h4>
                                <div style="margin: 8px 0;">
                                    <strong>COD_USO:</strong> 
                                    <span style="color: #27ae60; font-weight: bold; font-size: 16px;">${codUso || 'N/A'}</span>
                                </div>
                                ${feature.properties.HRL_Code ? `
                                <div style="margin: 8px 0;">
                                    <strong>HRL Code:</strong> ${feature.properties.HRL_Code}
                                </div>` : ''}
                                <hr style="margin: 10px 0; border: none; border-top: 1px solid #ecf0f1;">
                                <div style="font-size: 11px; color: #7f8c8d;">
                                    ID: ${feature.properties.id || feature.properties.gsa_par_id || 'N/A'}
                                </div>
                            </div>
                        `;
                        
                        layer.bindPopup(popupContent, {
                            maxWidth: 300,
                            className: 'custom-popup'
                        });
                        
                        parcelLayer.addLayer(layer);
                    });
                    
                    updateCharts(data.stats);
                    
                    if (data.stats.cod_uso_distribution) {
                        var topCodes = Object.entries(data.stats.cod_uso_distribution)
                            .sort((a, b) => b[1] - a[1]);
                        updateLegend(topCodes);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('parcel-count').innerHTML = 'Error loading data';
                });
        }
        
        function updateCharts(stats) {
            // Parcel distribution
            if (stats.cod_uso_distribution && Object.keys(stats.cod_uso_distribution).length > 0) {
                var parcelData = Object.entries(stats.cod_uso_distribution)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 15);
                
                Plotly.newPlot('parcel-chart', [{
                    x: parcelData.map(d => `Code ${d[0]}`),
                    y: parcelData.map(d => d[1]),
                    type: 'bar',
                    marker: {
                        color: parcelData.map(d => codUsoColors[d[0]] || '#888888')
                    }
                }], {
                    margin: {t: 20, b: 60, l: 50, r: 20},
                    xaxis: {tickangle: -45}
                });
            }
            
            // Raster distribution
            if (stats.raster_stats && stats.raster_stats.distribution) {
                var rasterData = Object.entries(stats.raster_stats.distribution)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 15);
                
                Plotly.newPlot('raster-chart', [{
                    x: rasterData.map(d => `Code ${d[0]}`),
                    y: rasterData.map(d => d[1]),
                    type: 'bar',
                    marker: {
                        color: parcelData.map(d => codUsoColors[d[0]] || '#888888')
                    }
                }], {
                    margin: {t: 20, b: 60, l: 50, r: 20},
                    xaxis: {tickangle: -45},
                    yaxis: {title: 'Pixel Count'}
                });
                
                // Comparison chart
                createComparisonChart(stats.cod_uso_distribution, stats.raster_stats.distribution);
            } else {
                document.getElementById('raster-chart').innerHTML = 
                    '<p style="text-align: center; color: #e74c3c; padding: 40px;">Raster data not available</p>';
                document.getElementById('comparison-chart').innerHTML = '';
            }
        }
        
        function createComparisonChart(parcelDist, rasterDist) {
            // Get all unique codes from both datasets
            var allCodes = new Set([...Object.keys(parcelDist), ...Object.keys(rasterDist)]);
            var sortedCodes = Array.from(allCodes).sort((a, b) => {
                return (parcelDist[b] || 0) - (parcelDist[a] || 0);
            }).slice(0, 10);
            
            var parcelCounts = sortedCodes.map(code => parcelDist[code] || 0);
            var rasterCounts = sortedCodes.map(code => rasterDist[code] || 0);
            
            // Normalize to percentages for fair comparison
            var parcelTotal = parcelCounts.reduce((a, b) => a + b, 0);
            var rasterTotal = rasterCounts.reduce((a, b) => a + b, 0);
            
            var parcelPct = parcelCounts.map(c => (c / parcelTotal * 100).toFixed(1));
            var rasterPct = rasterCounts.map(c => (c / rasterTotal * 100).toFixed(1));
            
            Plotly.newPlot('comparison-chart', [
                {
                    x: sortedCodes.map(c => `Code ${c}`),
                    y: parcelPct,
                    name: 'Parcels (%)',
                    type: 'bar',
                    marker: {color: '#4ECDC4'}
                },
                {
                    x: sortedCodes.map(c => `Code ${c}`),
                    y: rasterPct,
                    name: 'Raster (%)',
                    type: 'bar',
                    marker: {color: '#FF6B6B'}
                }
            ], {
                barmode: 'group',
                margin: {t: 20, b: 60, l: 50, r: 20},
                xaxis: {tickangle: -45},
                yaxis: {title: 'Percentage (%)'},
                legend: {x: 0.7, y: 1}
            });
        }
        
        map.on('moveend', updateMapData);
        map.on('zoomend', updateMapData);
        
        updateMapData();
    </script>
</body>
</html>
    """
    
    return render_template_string(
        html_template,
        parcel_count=f"{len(gdf_global):,}",
        cod_uso_colors=json.dumps(cod_uso_colors),
        raster_available=raster_dataset is not None
    )

@app.route('/api/features')
def get_features():
    """
    API endpoint to get features and comparison statistics
    """
    try:
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))
        max_features = int(request.args.get('max_features', 1000))
        
        start_time = time.time()
        
        # Get parcel data
        gdf_filtered = get_features_in_bbox(north, south, east, west, max_features)
        
        # Convert to GeoJSON
        if len(gdf_filtered) > 0:
            # Keep relevant columns
            columns_to_keep = [col for col in ['COD_USO', 'HRL_Code', 'id', 'gsa_par_id', 'geometry'] 
                             if col in gdf_filtered.columns]
            gdf_simplified = gdf_filtered[columns_to_keep]
            features = json.loads(gdf_simplified.to_json())['features']
        else:
            features = []
        
        # Calculate parcel statistics
        stats = {
            'total_parcels': len(gdf_filtered),
            'query_time': round(time.time() - start_time, 3)
        }
        
        if len(gdf_filtered) > 0 and 'COD_USO' in gdf_filtered.columns:
            cod_uso_counts = gdf_filtered['COD_USO'].value_counts()
            stats['cod_uso_distribution'] = cod_uso_counts.to_dict()
        else:
            stats['cod_uso_distribution'] = {}
        
        # Get raster statistics for same bbox
        raster_stats = get_raster_stats_in_bbox(north, south, east, west)
        if raster_stats:
            stats['raster_stats'] = raster_stats
        
        return jsonify({
            'features': features,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Configuration - PATHS
    GPKG_FILE = "downloaded_data/parcels_with_HRL_codes.gpkg"  # parcel file
    GEOTIFF_FILE = "data/hrl_tiles/hrl_croptype_2021_mosaic_compress.tif"  # HRL raster file
    
    print("🚀 Starting GSA Parcels vs HRL Comparison App")
    print("=" * 60)
    
    try:
        # Load parcel data
        load_parcel_data(GPKG_FILE)
        
        # Load raster data (optional)
        load_raster_data(GEOTIFF_FILE)
        
        print(f"\n✅ Ready to serve!")
        print(f"📊 Dataset: {len(gdf_global):,} parcels")
        if raster_dataset:
            print(f"🗺️  Raster: {raster_dataset.shape[0]} x {raster_dataset.shape[1]} pixels")
        print("=" * 60)
        
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()