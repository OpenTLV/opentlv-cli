// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_DIAGNOSTICS_HPP
#define OPENTLV_CLI_DIAGNOSTICS_HPP
#include <iostream>

namespace cli {

// Prints "otlv: <message>" to stderr and returns code, so call sites can
// return a diagnostic in one expression: `return fail(2, "...");`.
inline int fail(int code, const char* message) {
    std::cerr << "otlv: " << message << "\n";
    return code;
}

// Flushes stdout and returns 0, or fail(3, ...) if writing to it failed.
// Shared by every command path that finishes by producing stdout output.
inline int flush_stdout() {
    std::cout.flush();
    return std::cout ? 0 : fail(3, "cannot write output");
}

} // namespace cli
#endif
