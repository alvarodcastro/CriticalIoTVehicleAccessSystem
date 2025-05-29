#define VERBOSE

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WebServer.h>
#include <EloquentSurveillance.h>
#include "TelegramChat.h"

// WiFi Settings
#define WIFI_SSID ""
#define WIFI_PASS ""

// Telegram Settings
#define BOT_TOKEN ""
#define CHAT_ID 

//Flash LED PIN
#define FLASH_PIN 4

// Webserver object
WebServer server(80);

// Motion detection
EloquentSurveillance::Motion motion;

// Telegram chat initialization
EloquentSurveillance::TelegramChat chat(BOT_TOKEN, CHAT_ID);

// MQTT Client
#define MQTT_SERVER ""
#define MQTT_USER ""
#define MQTT_PASS ""
String DEVICE_ID;

WiFiClient wClient;
PubSubClient mqtt_client(wClient);

void debug(String level, String message) {
  Serial.print("[" + level + "] ");
  Serial.println(message);
}

void start_wifi_connection() {
  debug("INFO", "Connecting to WiFi" + String(WIFI_SSID));
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  WiFi.setSleep(false);

  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }

  Serial.println("");
  debug("SUCCESS", "WiFi connected!");
  Serial.print("Dirección IP: ");
  Serial.println(WiFi.localIP());
}

void start_mqtt_connection() {
  while (!mqtt_client.connected()) {
    debug("INFO", "Attempting MQTT connection...");
    
    if (mqtt_client.connect(DEVICE_ID.c_str(), MQTT_USER, MQTT_PASS)) { 
      debug("INFO", "Connected to broker " + String(MQTT_SERVER));
    } else {
      debug("ERROR", String(mqtt_client.state()) +" reintento en 5s" );
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void mqtt_handle_message(char* topic, byte* payload, unsigned int length) {
  String msg="";
  for(int i=0; i<length; i++) msg+= (char)payload[i];
  debug("Received message", msg);
}

void startWebServer() {
  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html",
      "<html><body><h1>ESP32-CAM</h1>"
      "<p>Usa <a href='/capture'>/capture</a> para capturar manualmente una imagen.</p>"
      "</body></html>");
  });

  server.on("/capture", HTTP_GET, []() {
    debug("INFO", "Petición manual de captura recibida");
    captureAndSendImage();
  });

  server.begin();
  debug("SUCCESS", "Servidor web iniciado en puerto 80");
}

void captureAndSendImage() {
  digitalWrite(FLASH_PIN, HIGH);
  delay(100);

  if (!camera.capture()) {
    debug("ERROR", camera.getErrorMessage());
    digitalWrite(FLASH_PIN, LOW);
    server.send(500, "text/plain", "Error al capturar la imagen");
    return;
  }

  digitalWrite(FLASH_PIN, LOW);

  uint8_t* buffer = camera.getBuffer();
  size_t bufferSize = camera.getFileSize();

  if (!buffer || bufferSize == 0) {
    debug("ERROR", "No se pudo obtener buffer de imagen");
    server.send(500, "text/plain", "Error al obtener el buffer");
    return;
  }

  server.sendHeader("Content-Disposition", "attachment; filename=\"captura.jpg\"");
  server.send_P(200, "image/jpeg", (const char*)buffer, bufferSize);

  debug("INFO", "Imagen enviada correctamente");
}

void setup() {
  Serial.begin(115200);
  delay(3000);

  debug("INFO", "Starting setup...");

  // Configura el pin del flash
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);

  // Camera Settings
  camera.aithinker();
  camera.svga();          // VGA Resolution
  camera.bestQuality();   // Best Quality JPEG
  camera.setBrightness(1);
  camera.setSaturation(0);

  // Camera initilization
  while (!camera.begin()) {
    debug("ERROR", camera.getErrorMessage());
    delay(1000);
  }

  // Motion detection settings
  motion.setMinChanges(0.1);    // Sensibility
  motion.setMinPixelDiff(10);
  motion.setMinSizeDiff(0.05);

  start_wifi_connection();
  DEVICE_ID = String(WiFi.getHostname());
  //mqtt_client.setServer(MQTT_SERVER, 1883);
  //mqtt_client.setBufferSize(512); 
  //mqtt_client.setCallback(mqtt_handle_message);
  //start_mqtt_connection();


  startWebServer();
}

void loop() {
  server.handleClient();

  if (!camera.capture()) {
    debug("ERROR", camera.getErrorMessage());
    return;
  }

  if (!motion.update()) {
    return;
  }

  if (motion.detect()) {
    debug("INFO", "Motion detected! Taking a picture...");

    // Activa el flash
    digitalWrite(FLASH_PIN, HIGH);
    delay(100);

    if (camera.capture()) {
      debug("INFO", "Image taken successfully.");

      bool messageResponse = chat.sendMessage("Motion Detected!");
      debug("TELEGRAM MSG", messageResponse ? "OK" : "ERR");

      bool photoResponse = chat.sendPhoto();
      debug("TELEGRAM PHOTO", photoResponse ? "OK" : "ERR");
    }

    digitalWrite(FLASH_PIN, LOW);
  }
  else if (!motion.isOk()) {
    debug("ERROR", motion.getErrorMessage());
  }
}