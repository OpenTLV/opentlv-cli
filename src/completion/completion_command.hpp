// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_COMPLETION_COMMAND_HPP
#define OPENTLV_CLI_COMPLETION_COMPLETION_COMMAND_HPP
#include <string>
#include <utility>
#include "command.hpp"

namespace cli {

// otlv completion SHELL: prints a shell completion script for "bash", "zsh",
// "fish" or "powershell" to stdout, describing otlv's commands and options as
// this build supports them (enabled formats, and EMV/fixed options only when
// their module/format is compiled in). An empty (no argument given) or
// unknown shell name is a usage error (exit code 2).
class completion_command : public command {
public:
    explicit completion_command(std::string shell) : shell_(std::move(shell)) {}
    int run() override;

private:
    std::string shell_;
};

} // namespace cli
#endif
