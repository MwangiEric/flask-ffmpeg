import os
import io
import uuid
from flask import Flask, request, send_file, jsonify
from rembg import remove, new_session
from PIL import Image, ImageOps
from colorthief import ColorThief

app = Flask(__name__)

# Initialize the session once for the worker
# This downloads the u2net model to /home/user/.u2net on the first run
# Tip: Ensure Leapcell has enough disk space for the ~170MB model
try:
    session = new_session()
except Exception as e:
    print(f"Model initialization warning: {e}")
    session = None

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

@app.route('/process-image', methods=['POST'])
def process_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    # Default to 800px for catalog consistency
    target_size = int(request.form.get('size', 800))
    
    try:
        input_data = file.read()
        
        # 1. Background Removal
        # session=session reuses the loaded model for speed
        no_bg_bytes = remove(input_data, session=session, alpha_matting=True)
        
        # 2. Image Processing (Pillow)
        subject_img = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")
        
        # Maintain aspect ratio & center on transparent 800x800 canvas
        # This keeps Avechi/Kenyatronics listings looking uniform
        final_img = ImageOps.pad(subject_img, (target_size, target_size), color=(0, 0, 0, 0))
        
        # 3. Color Extraction (ColorThief)
        img_byte_arr = io.BytesIO()
        final_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        ct = ColorThief(img_byte_arr)
        dominant = ct.get_color(quality=1)
        # Get palette of 5 colors for UI accents
        palette = ct.get_palette(color_count=5, quality=1)
        
        # 4. Save & Cleanup
        output_filename = f"{uuid.uuid4()}.png"
        output_path = os.path.join('/tmp', output_filename)
        final_img.save(output_path)

        return jsonify({
            "status": "success",
            "file_id": output_filename,
            "download_url": f"/download/{output_filename}",
            "colors": {
                "dominant": rgb_to_hex(dominant),
                "palette": [rgb_to_hex(c) for c in palette]
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    path = os.path.join('/tmp', filename)
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    return jsonify({"error": "File expired or not found"}), 404

if __name__ == '__main__':
    # Local dev only; Leapcell uses Gunicorn
    app.run(host='0.0.0.0', port=8080)
