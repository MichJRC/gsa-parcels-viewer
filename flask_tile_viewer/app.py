from flask import Flask, render_template, send_from_directory, jsonify, request
import os
import json
import pandas as pd
from shapely.geometry import box
from functools import lru_cache
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# Paths
TILE_DIR = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_tiles_mosaic'
GPKG_PATH = '/workspaces/gsa-parcels-viewer/downloaded_data/parcels_with_HRL_codes.gpkg'
GEOTIFF_PATH = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_croptype_2021_mosaic_compress.tif'

# Global variable for cached parcels
gdf_global = None

# Crop class mapping
CROP_CLASS_MAP = {
    0: 'Unmapped',
    1110: 'Wheat', 1120: 'Barley', 1130: 'Maize', 1140: 'Rice', 1150: 'Other cereals',
    1210: 'Fresh Vegetables', 1220: 'Dry pulses', 1310: 'Potatoes', 1320: 'Sugar Beet',
    1410: 'Sunflower', 1420: 'Soybeans', 1430: 'Rapeseed', 1440: 'Flax, cotton and hemp',
    2100: 'Grapes', 2200: 'Olives', 2310: 'Fruits', 2320: 'Nuts',
    3100: 'Unclassified arable crop', 3200: 'Unclassified permanent crop'
}

def load_parcels():
    """Load GeoPackage once at startup with optimizations"""
    global gdf_global
    
    print("\n" + "="*60)
    print("🌾 LOADING AGRICULTURAL PARCELS DATA")
    print("="*60)
    
    import geopandas as gpd
    
    print(f"📂 Reading: {GPKG_PATH}")
    gdf = gpd.read_file(GPKG_PATH)
    print(f"✓ Loaded {len(gdf):,} parcels")
    print(f"  CRS: {gdf.crs}")
    
    # Convert to WGS84 for web display
    if gdf.crs.to_epsg() != 4326:
        print("🔄 Converting to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    # Create spatial index for fast bbox queries
    print("🗂️  Creating spatial index...")
    gdf.sindex  # This creates the R-tree spatial index
    
    # Pre-compute centroids for faster filtering
    print("📍 Computing centroids...")
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    # Keep only necessary columns
    cols_to_keep = ['COD_SUOLO', 'DESC_SUOLO', 'hrl_code', 'hrl_name', 
                    'centroid_x', 'centroid_y', 'geometry']
    gdf = gdf[cols_to_keep]
    
    gdf_global = gdf
    print(f"✓ Data loaded and indexed successfully!")
    print("="*60 + "\n")
    
    return gdf

@lru_cache(maxsize=200)
def get_parcels_in_bbox(north, south, east, west, max_features=2000):
    """Get parcels within bounding box with caching"""
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
    
    # Further filter with actual geometry intersection
    bbox_geom = box(west, south, east, north)
    gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox_geom)]
    
    # Limit results for performance
    if len(gdf_filtered) > max_features:
        gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
    
    return gdf_filtered

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def tiles(z, x, y):
    """Serve tile images"""
    try:
        return send_from_directory(
            os.path.join(TILE_DIR, str(z), str(x)),
            f'{y}.png',
            mimetype='image/png'
        )
    except FileNotFoundError:
        return '', 404

