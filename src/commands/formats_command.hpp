// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_FORMATS_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_FORMATS_COMMAND_HPP
#include <string>
#include <vector>
#include "command.hpp"

namespace cli {

// The TLV format names enabled in this build (the same names --format
// accepts), in the order formats_command prints them. Shared with `otlv
// completion`'s --format value list.
std::vector<std::string> enabled_formats();

// otlv formats: prints the TLV formats enabled in this build, one per line.
class formats_command : public command {
public:
    int run() override;
};

} // namespace cli
#endif
