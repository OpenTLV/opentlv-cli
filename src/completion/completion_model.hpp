// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_COMPLETION_MODEL_HPP
#define OPENTLV_CLI_COMPLETION_COMPLETION_MODEL_HPP
#include <string>
#include <vector>
#include "completion/completion_command_spec.hpp"
#include "completion/completion_option.hpp"

namespace cli {

// The commands and options `otlv completion` renders.
class completion_model {
public:
    static completion_model build();

    const std::vector<completion_command_spec>& commands() const {
        return commands_;
    }
    // Every option some command accepts in this build, with its
    // value-completion hint, for the "$prev" (bash/zsh) or option-name
    // (fish/PowerShell) value-completion branches, which do not need to be
    // repeated per command.
    std::vector<completion_option> all_options() const;
    // Every command name, plus the top-level-only "--help"/"--version".
    std::vector<std::string> command_names() const;

private:
    std::vector<completion_command_spec> commands_;
};

} // namespace cli
#endif
