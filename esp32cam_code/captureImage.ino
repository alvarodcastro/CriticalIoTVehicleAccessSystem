#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <EloquentSurveillance.h>
#include "TelegramChat.h"
#include <base64.h>

// WiFi Settings
#define WIFI_SSID "yourwifissid"
#define WIFI_PASS "yourwifipass"

// Telegram Settings
#define BOT_TOKEN "yourbottoken"
#define CHAT_ID yourchatid

// Flash LED PIN
#define FLASH_PIN 4

// Motion detection
EloquentSurveillance::Motion motion;

// Telegram chat initialization
EloquentSurveillance::TelegramChat chat(BOT_TOKEN, CHAT_ID);

// MQTT Client
#define MQTT_SERVER "brokerip"
#define MQTT_USER "mqttuser"
#define MQTT_PASS "mqttpass"

String DEVICE_ID;

WiFiClient wClient;
PubSubClient mqtt_client(wClient);

String TOPIC_STATUS;
String TOPIC_SEND_PICTURE;
String TOPIC_SERVER_RESPONSE;
String TOPIC_NOTIFY_PICTURE = "picture/notify";
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

    // Last Will
    JsonDocument lwtDoc;
    lwtDoc["status"] = "offline";
    String lwtPayload;
    serializeJson(lwtDoc, lwtPayload);

    if (mqtt_client.connect(DEVICE_ID.c_str(), MQTT_USER, MQTT_PASS, TOPIC_STATUS.c_str(), 1, true, lwtPayload.c_str()))
    {
      debug("INFO", "Connected to broker " + String(MQTT_SERVER));

      // Publishing device status
      JsonDocument doc;
      doc["status"] = "online";
      String jsonPayload;
      serializeJson(doc, jsonPayload);

      mqtt_client.publish(TOPIC_STATUS.c_str(), jsonPayload.c_str(), false);
      debug("INFO", "Published status: " + jsonPayload);

      // Suscribing to topic
      mqtt_client.subscribe(TOPIC_SERVER_RESPONSE.c_str());
    }
    else
    {
      debug("ERROR", String(mqtt_client.state()) + " reintento en 5s");
      delay(5000);
    }
  }
}

void mqtt_handle_message(char *topic, byte *payload, unsigned int length)
{
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  debug("Received message", msg);

  JsonDocument json;

  if (String(topic) == TOPIC_SERVER_RESPONSE) {
    DeserializationError error = deserializeJson(json, msg);
    
    if (error) 
      debug("ERROR", String(error.c_str()));
    else if (json.containsKey("access_granted") && json.containsKey("plate_number")) {
      bool open_gate = bool(json["access_granted"]);
      String plate_number = String(json["plate_number"]);

      if (open_gate) {
        debug("INFO", "Access granted to " + plate_number); 
        digitalWrite(FLASH_PIN, HIGH);
        delay(500);
        digitalWrite(FLASH_PIN, LOW);

        chat.sendMessage("Motion detected! Waiting for access confirmation...");
        chat.sendMessage("Access granted to " + plate_number);
        bool photoResponse = chat.sendPhoto();
        debug("TELEGRAM PHOTO", photoResponse ? "ERR" : "OK");
      } else if (plate_number != "No plate detected") {
        chat.sendMessage("Access denied. Plate detected: " + plate_number);
        debug("INFO", "Access denied");
      }
    }
  }
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
  debug("INFO", "Sending image through MQTT " + String(TOPIC_SEND_PICTURE));
  debug("INFO", payloadJson.c_str());
  mqtt_client.publish(TOPIC_SEND_PICTURE.c_str(), payloadJson.c_str(), false);

  debug("INFO", "Imagen enviada por MQTT en formato JSON correctamente.");
}

void build_topics(String device_mac) {
  TOPIC_STATUS = "gate/" + device_mac + "/status";
  TOPIC_SEND_PICTURE = "gate/" + device_mac + "/access";
  TOPIC_SERVER_RESPONSE = "server/response/" + device_mac;
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
  camera.qvga();        // VGA Resolution
  camera.lowQuality(); // Best Quality JPEG
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

  start_wifi_connection();
  DEVICE_ID = String(WiFi.getHostname());
  String device_mac = String(WiFi.macAddress());
  build_topics(device_mac);
  mqtt_client.setServer(MQTT_SERVER, 1883);
  mqtt_client.setBufferSize(51200);
  mqtt_client.setCallback(mqtt_handle_message);
  start_mqtt_connection();
}

void loop() {
  if (!mqtt_client.connected()) {
    start_mqtt_connection();
  }
  mqtt_client.loop();

  yield();

  if (!camera.capture()) {
    debug("ERROR", camera.getErrorMessage());
    delay(100);
    return;
  }

  if (!motion.update()) {
    delay(10);
    return;
  }

  if (motion.detect()) {
    debug("INFO", "Motion detected!");

    if (camera.capture()) {
      debug("INFO", "Image captured successfully.");

      sendPictureOverMQTT();
    } else {
      debug("ERROR", camera.getErrorMessage());
    }

    delay(100); 
  }

  delay(10);
}
