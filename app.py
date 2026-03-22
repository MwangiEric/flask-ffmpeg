import os
import io
import json
import base64
import requests
from flask import Flask, request, send_file, jsonify

# Core Engines
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
from pptx import Presentation
from pptx.util import Inches, Pt
from moviepy.editor import ImageClip, AudioFileClip

app = Flask(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, 'tk_port.json')
POPPINS_PATH = os.path.join(BASE_DIR, 'assets', 'poppins.ttf')

def get_font_path():
    return POPPINS_PATH if os.path.exists(POPPINS_PATH) else None

def get_json_template():
    with open(TEMPLATE_PATH, 'r') as f:
        return json.load(f)

# --- PDF GENERATION (FPDF) ---
def generate_pdf(user_data, template):
    pdf = FPDF(orientation='P', unit='pt', format=(1080, 1920))
    pdf.add_page()
    
    # Draw Background (temporary file needed for FPDF)
    bg_data = template['background']['base64'].split("base64,")[1]
    bg_path = "/tmp/bg_temp.png"
    with open(bg_path, "wb") as f:
        f.write(base64.b64decode(bg_data))
    pdf.image(bg_path, x=0, y=0, w=1080, h=1920)

    # Add Poppins if available
    font_p = get_font_path()
    if font_p:
        pdf.add_font('Poppins', '', font_p, uni=True)
        pdf.set_font('Poppins', '', 40)
    else:
        pdf.set_font("Arial", size=40)

    for el in template['elements']:
        val = str(user_data.get(el['name'].strip("{}"), el.get('placeholderText', '')))
        if el['type'] == 'text':
            pdf.text(el['x'], el['y'] + int(el['fontSize']), val)
            
    buf = io.BytesIO()
    pdf.output(dest='S').encode('latin-1') # Return as string buffer
    return pdf.output(dest='S')

# --- PPTX GENERATION (python-pptx) ---
def generate_pptx(user_data, template):
    prs = Presentation()
    # Set slide size to 1080x1920 (in pixels to inches conversion)
    prs.slide_width = Inches(11.25) 
    prs.slide_height = Inches(20)
    
    slide = prs.slides.add_slide(prs.slide_layouts[6]) # Blank layout
    
    for el in template['elements']:
        val = str(user_data.get(el['name'].strip("{}"), el.get('placeholderText', '')))
        if el['type'] == 'text':
            txBox = slide.shapes.add_textbox(Inches(el['x']/96), Inches(el['y']/96), Inches(4), Inches(1))
            tf = txBox.text_frame
            tf.text = val
    
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf

# --- VIDEO GENERATION (MoviePy) ---
def generate_video(image_stream, audio_url=None):
    # Create a 5-second clip from the generated PNG
    with Image.open(image_stream) as img:
        img.save("/tmp/frame.png")
    
    clip = ImageClip("/tmp/frame.png").set_duration(5)
    
    if audio_url:
        audio = AudioFileClip(audio_url)
        clip = clip.set_audio(audio)
    
    output_path = "/tmp/promo.mp4"
    # MoviePy uses the FFmpeg already on your Leapcell
    clip.write_videofile(output_path, fps=24, codec="libx264")
    return output_path

@app.route('/export/<fmt>', methods=['POST'])
def export_format(fmt):
    user_data = request.json
    template = get_json_template()

    if fmt == 'pdf':
        pdf_content = generate_pdf(user_data, template)
        return Response(pdf_content, mimetype="application/pdf")
    
    elif fmt == 'pptx':
        pptx_buf = generate_pptx(user_data, template)
        return send_file(pptx_buf, as_attachment=True, download_name="poster.pptx")

    elif fmt == 'video':
        # 1. Generate PNG first
        # (Reuse your existing PIL drawing logic here)
        # 2. Convert to Video
        video_path = generate_video("/tmp/last_generated.png", user_data.get('audio_url'))
        return send_file(video_path, as_attachment=True)

    return jsonify({"error": "Unsupported format"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
