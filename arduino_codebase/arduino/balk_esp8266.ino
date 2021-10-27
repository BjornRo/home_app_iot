#include <ESP8266WiFi.h>
#include <PubSubClient.h>
//#include <stdio.h>
//#include <string.h>

#define LED_BOARD 1  //pins_arduino.h says 1. Pinout says 0.

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "www.home"

//IPAddress IP_ADDR(192, 168, 1, 233);
//IPAddress GATEWAY(192, 168, 1, 1);
//IPAddress SUBNET(255, 255, 255, 0);

#define MQTT_ID "balcony"
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
#define SEND_BUFFER_SIZE 12
#define RECEIVE_BUFFER_SIZE 20
char SEND_BUFFER[SEND_BUFFER_SIZE];
char RECEIVE_BUFFER[RECEIVE_BUFFER_SIZE];
char topic_buff[10];
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
    if (sscanf(RECEIVE_BUFFER, "(%c,%[(0-9,])", &ARDUINO_CHAR, &ARDUINO_DATA) == 2) {
        uint8_t strlength = strlen(ARDUINO_DATA);
        if (strlength > RECEIVE_BUFFER_SIZE - 1) {
            // we need to have 1 slot open to append ')'. IF string is full, then data is invalid.
            return;
        }
        ARDUINO_DATA[strlength] = ')';
        ARDUINO_DATA[strlength + 1] = '\0';
        if (ARDUINO_CHAR == 'T') {
            mqtt.publish(PUBLISH, ARDUINO_DATA);
        } else if (ARDUINO_CHAR == 'S') {
            mqtt.publish(PUBLISH_STATUS, ARDUINO_DATA, true);
        }
    }
}

bool isposnumber(const char* str) {
    bool isnumber = true;
    for (char* i = str; *i; i++)
        if (!isdigit(*i)) {
            isnumber = false;
            break;
        }
    return isnumber;
}

void _msg_from_broker(char* topic, uint8_t* payload, unsigned int payload_length) {
    strncpy(topic_buff, &topic[27], sizeof(topic_buff));
    topic_buff[sizeof(topic_buff) - 1] = '\0';

    if (strcmp(topic_buff, "ALLOFF") == 0) {
        Serial.println(F("ALLOFF"));
        return;
    }

    uint8_t id = 0;
    uint8_t comm = 0;
    uint16_t time = 0;
    uint8_t count = 0;

    char* token = strtok(topic_buff, "/");
    while (token != NULL) {
        if (count == 0)
            if (isposnumber(token) && strlen(token) <= 2)
                id = atoi(token);
            else
                return;
        else if (count == 1)
            if (strcmp(token, "ON") == 0 || strcmp(token, "OFF") == 0)
                comm = strcmp(token, "ON") == 0 ? 1 : 0;
            else
                return;
        else if (count == 2)
            if (comm)
                if (isposnumber(token) && strlen(token) <= 4)
                    time = atoi(token);
                else
                    return;
        count++;
        token = strtok(NULL, "/");
    }

    if (count <= 1 || id > 3 || comm && !time)
        return;

    sprintf(SEND_BUFFER, "(%d,%d)", id, comm. time);
    printf(SEND_BUFFER);
}

void setup() {
    pinMode(LED_BOARD, OUTPUT);
    digitalWrite(LED_BOARD, LOW);
    Serial.begin(115200);
    delay(10);
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    //WiFi.config(IP_ADDR, GATEWAY, SUBNET);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(_msg_from_broker);
}
void _reconnect() {
    while (!mqtt.connected()) {
        //String clientId = "ESP8266Client-";
        //clientId += String(random(0xffff), HEX);
        // Attempt to connect
        if (mqtt.connect(MQTT_ID)) {
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