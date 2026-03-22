import os
import io
import json
import base64
import requests
import traceback
from flask import Flask, request, send_file, jsonify, Response

# Core Engines
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Inches

# MoviePy v2.0+ Modular Imports
from moviepy.VideoClip import ImageClip
from moviepy.audio.AudioClip import AudioFileClip

app = Flask(__name__)

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Note: Using the specific folder structure you requested
TEMPLATE_PATH = os.path.join(BASE_DIR, 'templates', 'tk_port.json')
POPPINS_PATH = os.path.join(BASE_DIR, 'assets', 'poppins.ttf')

def get_font(size):
    """Graceful font fallback: Poppins -> DejaVu -> Default"""
    try:
        return ImageFont.truetype(POPPINS_PATH, size=size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=size)
        except:
            return ImageFont.load_default()

def get_template():
    with open(TEMPLATE_PATH, 'r') as f:
        return json.load(f)

# --- RENDERING ENGINE ---
def draw_poster(user_data, template):
    """Common logic to create the PIL Image object"""
    bg_data = template['background']['base64']
    if "base64," in bg_data:
        bg_data = bg_data.split("base64,")[1]
    
    canvas = Image.open(io.BytesIO(base64.b64decode(bg_data))).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    for el in template['elements']:
        clean_key = el['name'].strip("{}")
        value = str(user_data.get(clean_key, el.get('placeholderText', '')))

        if el['type'] == 'text':
            font = get_font(int(el.get('fontSize', 40)))
            draw.text((el['x'], el['y']), value, fill=el.get('fill', '#FFFFFF'), font=font)

        elif el['type'] == 'image':
            img_url = user_data.get(clean_key)
            if img_url:
                resp = requests.get(img_url, timeout=10)
                overlay = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                overlay = overlay.resize((int(el['width']), int(el['height'])), Image.LANCZOS)
                canvas.paste(overlay, (int(el['x']), int(el['y'])), overlay)
    
    return canvas

# --- ROUTES ---

@app.route('/export/png', methods=['POST'])
def export_png():
    try:
        template = get_template()
        canvas = draw_poster(request.json, template)
        buf = io.BytesIO()
        canvas.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/pdf', methods=['POST'])
def export_pdf():
    try:
        template = get_template()
        user_data = request.json
        
        pdf = FPDF(orientation='P', unit='pt', format=(1080, 1920))
        pdf.add_page()
        
        # Save temp BG for FPDF
        bg_path = "/tmp/temp_bg.png"
        canvas = draw_poster(user_data, template)
        canvas.save(bg_path)
        pdf.image(bg_path, x=0, y=0, w=1080, h=1920)

        return Response(pdf.output(), mimetype="application/pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/export/video', methods=['POST'])
def export_video():
    clip = None
    try:
        template = get_template()
        user_data = request.json
        
        # 1. Generate the Frame
        frame_path = "/tmp/video_frame.png"
        canvas = draw_poster(user_data, template)
        canvas.save(frame_path)

        # 2. MoviePy v2.0 logic
        clip = ImageClip(frame_path).with_duration(5)
        
        audio_url = user_data.get('audio_url')
        if audio_url:
            audio_resp = requests.get(audio_url)
            with open("/tmp/temp_audio.mp3", "wb") as f:
                f.write(audio_resp.content)
            audio = AudioFileClip("/tmp/temp_audio.mp3")
            clip = clip.with_audio(audio)

        out_path = "/tmp/export_video.mp4"
        clip.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")
        
        return send_file(out_path, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
    finally:
        if clip: clip.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
