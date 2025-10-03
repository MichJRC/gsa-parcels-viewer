#!/usr/bin/env python3
"""
GSA Parcels vs HRL Crop Type Comparison - Ferrara Region
Optimized for hrl_code comparison
"""

from flask import Flask, jsonify, render_template_string, request, send_file
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import box
import numpy as np
from functools import lru_cache
import time
import warnings
import gc
import io
from PIL import Image
warnings.filterwarnings('ignore')

try:
    import rasterio
    from rasterio.mask import mask
    from rasterio.warp import transform_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("⚠️  Warning: rasterio not installed.")

app = Flask(__name__)

# Global variables
gdf_global = None
raster_path = None
raster_crs = None
cod_suolo_colors = None

# Ferrara region bounds - UPDATE THESE to match your actual data coverage!
# After running with CROP_TO_FERRARA = False, check the console output for
# "Data bounds (WGS84): ..." and update these values accordingly
FERRARA_BOUNDS = {
    'north': 45.447,   # Update with your max latitude
    'south': 43.994,   # Update with your min latitude
    'east': 12.568,    # Update with your max longitude
    'west': 10.903     # Update with your min longitude
}
# Example: If console shows "Data bounds (WGS84): (11.234, 44.567) to (12.789, 45.234)"
# Then update to: west=11.234, south=44.567, east=12.789, north=45.234

def load_parcel_data(file_path, crop_to_ferrara=True):
    """
    Load and prepare the GPKG data focused on Ferrara region
    """
    global gdf_global, cod_suolo_colors
    
    print("🌾 Loading GSA Parcels Data...")
    
    # Load all data first
    gdf = gpd.read_file(file_path)
    print(f"Loaded {len(gdf)} total parcels")
    
    # Check CRS and convert to WGS84 if needed
    if gdf.crs.to_epsg() != 4326:
        print(f"Converting from {gdf.crs} to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    # Show actual data bounds
    print(f"   Data bounds (WGS84): ({gdf.total_bounds[0]:.3f}, {gdf.total_bounds[1]:.3f}) to ({gdf.total_bounds[2]:.3f}, {gdf.total_bounds[3]:.3f})")
    
    # Filter to Ferrara region after loading if requested
    if crop_to_ferrara:
        print(f"📍 Filtering to Ferrara region: {FERRARA_BOUNDS}")
        
        # Create bbox and filter
        bbox_geom = box(FERRARA_BOUNDS['west'], FERRARA_BOUNDS['south'], 
                       FERRARA_BOUNDS['east'], FERRARA_BOUNDS['north'])
        
        # Check intersection
        gdf = gdf[gdf.geometry.intersects(bbox_geom)]
        print(f"   Kept {len(gdf)} parcels in Ferrara region")
        
        if len(gdf) == 0:
            print("⚠️  WARNING: No parcels found in the specified region!")
            print(f"   The Ferrara bbox might not match your data coverage.")
            print(f"   Set CROP_TO_FERRARA = False to load all data and explore")
            # Don't exit - continue with empty dataset so app can still run
    
    if len(gdf) == 0:
        print("⚠️  Creating empty GeoDataFrame to prevent crashes")
        # Create an empty geodataframe with expected columns
        gdf = gpd.GeoDataFrame(columns=['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name', 'geometry'], 
                              crs='EPSG:4326')
        cod_suolo_colors = {}
        gdf_global = gdf
        return gdf
    
    # Create spatial index
    print("Creating spatial index...")
    gdf.sindex
    
    # Analyze COD_SUOLO distribution for color mapping
    if 'COD_SUOLO' in gdf.columns:
        cod_suolo_counts = gdf['COD_SUOLO'].value_counts()
        print(f"Found {len(cod_suolo_counts)} unique COD_SUOLO codes")
        
        # Create color mapping for top codes
        top_codes = cod_suolo_counts.head(25).index.tolist()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                  '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
                  '#AED6F1', '#F8B88B', '#ABEBC6', '#F5B7B1', '#D2B4DE',
                  '#FAD7A0', '#D5F4E6', '#FADBD8', '#E8DAEF', '#D6EAF8']
        cod_suolo_colors = {code: colors[i % len(colors)] for i, code in enumerate(top_codes)}
    else:
        print("⚠️  Warning: COD_SUOLO column not found in data")
        cod_suolo_colors = {}
    
    # Check for required columns
    required_cols = ['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name']
    missing_cols = [col for col in required_cols if col not in gdf.columns]
    if missing_cols:
        print(f"⚠️  Warning: Missing columns: {missing_cols}")
        print(f"Available columns: {list(gdf.columns)}")
    
    # Add centroids for faster queries
    print("Computing centroids...")
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    gdf_global = gdf
    print(f"✅ Parcel data loaded successfully!")
    print(f"   Bounds: ({gdf.total_bounds[0]:.3f}, {gdf.total_bounds[1]:.3f}) to ({gdf.total_bounds[2]:.3f}, {gdf.total_bounds[3]:.3f})")
    return gdf

