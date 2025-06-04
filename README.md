# Critical IoT Vehicle Access System

An IoT-based access control system using Automatic Number Plate Recognition (ANPR) for vehicle access management in critical infrastructure. The system uses containerized services for MQTT and ANPR processing.

## Features

- Automatic Number Plate Recognition using YOLO and PaddleOCR
- Containerized microservices architecture
- Web-based management interface
- Real-time gate control with ESP32-CAM
- Offline operation capability with local SQLite database
- BigQuery integration for cloud storage and analytics
- Access log tracking and synchronization
- Multiple gate support
- High availability design
- Telegram notification system

## System Architecture

### Components
1. **Web Application**
   - Flask-based admin interface
   - Vehicle and gate management
   - Access log visualization
   - Authentication system

2. **MQTT Broker (Docker)**
   - Handles communication between components
   - Manages gate access requests
   - Supports multiple concurrent connections

3. **YOLO ANPR Service (Docker)**
   - REST API for plate recognition
   - Uses YOLO for plate detection
   - PaddleOCR for text recognition

4. **Gate Controller (ESP32-CAM)**
   - Captures vehicle images
   - Communicates with MQTT broker
   - Controls gate mechanism

5. **Database System**
   - Local SQLite for offline operation
   - Google BigQuery for cloud storage
   - Automatic synchronization

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- ESP32 with camera module
- Google Cloud Platform account with BigQuery enabled
- Network connectivity (WiFi/Ethernet)

## Installation

1. Clone the repository:
```powershell
git clone <repository-url>
cd CriticalIoTVehicleAccessSystem
```

2. Set up Python environment:
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure Docker services:

   a. MQTT Broker:
   ```powershell
   cd docker/mosquitto
   docker-compose up -d
   ```

   b. YOLO ANPR Service:
   ```powershell
   cd docker/yolo
   docker-compose up -d
   ```

4. Configure Google Cloud:
- Create a project and enable BigQuery API
- Download service account key to `iot2-final-project-credentials.json`
- Update BigQuery configuration in environment variables

5. Configure the ESP32:
- Upload `esp32cam_code/captureImage.ino` to your device
- Update WiFi and MQTT broker credentials

## Configuration

1. Environment Variables:
```bash
GOOGLE_APPLICATION_CREDENTIALS=iot2-final-project-credentials.json
MQTT_BROKER_URL=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=user
MQTT_PASSWORD=user123
YOLO_API_URL=http://localhost:4000
```

2. Docker Services Configuration:
- MQTT Broker: `docker/mosquitto/config/mosquitto.conf`
- YOLO Service: `docker/yolo/app.py`

## Usage

1. Start all services:
```powershell
# Start MQTT Broker
docker-compose -f docker/mosquitto/docker-compose.yml up -d

# Start YOLO Service
docker-compose -f docker/yolo/docker-compose.yml up -d

# Start main application
python main.py
```

2. Access the web interface:
- Navigate to `http://localhost:5000`
- Login with your credentials

## Testing

The system includes various test tools located in the `tests` directory:

1. MQTT Testing:
```powershell
# Test MQTT sending
python tests/test_mqtt_send.py --mode mqtt

# Test YOLO API directly
python tests/test_mqtt_send.py --mode api

# Test both
python tests/test_mqtt_send.py --mode both
```

2. Log Synchronization Testing:
```powershell
python tests/test_log_sync.py
```

See `tests/README.md` for detailed testing instructions.

## Development

### Project Structure
```
CriticalIoTVehicleAccessSystem/
├── app/                    # Main application
│   ├── controllers/       # Web interface controllers
│   ├── database/         # Database handlers
│   └── templates/        # Web interface templates
├── docker/               # Containerized services
│   ├── mosquitto/       # MQTT broker
│   └── yolo/            # ANPR service
├── esp32cam_code/       # ESP32-CAM firmware
├── instance/            # Local databases
└── tests/               # Testing tools
```

### Adding New Features
1. Implement feature in appropriate module
2. Add tests in `tests` directory
3. Update documentation
4. Test with both online and offline operation

## Troubleshooting

1. MQTT Connection Issues:
```powershell
# Check MQTT broker logs
docker logs mosquitto
```

2. YOLO API Issues:
```powershell
# Check YOLO service logs
docker logs yolo-api
```

3. Database Issues:
- Check `instance/access_control.db` permissions
- Verify BigQuery credentials
- Check sync service logs

## Security Considerations

1. Docker Security:
- Use custom networks
- Configure proper authentication
- Regular security updates

2. MQTT Security:
- TLS encryption (optional)
- Strong passwords
- Access control lists

3. Application Security:
- HTTPS in production
- Regular backups
- Input validation

## License

This project is licensed under the MIT License - see the LICENSE file for details.
