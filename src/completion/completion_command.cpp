// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/completion_command.hpp"
#include <iostream>
#include <memory>
#include "completion/bash_completer.hpp"
#include "completion/completion_model.hpp"
#include "completion/fish_completer.hpp"
#include "completion/powershell_completer.hpp"
#include "completion/shell_completer.hpp"
#include "completion/zsh_completer.hpp"
#include "diagnostics.hpp"

namespace cli {

int completion_command::run() {
    if (shell_.empty())
        return fail(2, "completion requires a shell: bash, zsh, fish or powershell");
    const completion_model           model = completion_model::build();
    std::unique_ptr<shell_completer> completer;
    if (shell_ == "bash")
        completer.reset(new bash_completer());
    else if (shell_ == "zsh")
        completer.reset(new zsh_completer());
    else if (shell_ == "fish")
        completer.reset(new fish_completer());
    else if (shell_ == "powershell")
        completer.reset(new powershell_completer());
    else
        return fail(2, "unknown shell; use bash, zsh, fish or powershell");
    completer->render(std::cout, model);
    return flush_stdout();
}

} // namespace cli