def load_raster_data(file_path, crop_to_ferrara=True):
    """
    Load GeoTIFF metadata and optionally crop to Ferrara region
    """
    global raster_path, raster_crs
    
    if not RASTERIO_AVAILABLE:
        print("⚠️  Skipping raster data - rasterio not available")
        return None
    
    print("🗺️  Loading HRL Crop Type GeoTIFF...")
    
    try:
        with rasterio.open(file_path) as src:
            raster_crs = src.crs
            
            print(f"Raster info:")
            print(f"  - CRS: {src.crs}")
            print(f"  - Shape: {src.shape}")
            print(f"  - Bounds: {src.bounds}")
            print(f"  - Resolution: {src.res}")
            print(f"  - NoData value: {src.nodata}")
            print(f"  - Data type: {src.dtypes[0]}")
            
            # Read a small sample to check data values
            sample_data = src.read(1, window=((0, 100), (0, 100)))
            unique_sample = np.unique(sample_data)
            print(f"  - Sample values (first 100x100): {unique_sample[:20]}")
            print(f"  - Sample min: {sample_data.min()}, max: {sample_data.max()}")
            
            # Check if Ferrara region intersects with raster
            ferrara_in_raster_crs = transform_bounds(
                'EPSG:4326', src.crs,
                FERRARA_BOUNDS['west'], FERRARA_BOUNDS['south'],
                FERRARA_BOUNDS['east'], FERRARA_BOUNDS['north']
            )
            print(f"  - Ferrara region in raster CRS: {ferrara_in_raster_crs}")
            
            # Check if it actually overlaps
            raster_bounds = src.bounds
            overlaps = not (ferrara_in_raster_crs[0] > raster_bounds.right or 
                          ferrara_in_raster_crs[2] < raster_bounds.left or
                          ferrara_in_raster_crs[1] > raster_bounds.top or
                          ferrara_in_raster_crs[3] < raster_bounds.bottom)
            
            if overlaps:
                print(f"  ✓ Ferrara region OVERLAPS with raster")
            else:
                print(f"  ⚠️  WARNING: Ferrara region does NOT overlap with raster!")
                print(f"     Raster covers: {raster_bounds}")
        
        raster_path = file_path
        print(f"✅ Raster metadata loaded successfully!")
        return True
        
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
    mask_filter = (
        (gdf_global['centroid_x'] >= west) & 
        (gdf_global['centroid_x'] <= east) &
        (gdf_global['centroid_y'] >= south) & 
        (gdf_global['centroid_y'] <= north)
    )
    
    gdf_subset = gdf_global[mask_filter]
    
    if len(gdf_subset) == 0:
        return gdf_subset
    
    gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox)]
    
    if len(gdf_filtered) > max_features:
        gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
    
    return gdf_filtered

