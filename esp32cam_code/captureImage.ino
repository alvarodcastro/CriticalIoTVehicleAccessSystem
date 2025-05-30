#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <EloquentSurveillance.h>
#include "TelegramChat.h"
#include <base64.h>

// WiFi Settings
#define WIFI_SSID "ESP32_AP"
#define WIFI_PASS "mah-iot2"

// Telegram Settings
#define BOT_TOKEN "7422198409:AAFH1EwZvidiSG6PASmMJjbsyOqx4_bLfsI"
#define CHAT_ID 938197683

// Flash LED PIN
#define FLASH_PIN 4

// Webserver object
WebServer server(80);

// Motion detection
EloquentSurveillance::Motion motion;

// Telegram chat initialization
EloquentSurveillance::TelegramChat chat(BOT_TOKEN, CHAT_ID);

// MQTT Client
#define MQTT_SERVER "192.168.50.1"
#define MQTT_USER "mqtt_iot2"
#define MQTT_PASS "mah-iot2"

String DEVICE_ID;
String DEVICE_MAC;

WiFiClient wClient;
PubSubClient mqtt_client(wClient);

String TOPIC_CONNECTION = "conexion";
String TOPIC_NOTIFY_PICTURE = "picture/notify";
String TOPIC_SEND_PICTURE;
String TOPIC_NOTIFY_MOTION_DETECTED = "motion/notify";

void debug(String level, String message)
{
  Serial.print("[" + level + "] ");
  Serial.println(message);
}

void start_wifi_connection()
{
  debug("INFO", "Connecting to WiFi " + String(WIFI_SSID));

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  WiFi.setSleep(false);

  while (WiFi.status() != WL_CONNECTED)
  {
    delay(200);
    Serial.print(".");
  }

  Serial.println("");
  debug("SUCCESS", "WiFi connected!");
  Serial.print("Dirección IP: ");
  Serial.println(WiFi.localIP());
}

