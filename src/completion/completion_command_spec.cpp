// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/completion_command_spec.hpp"
#include <utility>
#include "options.hpp"

namespace cli {

completion_command_spec::completion_command_spec(std::string name) : name_(std::move(name)) {
    std::size_t         count = 0;
    const option_entry* table = option_table(&count);
    const uint64_t      mask = command_options_mask(name_.c_str());
    const uint64_t      flags = flag_options_mask();
    for (std::size_t i = 0; i < count; ++i) {
        if (!(table[i].bit & mask)) continue;
        completion_option option(table[i], name_.c_str());
        // --value is a flag under "query" (print only the addressed values)
        // and a value-taking option (the encoded value bytes) under
        // "encode"; every other option's arity does not depend on the
        // command.
        option.set_takes_value(
            !(table[i].bit & flags) &&
            !(name_ == "query" && (option.name() == "--value" || option.name() == "--count")));
        options_.push_back(std::move(option));
    }
}

void completion_command_spec::set_positional_values(std::vector<std::string> values) {
    has_positional_ = true;
    positional_values_ = std::move(values);
}

} // namespace cli
