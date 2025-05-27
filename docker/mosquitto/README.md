# Mosquitto MQTT Broker Docker Setup

This directory contains the configuration and setup files for running an Eclipse Mosquitto MQTT broker in Docker. This broker is used as part of the Critical IoT Vehicle Access System for message handling between different components.

## Directory Structure

```
mosquitto/
├── config/
│   ├── mosquitto.conf    # Mosquitto configuration file
│   └── pwfile           # Password file for MQTT users
├── data/                # Persistence data directory
├── log/                 # Log files directory
└── docker-compose.yml   # Docker compose configuration
```

## Prerequisites

- Docker
- Docker Compose

## Setup Instructions

1. First, ensure you're in the mosquitto directory:
   ```bash
   cd docker/mosquitto
   ```

2. Create config directory if it does not exist:
   ```bash
   mkdir -p config 
   ```

3. Create a password file for MQTT users:
   ```bash
   docker exec -it <container-id> sh
   mosquitto_passwd -c /mosquitto/config/pwfile <username>
   ```
   Replace `<username>` with your desired username. You'll be prompted to enter a password.

5. Make sure the mosquitto.conf file in the config directory has the following settings:
   ```
   persistence true
   persistence_location /mosquitto/data/
   log_dest file /mosquitto/log/mosquitto.log
   password_file /mosquitto/config/pwfile
   allow_anonymous false
   listener 1883
   ```

## Deployment

1. Start the Mosquitto broker using Docker Compose:
   ```bash
   docker-compose up -d
   ```

2. Verify the broker is running:
   ```bash
   docker-compose ps
   ```

## Adding New Users

To add additional users to the broker:

1. Add a new user:
   ```bash
   docker-compose exec mosquitto mosquitto_passwd -b /mosquitto/config/pwfile <new_username> <password>
   ```

2. Restart the broker to apply changes:
   ```bash
   docker-compose restart
   ```

## Testing the Connection

You can test the MQTT broker connection using mosquitto_pub and mosquitto_sub clients:

1. Subscribe to a topic:
   ```bash
   mosquitto_sub -h localhost -p 1883 -u "<username>" -P "<password>" -t "test/topic"
   ```

2. Publish to the same topic:
   ```bash
   mosquitto_pub -h localhost -p 1883 -u "<username>" -P "<password>" -t "test/topic" -m "Hello MQTT"
   ```

## Troubleshooting

1. Check broker logs:
   ```bash
   docker-compose logs mosquitto
   ```

2. Verify port availability:
   ```bash
   netstat -an | findstr "1883"
   ```

3. Check file permissions if you encounter access issues.

## Security Considerations

- Always change default passwords
- Keep your Docker and Mosquitto versions updated
- Regularly backup the password file
- Consider implementing SSL/TLS for production environments
- Monitor logs for unauthorized access attempts

## Stopping the Broker

To stop the Mosquitto broker:
```bash
docker-compose down
```

This will stop and remove the containers while preserving your configuration and data.