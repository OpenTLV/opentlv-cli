// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_VERSION_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_VERSION_COMMAND_HPP
#include "command.hpp"

namespace cli {

// otlv --version: prints "otlv <version>" to stdout.
class version_command : public command {
public:
    int run() override;
};

} // namespace cli
#endif