def get_raster_stats_in_bbox(north, south, east, west):
    """
    Extract raster pixel statistics (hrl_code values) within bounding box
    """
    if raster_path is None or not RASTERIO_AVAILABLE:
        return None
    
    try:
        bbox_width = abs(east - west)
        bbox_height = abs(north - south)
        
        # Estimate pixels (10m resolution at ~45°N)
        approx_width_m = bbox_width * 78000
        approx_height_m = bbox_height * 111000
        approx_pixels = (approx_width_m / 10) * (approx_height_m / 10)
        
        print(f"🔍 Raster query - Est. pixels: {approx_pixels:.0f}")
        
        MAX_PIXELS = 50_000_000
        
        if approx_pixels > MAX_PIXELS:
            print(f"⚠️  Too many pixels, skipping")
            return {
                'distribution': {},
                'total_pixels': 0,
                'unique_codes': 0,
                'skipped': True,
                'reason': 'Zoom in for raster comparison'
            }
        
        with rasterio.open(raster_path) as src:
            bbox_geom = box(west, south, east, north)
            
            bbox_raster_crs = transform_bounds('EPSG:4326', src.crs, west, south, east, north)
            
            print(f"📍 Raster CRS bbox: ({bbox_raster_crs[0]:.0f}, {bbox_raster_crs[1]:.0f}, {bbox_raster_crs[2]:.0f}, {bbox_raster_crs[3]:.0f})")
            
            # Check intersection
            raster_bounds = src.bounds
            if (bbox_raster_crs[0] > raster_bounds.right or 
                bbox_raster_crs[2] < raster_bounds.left or
                bbox_raster_crs[1] > raster_bounds.top or
                bbox_raster_crs[3] < raster_bounds.bottom):
                print(f"⚠️  Bbox outside raster coverage")
                return {
                    'distribution': {},
                    'total_pixels': 0,
                    'unique_codes': 0,
                    'skipped': True,
                    'reason': 'Area outside raster coverage'
                }
            
            # Transform bbox and read
            bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs='EPSG:4326')
            bbox_gdf = bbox_gdf.to_crs(src.crs)
            bbox_geom_transformed = bbox_gdf.geometry.iloc[0]
            
            print(f"🗺️  Reading raster data...")
            out_image, out_transform = mask(src, [bbox_geom_transformed], crop=True, all_touched=True)
            
            data = out_image[0]
            print(f"📦 Raw data shape: {data.shape}, size: {data.size:,} pixels")
            
            # Check what values we have before filtering
            print(f"   Data type: {data.dtype}")
            print(f"   Min value: {data.min()}, Max value: {data.max()}")
            print(f"   Unique values sample: {np.unique(data)[:20]}")
            
            # Downsample if needed
            if data.size > 10_000_000:
                sample_rate = int(np.sqrt(data.size / 1_000_000))
                data = data[::sample_rate, ::sample_rate]
                print(f"✓ Downsampled to {data.size:,} pixels")
            
            # Filter valid data - NoData is typically 0 for this dataset
            # Based on sample, valid values are in range 1000-2999 (HRL codes)
            nodata_value = src.nodata
            print(f"🚫 NoData value from file: {nodata_value}")
            
            # Count before filtering
            print(f"   Pixels before any filter: {data.size:,}")
            
            # Remove zeros (nodata) and negative values
            valid_before = data.size
            data = data[data > 0]
            print(f"   Pixels > 0: {data.size:,} (removed {valid_before - data.size:,} zeros/negatives)")
            
            # Show what's left
            if data.size > 0:
                print(f"   After zero filter - Min: {data.min()}, Max: {data.max()}")
                unique_vals = np.unique(data)
                print(f"   After zero filter - Unique values: {len(unique_vals)}")
                print(f"   Sample unique values: {unique_vals[:20]}")
            
            # Keep only reasonable HRL codes (1-9999 range, based on sample showing 1110, 1120, 2310, etc)
            # Don't filter too aggressively!
            valid_before_range = data.size
            data = data[(data >= 1) & (data < 10000)]
            
            print(f"   Pixels in range (1-9999): {data.size:,} (filtered {valid_before_range - data.size:,})")
            print(f"   ✅ Valid pixels: {data.size:,}")
            
            if data.size == 0:
                print(f"⚠️  No valid pixels found!")
                return {
                    'distribution': {},
                    'total_pixels': 0,
                    'unique_codes': 0,
                    'skipped': True,
                    'reason': 'No valid pixels in this area'
                }
            
            # Count unique hrl_code values
            unique, counts = np.unique(data, return_counts=True)
            
            print(f"✓ Found {len(unique)} unique HRL codes")
            print(f"  Top 5: {list(zip(unique[:5], counts[:5]))}")
            
            # Limit to top 25
            if len(unique) > 25:
                top_indices = np.argsort(counts)[-25:]
                unique = unique[top_indices]
                counts = counts[top_indices]
            
            # IMPORTANT: Convert numpy types to Python native types for JSON serialization
            hrl_distribution = {int(code): int(count) for code, count in zip(unique, counts)}
            
            del data, out_image
            gc.collect()
            
            result = {
                'distribution': hrl_distribution,
                'total_pixels': int(np.sum(counts)),
                'unique_codes': int(len(unique))
            }
            
            print(f"✅ Raster stats: {result['total_pixels']:,} pixels, {result['unique_codes']} codes")
            
            return result
        
    except Exception as e:
        print(f"❌ Error extracting raster stats: {e}")
        import traceback
        traceback.print_exc()
        return {
            'distribution': {},
            'total_pixels': 0,
            'unique_codes': 0,
            'error': str(e)
        }

