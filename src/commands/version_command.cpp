// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/version_command.hpp"
#include <iostream>
#include "diagnostics.hpp"
#include "cli/version.hpp"

namespace cli {

int version_command::run() {
    std::cout << "OpenTLV CLI " << OPENTLV_CLI_VERSION << "\n";
    return flush_stdout();
}

} // namespace cli
