from flask import Flask, render_template, request, Response
import RPi.GPIO as GPIO
import time
import pyzbar.pyzbar as pyzbar
import cv2
import numpy as np
import os
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

app = Flask(__name__)

# GPIO Configuration
ENA = 17
ENB = 27
IN1 = 22
IN2 = 23
IN3 = 24
IN4 = 25

GPIO.setwarnings(False)  # Tắt cảnh báo GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(ENA, GPIO.OUT)
GPIO.setup(ENB, GPIO.OUT)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

pwm_a = GPIO.PWM(ENA, 100)
pwm_b = GPIO.PWM(ENB, 100)
pwm_a.start(0)
pwm_b.start(0)

# GStreamer Pipeline
pipeline_str = (
    "v4l2src device=/dev/video0 ! "
    "videoconvert ! "
    "videoscale ! "
    "capsfilter caps=video/x-raw,format=I420 ! "  # Thêm capsfilter
    "jpegenc ! "
    "rtpjpegpay ! "
    "udpsink host=192.168.1.100 port=5000"  # Thay đổi IP
)

# Initialize GStreamer
Gst.init(None)
pipeline = Gst.parse_launch(pipeline_str)

# Check if pipeline was created successfully
if pipeline is None:
    print("Could not create pipeline. Check your pipeline string!")
    exit()

# Setting pipeline state to playing
pipeline.set_state(Gst.State.PLAYING)
# Define a global variable to store the latest frame
global latest_frame
latest_frame = None

# Haar Cascade Classifier (Ensure the path is correct)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')  # Đảm bảo tệp này tồn tại

# Motor Control Functions (same as before)
def forward(speed):
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(speed)
    pwm_b.ChangeDutyCycle(speed)

def backward(speed):
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    pwm_a.ChangeDutyCycle(speed)
    pwm_b.ChangeDutyCycle(speed)

def left(speed):
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(0)
    pwm_b.ChangeDutyCycle(speed)

def right(speed):
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(speed)
    pwm_b.ChangeDutyCycle(0)

def stop():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    pwm_a.ChangeDutyCycle(0)
    pwm_b.ChangeDutyCycle(0)

# Global variable to store target coordinates
target_coordinates = None

# QR Code and Obstacle Detection
def process_frame():

    global latest_frame
    if latest_frame is None:
        return None, None, False # Return if no frame is available

    frame = latest_frame.copy() # Make a copy to avoid modifying the original

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # QR Code Decoding
    qr_data = None
    decoded_objects = pyzbar.decode(gray)
    for obj in decoded_objects:
        qr_data = obj.data.decode("utf-8")
        print("QR Code data:", qr_data)
        break

    # Obstacle Detection (Haar Cascade)
    obstacle_detected = False

    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        obstacle_detected = True
        print("Obstacle Detected")
        break

    # Return the qr_data and obstacle_detected flag
    return frame, qr_data, obstacle_detected

def generate_frames():
    """Video streaming generator function."""
    global latest_frame # Declare it's using the global frame
    while True:
        if latest_frame is not None:
             ret, jpeg = cv2.imencode('.jpg', latest_frame)
             if not ret:
                 continue
             frame = jpeg.tobytes()
             yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n') # Send an empty frame
        time.sleep(0.1)  # Adjust the sleep time to control the frame rate

# Create a GStreamer bus to receive messages
bus = pipeline.get_bus()

# This function will be called when a new message arrives on the bus
def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End-of-stream")
        loop.quit()
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("Error: %s" % err, debug)
        loop.quit()
    elif t == Gst.MessageType.NEW_BUFFER: # Sử dụng MESSAGE_NEW_BUFFER
        sample = message.get_structure().get_value('sample')

        buf = sample.get_buffer()
        caps = sample.get_caps()
        # Extract data from GStreamer buffer
        buf_size = buf.get_size()
        buf_data = buf.extract_dup(0, buf_size)
        # Convert the data to a NumPy array
        try:
            frame = np.frombuffer(buf_data, dtype=np.uint8)
            frame = frame.reshape((480, 640,3))
            global latest_frame
            latest_frame = frame.copy() #Update global variable
        except Exception as e:
            print(f"Error processing GStreamer sample: {e}")
    return True

# Create a main loop to receive messages from the bus
loop = GLib.MainLoop()

# Add the bus_call function to the bus to be called for each message
bus.add_signal_watch()
bus.connect("message", bus_call, loop)

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/move/<direction>')
def move_command(direction):
    speed = 50  # Set a default speed
    if direction == 'forward':
        forward(speed)
    elif direction == 'backward':
        backward(speed)
    elif direction == 'left':
        left(speed)
    elif direction == 'right':
        right(speed)
    elif direction == 'stop':
        stop()
    else:
        return "Invalid command", 400
    return "OK"

@app.route('/process')
def process():
    global target_coordinates
    frame, qr_data, obstacle_detected = process_frame()

    if obstacle_detected:
        stop()
        return "Obstacle Detected!"

    if qr_data:
        try:
            # Assuming QR code contains comma-separated coordinates (x, y)
            x, y = map(int, qr_data.split(','))
            target_coordinates = (x, y)  # Store the coordinates
            # Implement basic pathfinding or movement logic here
            print("Moving Towards coordinates:",target_coordinates)
            forward(50) # Simple move forward
            time.sleep(2)  # Move some distance
            stop()
            return f"Moving to coordinates ({x},{y})"
        except ValueError:
            return "Invalid QR code format. Coordinates should be 'x,y'."

    return "No QR code detected."

@app.route('/cleanup')
def cleanup():
    GPIO.cleanup()
    return "GPIO Cleaned Up"

if __name__ == '__main__':
    try:
        #Create a thread to start gstreamer loop.
        import threading
        gst_thread = threading.Thread(target=loop.run)
        gst_thread.start()

        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        # Stop GStreamer pipeline
        pipeline.set_state(Gst.State.NULL)
        GPIO.cleanup()
