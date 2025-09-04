# backend_display.py
from flask import Flask, render_template_string, Response
import requests

app = Flask(__name__)

PI_IP = "100.69.169.69" # STATIC IP of the Raspberry Pi
PORT = 5000
CAMERA_STREAM_URL = f"http://{PI_IP}:{PORT}/video_feed"

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head><title>Pi Camera</title></head>
            <body>
                <h1>Pi Camera Live-Stream</h1>
                <img src="/proxy_stream">
            </body>
        </html>
    ''')

@app.route('/proxy_stream')
def proxy_stream():
    def generate():
        try:
            with requests.get(CAMERA_STREAM_URL, stream=True, timeout=5) as r:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
        except requests.RequestException as e:
            print(f"[!] Error connecting to Pi: {e}")
            yield b'' # Yield empty bytes to keep the connection alive
    return Response(generate(), content_type='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
