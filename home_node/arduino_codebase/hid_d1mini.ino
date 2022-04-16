#define _KI 1

#include <BME280I2C.h>
#include <ESP8266WiFi.h>
#include <LiquidCrystal_I2C.h>
#include <PubSubClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <Wire.h>
#include <my_cfg.h>
#include <inttypes.h>

#define SSID _wssid
#define PASS _wpass
#define PORT _port
#define BROKER _broker
#define MQTT_ID _mqtt_id
#define MQTT_USER _name
#define MQTT_PASS _pass
#define PUBLISH_COMM "home/balcony/relay"
#define SUB_BALC "home/balcony/sensor/data"
#define SUB_BIKE "home/bikeroom/sensor/data"

// Time-related variables
#define TIMEOUT 5000
#define LCD_TIMEOUT 12000
#define POLLRATE 350
#define UPDATE_TIME 4000

#define BUTTON_TIMEOUT 1000
#define BUTTON_DECISION_INTERVAL 750
unsigned long scheduler_timer, last_poll_time, lcd_timer, saved_time;

// pin 0: all off | pin1: bright lights | pin2: less bright | pin3: heater | pin4: Unused D8.
// One click on, double off
//  LCD D1 D2
#define NBUTTONS 4
#define all_off_button 0     // D3
#define light_hi_button 14   // D5
#define light_low_button 12  // D6
#define heater_button 13     // D7
#define LCD_ON_DISTANCE_CM 20
const uint8_t pin_list[] = {all_off_button, light_hi_button, light_low_button, heater_button};
char* const pin_command[] = {"\"all_off\"", "{\"light_high\":-1}", "{\"light_low\":-1}", "{\"heater\":-1}"};

// Ultrasonic
#define trig_pin 15  // D8
#define echo_pin 16  // D0

// WIFI, MQTT
BearSSL::WiFiClientSecure wifi;

PubSubClient mqtt(BROKER, PORT, wifi);

// Temp
BME280I2C bme;
BME280::TempUnit tempUnit(BME280::TempUnit_Celsius);
BME280::PresUnit presUnit(BME280::PresUnit_Pa);

// LCD
#define LCD_WIDTH_CELLS 21  // Cells width + 1, to include null.
LiquidCrystal_I2C lcd(0x26, LCD_WIDTH_CELLS - 1, 4);

// Buffers
char lcd_print_buffer[LCD_WIDTH_CELLS];
#define SEND_RECV_BUFFER_SIZE 70
char send_buffer[SEND_RECV_BUFFER_SIZE];

// Read payload
#define MAX_KEYS 5
float payload_values[MAX_KEYS];
char* keys[MAX_KEYS];
char payload_cpy[SEND_RECV_BUFFER_SIZE];
char separator[] = "[]),";
char* token;
uint8_t number_of_tokens = 0;

// Temperatures:
char balcony_temp[] = "-99.6";
char balcony_humid[] = "999.6";

char bike_room_temp[] = "-99.6";

char temp[] = "-99.6";
char humid[] = "999.6";
char air_pressure[] = "5555.7";

// Pre-allocate real values for publish and strings for lcd printing. Hoping faster lcd-print
float temp_f = -99.66;
float humid_f = 555.66;
float air_pressure_f = 5555.66;

void read_bme() {
    bme.read(air_pressure_f, temp_f, humid_f, tempUnit, presUnit);
    air_pressure_f = air_pressure_f / (float)100;
    dtostrf(air_pressure_f, 4, 1, air_pressure);
    dtostrf(temp_f, 3, 1, temp);
    dtostrf(humid_f, 3, 1, humid);
}

void mqtt_publish_data() {
    if (temp_f < -50 || temp_f > 60) return;
    if (humid_f < 0 || humid_f > 105) return;
    if (air_pressure_f < 300 || air_pressure_f > 1300) return;
    snprintf(send_buffer,
             SEND_RECV_BUFFER_SIZE,
             "{\"temperature\":%.2f,\"humidity\":%.2f,\"airpressure\":%.2f}",
             temp_f,
             humid_f,
             air_pressure_f);
    mqtt.publish(PUBLISH_DATA, send_buffer);
}

void scheduler() {
    read_bme();
    update_lcd();
    mqtt_publish_data();
}

void update_lcd() {
    // Row 1
    lcd.setCursor(0, 0);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "Bal: %5s%c ", balcony_temp, char(0x01));
    lcd.print(lcd_print_buffer);
    lcd.setCursor(12, 0);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "| %5s%%", balcony_humid);
    lcd.print(lcd_print_buffer);

    // Row 2
    lcd.setCursor(0, 1);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "Kok: %5s%c ", temp, char(0x01));
    lcd.print(lcd_print_buffer);
    lcd.setCursor(12, 1);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "| %5s%%", humid);
    lcd.print(lcd_print_buffer);

    // Row 3
    lcd.setCursor(0, 2);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "Cykelrum ute: %5s%c  ", bike_room_temp, char(0x01));
    lcd.print(lcd_print_buffer);

    // Row 4
    lcd.setCursor(0, 3);
    snprintf(lcd_print_buffer, LCD_WIDTH_CELLS, "Lufttryck: %6shPa   ", air_pressure);
    lcd.print(lcd_print_buffer);
}

bool string_equals(char* str1, char* str2) {
    return strcmp(str1, str2) == 0;
}

