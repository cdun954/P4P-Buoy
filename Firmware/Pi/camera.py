# pi_camera_server.py
from flask import Flask, Response
from picamera2 import Picamera2
from picamera2.allocators import MappedAllocator   # <— fallback allocator
import time

app = Flask(__name__)

picam2 = Picamera2(allocator=MappedAllocator())    # <— use fallback
video_config = picam2.create_video_configuration(
    main={"size": (640, 480), "format": "MJPEG"},
    controls={"FrameRate": 15, "AwbEnable": True, "AeEnable": True}
)
picam2.configure(video_config)
picam2.start()
time.sleep(0.5)

BOUNDARY = b"--frame"

def gen_frames():
    while True:
        jpeg = picam2.capture_buffer("main")
        yield (
            BOUNDARY + b"\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(jpeg)}\r\n".encode("ascii")
            + b"\r\n" + jpeg + b"\r\n"
        )

@app.route("/video_feed")
def video_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
