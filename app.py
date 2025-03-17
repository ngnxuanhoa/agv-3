from flask import Flask, render_template, Response, request
from flask_socketio import SocketIO, emit
import cv2
from picamera2 import Picamera2
import time
import RPi.GPIO as GPIO

# Cấu hình chân GPIO (thay đổi nếu bạn sử dụng chân khác)
IN1 = 17
IN2 = 18
IN3 = 22
IN4 = 23
ENA = 12  # Tùy chọn: Điều khiển tốc độ
ENB = 13  # Tùy chọn: Điều khiển tốc độ

# Khởi tạo Flask và SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Khởi tạo camera (sử dụng picamera2)
picam2 = Picamera2()
camera_config = picam2.create_video_configuration(main={"size": (640, 480)})
picam2.configure(camera_config)
picam2.start()
time.sleep(2)  # Chờ camera khởi động

# Cấu hình GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)
GPIO.setup(ENA, GPIO.OUT)  # Tùy chọn
GPIO.setup(ENB, GPIO.OUT)  # Tùy chọn

# Hàm điều khiển động cơ
def motor_control(left_forward, left_backward, right_forward, right_backward):
    GPIO.output(IN1, left_forward)
    GPIO.output(IN2, left_backward)
    GPIO.output(IN3, right_forward)
    GPIO.output(IN4, right_backward)

# Dừng xe
def stop():
    motor_control(0, 0, 0, 0)

# Đi thẳng
def forward():
    motor_control(1, 0, 1, 0)
    # p1.ChangeDutyCycle(50)  # Điều chỉnh tốc độ (nếu dùng PWM)
    # p2.ChangeDutyCycle(50)

# Lùi
def backward():
    motor_control(0, 1, 0, 1)

# Rẽ trái
def turn_left():
    motor_control(0, 1, 1, 0)

# Rẽ phải
def turn_right():
    motor_control(1, 0, 0, 1)

# Xử lý sự kiện điều khiển từ web
@socketio.on('control')
def handle_control(command):
    if command == 'forward':
        forward()
    elif command == 'backward':
        backward()
    elif command == 'left':
        turn_left()
    elif command == 'right':
        turn_right()
    elif command == 'stop':
        stop()

# Hàm tạo stream video
def gen_frames():
    while True:
        frame = picam2.capture_array("main")  # Lấy frame từ picamera2

        # Xử lý ảnh ở đây (ví dụ: tìm bản đồ)
        # ... (Phần phát hiện mã màu hoặc xử lý ảnh khác của bạn)
         # Chuyển đổi sang không gian màu HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Xác định ngưỡng màu (ví dụ: màu đỏ)
        lower_red = (0, 100, 100)  # Điều chỉnh giá trị cho phù hợp
        upper_red = (10, 255, 255)

        # Tạo mask
        mask = cv2.inRange(hsv, lower_red, upper_red)

        # Tìm contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Vẽ contours và tìm tọa độ
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Lọc bỏ các contours nhỏ
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Vẽ hình chữ nhật
                center_x = x + w // 2
                center_y = y + h // 2
                print(f"Tọa độ trung tâm màu đỏ: ({center_x}, {center_y})")
                # TODO: Di chuyển đến tọa độ (center_x, center_y)


        # Chuyển đổi ảnh thành JPEG để stream
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Route cho trang chủ (index)
@app.route('/')
def index():
    return render_template('index.html')  # Tạo file index.html sau

# Route cho video stream
@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route cho xử lý click map (xử lý tọa độ)
@app.route('/map_click', methods=['POST'])
def map_click():
    x = request.form.get('x')
    y = request.form.get('y')
    print(f"Tọa độ nhận được: x={x}, y={y}")
    # TODO: Thêm logic di chuyển đến tọa độ (x, y)
    return "OK"

# Chạy ứng dụng
if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)  # Thay debug=True để debug dễ hơn
    finally:
        GPIO.cleanup()
        picam2.stop()