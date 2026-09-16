#include "point.h"
int main(void) {
    struct point p = {3, 4};
    return p.x * 10 + p.y;
}
