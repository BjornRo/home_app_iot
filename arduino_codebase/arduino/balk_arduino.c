#include <Arduino.h>
#include <DHT.h>
#include <avr/interrupt.h>
#include <avr/io.h>
#include <stdint.h>
#include <util/delay.h>

#include <wiring.c>
#define F_CPU 16000000UL

uint8_t DHT22_expect(uint8_t level) {
    uint32_t starttime = micros();
    uint32_t endtime = starttime;
    if (level)
        while ((PINC & 1) ^ 0) {
            if ((endtime - starttime) >= 100)
                return 0;
            endtime = micros();
        }
    else
        while (PINC & 1) {
            if ((endtime - starttime) >= 100)
                return 0;
            endtime = micros();
        }
    return 1;
}

uint8_t read() {
    uint8_t data[5];
    uint32_t cycles[80];

    DDRC &= ~1;
    PORTC |= 1;
    _delay_ms(1);
    DDRC |= 1;
    PORTC &= ~1;
    _delay_us(1100);
    DDRC &= ~1;
    PORTC |= 1;
    _delay_ms(55);

    cli();
    if (!DHT22_expect(0))
        return 0;
    if (!DHT22_expect(1))
        return 0;

    for (int i = 0; i < 80; i += 2) {
        cycles[i] = DHT22_expect(0);
        cycles[i + 1] = DHT22_expect(1);
    }
    sei();
}


int main(void) {
    while (1) {
    }
}