import os
import io
import uuid
from flask import Flask, request, send_file, jsonify
from rembg import remove, new_session
from PIL import Image, ImageOps
from colorthief import ColorThief

app = Flask(__name__)

# Pre-load the session to speed up subsequent requests on Leapcell
session = new_session()

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

@app.route('/process-image', methods=['POST'])
def process_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    target_size = int(request.form.get('size', 800))
    
    # 1. Read input and Remove Background
    input_data = file.read()
    # alpha_matting=True is essential for clean edges on electronics
    no_bg_bytes = remove(input_data, session=session, alpha_matting=True)
    
    # 2. Resize and Center (Lego-style Uniformity)
    subject_img = Image.open(io.BytesIO(no_bg_bytes)).convert("RGBA")
    
    # ImageOps.pad maintains aspect ratio and centers the product on a transparent canvas
    final_img = ImageOps.pad(subject_img, (target_size, target_size), color=(0, 0, 0, 0))
    
    # 3. Extract Colors (using the processed bytes)
    img_byte_arr = io.BytesIO()
    final_img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    ct = ColorThief(img_byte_arr)
    dominant = ct.get_color(quality=1)
    palette = ct.get_palette(color_count=5, quality=1)
    
    # 4. Save to /tmp for retrieval or send back directly
    output_filename = f"{uuid.uuid4()}.png"
    output_path = os.path.join('/tmp', output_filename)
    final_img.save(output_path)

    return jsonify({
        "status": "success",
        "download_url": f"/download/{output_filename}",
        "color_data": {
            "dominant_hex": rgb_to_hex(dominant),
            "palette_hex": [rgb_to_hex(c) for c in palette]
        }
    })

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_file(os.path.join('/tmp', filename), mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
