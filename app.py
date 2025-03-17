from flask import Flask, render_template, Response, request
import cv2
import RPi.GPIO as GPIO
import time
import pyzbar.pyzbar as pyzbar  # Import pyzbar

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

# Camera Setup
camera = cv2.VideoCapture(0)

# Haar Cascade Classifier (Ensure the path is correct)
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

# Motor Control Functions
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

# Obstacle Detection Function
def detect_obstacles(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        return True
    return False

# QR Code Decoding Function
def decode(image):
    decoded_objects = pyzbar.decode(image)
    for obj in decoded_objects:
        print("Data:", obj.data.decode("utf-8"))
        return obj.data.decode("utf-8")  # Return the decoded data
    return None

# Frame Generator for Video Stream
def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            obstacle_detected = detect_obstacles(frame)
            if obstacle_detected:
                print("Obstacle detected! Stopping...")
                stop()

            qr_data = decode(frame)
            if qr_data:
                print("QR Code data:", qr_data)
                # Add your logic here to process the QR code data
                # e.g., update target coordinates, adjust path

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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

@app.route('/cleanup')
def cleanup():
    GPIO.cleanup()
    return "GPIO Cleaned Up"


if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        GPIO.cleanup()  # Ensure GPIO cleanup on exit
