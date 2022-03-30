#include <BME280I2C.h>
#include <ESP8266WiFi.h>
#include <LiquidCrystal_I2C.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <inttypes.h>

#define SSID ""
#define PASS ""
#define PORT 1883
#define BROKER "mqtt.lan"
#define MQTT_ID "kitchen_hid"
#define MQTT_USER "kitchen"
#define MQTT_PASS ""
#define PUBLISH "home/kitchen/temphumidpress"
#define PUBLISH_COMM "home/balcony/relay/command"
const char* SUB_BALC = "home/balcony/temphumid";
const char* SUB_BIKE = "home/bikeroom/temp";
const char* SUBS[] = {SUB_BALC, SUB_BIKE};

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
#define all_off_button D3
#define hi_light_button D5
#define lo_light_button D6
#define heater_button D7
#define LCD_ON_DISTANCE_CM 20
const uint8_t pin_list[] = {all_off_button, hi_light_button, lo_light_button, heater_button};
const char* pin_command_on[] = {"ALLOFF", "(0,1,5)", "(1,1,420)", "(2,1,420)"};
const char* pin_command_off[] = {"ALLOFF", "(0,0,0)", "(1,0,0)", "(2,0,0)"};

// Ultrasonic
#define trig_pin D8
#define echo_pin D0

// WIFI, MQTT
WiFiClient wifi;
PubSubClient mqtt(wifi);

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
char* key[MAX_KEYS];
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

void publish() {
    if (temp_f < -50 || temp_f > 60) return;
    if (humid_f < 0 || humid_f > 105) return;
    if (air_pressure_f < 300 || air_pressure_f > 1300) return;
    snprintf(send_buffer, SEND_RECV_BUFFER_SIZE,
             "{\"temperature\":%.2f,\"humidity\":%.2f,\"airpressure\":%.2f}",
             temp_f, humid_f, air_pressure_f);
    mqtt.publish(PUBLISH, send_buffer);
}

void scheduler() {
    read_bme();
    update_lcd();
    publish();
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
        key[i] = contents;
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

// Function to read button and Debounce it. Async version.
uint8_t button_counter[4];
uint8_t button_pressed;  // 0b#0(0000) #1(0000), #0 = "Active", #1 = "If buttons been pressed"
void checkButtons() {
    for (uint8_t i = 0; i < NBUTTONS; i++) {
        if (digitalRead(pin_list[i]) == 0) {
            // Prevent overflow.
            if (button_counter[i] < UINT8_MAX)
                button_counter[i]++;
        } else {
            button_counter[i] = 0;
        }
        // After 10 loops of button stabilizing, set button to true. "Sensitivity".
        if (button_counter[i] == 10) {
            button_pressed |= (1 << i);
        }
    }
}

// Works both as timeout and check for double click.
unsigned long button_start_click[4];
void check_buttons_then_decide() {
    checkButtons();
    for (uint8_t i = 0; i < NBUTTONS; i++) {
        // Check if button is pressed or active. -- old (1 << i) | (1 << i + NBUTTONS))
        if (button_pressed & (0b10001 << i)) {
            // IF button is active, let it pass | Button click "cooldown". Using binary explicit is more verbose.
            // 1 << i + NBUTTONS == 0b10000 << i, in this case. Less cycles I suppose?
            if (button_pressed & (0b10000 << i) || millis() - button_start_click[i] >= BUTTON_TIMEOUT) {
                // All off, no double click/delay. Skip the entire algorithm.
                if (i == 0) {
                    mqtt.publish(PUBLISH_COMM, pin_command_on[i], false);
                } else {
                    // If button isn't active, then set it to 1, set pressed to 0 and store time.
                    // Continue loop since we want to recheck if button is pressed again or held.
                    if (!(button_pressed & (0b10000 << i))) {
                        button_start_click[i] = millis();
                        // Set active bit to 1. Set pressed bit to 0
                        button_pressed = (button_pressed | (0b10000 << i)) & ~(1 << i);
                        continue;
                    }
                    // From this point on, button active has to be 1 or active.
                    // If button is pressed again, we know that it has to be a double click.
                    if (button_pressed & (1 << i)) {
                        mqtt.publish(PUBLISH_COMM, pin_command_off[i], false);
                    } else if (millis() - button_start_click[i] >= BUTTON_DECISION_INTERVAL) {
                        // If timer for the button has passed, then we check the state of the pin.
                        // If active = long press. Otherwise it has to be a single click.
                        if (digitalRead(pin_list[i]) == 0) {
                            mqtt.publish(PUBLISH_COMM, pin_command_off[i], false);
                        } else {
                            mqtt.publish(PUBLISH_COMM, pin_command_on[i], false);
                        }
                        // Last else to just keep continuing the loop until a decision is made.
                    } else {
                        continue;
                    }
                }
                // If a decision has been made, then timeout.
                button_start_click[i] = millis();
            }
            // Buttons will only reach this if button timeout or decision has been made.
            // Set both i flags to 0.
            button_pressed &= ~(0b10001 << i);  //(1 << i) | (1 << i + NBUTTONS)
        }
    }
}

// const char* pin_command_on[] = {"ALLOFF", "(0,1,5)", "(1,1,420)", "(2,1,420)"};
// const char* pin_command_off[] = {"ALLOFF", "(0,0,0)", "(1,0,0)", "(2,0,0)"};

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
    } else if (millis() - lcd_timer >= LCD_TIMEOUT)
        lcd.noBacklight();
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

    while (WiFi.status() != WL_CONNECTED)
        delay(250);

    mqtt.setServer(BROKER, PORT);
    mqtt.setCallback(msg_from_broker);
    read_bme();
    update_lcd();
}

void _reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(MQTT_ID, MQTT_USER, MQTT_PASS)) {
            mqtt.publish("void", "kitchen");
            for (const char* const sub : SUBS) {
                delay(250);
                mqtt.subscribe(sub);
            }
        } else {
            delay(5000);
        }
    }
}

void loop() {
    if (!mqtt.connected()) _reconnect();

    mqtt.loop();
    check_buttons_then_decide();

    if (millis() - last_poll_time >= POLLRATE) {
        last_poll_time = millis();
        lcd_backlight(ultrasonic_polling());
    }

    if (millis() - scheduler_timer >= UPDATE_TIME) {
        scheduler_timer = millis();
        scheduler();
    }
}