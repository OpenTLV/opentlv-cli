// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

// Deliberate faults in a separate test executable. Never linked into otlv.
#include <cstdlib>
#include <limits>

int main(int argc, char**) {
    if (argc == 2) {
        volatile int value = std::numeric_limits<int>::max();
        return value + 1;
    }
    volatile char* data = static_cast<char*>(std::malloc(8));
    if (!data) return 2;
    std::free(const_cast<char*>(data));
    return data[0];
}
