#define _HY 1

#include <BME280I2C.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <my_cfg.h>

#define SSID _wssid
#define PASS _wpass
#define PORT _port
#define BROKER _broker
#define MQTT_ID _mqtt_id
#define MQTT_USER _name
#define MQTT_PASS _pass

// Sensor pins BME280
BME280I2C bme;
BME280::TempUnit tempUnit(BME280::TempUnit_Celsius);
BME280::PresUnit presUnit(BME280::PresUnit_Pa);
float air_pressure_f, temp_f, humid_f;

#define TIMEOUT 10000
#define UPDATE_TICK 5000
uint32_t last_tick;

#define BUFFER_SIZE 70
char send_buffer[BUFFER_SIZE];

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

void read_and_publish_temp() {
    bme.read(air_pressure_f, temp_f, humid_f, tempUnit, presUnit);
    air_pressure_f = air_pressure_f / (float)100;

    if (temp_f < -50 || temp_f > 70) return;
    if (humid_f < 0 || humid_f > 105) return;
    if (air_pressure_f < 700 || air_pressure_f > 1350) return;
    snprintf(send_buffer,
             BUFFER_SIZE,
             "{\"temperature\":%.2f,\"humidity\":%.2f,\"airpressure\":%.2f}",
             temp_f,
             humid_f,
             air_pressure_f);
    mqtt.publish(PUBLISH_DATA, send_buffer);
}

void _reconnect() {
    while (!mqtt.connected()) {
        getTime();
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", MQTT_USER);
        } else {
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

void loop(void) {
    _reconnect();
    if (millis() - last_tick >= UPDATE_TICK) {
        last_tick = millis();
        read_and_publish_temp();
    }
}