#include <ESP8266WiFi.h>
#include <PubSubClient.h>
//#include <stdio.h>
//#include <string.h>

#define LED_BOARD 1  // pins_arduino.h says 1. Pinout says 0.

#define SSID ""
#define PASS ""
// MQTT
#define PORT 1883
#define BROKER "mqtt.lan"
#define MQTT_USER "balcony"
#define MQTT_PASS ""
#define MQTT_ID "balcony_unit"

// IPAddress IP_ADDR(192, 168, 1, 233);
// IPAddress GATEWAY(192, 168, 1, 1);
// IPAddress SUBNET(255, 255, 255, 0);

#define PUBLISH "home/balcony/temphumid"
#define PUBLISH_STATUS "home/balcony/relay/status"
#define SUBSCRIBE "home/balcony/relay/command/#"

// Time variables
#define TIMEOUT 5000
uint32_t TIMEOUT_RECEIVE;

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

// Buffers
#define SEND_BUFFER_SIZE 41
#define RECEIVE_BUFFER_SIZE 20
char SEND_BUFFER[SEND_BUFFER_SIZE];
char RECEIVE_BUFFER[RECEIVE_BUFFER_SIZE];
char PAYLOAD_CPY[RECEIVE_BUFFER_SIZE];
int16_t PAYLOAD_VALUES[3];
float first, second;
char ARDUINO_CHAR;
char ARDUINO_DATA[RECEIVE_BUFFER_SIZE];

void receive_arduino() {
    static uint8_t input_pos = 0;
    while (Serial.available() > 0) {
        char inByte = Serial.read();
        switch (inByte) {
            case '\n':
                RECEIVE_BUFFER[input_pos] = 0;
                publish_arduino();
                input_pos = 0;
                break;
            case '\r':
                break;
            default:
                if (input_pos < (RECEIVE_BUFFER_SIZE - 1))
                    RECEIVE_BUFFER[input_pos] = inByte;
                input_pos = input_pos + 1;
                break;
        }
    }
}

void publish_arduino() {
    // Add to the start of the array
    if (sscanf(RECEIVE_BUFFER, "(%c,(%[^)])", &ARDUINO_CHAR, ARDUINO_DATA) == 2) {
        uint8_t strlength = strlen(ARDUINO_DATA);
        if (strlength > RECEIVE_BUFFER_SIZE - 1) {
            // we need to have 1 slot open to append ']'. IF string is full, then data is invalid.
            return;
        }
        if (ARDUINO_CHAR == 'T') {
            sscanf(ARDUINO_DATA, "%f,%f", &first, &second);
            snprintf(SEND_BUFFER, SEND_BUFFER_SIZE, "{\"temperature\":%.2f,\"humidity\":%.2f}", first / 100, second / 100);
            mqtt.publish(PUBLISH, SEND_BUFFER);
        } else if (ARDUINO_CHAR == 'S') {
            SEND_BUFFER[0] = '[';
            for (uint8_t i = 0; i < strlength; i++) {
                SEND_BUFFER[i + 1] = ARDUINO_DATA[i];
            }
            SEND_BUFFER[strlength+1] = ']';
            SEND_BUFFER[strlength+2] = '\0';
            mqtt.publish(PUBLISH_STATUS, SEND_BUFFER, true);
        }
    }
}

char separator[] = "(),";
char* token;
uint8_t number_of_tokens = 0;
uint8_t store_values(char* string) {
    number_of_tokens = 0;
    token = strtok(string, separator);
    while (token != NULL) {
        PAYLOAD_VALUES[number_of_tokens++] = atoi(token);
        token = strtok(NULL, separator);
    }
    return number_of_tokens;
}

void _msg_from_broker(char* topic, uint8_t* payload, unsigned int payload_length) {
    memcpy(PAYLOAD_CPY, (char*)payload, payload_length);
    if (payload_length < RECEIVE_BUFFER_SIZE)
        PAYLOAD_CPY[payload_length] = '\0';

    if (payload_length < 6 || payload_length > 9) return;
    if (strcasecmp(PAYLOAD_CPY, "ALLOFF") == 0) {
        Serial.println(F("ALLOFF"));
        return;
    }

    if (store_values(PAYLOAD_CPY) == 3) {
        sprintf(SEND_BUFFER, "(%d,%d,%d)", PAYLOAD_VALUES[0], PAYLOAD_VALUES[1], PAYLOAD_VALUES[2]);
        Serial.println(SEND_BUFFER);
        return;
    }
}

void setup() {
    pinMode(LED_BOARD, OUTPUT);
    digitalWrite(LED_BOARD, LOW);
    Serial.begin(115200);
    delay(10);
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    // WiFi.config(IP_ADDR, GATEWAY, SUBNET);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(_msg_from_broker);
}
void _reconnect() {
    while (!mqtt.connected()) {
        // String clientId = "ESP8266Client-";
        // clientId += String(random(0xffff), HEX);
        //  Attempt to connect
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", "balcony");
            mqtt.subscribe(SUBSCRIBE);
        } else {
            delay(5000);
        }
    }
    while (Serial.available() > 0) {
        Serial.read();
    }
    Serial.println(F("STATUS"));
}
void loop() {
    if (!mqtt.connected()) _reconnect();
    receive_arduino();
    mqtt.loop();
}