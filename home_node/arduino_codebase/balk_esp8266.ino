#define _BA 1

#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <my_cfg.h>

#define LED_BOARD 1  // pins_arduino.h says 1. Pinout says 0.

#define SSID _wssid
#define PASS _wpass
#define PORT _port
#define BROKER _broker
#define MQTT_USER _name
#define MQTT_PASS _pass
#define MQTT_ID _mqtt_id

#define PUB_RELAY_STATUS _default_path "relay/status"
#define SUB_RELAY_CMD _default_path "relay"

// Buffers
#define BUFF_SIZE 192

// WIFI, MQTT
// WiFiClientSecure wifi

BearSSL::WiFiClientSecure wifi;

PubSubClient mqtt(BROKER, PORT, wifi);

StaticJsonDocument<BUFF_SIZE> json_buff;

char msg_buff[BUFF_SIZE];
char msg_buff_2[BUFF_SIZE];

void recv_arduino() {
    static uint8_t i = 0;
    static char buffer[BUFF_SIZE];
    while (Serial.available()) {
        char r = Serial.read();
        if (r == '\n') {
            i = 0;
            DeserializationError error = deserializeJson(json_buff, buffer);
            if (error) {
                publish_error(error, "info", "Invalid json from arduino: ");
                return;
            }
            from_arduino_to_mqtt();
            return;
        } else if (i < BUFF_SIZE) {
            buffer[i] = r;
            i++;
        }
    }
}

void from_arduino_to_mqtt() {
    const char* cmd = json_buff["cmd"];
    JsonObject data = json_buff["data"];
    if (!strcasecmp(cmd, "error")) {
        data["device_name"] = MQTT_USER;
        serializeJson(data, msg_buff);
        mqtt.publish(PUBLISH_ERROR, msg_buff);
        return;
    }
    serializeJson(data, msg_buff);
    if (!strcasecmp(cmd, "relay")) {
        mqtt.publish(PUB_RELAY_STATUS, msg_buff, 1);
    } else if (!strcasecmp(cmd, "sensor")) {
        mqtt.publish(PUBLISH_DATA, msg_buff);
    }
}

void on_message(char* topic, uint8_t* payload, unsigned int payload_length) {
    if (payload_length >= BUFF_SIZE) return;

    // Copy to msg_buffer.
    memcpy(msg_buff, (char*)payload, payload_length);
    msg_buff[payload_length] = '\0';

    DeserializationError error = deserializeJson(json_buff, msg_buff);
    if (error) {
        publish_error(error, "debug", "Invalid json from broker: ");
        return;
    }
    serializeJson(json_buff, msg_buff_2);
    Serial.println(msg_buff_2);
}

void publish_error(DeserializationError error, char* log_level, char* msg) {
    json_buff.clear();
    strcpy(msg_buff, msg);
    strcat(msg_buff, error.c_str());
    json_buff["detail"] = msg_buff;
    json_buff["log_level"] = log_level;
    json_buff["device_name"] = MQTT_USER;

    serializeJson(json_buff, msg_buff_2);
    mqtt.publish(PUBLISH_ERROR, msg_buff_2);
}

void setup() {
    // Turn off led
    pinMode(LED_BOARD, OUTPUT);
    digitalWrite(LED_BOARD, LOW);

    Serial.begin(115200);
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    wifi.setTrustAnchors(&cert);
    wifi.setClientRSACert(&client_crt, &key);

    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(on_message);
}

void _reconnect() {
    while (!mqtt.connected()) {
        getTime();
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", MQTT_USER);
            mqtt.subscribe(SUB_RELAY_CMD, 1);
            delay(100);
            Serial.println("!");  // Invalid command to clear buffer.
            delay(60);
            while (Serial.available()) {
                delayMicroseconds(250);
                Serial.read();
            }
            Serial.println("{\"cmd\":\"relay_status\"}");
        } else {
            delay(5000);
        }
    }
}

void loop() {
    _reconnect();
    recv_arduino();
    mqtt.loop();
}
