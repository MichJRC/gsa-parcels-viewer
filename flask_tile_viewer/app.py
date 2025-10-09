from flask import Flask, render_template, send_from_directory, jsonify, request
import os
import json
import pandas as pd

app = Flask(__name__)

# Paths
TILE_DIR = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_tiles_mosaic'
GPKG_PATH = '/workspaces/gsa-parcels-viewer/downloaded_data/parcels_with_HRL_codes.gpkg'
GEOTIFF_PATH = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_croptype_2021_mosaic_compress.tif'

# Crop class mapping (raster value -> crop name)
CROP_CLASS_MAP = {
    0: 'Unmapped',
    1110: 'Wheat',
    1120: 'Barley',
    1130: 'Maize',
    1140: 'Rice',
    1150: 'Other cereals',
    1210: 'Fresh Vegetables',
    1220: 'Dry pulses',
    1310: 'Potatoes',
    1320: 'Sugar Beet',
    1410: 'Sunflower',
    1420: 'Soybeans',
    1430: 'Rapeseed',
    1440: 'Flax, cotton and hemp',
    2100: 'Grapes',
    2200: 'Olives',
    2310: 'Fruits',
    2320: 'Nuts',
    3100: 'Unclassified arable crop',
    3200: 'Unclassified permanent crop'
}

# Color mapping (for reference)
CROP_COLORS = {
    0: [0, 0, 0, 0],
    1110: [255, 235, 59, 255],
    1120: [255, 193, 7, 255],
    1130: [205, 220, 57, 255],
    1140: [251, 192, 45, 255],
    1150: [244, 143, 177, 255],
    1210: [156, 39, 176, 255],
    1220: [103, 58, 183, 255],
    1310: [63, 81, 181, 255],
    1320: [33, 150, 243, 255],
    1410: [0, 188, 212, 255],
    1420: [0, 150, 136, 255],
    1430: [76, 175, 80, 255],
    1440: [139, 195, 74, 255],
    2100: [255, 87, 34, 255],
    2200: [121, 85, 72, 255],
    2310: [158, 158, 158, 255],
    2320: [117, 117, 117, 255],
    3100: [255, 152, 0, 255],
    3200: [255, 193, 7, 255]
}

@app.route('/')
def index():
    return render_template('map.html')