uint8_t store_values(char* string) {
    number_of_tokens = 0;
    token = strtok(string, separator);
    while (token != NULL) {
        payload_values[number_of_tokens++] = atoi(token);
        token = strtok(NULL, separator);
    }
    return number_of_tokens;
}

uint8_t read_simple_json(char* payload, float payload_vals[]) {
    uint8_t i = 0;
    // char json[80] = "{\"temperature\":4459,\"humidity\":100.00,\"airpressure\":1000.99}";
    char* contents = strtok(payload, "{\"");
    while (contents != NULL) {
        keys[i] = contents;
        contents = strtok(NULL, "\":,}");
        if (contents == NULL) {
            return 0;
        }
        sscanf(contents, "%f", &payload_vals[i]);
        contents = strtok(NULL, "\":,}");
        i++;
    }
    return i;
}

void msg_from_broker(char* topic, uint8_t* payload, unsigned int payload_len) {
    if (payload_len >= SEND_RECV_BUFFER_SIZE) return;

    memcpy(payload_cpy, (char*)payload, payload_len);
    if (payload_len < SEND_RECV_BUFFER_SIZE)
        payload_cpy[payload_len] = '\0';

    // sscanf((const char*)payload_cpy, "(%" SCNd16 ",%" SCNd16 ")", &payload_values[0], &payload_values[1]) == 2
    if (payload_len < 2) {
        return;
    }
    if (string_equals((char*)SUB_BALC, topic)) {
        if (read_simple_json(payload_cpy, payload_values) == 2) {
            dtostrf(payload_values[0], 5, 1, balcony_temp);
            dtostrf(payload_values[1], 5, 1, balcony_humid);
            return;
        }
    }
    // sscanf((char*)payload_cpy, "%" SCNd16, &payload_values[0]) == 1
    else if (string_equals((char*)SUB_BIKE, topic)) {
        if (read_simple_json(payload_cpy, payload_values) == 1) {
            dtostrf(payload_values[0], 5, 1, bike_room_temp);
            return;
        }
    }
}

// Function to read button and "Debounce".
#define BTN_DEBOUNCE_NUMBER 4
void checkButtons() {
    static uint32_t button_timeout[4];
    static uint8_t button_counter[4];
    for (uint8_t i = 0; i < NBUTTONS; i++) {
        if (digitalRead(pin_list[i]) == 0) {
            if (millis() - button_timeout[i] > BUTTON_TIMEOUT && button_counter[i] < BTN_DEBOUNCE_NUMBER) {
                if (++button_counter[i] == BTN_DEBOUNCE_NUMBER) {
                    mqtt_publish_command(PUBLISH_COMM, i);
                    button_timeout[i] = millis();
                }
            }
        } else {
            button_counter[i] = 0;
        }
    }
}

void mqtt_publish_command(char* topic, uint8_t pin_index) {
    static char data[25];
    strcpy(send_buffer, "{\"cmd\":\"set_relay\",\"data\":");
    strcat(send_buffer, pin_command[pin_index]);
    strcat(send_buffer, "}");
    mqtt.publish(topic, send_buffer);
}

bool ultrasonic_polling() {
    digitalWrite(trig_pin, LOW);
    delayMicroseconds(2);
    digitalWrite(trig_pin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trig_pin, LOW);
    return LCD_ON_DISTANCE_CM >= (pulseIn(echo_pin, HIGH) / 58.2);
}

void lcd_backlight(bool ultrasound) {
    if (ultrasound) {
        lcd_timer = millis();
        lcd.backlight();
    } else if (millis() - lcd_timer >= LCD_TIMEOUT) {
        lcd.noBacklight();
    }
}

void setup() {
    // Ultrasonic sensor
    pinMode(trig_pin, OUTPUT);
    digitalWrite(trig_pin, LOW);
    pinMode(echo_pin, INPUT);

    // Buttons
    for (uint8_t pin : pin_list) pinMode(pin, INPUT_PULLUP);

    // LCD
    lcd.init();
    lcd.begin(20, 4);
    lcd.backlight();
    uint8_t celcius[8] = {
        0b01000,
        0b10100,
        0b01000,
        0b00011,
        0b00100,
        0b00100,
        0b00100,
        0b00011};
    lcd.createChar(1, celcius);

    // BME280 temp,humid,pressure sensor.
    Wire.begin();
    bme.begin();

    WiFi.mode(WIFI_STA);
    WiFi.begin(SSID, PASS);

    while (WiFi.status() != WL_CONNECTED) {
        delay(250);
    }

    wifi.setTrustAnchors(&cert);
    wifi.setClientRSACert(&client_crt, &key);

    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(msg_from_broker);
    read_bme();
    update_lcd();
}

void _reconnect() {
    while (!mqtt.connected()) {
        getTime();
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.subscribe(SUB_BALC, 1);
            mqtt.subscribe(SUB_BIKE, 1);
            mqtt.publish("void", MQTT_USER);
        } else {
            delay(5000);
        }
    }
}

void loop() {
    _reconnect();

    mqtt.loop();
    checkButtons();

    if (millis() - last_poll_time >= POLLRATE) {
        last_poll_time = millis();
        lcd_backlight(ultrasonic_polling());
    }

    if (millis() - scheduler_timer >= UPDATE_TIME) {
        scheduler_timer = millis();
        scheduler();
    }
}
