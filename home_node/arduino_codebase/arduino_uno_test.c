#include <avr/io.h>
#define F_CPU 16000000UL
#include <util/delay.h>

int main(void) {
    uint8_t delay = 50;
    DDRB |= (1 << PORTB5);
    DDRD = 0xFF;
    PORTD |= (1 << PORTD2);

    while (1) {
        _delay_ms(delay);
        if (PORTB != 0x20) {
            PORTD <<= 1;
        } else {
            PORTD >>= 1;
        }
        if (PORTD >= 0x80 || PORTD <= 0b100) {
            PORTB ^= (1 << PORTB5);
            _delay_ms(delay * 2);
        }
    }
    return 0;
}