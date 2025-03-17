# AGV Project

This is an AGV (Automated Guided Vehicle) project using Raspberry Pi, a camera, and L298N motor driver.

## Requirements

*   Raspberry Pi 4
*   Raspberry Pi Camera Module (v2 or NoIR)
*   L298N Motor Driver
*   ... (other hardware)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/ngnxuanhoa/agv-3.git
    cd agv-3
    ```

2.  Install dependencies:
    ```bash
    pip3 install -r requirements.txt
    ```
3.  Configure the camera (see [Raspberry Pi documentation](https://www.raspberrypi.com/documentation/computers/configuration.html)).  Make sure `camera_auto_detect=1` is set in `/boot/config.txt`.

4.  Connect the hardware (L298N, motors, camera).

5.  Run the application:
    ```bash
    python3 app.py
    ```

6.  Access the web interface from a browser on the same network (e.g., `http://<raspberry_pi_ip>:5000`).

## Usage
... (Hướng dẫn sử dụng các nút điều khiển, click map,...)

## Contributing
... (Nếu bạn muốn người khác đóng góp)

## License
... (Chọn một license, ví dụ: MIT)