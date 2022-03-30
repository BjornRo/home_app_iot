#include <ESP8266WiFi.h>
#include <PubSubClient.h>

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "mqtt.lan"
#define MQTT_ID "switch_id1_unit"
#define MQTT_USER "switch_id1"
#define MQTT_PASS ""

#define PUB_STATUS "home/switch/id1/status"
#define PUB_REPLY "home/switch/id1/reply"

// Config
const char* SUBS[] = {"home/switch/id1/set", "home/switch/id1/get"};
const uint8_t PINS[] = {1, 3};
#define MAX_SWITCHES 2

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

void _reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", MQTT_ID);
            for (const char* const sub : SUBS) {
                delay(200);
                mqtt.subscribe(sub);
            }
            _publish_mqtt_status();
        } else {
            delay(5000);
        }
    }
}

void on_message(char* topic, uint8_t* payload, unsigned int payload_len) {
    uint8_t buffer_size = 9;  // See comment below
    if (payload_len >= buffer_size) return;

    int8_t value = -1;

    if (strcmp(SUBS[0], topic) == 0 && strcasecmp(payload, "all_off") == 0) {
        value = 0;
    } else if (strcmp(SUBS[0], topic) == 0 && strcasecmp(payload, "all_on") == 0) {
        value = 1;
    }
    if (value != -1) {
        for (uint8_t pin : PINS) {
            digitalWrite(pin, value);
        }
        _publish_mqtt_status();
        return;
    }

    int8_t id = -1;

    // buffer_size - should be adjusted depending on len({"1": 2}\0) == 9. len({"1": 2, "1": 0}\0) == 17.
    // Only accepting single values or all_on. => 9 is enough.
    char buffer[buffer_size];
    memcpy(buffer, payload, payload_len + 1);  // TODO test if this copies null too.
    if (sscanf(buffer, "{\"%d\":%d}", &id, &value) != MAX_SWITCHES) return;
    if (id <= -1 || id >= MAX_SWITCHES || value <= -1 || value >= 2) return;
    if (strcmp(SUBS[0], topic) == 0) {
        // Set
        digitalWrite(PINS[id], value);
        _publish_mqtt_status();
    } else {
        // Get
        printf(buffer_size, "{\"%d\":%d}", id, digitalRead(PINS[id]));
        mqtt.publish(PUB_REPLY, buffer_size);
    }
}

void _publish_mqtt_status() {
    char pseudo_json[8 + 6 * MAX_SWITCHES - 1] = '{';  // len({"0":0,"1":1}) == 14, Adds 6 for each new key:value.
    char value_pair[6];                                // "1":0
    uint8_t i;
    for (i; i < MAX_SWITCHES; i++) {
        printf(value_pair, "\"%d\":%d", i, digitalRead(PINS[i]));
        strcat(pseudo_json, value_pair);
        if (i < MAX_SWITCHES - 1) {
            strcat(pseudo_json, ",");
        }
    }
    strcat(pseudo_json, "}");

    mqtt.publish(PUB_STATUS, pseudo_json, true);
}

void setup(void) {
    ADCSRA = 0;
    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);
    while (WiFi.status() != WL_CONNECTED)
        delay(250);
    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(on_message);
}

void loop(void) {
    _reconnect();
}
