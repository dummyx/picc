long add_long(long a, long b);
int main(void) {
    return add_long(4000000000l, 1l) == 4000000001l ? 7 : 1;
}
