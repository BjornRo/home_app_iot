
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

char* key[8];
float value;
int read_simple_json(char* payload, float payload_vals[]) {
    int i = 0;
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

int main() {
    // char json[80] = "{\"temperature\":4459,\"humidity\":100.00,\"airpressure\":1000.99}";
    char ARDUINO_DATA[41];
    char SEND_BUFFER[41];
    char RECEIVE_BUFFER[80] = "{\"temperature\":-14.44}";
    float payload_values[5];
    char bike_room_temp[50];
    // char payload_cpy[] = "[2,2]";
    char ARDUINO_CHAR;
    float first, second;

    // sscanf(RECEIVE_BUFFER, "(%c,(%[^)])", &ARDUINO_CHAR, ARDUINO_DATA);
    // if (ARDUINO_CHAR == 'T') {
    //     sscanf(ARDUINO_DATA, "%f,%f", &first, &second);
    //     snprintf(SEND_BUFFER, 41, "{\"temperature\":%.2f,\"humidity\":%.2f}", first / 100, second / 100);
    // } else if (ARDUINO_CHAR == 'S') {
    //     SEND_BUFFER[0] = '[';
    //     int len = strlen(ARDUINO_DATA);
    //     for (int i = 0; i < len; i++) {
    //         SEND_BUFFER[i + 1] = ARDUINO_DATA[i];
    //     }
    //     SEND_BUFFER[len+1] = ']';
    //     SEND_BUFFER[len+2] = '\0';
    // }
    int i = read_simple_json(RECEIVE_BUFFER, payload_values);
    printf("%d\n", i);
    // printf("%s\n", RECEIVE_BUFFER);

    char* b = "'{\"s\": \"1\" }'";
    printf("%s\n", b);
    int id, value;
    int a = sscanf(b, "'{\"%d\":%d}'", &id, &value);
    printf("%d\n", a);
    printf("%d\n", id);
    printf("%d\n", value);

    // if (!(payload_cpy[0] == '[' && payload_cpy[payload_len - 1] == ']')) {
    //     int n = read_simple_json(payload_cpy, payload_values);
    //     for (int i = 0; i < n; i++) {
    //         printf("%s || %.2f\n", key[i], payload_values[i]);
    //     }
    //     printf("%d\n", n);
    // }

    return 0;
}
