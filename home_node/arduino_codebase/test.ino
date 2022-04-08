#define _BA 1

#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266HTTPClient.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <cfg.h>
#include <time.h>

#define SSID _ssid
#define PASS _pass
#define PORT _port
#define BROKER _broker
#define MQTT_USER _ba_name
#define MQTT_PASS _ba_pass
#define MQTT_ID "booom_baa"

#define p(x) Serial.println(x)

BearSSL::WiFiClientSecure wifi;

BearSSL::X509List cert(ca_cert);
BearSSL::X509List client_crt(client_cert);
BearSSL::PrivateKey key(client_key);

PubSubClient mqtt(BROKER, PORT, wifi);

void setup() {
    Serial.begin(115200);
    p("starting");
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    p("wificerts");
    getTime();
    wifi.setTrustAnchors(&cert);
    wifi.setClientRSACert(&client_crt, &key);

    p("mqtt");
    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(f);
    p(mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS));
    delay(2000);
    mqtt.publish("void", "Hello testing esp8266");
    delay(5000);
    p("mqtt");
    mqtt.loop();
}
void f(char* topic, uint8_t* payload, unsigned int payload_len) {}

void loop() {
    p("in loop sorry :(");
    mqtt.publish("void", "Hello testing esp8266");
    mqtt.loop();
    delay(5000);
    p(mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS));
}
