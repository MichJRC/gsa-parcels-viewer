#!/usr/bin/env python3
"""
GSA Parcels vs HRL Crop Type Comparison
Web application with raster tile overlay
"""

from flask import Flask, jsonify, render_template_string, request, send_from_directory
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import box
import numpy as np
from functools import lru_cache
import time
import warnings
import gc
import os
warnings.filterwarnings('ignore')

try:
    import rasterio
    from rasterio.mask import mask
    from rasterio.warp import transform_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    print("⚠️  Warning: rasterio not installed - raster comparison disabled")

app = Flask(__name__)

# Global variables
gdf_global = None
raster_path = None
raster_crs = None
cod_suolo_colors = None

# Region bounds - adjusted to match tile coverage
# Tiles cover Northern Italy (approximately)
REGION_BOUNDS = {
    'north': 45.5,
    'south': 43.5,
    'east': 12.5,
    'west': 11.0
}

def load_parcel_data(file_path, crop_to_region=False):
    """Load and prepare parcel data"""
    global gdf_global, cod_suolo_colors
    
    print("🌾 Loading GSA Parcels Data...")
    gdf = gpd.read_file(file_path)
    print(f"   Loaded {len(gdf):,} total parcels")
    
    if gdf.crs.to_epsg() != 4326:
        print("   Converting to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    print(f"   Bounds: ({gdf.total_bounds[0]:.3f}, {gdf.total_bounds[1]:.3f}) to ({gdf.total_bounds[2]:.3f}, {gdf.total_bounds[3]:.3f})")
    
    if crop_to_region:
        bbox_geom = box(REGION_BOUNDS['west'], REGION_BOUNDS['south'], 
                       REGION_BOUNDS['east'], REGION_BOUNDS['north'])
        gdf = gdf[gdf.geometry.intersects(bbox_geom)]
        print(f"   Filtered to {len(gdf):,} parcels in region")
    
    gdf.sindex
    
    if 'COD_SUOLO' in gdf.columns:
        cod_suolo_counts = gdf['COD_SUOLO'].value_counts()
        print(f"   Found {len(cod_suolo_counts)} unique COD_SUOLO codes")
        
        top_codes = cod_suolo_counts.head(25).index.tolist()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                  '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2',
                  '#AED6F1', '#F8B88B', '#ABEBC6', '#F5B7B1', '#D2B4DE',
                  '#FAD7A0', '#D5F4E6', '#FADBD8', '#E8DAEF', '#D6EAF8']
        cod_suolo_colors = {code: colors[i % len(colors)] for i, code in enumerate(top_codes)}
    else:
        cod_suolo_colors = {}
    
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    gdf_global = gdf
    print("✅ Parcel data loaded!")
    return gdf

def load_raster_data(file_path):
    """Load raster metadata"""
    global raster_path, raster_crs
    
    if not RASTERIO_AVAILABLE:
        print("⚠️  Skipping raster - rasterio not available")
        return None
    
    print("🗺️  Loading HRL raster metadata...")
    try:
        with rasterio.open(file_path) as src:
            raster_crs = src.crs
            print(f"   Shape: {src.shape}, CRS: {src.crs}")
        raster_path = file_path
        print("✅ Raster metadata loaded!")
        return True
    except Exception as e:
        print(f"❌ Error loading raster: {e}")
        return None

