/* This file defines its own `open` helper. Calls to it must NOT be
 * counted as evidence of real filesystem syscall usage by the AI
 * assist heuristic resolver -- that is what this fixture exists to
 * exercise. */

int open(const char *label, int mode)
{
    (void)label;
    (void)mode;
    return -1;
}

int use_it(void)
{
    return open("not-a-real-file", 0);
}
