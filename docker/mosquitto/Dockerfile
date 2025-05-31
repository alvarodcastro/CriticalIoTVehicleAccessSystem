FROM eclipse-mosquitto:2.0

COPY config/mosquitto.conf /mosquitto/config/mosquitto.conf
COPY config/pwfile /mosquitto/config/pwfile

RUN chmod 600 /mosquitto/config/pwfile


# Exponer los puertos
EXPOSE 1883
EXPOSE 9001

# Mosquitto se lanzará con la configuración que ya tiene la imagen por defecto:
# /docker-entrypoint.sh mosquitto -c /mosquitto/config/mosquitto.conf