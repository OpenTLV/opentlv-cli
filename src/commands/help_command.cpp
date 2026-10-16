// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/help_command.hpp"
#include "diagnostics.hpp"
#include "options.hpp"

namespace cli {

int help_command::run() {
    options::usage();
    return flush_stdout();
}

} // namespace cli
