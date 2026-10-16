// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/support.hpp"

namespace cli {

std::string join(const std::vector<std::string>& items) {
    std::string result;
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (i) result += ' ';
        result += items[i];
    }
    return result;
}

std::vector<std::string> option_names(const std::vector<completion_option>& options) {
    std::vector<std::string> names;
    for (const completion_option& option : options) names.push_back(option.name());
    return names;
}

} // namespace cli
