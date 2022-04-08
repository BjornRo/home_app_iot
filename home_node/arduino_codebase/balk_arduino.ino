#define ARDUINOJSON_USE_LONG_LONG 1
#define __AVR_ATmega328P__
#include <Arduino.h>
#include <ArduinoJson.h>
#include <WString.h>
#include <avr/io.h>
#include <math.h>
#include <stdint.h>

#include "DHT.h"

// Safety variables
#define MAXTEMP_SAFETY 30
#define MAXTEMP_START 26
#define MAX_TIME 6 * 60

// Time variables
#define SCHEDULER_TICK_MS 5000
#define MINUTES_TO_MS_FACTOR 60000
#define TIMEOUT 5000
// Relays with their state: active and timer.
#define PIN_OFFSET 2  // Port D2 - For offsetting in the functions. 0-3 should be used.
#define HEATER_PIN_INDEX 2
#define RELAY_PINS 3

// By pin index 0-3(2-5): 0: High light, 1: Low Light, 2: HEATER_PIN, 3: Unused
// Temperature sensor
DHT dht(7, DHT22);

float temp, humid;
#define BUFF_SIZE 128
char msg_buffer[BUFF_SIZE], print_data_buffer[BUFF_SIZE];
StaticJsonDocument<BUFF_SIZE> receive;

char* const command_list[] = {"relay_status", "set_relay"};
char* const pin_names[] = {"light_high", "light_low", "heater"};
struct Pins {
    uint8_t id;
    char* name;
    uint32_t timer_start;
    uint32_t timer_length;
    bool active;
} pins[RELAY_PINS];

void init_pins() {
    // Set pinmode to OUT
    DDRD |= ((1 << RELAY_PINS) - 1 << PIN_OFFSET);

    for (uint8_t i = 0; i < RELAY_PINS; i++) {
        struct Pins pin = {
            .id = i + PIN_OFFSET,
            .name = pin_names[i],
            .timer_start = 0,
            .timer_length = 0,
            .active = false,
        };
        pins[i] = pin;
    }
}

void scheduler() {
    read_dht();
    publish_temp();
    check_heater();
    check_relay_timers();
}

void read_dht() {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) {
        snprintf(print_data_buffer, BUFF_SIZE, "\"DHT values is null: [h: %f, t: %f]\"", t, h);
        print_error_to_esp("info");
        return;
    }
    temp = t;
    humid = h;
}

void publish_temp() {
    static char t[7], h[7];
    dtostrf(temp, 3, 2, t);
    dtostrf(humid, 3, 2, h);
    if (temp < -50 || temp > 90 || humid < 0 || humid > 105) {
        snprintf(print_data_buffer, BUFF_SIZE, "Bad DHT values: [t:%s, h: %s]", t, h);
        print_error_to_esp("warning");
        return;
    }
    snprintf(print_data_buffer, BUFF_SIZE, "{\"temperature\":%s,\"humidity\":%s}", t, h);
    print_to_esp("sensor");
}

void publish_relay_status() {
    uint8_t i, j, len, pos;
    pos = 0;
    for (i = 0; i < RELAY_PINS; i++) {  // Leave space for null
        const Pins& p = pins[i];
        snprintf(msg_buffer, BUFF_SIZE, ",\"%s\":%s", p.name, p.active ? "true" : "false");
        len = strlen(msg_buffer);
        for (j = 0; j < len; j++) {
            print_data_buffer[pos++] = msg_buffer[j];
            if (pos >= BUFF_SIZE) {
                strcpy(print_data_buffer, "Relay status msg too long");
                print_error_to_esp("warning");
                return;
            }
        }
    }
    print_data_buffer[0] = '{';  // Replace , with {
    print_data_buffer[pos] = '}';
    print_data_buffer[pos + 1] = '\0';
    print_to_esp("relay");
}

void check_heater() {
    Pins* hp = &pins[HEATER_PIN_INDEX];
    if (hp->active && temp >= MAXTEMP_SAFETY) {
        turn_off_pin_publish(hp);
    }
}

void check_relay_timers() {
    bool state_change = false;
    for (uint8_t i = 0; i < RELAY_PINS; i++) {
        Pins* p = &pins[i];
        if (p->active && (millis() - p->timer_start >= p->timer_length)) {
            turn_off_pin(p);
            state_change = true;
        }
    }
    if (state_change) publish_relay_status();
}