@app.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def tiles(z, x, y):
    """Serve tile images from the GDAL tiles directory"""
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
    """Get parcels in current viewport only"""
    try:
        import geopandas as gpd
        
        # Get bbox from query params
        bbox = request.args.get('bbox')
        
        if not bbox:
            return jsonify({"error": "bbox parameter required. Use: /api/parcels?bbox=minx,miny,maxx,maxy"}), 400
        
        minx, miny, maxx, maxy = map(float, bbox.split(','))
        
        print(f"\n=== Loading Parcels ===")
        print(f"BBox: {bbox}")
        
        # Read only parcels in bbox using spatial filter
        gdf = gpd.read_file(GPKG_PATH, bbox=(minx, miny, maxx, maxy))
        print(f"Loaded {len(gdf)} parcels in bbox")
        
        if len(gdf) == 0:
            return jsonify({
                "type": "FeatureCollection",
                "features": []
            })
        
        # Limit to reasonable number for display
        if len(gdf) > 5000:
            print(f"Too many parcels ({len(gdf)}), sampling 5000")
            gdf = gdf.sample(5000)
        
        # Convert to WGS84 if needed
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        
        # Simplify geometries for faster display
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0001, preserve_topology=True)
        
        # Convert to GeoJSON
        geojson = json.loads(gdf.to_json())
        print(f"Returning {len(geojson['features'])} features")
        
        return jsonify(geojson)
    
    except Exception as e:
        print(f"ERROR in /api/parcels: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/parcel/<int:parcel_id>/raster-class')
def get_parcel_raster_class(parcel_id):
    """Get raster classification for a specific parcel"""
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.mask import mask
        import numpy as np
        
        # Read the specific parcel
        gdf = gpd.read_file(GPKG_PATH)
        parcel = gdf[gdf.index == parcel_id].iloc[0]
        
        # Get parcel geometry
        geometry = [parcel.geometry.__geo_interface__]
        
        # Extract raster pixels under this parcel
        with rasterio.open(GEOTIFF_PATH) as src:
            # Ensure same CRS
            if gdf.crs != src.crs:
                gdf_temp = gdf[gdf.index == parcel_id].to_crs(src.crs)
                geometry = [gdf_temp.iloc[0].geometry.__geo_interface__]
            
            # Extract pixels
            out_image, out_transform = mask(src, geometry, crop=True)
            pixels = out_image[0]
            pixels = pixels[pixels != 0]  # Remove nodata
            
            if len(pixels) == 0:
                return jsonify({
                    "error": "No raster pixels found under this parcel",
                    "parcel_too_small": True
                })
            
            # Count pixel classes
            unique, counts = np.unique(pixels, return_counts=True)
            total_pixels = counts.sum()
            
            # Build classification breakdown
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
            
            # Sort by pixel count (descending)
            pixel_breakdown.sort(key=lambda x: x['pixel_count'], reverse=True)
            
            # Get vector class
            vector_class = parcel.get('hrl_name', 'Unknown')
            
            # Check agreement
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/viewport-stats')
def viewport_stats():
    """Calculate confusion matrix for visible parcels in viewport"""
    try:
        import geopandas as gpd
        import rasterio
        from rasterio.mask import mask
        from rasterio.windows import from_bounds
        import numpy as np
        
        bbox = request.args.get('bbox')
        zoom = request.args.get('zoom', type=int)
        
        if not bbox:
            return jsonify({"error": "bbox parameter required"}), 400
        
        # Only calculate if zoom is high enough
        if zoom < 12:
            return jsonify({
                "error": "Please zoom in for statistics (zoom >= 12)",
                "zoom_required": 12,
                "current_zoom": zoom
            })
        
        minx, miny, maxx, maxy = map(float, bbox.split(','))
        
        print(f"\n=== Viewport Stats Request ===")
        print(f"BBox: {bbox}")
        print(f"Zoom: {zoom}")
        
        # Limit area size to prevent overload
        area = (maxx - minx) * (maxy - miny)
        print(f"Area: {area} degrees²")
        if area > 0.1:  # ~100 km²
            return jsonify({
                "error": "Area too large. Please zoom in further.",
                "area_degrees": round(area, 4)
            })
        
        # Load parcels in bbox
        print("Loading GeoPackage...")
        gdf = gpd.read_file(GPKG_PATH)
        print(f"Total parcels in file: {len(gdf)}")
        
        # Filter by bbox
        gdf_filtered = gdf.cx[minx:maxx, miny:maxy]
        print(f"Parcels in viewport: {len(gdf_filtered)}")
        
        if len(gdf_filtered) == 0:
            return jsonify({
                "error": "No parcels found in this area",
                "total_parcels": 0
            })
        
        # Limit to reasonable number for performance
        if len(gdf_filtered) > 500:
            print(f"Too many parcels, sampling 500")
            gdf_filtered = gdf_filtered.sample(500)
        
        # Initialize confusion matrix
        matrix = {}
        vector_classes = sorted(gdf_filtered['hrl_name'].dropna().unique())
        print(f"Vector classes found: {vector_classes}")
        
        with rasterio.open(GEOTIFF_PATH) as src:
            print(f"Raster CRS: {src.crs}")
            print(f"GDF CRS: {gdf_filtered.crs}")
            
            # Ensure same CRS
            if gdf_filtered.crs != src.crs:
                print("Converting CRS...")
                gdf_filtered = gdf_filtered.to_crs(src.crs)
                # Recalculate bbox in raster CRS
                minx, miny, maxx, maxy = gdf_filtered.total_bounds
            
            # Get all raster classes in area (sample, not full read)
            print("Sampling raster values...")
            window = from_bounds(minx, miny, maxx, maxy, src.transform)
            raster_data = src.read(1, window=window)
            raster_classes = sorted(np.unique(raster_data[raster_data != 0]))
            print(f"Raster classes in area: {len(raster_classes)} unique values")
            
            # Initialize matrix
            for v_class in vector_classes:
                matrix[v_class] = {}
                for r_value in raster_classes:
                    r_class = CROP_CLASS_MAP.get(int(r_value), f'Unknown ({r_value})')
                    matrix[v_class][r_class] = 0
            
            # Process each parcel
            processed = 0
            for idx, parcel in gdf_filtered.iterrows():
                if pd.isna(parcel['hrl_name']):
                    continue
                    
                vector_class = parcel['hrl_name']
                geometry = [parcel.geometry.__geo_interface__]
                
                try:
                    # Extract pixels under parcel
                    out_image, out_transform = mask(src, geometry, crop=True, all_touched=False)
                    pixels = out_image[0]
                    pixels = pixels[pixels != 0]
                    
                    if len(pixels) == 0:
                        continue
                    
                    # Count raster classes
                    unique, counts = np.unique(pixels, return_counts=True)
                    
                    for raster_value, count in zip(unique, counts):
                        raster_class = CROP_CLASS_MAP.get(int(raster_value), f'Unknown ({raster_value})')
                        if raster_class in matrix[vector_class]:
                            matrix[vector_class][raster_class] += int(count)
                    
                    processed += 1
                
                except Exception as e:
                    print(f"Error processing parcel {idx}: {e}")
                    continue
            
            print(f"Successfully processed {processed} parcels")
        
        # Calculate metrics
        total_pixels = sum(sum(row.values()) for row in matrix.values())
        print(f"Total pixels: {total_pixels}")
        
        if total_pixels == 0:
            return jsonify({
                "error": "No pixels extracted from parcels",
                "total_parcels": len(gdf_filtered),
                "processed_parcels": processed
            })
        
        correct_pixels = sum(
            matrix.get(cls, {}).get(cls, 0) 
            for cls in set(matrix.keys()) | set(
                rclass for row in matrix.values() for rclass in row.keys()
            )
        )
        
        overall_accuracy = (correct_pixels / total_pixels * 100) if total_pixels > 0 else 0
        
        # Per-class metrics
        class_metrics = {}
        for cls in vector_classes:
            if cls not in matrix:
                continue
            vector_total = sum(matrix[cls].values())
            if vector_total == 0:
                continue
            correct = matrix[cls].get(cls, 0)
            
            producers_acc = (correct / vector_total * 100) if vector_total > 0 else 0
            
            class_metrics[cls] = {
                'producers_accuracy': round(producers_acc, 1),
                'total_pixels': vector_total,
                'correct_pixels': correct
            }
        
        print(f"Overall accuracy: {overall_accuracy:.1f}%")
        print("=== Request Complete ===\n")
        
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
        print(f"\nERROR in viewport_stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/crop-classes')
def crop_classes():
    """Get crop class mapping"""
    return jsonify(CROP_CLASS_MAP)

@app.route('/api/raster/info')
def raster_info():
    """Get raster metadata"""
    try:
        import rasterio
        
        with rasterio.open(GEOTIFF_PATH) as src:
            return jsonify({
                'crs': str(src.crs),
                'bounds': list(src.bounds),
                'resolution': list(src.res),
                'width': src.width,
                'height': src.height,
                'nodata': src.nodata
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Check paths
    if not os.path.exists(TILE_DIR):
        print(f"WARNING: Tile directory not found: {TILE_DIR}")
    else:
        print(f"✓ Tiles directory: {TILE_DIR}")
    
    if not os.path.exists(GPKG_PATH):
        print(f"WARNING: GeoPackage not found: {GPKG_PATH}")
    else:
        print(f"✓ GeoPackage: {GPKG_PATH}")
    
    if not os.path.exists(GEOTIFF_PATH):
        print(f"WARNING: GeoTIFF not found: {GEOTIFF_PATH}")
    else:
        print(f"✓ GeoTIFF: {GEOTIFF_PATH}")
    
    print("\nEndpoints available:")
    print("  - http://localhost:5000/")
    print("  - http://localhost:5000/api/parcels")
    print("  - http://localhost:5000/api/parcel/<id>/raster-class")
    print("  - http://localhost:5000/api/analysis/viewport-stats")
    print("  - http://localhost:5000/api/crop-classes")
    
    app.run(debug=True, host='0.0.0.0', port=5000)