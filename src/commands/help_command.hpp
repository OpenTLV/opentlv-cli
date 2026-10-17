// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_HELP_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_HELP_COMMAND_HPP
#include "command.hpp"

namespace cli {

// otlv --help: prints the usage text (options::usage()) to stdout.
class help_command : public command {
public:
    int run() override;
};

} // namespace cli
#endif
