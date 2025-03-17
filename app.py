from flask import Flask, render_template, Response, request
import cv2
import numpy as np
from picamera2 import Picamera2
import RPi.GPIO as GPIO
import time

app = Flask(__name__)

# Cấu hình GPIO điều khiển động cơ
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Chân GPIO điều khiển động cơ
IN1, IN2 = 17, 18  # Motor trái
IN3, IN4 = 22, 23  # Motor phải
ENA, ENB = 12, 13  # PWM điều khiển tốc độ

# Thiết lập GPIO là output
GPIO.setup([IN1, IN2, IN3, IN4, ENA, ENB], GPIO.OUT)
GPIO.output([IN1, IN2, IN3, IN4], GPIO.LOW)

# Tạo PWM điều khiển tốc độ động cơ
pwmA = GPIO.PWM(ENA, 1000)
pwmB = GPIO.PWM(ENB, 1000)
pwmA.start(0)
pwmB.start(0)

# Khởi tạo camera
picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
picam2.start()

def detect_obstacle(frame):
    """ Phát hiện vật cản bằng Canny + Contour """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # Chuyển ảnh sang grayscale
    blur = cv2.GaussianBlur(gray, (5, 5), 0)  # Làm mờ để giảm nhiễu
    edges = cv2.Canny(blur, 50, 150)  # Phát hiện cạnh

    # Tìm contour trong ảnh
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # Nếu có contour lớn (vật cản), vẽ lên ảnh
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:  # Ngưỡng diện tích vật cản
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)  # Vẽ hộp quanh vật cản
            return True, frame

    return False, frame

def generate_frames():
    """ Truyền hình ảnh đã xử lý đến trình duyệt """
    while True:
        frame = picam2.capture_array()
        obstacle_detected, processed_frame = detect_obstacle(frame)

        _, buffer = cv2.imencode('.jpg', processed_frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)

def move_forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    pwmA.ChangeDutyCycle(70)
    pwmB.ChangeDutyCycle(70)

def move_backward():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    pwmA.ChangeDutyCycle(70)
    pwmB.ChangeDutyCycle(70)

def turn_left():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    pwmA.ChangeDutyCycle(50)
    pwmB.ChangeDutyCycle(70)

def turn_right():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    pwmA.ChangeDutyCycle(70)
    pwmB.ChangeDutyCycle(50)

def stop():
    GPIO.output([IN1, IN2, IN3, IN4], GPIO.LOW)
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(0)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/control', methods=['POST'])
def control():
    command = request.form.get('command')
    if command == 'forward':
        move_forward()
    elif command == 'backward':
        move_backward()
    elif command == 'left':
        turn_left()
    elif command == 'right':
        turn_right()
    elif command == 'stop':
        stop()
    return "OK"

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
