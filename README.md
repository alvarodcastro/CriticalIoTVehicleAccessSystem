# Access Control System with ANPR

An IoT-based access control system using Automatic Number Plate Recognition (ANPR) for vehicle access management in critical infrastructure.

## Features

- Automatic Number Plate Recognition using YOLO and PaddleOCR
- Web-based management interface
- Real-time gate control with ESP32
- Offline operation capability
- Access log tracking with image storage
- Multiple gate support
- High availability design

## System Requirements

- Python 3.8+
- ESP32 with camera module
- Raspberry Pi (or similar) for main server
- Network connectivity (WiFi/Ethernet)
- Camera with night vision capability

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ProyectoFinal
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up the YOLO model:
- Place your trained YOLO model (`best.pt`) in the `app/models` directory
- The model should be trained for license plate detection

4. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

5. Configure the ESP32:
- Upload the ESP32 code to your device
- Update WiFi credentials and server URL in the ESP32 code
- Connect the gate control mechanism to the specified pins

## MQTT Broker Setup

1. Install Mosquitto MQTT Broker:
- Windows:
  - Download and install from: https://mosquitto.org/download/
  - Add Mosquitto to system PATH
  - Create a password file:
    ```
    mosquitto_passwd -c C:\mosquitto\passwd mqtt_user
    ```
  - Edit C:\mosquitto\mosquitto.conf to add:
    ```
    listener 1883
    allow_anonymous false
    password_file C:\mosquitto\passwd
    ```
  - Start Mosquitto service:
    ```
    net start mosquitto
    ```

- Linux (Raspberry Pi):
  ```bash
  sudo apt-get update
  sudo apt-get install -y mosquitto mosquitto-clients
  sudo mosquitto_passwd -c /etc/mosquitto/passwd mqtt_user
  ```
  Edit /etc/mosquitto/conf.d/default.conf:
  ```
  listener 1883
  allow_anonymous false
  password_file /etc/mosquitto/passwd
  ```
  ```bash
  sudo systemctl restart mosquitto
  ```

2. Test MQTT Connection:
```bash
# Subscribe to test topic
mosquitto_sub -h localhost -p 1883 -u mqtt_user -P mqtt_password -t "test"

# Publish to test topic (in another terminal)
mosquitto_pub -h localhost -p 1883 -u mqtt_user -P mqtt_password -t "test" -m "hello"
```

## Configuration

1. Environment Variables:
```bash
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///access_control.db
DEBUG=False
```

2. ESP32 Configuration (in esp32_code/main.py):
- Update `WIFI_SSID` and `WIFI_PASSWORD`
- Set `SERVER_URL` to your server's address
- Adjust `GATE_ID` for each gate

## Usage

1. Start the server:
```bash
python main.py
```

2. Access the web interface:
- Open a browser and navigate to `http://localhost:5000`
- Default admin credentials: 
  - Username: admin
  - Password: admin123 (change this in production)

3. System Management:
- Add/remove vehicles and manage access permissions
- Monitor gate status and access logs
- View ANPR detection results
- Manage multiple gates

## Security Considerations

1. Change default admin password
2. Use HTTPS in production
3. Implement proper network security
4. Regular system updates
5. Monitor system logs

## Offline Operation

The system maintains operation during network outages:
- ESP32 stores a local cache of authorized vehicles
- Regular synchronization when online
- Manual override capability
- All operations are logged and synced when connection is restored

## Troubleshooting

1. Gate Communication Issues:
- Check network connectivity
- Verify ESP32 status LED indicators
- Check gate mechanism connections

2. ANPR Problems:
- Ensure proper camera positioning and lighting
- Verify model is loaded correctly
- Check debug images in static/debug_images

3. Database Issues:
- Check database connections
- Verify file permissions
- Review application logs

## Development

To run tests:
```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.