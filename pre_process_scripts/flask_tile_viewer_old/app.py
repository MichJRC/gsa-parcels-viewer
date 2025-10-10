from flask import Flask, render_template, send_from_directory
import os

app = Flask(__name__)

# path to tile directory
TILE_DIR = '/workspaces/gsa-parcels-viewer/data/hrl_tiles/hrl_tiles_mosaic'

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
        # Return 404 if tile doesn't exist
        return '', 404

if __name__ == '__main__':
    # Check if tile directory exists
    if not os.path.exists(TILE_DIR):
        print(f"WARNING: Tile directory not found: {TILE_DIR}")
        print("Please update TILE_DIR in the script to match your tiles location")
    else:
        print(f"Serving tiles from: {TILE_DIR}")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

