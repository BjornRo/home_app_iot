#define _BR 1

#include <DallasTemperature.h>
#include <ESP8266WiFi.h>
#include <OneWire.h>
#include <PubSubClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <cfg.h>

#define SSID _ssid
#define PASS _pass
#define PORT _port
#define BROKER _broker
#define MQTT_ID _mqtt_id
#define MQTT_USER _name
#define MQTT_PASS _pass

// TX pin 1. DS18B20 sensor.
#define ONE_WIRE_BUS 1
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

#define UPDATE_TICK 5000
#define SEND_BUFFER_SIZE 30
uint32_t last_tick;
char send_buffer[SEND_BUFFER_SIZE];

// WIFI, MQTT
BearSSL::WiFiClientSecure wifi;

PubSubClient mqtt(BROKER, PORT, wifi);

void _reconnect() {
    uint16_t attempts = 0;
    while (!mqtt.connected()) {
        if (!attempts) {
            getTime();
        }
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", MQTT_USER);
        } else {
            attempts++;
            if (attempts >= 17280) {
                attempts = 0;
            }
            delay(5000);
        }
    }
}

void setup(void) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    wifi.setTrustAnchors(&cert);
    wifi.setClientRSACert(&client_crt, &key);

    mqtt.setServer(BROKER, PORT);
    sensors.begin();
}

void read_and_publish_temp() {
    sensors.requestTemperatures();
    static float temp = sensors.getTempCByIndex(0);
    if (-60 <= temp && temp <= 80) {
        snprintf(send_buffer, SEND_BUFFER_SIZE, "{\"temperature\":%f}", temp);
        mqtt.publish(PUBLISH_DATA, send_buffer);
    }
}

void loop(void) {
    _reconnect();
    if (millis() - last_tick >= UPDATE_TICK) {
        last_tick = millis();
        read_and_publish_temp();
    }
}