@lru_cache(maxsize=100)
def get_features_in_bbox(north, south, east, west, max_features=1000):
    """Get parcel features within bounding box"""
    bbox = box(west, south, east, north)
    
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
    """Extract raster statistics within bounding box"""
    if raster_path is None or not RASTERIO_AVAILABLE:
        return None
    
    try:
        bbox_width = abs(east - west)
        bbox_height = abs(north - south)
        approx_pixels = (bbox_width * 78000 / 10) * (bbox_height * 111000 / 10)
        
        if approx_pixels > 50_000_000:
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
            
            raster_bounds = src.bounds
            if (bbox_raster_crs[0] > raster_bounds.right or 
                bbox_raster_crs[2] < raster_bounds.left or
                bbox_raster_crs[1] > raster_bounds.top or
                bbox_raster_crs[3] < raster_bounds.bottom):
                return {
                    'distribution': {},
                    'total_pixels': 0,
                    'unique_codes': 0,
                    'skipped': True,
                    'reason': 'Outside raster coverage'
                }
            
            bbox_gdf = gpd.GeoDataFrame([1], geometry=[bbox_geom], crs='EPSG:4326')
            bbox_gdf = bbox_gdf.to_crs(src.crs)
            
            out_image, _ = mask(src, [bbox_gdf.geometry.iloc[0]], crop=True, all_touched=True)
            data = out_image[0]
            
            if data.size > 10_000_000:
                sample_rate = int(np.sqrt(data.size / 1_000_000))
                data = data[::sample_rate, ::sample_rate]
            
            data = data[(data > 0) & (data < 10000)]
            
            if data.size == 0:
                return {
                    'distribution': {},
                    'total_pixels': 0,
                    'unique_codes': 0,
                    'skipped': True,
                    'reason': 'No valid pixels'
                }
            
            unique, counts = np.unique(data, return_counts=True)
            
            if len(unique) > 25:
                top_indices = np.argsort(counts)[-25:]
                unique = unique[top_indices]
                counts = counts[top_indices]
            
            hrl_distribution = {int(code): int(count) for code, count in zip(unique, counts)}
            
            del data, out_image
            gc.collect()
            
            return {
                'distribution': hrl_distribution,
                'total_pixels': int(np.sum(counts)),
                'unique_codes': int(len(unique))
            }
            
    except Exception as e:
        print(f"Error in raster stats: {e}")
        return None

