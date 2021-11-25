#include <DallasTemperature.h>
#include <ESP8266WiFi.h>
#include <OneWire.h>
#include <PubSubClient.h>

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "www.home"
#define MQTT_ID "cykelrum_temp"
#define PUBLISH "home/bikeroom/temp"

// TX pin 1. DS18B20 sensor.
#define ONE_WIRE_BUS 1
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

#define TIMEOUT 10000
#define UPDATE_TICK 5000
uint32_t last_tick;
uint32_t saved_time;
int16_t temp = -5544;
#define SEND_BUFFER_SIZE 6
char send_buffer[SEND_BUFFER_SIZE];

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

void _reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(MQTT_ID)) {
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
    temp = (int16_t)(sensors.getTempCByIndex(0) * 100);
    if (-5000 <= temp && temp <= 6000) {
        snprintf(send_buffer, SEND_BUFFER_SIZE, "%d", temp);
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