@app.route('/api/parcels')
def get_parcels():
    """Get parcels in viewport - FAST with caching"""
    try:
        # Get bbox from query params (in WGS84)
        bbox_param = request.args.get('bbox')
        if not bbox_param:
            return jsonify({"error": "bbox parameter required"}), 400
        
        west, south, east, north = map(float, bbox_param.split(','))
        
        # Get zoom to determine max features
        zoom = request.args.get('zoom', type=int, default=12)
        max_features = 3000 if zoom > 13 else 2000 if zoom > 12 else 1000
        
        # Use cached function
        gdf_filtered = get_parcels_in_bbox(north, south, east, west, max_features)
        
        if len(gdf_filtered) == 0:
            return jsonify({"type": "FeatureCollection", "features": []})
        
        # Simplify geometries
        gdf_filtered = gdf_filtered.copy()
        gdf_filtered['geometry'] = gdf_filtered['geometry'].simplify(
            tolerance=0.00005, preserve_topology=True
        )
        
        # Convert to GeoJSON
        geojson = json.loads(gdf_filtered.to_json())
        
        print(f"✓ Returned {len(geojson['features'])} parcels (zoom {zoom})")
        
        return jsonify(geojson)
    
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcel/<int:parcel_id>/raster-class')
def get_parcel_raster_class(parcel_id):
    """Get raster classification for a specific parcel"""
    try:
        import rasterio
        from rasterio.mask import mask
        import numpy as np
        import geopandas as gpd
        
        # Get parcel (in WGS84)
        parcel = gdf_global.iloc[parcel_id]
        
        # Open raster to check CRS
        with rasterio.open(GEOTIFF_PATH) as src:
            # Convert parcel to raster CRS if needed
            if src.crs.to_epsg() != 4326:
                # Create GeoDataFrame with single parcel
                parcel_gdf = gpd.GeoDataFrame([parcel], geometry='geometry', crs='EPSG:4326')
                # Transform to raster CRS
                parcel_gdf = parcel_gdf.to_crs(src.crs)
                geometry = [parcel_gdf.iloc[0].geometry.__geo_interface__]
            else:
                geometry = [parcel.geometry.__geo_interface__]
            
            # Extract raster pixels
            out_image, out_transform = mask(src, geometry, crop=True, all_touched=False)
            pixels = out_image[0]
            pixels = pixels[pixels != 0]
            
            if len(pixels) == 0:
                return jsonify({"error": "No pixels found under this parcel"}), 404
            
            # Count pixel classes
            unique, counts = np.unique(pixels, return_counts=True)
            total_pixels = counts.sum()
            
            pixel_breakdown = []
            dominant_class = None
            max_count = 0
            
            for value, count in zip(unique, counts):
                crop_name = CROP_CLASS_MAP.get(int(value), f'Unknown ({value})')
                percentage = (count / total_pixels * 100)
                
                pixel_breakdown.append({
                    'class_value': int(value),
                    'class_name': crop_name,
                    'pixel_count': int(count),
                    'percentage': round(percentage, 1)
                })
                
                if count > max_count:
                    max_count = count
                    dominant_class = crop_name
            
            pixel_breakdown.sort(key=lambda x: x['pixel_count'], reverse=True)
            
            vector_class = parcel['hrl_name']
            agreement = (dominant_class == vector_class)
            
            return jsonify({
                'parcel_id': parcel_id,
                'vector_class': vector_class,
                'raster_dominant_class': dominant_class,
                'agreement': agreement,
                'total_pixels': int(total_pixels),
                'pixel_breakdown': pixel_breakdown,
                'purity': round((max_count / total_pixels * 100), 1)
            })
    
    except Exception as e:
        print(f"Error in raster extraction: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/viewport-stats')
def viewport_stats():
    """Calculate confusion matrix for viewport"""
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.mask import mask
        import numpy as np
        
        bbox = request.args.get('bbox')
        zoom = request.args.get('zoom', type=int)
        
        if not bbox or zoom < 12:
            return jsonify({"error": "zoom >= 12 required"}), 400
        
        west, south, east, north = map(float, bbox.split(','))
        
        # Get parcels in viewport
        gdf_filtered = get_parcels_in_bbox(north, south, east, west, max_features=500)
        
        if len(gdf_filtered) == 0:
            return jsonify({"error": "No parcels in viewport"}), 404
        
        # Initialize confusion matrix
        matrix = {}
        vector_classes = sorted(gdf_filtered['hrl_name'].dropna().unique())
        
        with rasterio.open(GEOTIFF_PATH) as src:
            for v_class in vector_classes:
                matrix[v_class] = {}
            
            processed = 0
            for idx, parcel in gdf_filtered.iterrows():
                if pd.isna(parcel['hrl_name']):
                    continue
                    
                vector_class = parcel['hrl_name']
                geometry = [parcel.geometry.__geo_interface__]
                
                try:
                    out_image, _ = mask(src, geometry, crop=True, all_touched=False)
                    pixels = out_image[0]
                    pixels = pixels[pixels != 0]
                    
                    if len(pixels) == 0:
                        continue
                    
                    unique, counts = np.unique(pixels, return_counts=True)
                    
                    for raster_value, count in zip(unique, counts):
                        raster_class = CROP_CLASS_MAP.get(int(raster_value), 'Unknown')
                        if raster_class not in matrix[vector_class]:
                            matrix[vector_class][raster_class] = 0
                        matrix[vector_class][raster_class] += int(count)
                    
                    processed += 1
                except:
                    continue
        
        # Calculate metrics
        total_pixels = sum(sum(row.values()) for row in matrix.values())
        if total_pixels == 0:
            return jsonify({"error": "No pixels extracted"}), 404
        
        correct_pixels = sum(matrix.get(cls, {}).get(cls, 0) for cls in vector_classes)
        overall_accuracy = (correct_pixels / total_pixels * 100)
        
        class_metrics = {}
        for cls in vector_classes:
            if cls not in matrix:
                continue
            vector_total = sum(matrix[cls].values())
            if vector_total == 0:
                continue
            correct = matrix[cls].get(cls, 0)
            producers_acc = (correct / vector_total * 100)
            
            class_metrics[cls] = {
                'producers_accuracy': round(producers_acc, 1),
                'total_pixels': vector_total,
                'correct_pixels': correct
            }
        
        return jsonify({
            'bbox': bbox,
            'zoom': zoom,
            'total_parcels': len(gdf_filtered),
            'processed_parcels': processed,
            'total_pixels': total_pixels,
            'correct_pixels': correct_pixels,
            'overall_accuracy': round(overall_accuracy, 1),
            'confusion_matrix': matrix,
            'class_metrics': class_metrics
        })
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/crop-classes')
def crop_classes():
    return jsonify(CROP_CLASS_MAP)

if __name__ == '__main__':
    # Check paths
    if not os.path.exists(GPKG_PATH):
        print(f"ERROR: GeoPackage not found: {GPKG_PATH}")
        exit(1)
    
    # Load data BEFORE starting server
    load_parcels()
    
    print("🚀 STARTING WEB SERVER")
    print("="*60)
    print(f"✓ Ready to serve {len(gdf_global):,} parcels")
    print("  Endpoints:")
    print("    - http://localhost:5000/")
    print("    - http://localhost:5000/api/parcels?bbox=...")
    print("    - http://localhost:5000/api/parcel/<id>/raster-class")
    print("    - http://localhost:5000/api/analysis/viewport-stats")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)