void turn_all_off_pins() {
    PORTD &= ~((1 << RELAY_PINS) - 1 << PIN_OFFSET);
    for (uint8_t i = 0; i < RELAY_PINS; i++) {
        pins[i].active = false;
    }
    publish_relay_status();
}

void turn_off_pin(Pins* pin) {
    PORTD &= ~(1 << pin->id);
    pin->active = false;
}

void turn_off_pin_publish(Pins* pin) {
    turn_off_pin(pin);
    publish_relay_status();
}

void turn_on_pin_publish(Pins* pin, uint16_t minutes) {
    turn_on_pin(pin, minutes);
    publish_relay_status();
}

void turn_on_pin(Pins* pin, uint16_t minutes) {
    if (minutes <= 0 || (pin->id - PIN_OFFSET == HEATER_PIN_INDEX && temp > MAXTEMP_START)) return;
    PORTD |= (1 << pin->id);
    pin->active = true;
    pin->timer_start = millis();
    pin->timer_length = minutes > MAX_TIME ? MAX_TIME * MINUTES_TO_MS_FACTOR : minutes * MINUTES_TO_MS_FACTOR;
}

void recv_esp() {
    static uint8_t pos = 0;
    static char buffer[BUFF_SIZE];
    while (Serial.available()) {
        const char c = Serial.read();
        if (c == '\n') {
            buffer[pos] = '\0';
            pos = 0;

            DeserializationError err = deserializeJson(receive, buffer);
            if (err) {
                strcpy(print_data_buffer, "Error in data sent to arduino: ");
                strcat(print_data_buffer, err.c_str());
                print_error_to_esp("warning");
                return;
            }
            command_handler();
        } else if (pos < BUFF_SIZE - 1) {
            buffer[pos++] = c;
        }
    }
}

void command_handler() {
    char* cmd = receive["cmd"];
    if (!(strcasecmp(cmd, command_list[0]))) return publish_relay_status();

    uint8_t i;
    JsonVariant data = receive["data"];

    if (!strcasecmp(cmd, command_list[1])) {
        if (data.is<const char*>()) {
            if (!strcasecmp(data, "all_off")) {
                turn_all_off_pins();
            } else {
                strcpy(print_data_buffer, "Unknown set_relay data, allowed values: [all_off, {\"key_name\":0-n minutes(0 turns off)}]");
                print_error_to_esp("warning");
            }
            return;
        } else if (data.is<JsonObject>()) {
            bool missing_keys = true;
            for (JsonPair kv : (JsonObject)data) {
                for (i = 0; i < RELAY_PINS; i++) {
                    Pins* p = &pins[i];
                    if (!strcasecmp(kv.key().c_str(), p->name)) {
                        missing_keys = false;
                        uint32_t val = kv.value().as<uint32_t>();
                        if (val) {
                            turn_on_pin(p, val);
                        } else {
                            turn_off_pin(p);
                        }
                    }
                }
            }
            if (missing_keys) {
                strcpy(print_data_buffer, "Missing keys for relays, valid: [");
                for (i = 0; i < RELAY_PINS; i++) {
                    strcat(print_data_buffer, pin_names[i]);
                    strcat(print_data_buffer, ", ");
                }
                i = strlen(print_data_buffer);
                print_data_buffer[i - 1] = ']';
                print_data_buffer[i] = '\0';
                print_error_to_esp("warning");
            } else {
                publish_relay_status();
            }
            return;
        }
    }
    strcpy(print_data_buffer, "Unkwn cmd sent, valid cmd: [set_relay[data:{key:0-n}], relay_status]");
    print_error_to_esp("warning");
}

void print_to_esp(char* cmd) {
    snprintf(msg_buffer, BUFF_SIZE, "{\"cmd\":\"%s\",\"data\":%s}", cmd, print_data_buffer);
    Serial.println(msg_buffer);
}

void print_error_to_esp(char* loglevel) {
    snprintf(
        msg_buffer,
        BUFF_SIZE,
        "{\"cmd\":\"error\",\"data\":{\"detail\":\"%s\",\"log_level\":\"%s\"}",
        print_data_buffer,
        loglevel);
    Serial.println(msg_buffer);
}

void setup() {
    ADCSRA = 0;
    Serial.begin(115200);
    dht.begin();
    init_pins();
}

void loop() {
    static uint32_t last = 0;
    recv_esp();
    // Tick-rate counter.
    if (millis() - last >= SCHEDULER_TICK_MS) {
        last = millis();
        scheduler();
    }
}
