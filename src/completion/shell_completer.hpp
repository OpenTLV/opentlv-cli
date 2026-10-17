// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_SHELL_COMPLETER_HPP
#define OPENTLV_CLI_COMPLETION_SHELL_COMPLETER_HPP
#include <ostream>
#include "completion/completion_model.hpp"

namespace cli {

// Renders a completion_model as one shell's completion script. Keeps
// shell-specific text generation isolated from the command/option model, so
// another shell can be added (its own subclass, in its own file) without
// touching the model or the other shells.
class shell_completer {
public:
    virtual ~shell_completer() = default;
    virtual void render(std::ostream& out, const completion_model& model) const = 0;
};

} // namespace cli
#endif
