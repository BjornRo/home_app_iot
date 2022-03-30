#include <DallasTemperature.h>
#include <ESP8266WiFi.h>
#include <OneWire.h>
#include <PubSubClient.h>

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "mqtt.lan"
#define MQTT_ID "bikeroom_unit"
#define MQTT_USER "bikeroom"
#define MQTT_PASS ""
#define PUBLISH "home/bikeroom/temp"

// TX pin 1. DS18B20 sensor.
#define ONE_WIRE_BUS 1
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

#define TIMEOUT 10000
#define UPDATE_TICK 5000
uint32_t last_tick;
uint32_t saved_time;
float temp = -55.44;
#define SEND_BUFFER_SIZE 25
char send_buffer[SEND_BUFFER_SIZE];

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

void _reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", "bikeroom");
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
    mqtt.setServer(BROKER, PORT);
    sensors.begin();
}

void read_and_publish_temp() {
    sensors.requestTemperatures();
    temp = sensors.getTempCByIndex(0);
    if (-50 <= temp && temp <= 60) {
        snprintf(send_buffer, SEND_BUFFER_SIZE, "{\"temperature\":%.2f}", temp);
        mqtt.publish(PUBLISH, send_buffer);
    }
}

void loop(void) {
    if (!mqtt.connected()) _reconnect();
    if (millis() - last_tick >= UPDATE_TICK) {
        last_tick = millis();
        read_and_publish_temp();
    }
}