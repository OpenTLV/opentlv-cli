// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_ZSH_COMPLETER_HPP
#define OPENTLV_CLI_COMPLETION_ZSH_COMPLETER_HPP
#include "completion/shell_completer.hpp"

namespace cli {

class zsh_completer : public shell_completer {
public:
    void render(std::ostream& out, const completion_model& model) const override;
};

} // namespace cli
#endif
