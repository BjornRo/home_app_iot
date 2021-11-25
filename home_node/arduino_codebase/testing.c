/******************************************************************************

                            Online C Compiler.
                Code, Compile, Run and Debug C program online.
Write your code in this editor and press "Run" button to compile and execute it.

*******************************************************************************/
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>

int main() {
    char * string = "(1,4)";
    char * string2 = "(1,4,1)";

    int i;
    int j;
    int k;
    int v = sscanf(string, "(%d,%d,%d)", &i,&j,&k);
    int d = (0b11111111 & (0b00 << 2)) ;
    int f = 0xC3;

    printf("v: %d\n", v);
    printf("i: %d\n", i);
    printf("j: %d\n", j);
    printf("k: %d\n", k);
    printf("d: %d\n", d);
    printf("f: %d\n", f);
    return 0;
}
