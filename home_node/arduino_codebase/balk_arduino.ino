#include <avr/io.h>
#include <stdint.h>
#include "DHT.h"

// Safety variables
#define MAXTEMP_SAFETY 30
#define MAXTEMP_START 25
#define MAX_TIMER 18000000  // 25 200 000

// Time variables
#define SCHEDULER_TICK_MS 5000
#define MINUTES_TO_MS_FACTOR 60000
#define TIMEOUT 5000
uint32_t _scheduler_current = 0;
uint32_t _timeout_recv = 0;

//Relays with their state: active and timer.
#define PIN_OFFSET 2  //Port D2 - For offsetting in the functions. 0-3 should be used.
#define HEATER_PIN 2
#define RELAY_PINS 4

// By pin index 0-3(2-5): 0: Full light, 1: Low Light, 2: HEATER_PIN, 3: Unused

//bool _active_pins[RELAY_PINS];
uint32_t _timer_duration[RELAY_PINS];
uint32_t _start_time[RELAY_PINS];

//Temperature sensor
DHT dht(7, DHT22);

// Buffers
#define RECV_BUFFER_SIZE 10
#define SEND_BUFFER_SIZE 18
int16_t _payload_values[3];
char _recv_buffer[RECV_BUFFER_SIZE];
char _send_buffer[SEND_BUFFER_SIZE];
float temp = -60;
float humid = -10;

void _scheduler() {
    _read_dht();
    _publish_temp();
    _check_heater();
    _check_relay_timers();
}

void _read_dht() {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) return;
    temp = t;
    humid = h;
}
void _publish_temp() {
    if (temp > 90 || temp < -50 || humid > 105 || humid < 0) return;
    snprintf(_send_buffer, SEND_BUFFER_SIZE, "(T,(%d,%d))", (int16_t)(temp * 100), (int16_t)(humid * 100));
    Serial.println(_send_buffer);
}

void _publish_status() {
    snprintf(_send_buffer, SEND_BUFFER_SIZE, "(S,(%d,%d,%d,%d))",
             PORTD & (1 << PIN_OFFSET) ? 1 : 0,
             PORTD & (1 << PIN_OFFSET + 1) ? 1 : 0,
             PORTD & (1 << PIN_OFFSET + 2) ? 1 : 0,
             PORTD & (1 << PIN_OFFSET + 3) ? 1 : 0);
    Serial.println(_send_buffer);
}

void _check_heater() {
    if (temp >= MAXTEMP_SAFETY && PORTD & (1 << PIN_OFFSET + HEATER_PIN)) {
        turn_off_pin(HEATER_PIN);
        _publish_status();
    }
}
void _check_relay_timers() {
    bool flag = false;
    for (uint8_t i = 0; i < RELAY_PINS; i++)
        if (PORTD & (1 << PIN_OFFSET + i))
            if (millis() - _start_time[i] >= _timer_duration[i] || millis() - _start_time[i] >= MAX_TIMER) {
                PORTD &= ~(1 << PIN_OFFSET + i);
                flag = true;
            }
    if (flag)
        _publish_status();
}

void turn_all_off_pins() {
    //for (uint8_t i = 0; i < RELAY_PINS; i++)
    //    turn_off_pin(i);
    PORTD &= ~((1 << RELAY_PINS) - 1 << PIN_OFFSET);
    _publish_status();
}
void turn_off_pin(uint8_t pin_id) {
    //digitalWrite(pin_id + PIN_OFFSET, LOW);
    PORTD &= ~(1 << PIN_OFFSET + pin_id);
    _publish_status();
}
void turn_on_pin(uint8_t pin_id, uint16_t minutes) {
    if (minutes <= 0 || (pin_id == 2 && temp >= MAXTEMP_START)) return;
    _timer_duration[pin_id] = (minutes <= 420) ? minutes * MINUTES_TO_MS_FACTOR : MAX_TIMER;
    //digitalWrite(pin_id + PIN_OFFSET, HIGH);
    PORTD |= (1 << PIN_OFFSET + pin_id);
    _start_time[pin_id] = millis();
    _publish_status();
}

void _recv_esp() {
    static uint8_t input_pos = 0;
    while (Serial.available() > 0) {
        char inByte = Serial.read();
        switch (inByte) {
            case '\n':
                _recv_buffer[input_pos] = 0;
                _string_handler();
                input_pos = 0;
                break;
            case '\r':
                break;
            default:
                if (input_pos < (RECV_BUFFER_SIZE - 1))
                    _recv_buffer[input_pos] = inByte;
                input_pos = input_pos + 1;
                break;
        }
    }
}

void _string_handler() {
    if (strcmp(_recv_buffer, "ALLOFF") == 0) return turn_all_off_pins();
    if (strcmp(_recv_buffer, "STATUS") == 0) return _publish_status();
    if (sscanf(_recv_buffer, "(%d,%d,%d)", &_payload_values[0], &_payload_values[1], &_payload_values[2]) == 3) {
        if (_payload_values[0] >= 0 && _payload_values[0] <= 3) {
            if (_payload_values[1] == 0) {
                turn_off_pin(_payload_values[0]);
                return;
            }
            if (_payload_values[1] == 1 && _payload_values[2] > 0 && _payload_values[2] <= 420) {
                turn_on_pin(_payload_values[0], _payload_values[2]);
                return;
            }
        }
    }
}

void setup() {
    ADCSRA = 0;
    Serial.begin(115200);
    dht.begin();
    //for (uint8_t i = 0; i < RELAY_PINS; i++)
    //    pinMode(i + PIN_OFFSET, OUTPUT);
    DDRD |= ((1 << RELAY_PINS) - 1 << PIN_OFFSET);
}

void loop() {
    _recv_esp();
    //Tick-rate counter.
    if (millis() - _scheduler_current >= SCHEDULER_TICK_MS) {
        _scheduler_current = millis();
        _scheduler();
    }
}