void start_mqtt_connection()
{
  while (!mqtt_client.connected())
  {
    debug("INFO", "Attempting MQTT connection...");

    if (mqtt_client.connect(DEVICE_ID.c_str(), MQTT_USER, MQTT_PASS, TOPIC_CONNECTION.c_str(), 1, true, "Dispositivo desconectado"))
    {
      debug("INFO", "Connected to broker " + String(MQTT_SERVER));
      mqtt_client.publish(TOPIC_CONNECTION.c_str(), "Dispositivo conectado a MQTT correctamente.", false);
    }
    else
    {
      debug("ERROR", String(mqtt_client.state()) + " reintento en 5s");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void mqtt_handle_message(char *topic, byte *payload, unsigned int length)
{
  String msg = "";
  for (int i = 0; i < length; i++)
    msg += (char)payload[i];
  debug("Received message", msg);
}

void sendPictureOverMQTT()
{
  if (!camera.capture())
  {
    debug("ERROR", camera.getErrorMessage());
    return;
  }

  // Obtiene el buffer de la imagen
  uint8_t *buffer = camera.getBuffer();
  size_t bufferSize = camera.getFileSize();

  if (!buffer || bufferSize == 0)
  {
    debug("ERROR", "No se pudo obtener buffer de imagen");
    return;
  }

  debug("INFO", "Imagen capturada correctamente, codificando en Base64...");

  // Codifica la imagen en Base64
  String encodedImage = base64::encode(buffer, bufferSize);

  // Elimina el recorte para enviar toda la imagen
  size_t maxSize = 48000;
  if (encodedImage.length() > maxSize)
  {
    debug("WARN", "Imagen demasiado grande, recortando para enviar por MQTT");
    encodedImage = encodedImage.substring(0, maxSize);
  }

  // Prepara el JSON con ArduinoJson
  JsonDocument doc; // Ajusta el tamaño según la longitud de tu imagen Base64
  doc["image"] = encodedImage;

  String payloadJson;
  serializeJson(doc, payloadJson);

  // Publica la notificación de imagen tomada
  mqtt_client.publish(TOPIC_NOTIFY_PICTURE.c_str(), "Image taken!");
  mqtt_client.publish(TOPIC_NOTIFY_MOTION_DETECTED.c_str(), "Motion detected!", false);

  // Envía el payload JSON con la imagen en Base64
  debug("INFO", "Enviando al topic " + String(TOPIC_SEND_PICTURE));
  debug("INFO", payloadJson.c_str());
  mqtt_client.publish(TOPIC_SEND_PICTURE.c_str(), payloadJson.c_str(), false);

  debug("INFO", "Imagen enviada por MQTT en formato JSON correctamente.");
}

void startWebServer()
{
  server.on("/", HTTP_GET, []()
            { server.send(200, "text/html",
                          "<html><body><h1>ESP32-CAM</h1>"
                          "<p>Usa <a href='/capture'>/capture</a> para capturar manualmente una imagen.</p>"
                          "</body></html>"); });

  server.on("/capture", HTTP_GET, []()
            {
    debug("INFO", "Petición manual de captura recibida");
    captureAndSendImage(); });

  server.begin();
  debug("SUCCESS", "Servidor web iniciado en puerto 80");
}

void captureAndSendImage()
{
  digitalWrite(FLASH_PIN, HIGH);
  delay(100);

  if (!camera.capture())
  {
    debug("ERROR", camera.getErrorMessage());
    digitalWrite(FLASH_PIN, LOW);
    server.send(500, "text/plain", "Error al capturar la imagen");
    return;
  }

  digitalWrite(FLASH_PIN, LOW);

  uint8_t *buffer = camera.getBuffer();
  size_t bufferSize = camera.getFileSize();

  if (!buffer || bufferSize == 0)
  {
    debug("ERROR", "No se pudo obtener buffer de imagen");
    server.send(500, "text/plain", "Error al obtener el buffer");
    return;
  }

  server.sendHeader("Content-Disposition", "attachment; filename=\"captura.jpg\"");
  server.send_P(200, "image/jpeg", (const char *)buffer, bufferSize);

  debug("INFO", "Imagen enviada correctamente");
}

void scanNetworks()
{
  debug("INFO", "Escaneando redes WiFi disponibles...");

  int n = WiFi.scanNetworks();
  if (n == 0)
  {
    debug("INFO", "No se encontraron redes WiFi");
  }
  else
  {
    debug("INFO", String(n) + " redes encontradas:");
    for (int i = 0; i < n; ++i)
    {
      String ssid = WiFi.SSID(i);
      int rssi = WiFi.RSSI(i);
      String encryptionType;
      switch (WiFi.encryptionType(i))
      {
      case WIFI_AUTH_OPEN:
        encryptionType = "Open";
        break;
      case WIFI_AUTH_WEP:
        encryptionType = "WEP";
        break;
      case WIFI_AUTH_WPA_PSK:
        encryptionType = "WPA/PSK";
        break;
      case WIFI_AUTH_WPA2_PSK:
        encryptionType = "WPA2/PSK";
        break;
      case WIFI_AUTH_WPA_WPA2_PSK:
        encryptionType = "WPA/WPA2/PSK";
        break;
      default:
        encryptionType = "Unknown";
        break;
      }

      debug("INFO", String(i + 1) + ": " + ssid + " (" + rssi + "dBm) [" + encryptionType + "]");
      delay(10);
    }
  }
}

void setup()
{
  Serial.begin(115200);
  delay(3000);

  debug("INFO", "Starting setup...");

  // Configura el pin del flash
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);

  // Camera Settings
  camera.aithinker();
  camera.svga();        // VGA Resolution
  camera.bestQuality(); // Best Quality JPEG
  camera.setBrightness(1);
  camera.setSaturation(0);

  // Camera initilization
  while (!camera.begin())
  {
    debug("ERROR", camera.getErrorMessage());
    delay(1000);
  }

  // Motion detection settings
  motion.setMinChanges(0.1); // Sensibility
  motion.setMinPixelDiff(10);
  motion.setMinSizeDiff(0.05);

  // scanNetworks();

  start_wifi_connection();
  DEVICE_ID = String(WiFi.getHostname());
  DEVICE_MAC = String(WiFi.macAddress());
  TOPIC_SEND_PICTURE = "gate/" + DEVICE_MAC + "/access";
  debug("INFO", String(TOPIC_SEND_PICTURE));
  mqtt_client.setServer(MQTT_SERVER, 1883);
  mqtt_client.setBufferSize(51200);
  mqtt_client.setCallback(mqtt_handle_message);
  start_mqtt_connection();

  startWebServer();
}

void loop()
{
  mqtt_client.loop();
  server.handleClient();

  // Captura periódica para detección de movimiento
  if (!camera.capture())
  {
    debug("ERROR", camera.getErrorMessage());
    return;
  }

  if (!motion.update())
  {
    return;
  }

  if (motion.detect())
  {
    debug("INFO", "Motion detected! Taking a picture...");

    // Activa el flash
    digitalWrite(FLASH_PIN, HIGH);
    delay(100);

    sendPictureOverMQTT();

    if (camera.capture())
    {
      debug("INFO", "Image taken successfully.");

      bool messageResponse = chat.sendMessage("Motion Detected!");
      debug("TELEGRAM MSG", messageResponse ? "OK" : "ERR");

      bool photoResponse = chat.sendPhoto();
      debug("TELEGRAM PHOTO", photoResponse ? "OK" : "ERR");
    }

    // Apaga el flash después de la captura
    digitalWrite(FLASH_PIN, LOW);
  }
  else if (!motion.isOk())
  {
    debug("ERROR", motion.getErrorMessage());
  }
}