// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_SUPPORT_HPP
#define OPENTLV_CLI_COMPLETION_SUPPORT_HPP
#include <string>
#include <vector>
#include "completion/completion_option.hpp"

// Small text-building helpers shared by the shell_completer subclasses.

namespace cli {

std::string join(const std::vector<std::string>& items);

std::vector<std::string> option_names(const std::vector<completion_option>& options);

} // namespace cli
#endif
