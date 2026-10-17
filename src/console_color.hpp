// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_CONSOLE_COLOR_HPP
#define OPENTLV_CLI_CONSOLE_COLOR_HPP
#include <ostream>

namespace cli {

// RAII guard: for its lifetime, wraps everything written to `stream` in the
// CLI's ANSI SGR tag accent color (cyan), or does nothing when `enabled` is
// false (redirected output, --no-color). Scopes are not meant to nest.
class console_color {
public:
    console_color(std::ostream& stream, bool enabled) : stream_(stream), enabled_(enabled) {
        if (enabled_) stream_ << "\033[36m";
    }
    ~console_color() {
        if (enabled_) stream_ << "\033[0m";
    }
    console_color(const console_color&) = delete;
    console_color& operator=(const console_color&) = delete;

private:
    std::ostream& stream_;
    bool          enabled_;
};

} // namespace cli
#endif
