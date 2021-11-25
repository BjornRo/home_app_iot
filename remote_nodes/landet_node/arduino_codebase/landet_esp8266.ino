#include <BME280I2C.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "192.168.1.200"
#define MQTT_ID "hydrofor"
#define PUBLISH "landet/hydrofor/temphumidpress"

// Sensor pins BME280
BME280I2C bme;
BME280::TempUnit tempUnit(BME280::TempUnit_Celsius);
BME280::PresUnit presUnit(BME280::PresUnit_Pa);

#define TIMEOUT 10000
#define UPDATE_TICK 5000
uint32_t last_tick;
uint32_t saved_time;
float temp_f = -99.66;
float humid_f = 555.66;
float air_pressure_f = 5555.66;

#define SEND_RECV_BUFFER_SIZE 22
char send_buffer[SEND_RECV_BUFFER_SIZE];

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

void read_bme() {
    bme.read(air_pressure_f, temp_f, humid_f, tempUnit, presUnit);
    air_pressure_f = air_pressure_f / (float)100;
}

void _reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(MQTT_ID)) {
            mqtt.publish("void", "hydrofor");
        } else {
            delay(5000);
        }
    }
}

void setup(void) {
    Wire.begin();
    while (!bme.begin())
        delay(1000);

    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);
    mqtt.setServer(BROKER, PORT);
}

void read_and_publish_temp() {
    read_bme();
    if (temp_f > 60 || temp_f < -50) return;
    if (humid_f > 105 || humid_f < 0) return;
    if (air_pressure_f > 1250 || air_pressure_f < 700) return;
    snprintf(send_buffer, SEND_RECV_BUFFER_SIZE, "(%d,%d,%d)", (int16_t)(temp_f * 100), (int16_t)(humid_f * 100), (int32_t)(air_pressure_f * 100));
    mqtt.publish(PUBLISH, send_buffer);
}

void loop(void) {
    if (!mqtt.connected()) _reconnect();
    if (millis() - last_tick >= UPDATE_TICK) {
        last_tick = millis();
        read_and_publish_temp();
    }
}