#define ARDUINOJSON_USE_LONG_LONG 1
#define __AVR_ATmega328P__
#include <Arduino.h>
#include <ArduinoJson.h>
//#include <avr/io.h>

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
#define PIN_OFFSET 2        // Port D3 - For offsetting in the functions. 0-3 should be used.
#define HEATER_PIN_INDEX 2  // Offsetted pin index. = 5
#define RELAY_PINS 3

#define HIGH_LIGHT_BUTTON_PIN 8  // Uno has interrupts on 2,3. Used async-polling on instead due to 'volatile'.
#define DHT22_PIN 7
#define BUTTON_TIMEOUT 1000

// By pin index 0-3(2-5): 0: High light, 1: Low Light, 2: HEATER_PIN, 3: Unused
// Temperature sensor
DHT dht(DHT22_PIN, DHT22);

#define BUFF_SIZE 144
float temp, humid;
char msg_buffer[BUFF_SIZE], print_data_buffer[BUFF_SIZE];
StaticJsonDocument<96> receive;

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
    pinMode(HIGH_LIGHT_BUTTON_PIN, INPUT_PULLUP);
}

#define BTN_DEBOUNCE_NUMBER 4
void check_btn() {
    static uint8_t btn_counter = 0;
    static uint32_t btn_timeout = 0;

    if (digitalRead(HIGH_LIGHT_BUTTON_PIN) == 0) {
        if (millis() - btn_timeout > BUTTON_TIMEOUT && btn_counter < BTN_DEBOUNCE_NUMBER) {
            btn_counter++;
            if (btn_counter == BTN_DEBOUNCE_NUMBER) {
                if (pins[0].active) {
                    turn_off_pin_publish(&pins[0]);
                } else {
                    turn_on_pin_publish(&pins[0], 10);
                }
                btn_timeout = millis();
            }
        }
    } else {
        btn_counter = 0;
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
    print_data_buffer[0] = '{';  // Replace ',' with {
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
    if (state_change) {
        publish_relay_status();
    }
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

void turn_on_pin(Pins* pin, uint16_t minutes) {
    if (minutes <= 0 || (pin->id - PIN_OFFSET == HEATER_PIN_INDEX && temp > MAXTEMP_START)) {
        return;
    }
    PORTD |= (1 << pin->id);
    pin->active = true;
    pin->timer_start = millis();
    pin->timer_length = minutes * MINUTES_TO_MS_FACTOR;
}

void turn_on_pin_publish(Pins* pin, uint16_t minutes) {
    turn_on_pin(pin, minutes);
    publish_relay_status();
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
    if (!(strcasecmp(cmd, command_list[0]))) {
        return publish_relay_status();
    }

    uint8_t i;
    JsonVariant data = receive["data"];

    if (!strcasecmp(cmd, command_list[1])) {
        if (data.is<const char*>()) {
            if (!strcasecmp(data, "all_off")) {
                turn_all_off_pins();
            } else {
                strcpy(print_data_buffer, "set_relay values: all_off | pin_name:0-n, min(0=off)");
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
                        int16_t val = kv.value().as<int16_t>();
                        if (val == -1) {  // Toggle. Default times.
                            val = p->active ? 0 : (i == 0 ? 10 : 420);
                        }
                        if (val == 0) {
                            turn_off_pin(p);
                        } else if (val > 0) {
                            turn_on_pin(p, val);
                        } else {  // Negative value
                            strcpy(print_data_buffer, "Only -1, 0 and positive numbers allowed for relays");
                            print_error_to_esp("warning");
                            return;
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
    strcpy(print_data_buffer, "cmd: relay_status | (set_relay:data:{key:0-n} | all_off)");
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
        "{\"cmd\":\"error\",\"data\":{\"detail\":\"%s\",\"log_level\":\"%s\"}}",
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
    check_btn();
    // Tick-rate counter.
    if (millis() - last >= SCHEDULER_TICK_MS) {
        last = millis();
        scheduler();
    }
}