@app.route('/')
def index():
    """
    Main page with interactive map and comparison
    """
    # Calculate center of Ferrara region
    center_lat = (FERRARA_BOUNDS['north'] + FERRARA_BOUNDS['south']) / 2
    center_lng = (FERRARA_BOUNDS['east'] + FERRARA_BOUNDS['west']) / 2
    
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>GSA Parcels vs HRL - Ferrara Region</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #container { display: flex; height: 100vh; }
        #map { flex: 2; }
        #sidebar { flex: 1; padding: 20px; background: #f5f5f5; overflow-y: auto; }
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
        .legend { background: white; padding: 10px; border-radius: 5px; margin-top: 10px; max-height: 400px; overflow-y: auto; }
        .legend-item { display: flex; align-items: center; margin: 5px 0; font-size: 12px; }
        .legend-color { width: 20px; height: 15px; margin-right: 8px; border-radius: 3px; flex-shrink: 0; }
        .warning { color: #e67e22; font-style: italic; font-size: 12px; }
        .custom-popup .leaflet-popup-content { margin: 12px 16px; max-width: 350px; }
        .custom-popup .leaflet-popup-content-wrapper { border-radius: 8px; }
    </style>
</head>
<body>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h2>🌾 Ferrara Region Analysis</h2>
            
            <div class="comparison-header">
                <h3 style="margin: 0; color: white;">📊 Parcels vs HRL Comparison</h3>
                <div style="font-size: 12px; margin-top: 5px; opacity: 0.9;">
                    Comparing hrl_code values
                </div>
            </div>
            
            <div class="info-box">
                <h3>Current View Statistics</h3>
                <div id="parcel-count" class="loading">Move map to load data...</div>
                <div id="raster-count"></div>
                <div id="zoom-warning" class="warning" style="margin-top: 10px;"></div>
            </div>
            
            <div class="info-box">
                <h3>📊 GSA Declared Crops (COD_SUOLO)</h3>
                <div id="parcel-chart" class="chart-container"></div>
            </div>
            
            <div class="info-box">
                <h3>⚖️ HRL Code Comparison: GSA vs Raster</h3>
                <div id="comparison-chart" class="chart-container"></div>
                <div id="raster-status"></div>
            </div>
            
            <div class="legend">
                <h4 style="margin-top: 0;">🎨 COD_SUOLO Legend</h4>
                <div id="legend-content"></div>
            </div>
            
            <div class="info-box">
                <h4>💡 Info</h4>
                <ul style="font-size: 13px; line-height: 1.6; margin: 10px 0; padding-left: 20px;">
                    <li><strong>{{ parcel_count }}</strong> parcels loaded</li>
                    <li>🎨 Map colors: <strong>COD_SUOLO</strong></li>
                    <li>📊 Pie chart: <strong>GSA declarations</strong></li>
                    <li>⚖️ Comparison: <strong>HRL codes</strong> (GSA vs Raster)</li>
                    <li>🔍 Zoom in (level 11+) for raster analysis</li>
                    <li>📍 Click parcels for details</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        var map = L.map('map').setView([{{ center_lat }}, {{ center_lng }}], 10);
        
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
        
        baseLayers["OpenStreetMap"].addTo(map);
        
        var parcelLayer = L.layerGroup().addTo(map);
        
        // Add HRL Raster layer (can be toggled on/off)
        var hrlRasterLayer = L.tileLayer('/raster_tile/{z}/{x}/{y}.png', {
            attribution: 'HRL Crop Type 2021',
            opacity: 0.7,
            maxZoom: 18
        });
        
        L.control.layers(baseLayers, {
            "Parcels": parcelLayer,
            "HRL Raster Classification": hrlRasterLayer
        }, {
            position: 'topright'
        }).addTo(map);
        
        var codSuoloColors = {{ cod_suolo_colors | safe }};
        
        function updateLegend(topCodes) {
            var legendContent = document.getElementById('legend-content');
            legendContent.innerHTML = '';
            
            topCodes.slice(0, 20).forEach(function(item) {
                var code = item[0];
                var desc = item[2] || 'Unknown';
                var div = document.createElement('div');
                div.className = 'legend-item';
                div.innerHTML = `
                    <div class="legend-color" style="background-color: ${codSuoloColors[code] || '#888888'}"></div>
                    <span><strong>${code}:</strong> ${desc.length > 30 ? desc.substring(0, 30) + '...' : desc}</span>
                `;
                legendContent.appendChild(div);
            });
        }
        
        function updateMapData() {
            var bounds = map.getBounds();
            var zoom = map.getZoom();
            
            var zoomWarning = document.getElementById('zoom-warning');
            if (zoom < 11) {
                zoomWarning.innerHTML = '⚠️ Zoom to level 11+ for raster comparison';
            } else {
                zoomWarning.innerHTML = '';
            }
            
            document.getElementById('parcel-count').innerHTML = '<span class="loading">Loading...</span>';
            
            var maxFeatures = zoom > 12 ? 2000 : zoom > 10 ? 1000 : 500;
            
            fetch(`/api/features?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&max_features=${maxFeatures}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Received data:', data);
                    
                    if (data.error) {
                        console.error('API error:', data.error);
                        document.getElementById('parcel-count').innerHTML = `Error: ${data.error}`;
                        return;
                    }
                    
                    parcelLayer.clearLayers();
                    
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
                            <span class="metric-label">🎯 Unique hrl_codes:</span>
                            <span class="metric-value">${Object.keys(data.stats.hrl_distribution || {}).length}</span>
                        </div>`;
                    
                    if (data.stats.raster_stats && !data.stats.raster_stats.skipped) {
                        document.getElementById('raster-count').innerHTML = 
                            `<div class="metric">
                                <span class="metric-label">🗺️ Raster Pixels:</span>
                                <span class="metric-value">${data.stats.raster_stats.total_pixels.toLocaleString()}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">🎯 Unique hrl_codes:</span>
                                <span class="metric-value">${data.stats.raster_stats.unique_codes}</span>
                            </div>`;
                        document.getElementById('raster-status').innerHTML = '';
                    } else if (data.stats.raster_stats && data.stats.raster_stats.skipped) {
                        document.getElementById('raster-count').innerHTML = '';
                        document.getElementById('raster-status').innerHTML = 
                            `<p class="warning">⚠️ ${data.stats.raster_stats.reason}</p>`;
                    } else {
                        document.getElementById('raster-count').innerHTML = '';
                        document.getElementById('raster-status').innerHTML = 
                            '<p class="warning">⚠️ Raster unavailable</p>';
                    }
                    
                    data.features.forEach(function(feature) {
                        var codSuolo = feature.properties.COD_SUOLO;
                        var color = codSuoloColors[codSuolo] || '#888888';
                        
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
                                <h4 style="margin: 0 0 15px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
                                    Agricultural Parcel
                                </h4>
                                
                                <div style="background: #e8f5e9; padding: 12px; border-radius: 6px; margin-bottom: 12px; border-left: 4px solid #27ae60;">
                                    <h5 style="margin: 0 0 8px 0; color: #27ae60; font-size: 14px;">
                                        📋 GSA Declaration
                                    </h5>
                                    
                                    <div style="margin: 6px 0;">
                                        <strong>COD_SUOLO:</strong> 
                                        <span style="color: #27ae60; font-weight: bold; font-size: 16px;">${feature.properties.COD_SUOLO || 'N/A'}</span>
                                    </div>
                                    
                                    <div style="margin: 6px 0;">
                                        <strong>DESC_SUOLO:</strong><br>
                                        <span style="color: #2c3e50; font-size: 14px;">${feature.properties.DESC_SUOLO || 'N/A'}</span>
                                    </div>
                                    
                                    <div style="margin: 6px 0;">
                                        <strong>HRL Code (GSA):</strong> 
                                        <span style="color: #d68910; font-weight: bold; font-size: 15px;">${feature.properties.hrl_code || 'N/A'}</span>
                                    </div>
                                </div>
                                
                                <div style="background: #fff3e0; padding: 12px; border-radius: 6px; border-left: 4px solid #f39c12;">
                                    <h5 style="margin: 0 0 8px 0; color: #d68910; font-size: 14px;">
                                        🗺️ HRL Crop Type (from Raster)
                                    </h5>
                                    
                                    <div style="margin: 6px 0;">
                                        <em style="color: #7f8c8d; font-size: 12px;">
                                            Click and zoom in (level 13+) to see raster value at this location
                                        </em>
                                    </div>
                                </div>
                                
                                <hr style="margin: 12px 0; border: none; border-top: 1px solid #ecf0f1;">
                                
                                <div style="font-size: 11px; color: #7f8c8d;">
                                    Parcel ID: ${feature.properties.id || feature.properties.gsa_par_id || 'N/A'}
                                </div>
                            </div>
                        `;
                        
                        layer.bindPopup(popupContent, {
                            maxWidth: 400,
                            className: 'custom-popup'
                        });
                        
                        parcelLayer.addLayer(layer);
                    });
                    
                    updateCharts(data.stats);
                    
                    if (data.stats.cod_suolo_with_desc) {
                        updateLegend(data.stats.cod_suolo_with_desc);
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    console.error('Error stack:', error.stack);
                    document.getElementById('parcel-count').innerHTML = `Error loading data: ${error.message}`;
                });
        }
        
        function updateCharts(stats) {
            // GSA COD_SUOLO PIE CHART (what farmers declared)
            if (stats.cod_suolo_distribution && Object.keys(stats.cod_suolo_distribution).length > 0) {
                var codSuoloData = Object.entries(stats.cod_suolo_distribution)
                    .sort((a, b) => b[1].count - a[1].count)
                    .slice(0, 15);
                
                Plotly.newPlot('parcel-chart', [{
                    values: codSuoloData.map(d => d[1].count),
                    labels: codSuoloData.map(d => {
                        var desc = d[1].desc;
                        return desc.length > 25 ? desc.substring(0, 25) + '...' : desc;
                    }),
                    text: codSuoloData.map(d => `${d[0]}: ${d[1].desc}`),
                    type: 'pie',
                    textinfo: 'label+percent',
                    textposition: 'inside',
                    hoverinfo: 'text+value+percent',
                    marker: {
                        colors: codSuoloData.map(d => codSuoloColors[d[0]] || '#888888')
                    }
                }], {
                    margin: {t: 20, b: 20, l: 20, r: 20},
                    showlegend: false
                });
            }
            
            // HRL Code comparison: GSA declarations vs Raster pixels
            if (stats.raster_stats && stats.raster_stats.distribution && 
                Object.keys(stats.raster_stats.distribution).length > 0 &&
                stats.hrl_distribution_with_names && stats.hrl_distribution_with_names.length > 0) {
                
                createComparisonChart(stats.hrl_distribution_with_names, stats.raster_stats.distribution);
            } else {
                document.getElementById('comparison-chart').innerHTML = 
                    '<p style="text-align: center; color: #95a5a6; padding: 40px;">Zoom in to level 11+ to view HRL code comparison</p>';
            }
        }
        
        function createComparisonChart(parcelHrlData, rasterDist) {
            // parcelHrlData is array of [hrl_code, count, hrl_name]
            // Create map for easy lookup
            var parcelMap = {};
            var nameMap = {};
            parcelHrlData.forEach(function(item) {
                parcelMap[item[0]] = item[1];
                nameMap[item[0]] = item[2];
            });
            
            // Get all unique codes from both datasets
            var allCodes = new Set([...Object.keys(parcelMap), ...Object.keys(rasterDist)]);
            var sortedCodes = Array.from(allCodes).sort((a, b) => {
                return (parcelMap[b] || 0) - (parcelMap[a] || 0);
            }).slice(0, 10);
            
            var parcelCounts = sortedCodes.map(code => parcelMap[code] || 0);
            var rasterCounts = sortedCodes.map(code => rasterDist[code] || 0);
            
            var parcelTotal = parcelCounts.reduce((a, b) => a + b, 0);
            var rasterTotal = rasterCounts.reduce((a, b) => a + b, 0);
            
            var parcelPct = parcelCounts.map(c => parcelTotal > 0 ? (c / parcelTotal * 100).toFixed(1) : 0);
            var rasterPct = rasterCounts.map(c => rasterTotal > 0 ? (c / rasterTotal * 100).toFixed(1) : 0);
            
            // Create labels with HRL code and name
            var labels = sortedCodes.map(function(code) {
                var name = nameMap[code] || 'Unknown';
                return name.length > 30 ? name.substring(0, 30) + '...' : name;
            });
            
            Plotly.newPlot('comparison-chart', [
                {
                    x: labels,
                    y: parcelPct,
                    name: 'GSA Parcels (%)',
                    type: 'bar',
                    marker: {color: '#4ECDC4'},
                    text: sortedCodes.map(c => `HRL ${c}`),
                    hovertemplate: '%{text}<br>%{y}%<extra></extra>'
                },
                {
                    x: labels,
                    y: rasterPct,
                    name: 'Raster Pixels (%)',
                    type: 'bar',
                    marker: {color: '#FF6B6B'},
                    text: sortedCodes.map(c => `HRL ${c}`),
                    hovertemplate: '%{text}<br>%{y}%<extra></extra>'
                }
            ], {
                barmode: 'group',
                margin: {t: 20, b: 100, l: 50, r: 20},
                xaxis: {tickangle: -45},
                yaxis: {title: 'Percentage (%)'},
                legend: {x: 0.6, y: 1}
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
        cod_suolo_colors=json.dumps(cod_suolo_colors),
        center_lat=center_lat,
        center_lng=center_lng
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
            columns_to_keep = [col for col in ['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name', 'id', 'gsa_par_id', 'geometry'] 
                             if col in gdf_filtered.columns]
            gdf_simplified = gdf_filtered[columns_to_keep]
            features = json.loads(gdf_simplified.to_json())['features']
        else:
            features = []
        
        # Calculate statistics
        stats = {
            'total_parcels': len(gdf_filtered),
            'query_time': round(time.time() - start_time, 3)
        }
        
        # COD_SUOLO distribution with descriptions (for pie chart)
        if len(gdf_filtered) > 0 and 'COD_SUOLO' in gdf_filtered.columns and 'DESC_SUOLO' in gdf_filtered.columns:
            cod_suolo_grouped = gdf_filtered.groupby(['COD_SUOLO', 'DESC_SUOLO']).size().reset_index(name='count')
            cod_suolo_dict = {}
            for _, row in cod_suolo_grouped.iterrows():
                # Ensure all values are native Python types
                cod_suolo_dict[str(row['COD_SUOLO'])] = {
                    'count': int(row['count']),
                    'desc': str(row['DESC_SUOLO'])
                }
            stats['cod_suolo_distribution'] = cod_suolo_dict
            
            # Also keep list format for legend
            cod_suolo_list = cod_suolo_grouped.sort_values('count', ascending=False)
            stats['cod_suolo_with_desc'] = [
                (str(row['COD_SUOLO']), int(row['count']), str(row['DESC_SUOLO'])) 
                for _, row in cod_suolo_list.iterrows()
            ]
        else:
            stats['cod_suolo_distribution'] = {}
            stats['cod_suolo_with_desc'] = []
        
        # hrl_code distribution with names (for comparison chart)
        if len(gdf_filtered) > 0 and 'hrl_code' in gdf_filtered.columns and 'hrl_name' in gdf_filtered.columns:
            hrl_grouped = gdf_filtered.groupby(['hrl_code', 'hrl_name']).size().reset_index(name='count')
            hrl_grouped = hrl_grouped.sort_values('count', ascending=False)
            # Convert to list of tuples with native Python types: (hrl_code, count, hrl_name)
            stats['hrl_distribution_with_names'] = [
                (int(row['hrl_code']), int(row['count']), str(row['hrl_name'])) 
                for _, row in hrl_grouped.iterrows()
            ]
        else:
            stats['hrl_distribution_with_names'] = []
        
        # Get raster statistics for same bbox
        raster_stats = get_raster_stats_in_bbox(north, south, east, west)
        if raster_stats:
            stats['raster_stats'] = raster_stats
        
        return jsonify({
            'features': features,
            'stats': stats
        })
        
    except Exception as e:
        print(f"❌ Error in /api/features: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/raster_tile/<int:z>/<int:x>/<int:y>.png')
def get_raster_tile(z, x, y):
def get_raster_tile(z, x, y):
    """
    Serve raster tiles for Leaflet overlay
    Returns a PNG tile with HRL classification colors
    """
    if raster_path is None or not RASTERIO_AVAILABLE:
        # Return empty transparent tile
        return send_file(io.BytesIO(b''), mimetype='image/png'), 404
    
    try:
        import mercantile
        from rasterio.warp import transform_bounds, reproject, Resampling
        
        # Get tile bounds in WGS84
        tile_bounds = mercantile.bounds(x, y, z)
        
        with rasterio.open(raster_path) as src:
            # Transform tile bounds to raster CRS
            raster_bbox = transform_bounds(
                'EPSG:4326', src.crs,
                tile_bounds.west, tile_bounds.south,
                tile_bounds.east, tile_bounds.north
            )
            
            # Create window for this tile
            from rasterio.windows import from_bounds
            window = from_bounds(*raster_bbox, transform=src.transform)
            
            # Read data
            data = src.read(1, window=window)
            
            # Create colored image based on HRL codes
            tile_size = 256
            img = np.zeros((tile_size, tile_size, 4), dtype=np.uint8)
            
            # Resize data to tile size if needed
            if data.shape != (tile_size, tile_size):
                from scipy.ndimage import zoom
                zoom_factor = (tile_size / data.shape[0], tile_size / data.shape[1])
                data = zoom(data, zoom_factor, order=0)
            
            # Color mapping for HRL codes
            hrl_colors = {
                1110: (255, 235, 59),   # Yellow - Common wheat
                1120: (255, 193, 7),    # Amber - Durum wheat
                1130: (205, 220, 57),   # Lime - Barley
                1140: (251, 192, 45),   # Orange wheat
                1150: (244, 143, 177),  # Pink wheat
                1210: (156, 39, 176),   # Purple - Rye
                1220: (103, 58, 183),   # Deep purple
                1310: (63, 81, 181),    # Indigo - Oats
                1320: (33, 150, 243),   # Blue oats
                1410: (0, 188, 212),    # Cyan - Maize
                1420: (0, 150, 136),    # Teal maize
                1430: (76, 175, 80),    # Green maize
                1440: (139, 195, 74),   # Light green maize
                2100: (255, 87, 34),    # Deep orange - Rice
                2200: (121, 85, 72),    # Brown - Other cereals
                2310: (158, 158, 158),  # Gray - Legumes
                2320: (117, 117, 117),  # Dark gray
                3100: (255, 152, 0),    # Orange - Root crops
                3200: (255, 193, 7),    # Amber - Tubers
            }
            
            for hrl_code, color in hrl_colors.items():
                mask = data == hrl_code
                img[mask] = (*color, 180)  # RGB + alpha (semi-transparent)
            
            # Set zeros (nodata) to fully transparent
            img[data == 0] = (0, 0, 0, 0)
            
            # Convert to PIL Image and save to BytesIO
            pil_img = Image.fromarray(img, mode='RGBA')
            output = io.BytesIO()
            pil_img.save(output, format='PNG')
            output.seek(0)
            
            return send_file(output, mimetype='image/png')
            
    except Exception as e:
        print(f"Error generating tile {z}/{x}/{y}: {e}")
        # Return empty transparent tile on error
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        output = io.BytesIO()
        img.save(output, format='PNG')
        output.seek(0)
        return send_file(output, mimetype='image/png')
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
            columns_to_keep = [col for col in ['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name', 'id', 'gsa_par_id', 'geometry'] 
                             if col in gdf_filtered.columns]
            gdf_simplified = gdf_filtered[columns_to_keep]
            features = json.loads(gdf_simplified.to_json())['features']
        else:
            features = []
        
        # Calculate statistics
        stats = {
            'total_parcels': len(gdf_filtered),
            'query_time': round(time.time() - start_time, 3)
        }
        
        # COD_SUOLO distribution with descriptions (for pie chart)
        if len(gdf_filtered) > 0 and 'COD_SUOLO' in gdf_filtered.columns and 'DESC_SUOLO' in gdf_filtered.columns:
            cod_suolo_grouped = gdf_filtered.groupby(['COD_SUOLO', 'DESC_SUOLO']).size().reset_index(name='count')
            cod_suolo_dict = {}
            for _, row in cod_suolo_grouped.iterrows():
                # Ensure all values are native Python types
                cod_suolo_dict[str(row['COD_SUOLO'])] = {
                    'count': int(row['count']),
                    'desc': str(row['DESC_SUOLO'])
                }
            stats['cod_suolo_distribution'] = cod_suolo_dict
            
            # Also keep list format for legend
            cod_suolo_list = cod_suolo_grouped.sort_values('count', ascending=False)
            stats['cod_suolo_with_desc'] = [
                (str(row['COD_SUOLO']), int(row['count']), str(row['DESC_SUOLO'])) 
                for _, row in cod_suolo_list.iterrows()
            ]
        else:
            stats['cod_suolo_distribution'] = {}
            stats['cod_suolo_with_desc'] = []
        
        # hrl_code distribution with names (for comparison chart)
        if len(gdf_filtered) > 0 and 'hrl_code' in gdf_filtered.columns and 'hrl_name' in gdf_filtered.columns:
            hrl_grouped = gdf_filtered.groupby(['hrl_code', 'hrl_name']).size().reset_index(name='count')
            hrl_grouped = hrl_grouped.sort_values('count', ascending=False)
            # Convert to list of tuples with native Python types: (hrl_code, count, hrl_name)
            stats['hrl_distribution_with_names'] = [
                (int(row['hrl_code']), int(row['count']), str(row['hrl_name'])) 
                for _, row in hrl_grouped.iterrows()
            ]
        else:
            stats['hrl_distribution_with_names'] = []
        
        # Get raster statistics for same bbox
        raster_stats = get_raster_stats_in_bbox(north, south, east, west)
        if raster_stats:
            stats['raster_stats'] = raster_stats
        
        return jsonify({
            'features': features,
            'stats': stats
        })
        
    except Exception as e:
        print(f"❌ Error in /api/features: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Configuration
    GPKG_FILE = "downloaded_data/parcels_with_HRL_codes.gpkg"
    GEOTIFF_FILE = "data/hrl_tiles/hrl_croptype_2021_mosaic_compress.tif"
    
    # Set to False initially to see where your data actually is!
    # Then adjust FERRARA_BOUNDS to match your data coverage
    CROP_TO_FERRARA = False
    
    print("🚀 Starting GSA Parcels vs HRL Comparison - Ferrara Region")
    print("=" * 60)
    
    try:
        # Load parcel data
        load_parcel_data(GPKG_FILE, crop_to_ferrara=CROP_TO_FERRARA)
        
        # Load raster data
        load_raster_data(GEOTIFF_FILE, crop_to_ferrara=CROP_TO_FERRARA)
        
        print(f"\n✅ Ready to serve!")
        print(f"📊 Dataset: {len(gdf_global):,} parcels")
        if raster_path:
            print(f"🗺️  Raster: Ready for on-demand queries")
        if CROP_TO_FERRARA:
            print(f"📍 Region: Ferrara ({FERRARA_BOUNDS['south']:.3f}°, {FERRARA_BOUNDS['west']:.3f}) to ({FERRARA_BOUNDS['north']:.3f}°, {FERRARA_BOUNDS['east']:.3f})")
        else:
            print(f"📍 Region: Full dataset (no cropping)")
        print("=" * 60)
        print("\n💡 TIP: Raster comparison activates at zoom level 11+")
        print("💡 TIP: Check the terminal output to see data bounds")
        print("💡 TIP: Adjust FERRARA_BOUNDS in the code to match your data")
        print("=" * 60)
        
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()