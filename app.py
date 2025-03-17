from flask import Flask, render_template, request
import RPi.GPIO as GPIO
import time
import pyzbar.pyzbar as pyzbar
import cv2
import numpy as np
from picamera2 import Picamera2
import os

app = Flask(__name__)

# GPIO Configuration
ENA = 17
ENB = 27
IN1 = 22
IN2 = 23
IN3 = 24
IN4 = 25

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

# Camera Setup using picamera2
picam2 = Picamera2()
picam2.configure(picam2.preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
picam2.start()

# MJPG-Streamer Output File
IMAGE_FILE = "/tmp/stream_image.jpg"

# Haar Cascade Classifier (Ensure the path is correct)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

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
    frame = picam2.capture_array()

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

    # Save the frame to a file for MJPG-streamer
    cv2.imwrite(IMAGE_FILE, frame)

    # Return the qr_data and obstacle_detected flag
    return qr_data, obstacle_detected

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

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
    qr_data, obstacle_detected = process_frame()

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
        # Start MJPG-streamer in a separate process
        # Replace with your actual mjpg_streamer command
        os.system(f"mjpg_streamer -i '/usr/lib/mjpg-streamer/input_file.so -f {IMAGE_FILE} -n' -o '/usr/lib/mjpg-streamer/output_http.so -w /usr/share/mjpg-streamer/www -p 8080'")

        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        GPIO.cleanup()
        picam2.close()
        # Kill mjpg_streamer process here (implementation depends on how it's started)