@app.route('/')
def index():
    """Main page"""
    # Center on actual tile coverage area
    # Based on tile coordinates: zoom 12, X: 2180, Y: 2617 (center)
    # This corresponds to Trentino-Alto Adige region (northern Italy)
    center_lat = 45.9
    center_lng = 11.8
    initial_zoom = 12  # Start at zoom level where tiles are visible
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>GSA Parcels vs HRL Comparison</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"/>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
    <style>
        body{margin:0;font-family:Arial,sans-serif}
        #container{display:flex;height:100vh}
        #map{flex:2}
        #sidebar{flex:1;padding:20px;background:#f5f5f5;overflow-y:auto}
        .info-box{background:white;padding:15px;margin-bottom:15px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
        .chart-container{height:350px;margin-top:10px}
        .loading{color:#666;font-style:italic}
        h2,h3{margin-top:0;color:#2c3e50}
        h3{font-size:16px}
        .comparison-header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:10px 15px;border-radius:8px;margin-bottom:15px}
        .metric{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #ecf0f1}
        .metric:last-child{border-bottom:none}
        .metric-label{font-weight:500;color:#7f8c8d}
        .metric-value{font-weight:bold;color:#2c3e50}
        .legend{background:white;padding:10px;border-radius:5px;margin-top:10px;max-height:400px;overflow-y:auto}
        .legend-item{display:flex;align-items:center;margin:5px 0;font-size:12px}
        .legend-color{width:20px;height:15px;margin-right:8px;border-radius:3px;flex-shrink:0}
        .warning{color:#e67e22;font-style:italic;font-size:12px}
        .custom-popup .leaflet-popup-content{margin:12px 16px;max-width:350px}
        .custom-popup .leaflet-popup-content-wrapper{border-radius:8px}
    </style>
</head>
<body>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h2>🌾 GSA vs HRL</h2>
            
            <div class="comparison-header">
                <h3 style="margin:0;color:white">📊 Parcels vs Raster Comparison</h3>
                <div style="font-size:12px;margin-top:5px;opacity:0.9">Vector GSA vs Satellite HRL</div>
            </div>
            
            <div class="info-box">
                <h3>Current View Statistics</h3>
                <div id="parcel-count" class="loading">Move map to load data...</div>
                <div id="raster-count"></div>
                <div id="zoom-warning" class="warning" style="margin-top:10px"></div>
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
                <h4 style="margin-top:0">🎨 COD_SUOLO Legend</h4>
                <div id="legend-content"></div>
            </div>
            
            <div class="info-box">
                <h4>💡 Info</h4>
                <ul style="font-size:13px;line-height:1.6;margin:10px 0;padding-left:20px">
                    <li><strong>{{ parcel_count }}</strong> parcels loaded</li>
                    <li>🎨 Map colors by <strong>COD_SUOLO</strong></li>
                    <li>📊 Pie chart shows GSA declarations</li>
                    <li>⚖️ Comparison uses <strong>HRL codes</strong></li>
                    <li>🗺️ Toggle HRL raster overlay (top-right)</li>
                    <li>🔍 Zoom 10-14 for best raster visibility</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        var map=L.map('map').setView([{{center_lat}},{{center_lng}}],{{initial_zoom}});
        
        var baseLayers={
            "OpenStreetMap":L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}),
            "Satellite (ESRI)":L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'© Esri'}),
            "Satellite (Google)":L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',{attribution:'© Google'})
        };
        
        baseLayers["OpenStreetMap"].addTo(map);
        
        var parcelLayer=L.layerGroup().addTo(map);
        
        var hrlRasterLayer=L.tileLayer('/data/hrl_tiles/hrl_tiles_mosaic/{z}/{x}/{y}.png',{
            attribution:'HRL Crop Type 2021',
            opacity:0.7,
            minZoom:10,
            maxZoom:14
        });
        
        L.control.layers(baseLayers,{
            "Parcels":parcelLayer,
            "HRL Raster Classification":hrlRasterLayer
        },{position:'topright'}).addTo(map);
        
        var codSuoloColors={{cod_suolo_colors|safe}};
        
        function updateLegend(topCodes){
            var html='';
            topCodes.slice(0,20).forEach(function(item){
                var code=item[0],desc=item[2]||'Unknown';
                var shortDesc=desc.length>30?desc.substring(0,30)+'...':desc;
                html+=`<div class="legend-item"><div class="legend-color" style="background-color:${codSuoloColors[code]||'#888'}"></div><span><strong>${code}:</strong> ${shortDesc}</span></div>`;
            });
            document.getElementById('legend-content').innerHTML=html;
        }
        
        function updateMapData(){
            var bounds=map.getBounds(),zoom=map.getZoom();
            
            var zoomWarning=document.getElementById('zoom-warning');
            if(zoom<11){
                zoomWarning.innerHTML='⚠️ Zoom to level 11+ for raster comparison';
            }else{
                zoomWarning.innerHTML='';
            }
            
            document.getElementById('parcel-count').innerHTML='<span class="loading">Loading...</span>';
            
            var maxFeatures=zoom>12?2000:zoom>10?1000:500;
            
            fetch(`/api/features?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&max_features=${maxFeatures}`)
                .then(r=>{
                    if(!r.ok)throw new Error(`HTTP ${r.status}`);
                    return r.json();
                })
                .then(data=>{
                    if(data.error){
                        document.getElementById('parcel-count').innerHTML=`Error: ${data.error}`;
                        return;
                    }
                    
                    parcelLayer.clearLayers();
                    
                    document.getElementById('parcel-count').innerHTML=
                        `<div class="metric"><span class="metric-label">📍 Parcels:</span><span class="metric-value">${data.stats.total_parcels.toLocaleString()}</span></div>
                        <div class="metric"><span class="metric-label">📏 Zoom:</span><span class="metric-value">${zoom}</span></div>
                        <div class="metric"><span class="metric-label">🎯 Unique HRL:</span><span class="metric-value">${(data.stats.hrl_distribution_with_names||[]).length}</span></div>`;
                    
                    if(data.stats.raster_stats&&!data.stats.raster_stats.skipped){
                        document.getElementById('raster-count').innerHTML=
                            `<div class="metric"><span class="metric-label">🗺️ Pixels:</span><span class="metric-value">${data.stats.raster_stats.total_pixels.toLocaleString()}</span></div>
                            <div class="metric"><span class="metric-label">🎯 Unique HRL:</span><span class="metric-value">${data.stats.raster_stats.unique_codes}</span></div>`;
                        document.getElementById('raster-status').innerHTML='';
                    }else if(data.stats.raster_stats&&data.stats.raster_stats.skipped){
                        document.getElementById('raster-count').innerHTML='';
                        document.getElementById('raster-status').innerHTML=`<p class="warning">⚠️ ${data.stats.raster_stats.reason}</p>`;
                    }else{
                        document.getElementById('raster-count').innerHTML='';
                        document.getElementById('raster-status').innerHTML='';
                    }
                    
                    data.features.forEach(function(feature){
                        var codSuolo=feature.properties.COD_SUOLO;
                        var color=codSuoloColors[codSuolo]||'#888';
                        
                        var layer=L.geoJSON(feature,{
                            style:{fillColor:color,weight:1,opacity:1,color:'white',fillOpacity:0.6}
                        });
                        
                        var popupContent=`
                            <div style="font-family:Arial,sans-serif">
                                <h4 style="margin:0 0 15px 0;color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:5px">Agricultural Parcel</h4>
                                
                                <div style="background:#e8f5e9;padding:12px;border-radius:6px;margin-bottom:12px;border-left:4px solid #27ae60">
                                    <h5 style="margin:0 0 8px 0;color:#27ae60;font-size:14px">📋 GSA Declaration</h5>
                                    <div style="margin:6px 0"><strong>COD_SUOLO:</strong> <span style="color:#27ae60;font-weight:bold;font-size:16px">${feature.properties.COD_SUOLO||'N/A'}</span></div>
                                    <div style="margin:6px 0"><strong>DESC_SUOLO:</strong><br><span style="color:#2c3e50;font-size:14px">${feature.properties.DESC_SUOLO||'N/A'}</span></div>
                                    <div style="margin:6px 0"><strong>HRL Code (GSA):</strong> <span style="color:#d68910;font-weight:bold;font-size:15px">${feature.properties.hrl_code||'N/A'}</span></div>
                                </div>
                                
                                <div style="background:#fff3e0;padding:12px;border-radius:6px;border-left:4px solid #f39c12">
                                    <h5 style="margin:0 0 8px 0;color:#d68910;font-size:14px">🗺️ HRL Crop Type (from Raster)</h5>
                                    <div style="margin:6px 0"><em style="color:#7f8c8d;font-size:12px">Toggle "HRL Raster Classification" to visualize</em></div>
                                </div>
                                
                                <hr style="margin:12px 0;border:none;border-top:1px solid #ecf0f1">
                                <div style="font-size:11px;color:#7f8c8d">ID: ${feature.properties.id||feature.properties.gsa_par_id||'N/A'}</div>
                            </div>
                        `;
                        
                        layer.bindPopup(popupContent,{maxWidth:400,className:'custom-popup'});
                        parcelLayer.addLayer(layer);
                    });
                    
                    updateCharts(data.stats);
                    
                    if(data.stats.cod_suolo_with_desc)updateLegend(data.stats.cod_suolo_with_desc);
                })
                .catch(error=>{
                    console.error('Error:',error);
                    document.getElementById('parcel-count').innerHTML=`Error: ${error.message}`;
                });
        }
        
        function updateCharts(stats){
            if(stats.cod_suolo_distribution&&Object.keys(stats.cod_suolo_distribution).length>0){
                var codSuoloData=Object.entries(stats.cod_suolo_distribution).sort((a,b)=>b[1].count-a[1].count).slice(0,15);
                
                Plotly.newPlot('parcel-chart',[{
                    values:codSuoloData.map(d=>d[1].count),
                    labels:codSuoloData.map(d=>{
                        var desc=d[1].desc;
                        return desc.length>25?desc.substring(0,25)+'...':desc;
                    }),
                    text:codSuoloData.map(d=>`${d[0]}: ${d[1].desc}`),
                    type:'pie',
                    textinfo:'label+percent',
                    textposition:'inside',
                    hoverinfo:'text+value+percent',
                    marker:{colors:codSuoloData.map(d=>codSuoloColors[d[0]]||'#888')}
                }],{margin:{t:20,b:20,l:20,r:20},showlegend:false});
            }
            
            if(stats.raster_stats&&stats.raster_stats.distribution&&
                Object.keys(stats.raster_stats.distribution).length>0&&
                stats.hrl_distribution_with_names&&stats.hrl_distribution_with_names.length>0){
                createComparisonChart(stats.hrl_distribution_with_names,stats.raster_stats.distribution);
            }else{
                document.getElementById('comparison-chart').innerHTML='<p style="text-align:center;color:#95a5a6;padding:40px">Zoom in to level 11+ for HRL comparison</p>';
            }
        }
        
        function createComparisonChart(parcelHrlData,rasterDist){
            var parcelMap={},nameMap={};
            parcelHrlData.forEach(function(item){parcelMap[item[0]]=item[1];nameMap[item[0]]=item[2];});
            
            var allCodes=new Set([...Object.keys(parcelMap),...Object.keys(rasterDist)]);
            var sortedCodes=Array.from(allCodes).sort((a,b)=>(parcelMap[b]||0)-(parcelMap[a]||0)).slice(0,10);
            
            var parcelCounts=sortedCodes.map(code=>parcelMap[code]||0);
            var rasterCounts=sortedCodes.map(code=>rasterDist[code]||0);
            
            var parcelTotal=parcelCounts.reduce((a,b)=>a+b,0);
            var rasterTotal=rasterCounts.reduce((a,b)=>a+b,0);
            
            var parcelPct=parcelCounts.map(c=>parcelTotal>0?(c/parcelTotal*100).toFixed(1):0);
            var rasterPct=rasterCounts.map(c=>rasterTotal>0?(c/rasterTotal*100).toFixed(1):0);
            
            var labels=sortedCodes.map(function(code){
                var name=nameMap[code]||'Unknown';
                return name.length>30?name.substring(0,30)+'...':name;
            });
            
            Plotly.newPlot('comparison-chart',[
                {x:labels,y:parcelPct,name:'GSA Parcels (%)',type:'bar',marker:{color:'#4ECDC4'},
                 text:sortedCodes.map(c=>`HRL ${c}`),hovertemplate:'%{text}<br>%{y}%<extra></extra>'},
                {x:labels,y:rasterPct,name:'Raster Pixels (%)',type:'bar',marker:{color:'#FF6B6B'},
                 text:sortedCodes.map(c=>`HRL ${c}`),hovertemplate:'%{text}<br>%{y}%<extra></extra>'}
            ],{barmode:'group',margin:{t:20,b:100,l:50,r:20},xaxis:{tickangle:-45},yaxis:{title:'Percentage (%)'},legend:{x:0.6,y:1}});
        }
        
        map.on('moveend',updateMapData);
        map.on('zoomend',updateMapData);
        updateMapData();
    </script>
</body>
</html>
    """
    
    return render_template_string(html, 
        parcel_count=f"{len(gdf_global):,}",
        cod_suolo_colors=json.dumps(cod_suolo_colors),
        center_lat=center_lat,
        center_lng=center_lng,
        initial_zoom=initial_zoom
    )

@app.route('/api/features')
def get_features():
    """API endpoint for features and statistics"""
    try:
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))
        max_features = int(request.args.get('max_features', 1000))
        
        gdf_filtered = get_features_in_bbox(north, south, east, west, max_features)
        
        if len(gdf_filtered) > 0:
            columns_to_keep = [col for col in ['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name', 'id', 'gsa_par_id', 'geometry'] 
                             if col in gdf_filtered.columns]
            features = json.loads(gdf_filtered[columns_to_keep].to_json())['features']
        else:
            features = []
        
        stats = {'total_parcels': len(gdf_filtered)}
        
        if len(gdf_filtered) > 0 and 'COD_SUOLO' in gdf_filtered.columns and 'DESC_SUOLO' in gdf_filtered.columns:
            cod_suolo_grouped = gdf_filtered.groupby(['COD_SUOLO', 'DESC_SUOLO']).size().reset_index(name='count')
            stats['cod_suolo_distribution'] = {
                str(row['COD_SUOLO']): {'count': int(row['count']), 'desc': str(row['DESC_SUOLO'])} 
                for _, row in cod_suolo_grouped.iterrows()
            }
            stats['cod_suolo_with_desc'] = [
                (str(row['COD_SUOLO']), int(row['count']), str(row['DESC_SUOLO'])) 
                for _, row in cod_suolo_grouped.sort_values('count', ascending=False).iterrows()
            ]
        else:
            stats['cod_suolo_distribution'] = {}
            stats['cod_suolo_with_desc'] = []
        
        if len(gdf_filtered) > 0 and 'hrl_code' in gdf_filtered.columns and 'hrl_name' in gdf_filtered.columns:
            hrl_grouped = gdf_filtered.groupby(['hrl_code', 'hrl_name']).size().reset_index(name='count').sort_values('count', ascending=False)
            stats['hrl_distribution_with_names'] = [
                (int(row['hrl_code']), int(row['count']), str(row['hrl_name'])) 
                for _, row in hrl_grouped.iterrows()
            ]
        else:
            stats['hrl_distribution_with_names'] = []
        
        raster_stats = get_raster_stats_in_bbox(north, south, east, west)
        if raster_stats:
            stats['raster_stats'] = raster_stats
        
        return jsonify({'features': features, 'stats': stats})
        
    except Exception as e:
        print(f"❌ Error in /api/features: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/raster_tile/<int:z>/<int:x>/<int:y>.png')
def get_raster_tile(z, x, y):
    """Serve pre-generated raster tiles"""
    # Get absolute path to tiles
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    tiles_base = os.path.join(repo_root, 'data', 'hrl_tiles', 'hrl_tiles_mosaic')
    
    tile_file = os.path.join(tiles_base, str(z), str(x), f'{y}.png')
    
    if os.path.exists(tile_file):
        tile_dir = os.path.join(tiles_base, str(z), str(x))
        return send_from_directory(tile_dir, f'{y}.png')
    else:
        return '', 404

if __name__ == '__main__':
    # Configuration - File paths (relative to repository root)
    # Get the directory where this script is located
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    REPO_ROOT = os.path.dirname(SCRIPT_DIR)
    
    GPKG_FILE = os.path.join(REPO_ROOT, "downloaded_data", "parcels_with_HRL_codes.gpkg")
    GEOTIFF_FILE = os.path.join(REPO_ROOT, "data", "hrl_tiles", "hrl_croptype_2021_mosaic_compress.tif")
    
    # Set to True to filter to specific region (faster loading)
    # Set to False to load all parcels
    CROP_TO_REGION = False
    
    print("=" * 60)
    print("🚀 GSA Parcels vs HRL Crop Type Comparison")
    print("=" * 60)
    
    try:
        # Load data
        load_parcel_data(GPKG_FILE, crop_to_region=CROP_TO_REGION)
        load_raster_data(GEOTIFF_FILE)
        
        print(f"\n✅ Ready to serve!")
        print(f"📊 Parcels: {len(gdf_global):,}")
        if raster_path:
            print(f"🗺️  Raster: Connected")
        print(f"🎨 HRL Tiles: data/hrl_tiles/hrl_tiles_mosaic (zoom 10-14)")
        print("=" * 60)
        print("\n💡 Usage Tips:")
        print("   - Open browser and go to http://localhost:5000")
        print("   - Toggle 'HRL Raster Classification' layer (top-right)")
        print("   - Zoom to levels 10-14 for best raster visibility")
        print("   - Zoom to level 11+ for raster comparison charts")
        print("   - Click parcels to see detailed information")
        print("=" * 60)
        
        # Start Flask server
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
        
    except FileNotFoundError as e:
        print(f"\n❌ File not found: {e}")
        print("\n💡 Make sure you've run ./setup.sh to download data!")
        print("   Or check that file paths in the script are correct.")
    except Exception as e:
        print(f"\n❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()