// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMAND_FACTORY_HPP
#define OPENTLV_CLI_COMMAND_FACTORY_HPP
#include <memory>
#include "command.hpp"

namespace cli {

// Parses argv into the command object to run.
class command_factory {
public:
    // On a usage error, prints the diagnostic (via cli::fail) itself and
    // returns NULL with *error_code set to the process exit code; otherwise
    // returns the command to run.
    static std::unique_ptr<command> create(int argc, char** argv, int* error_code);
};

} // namespace cli
#endif
