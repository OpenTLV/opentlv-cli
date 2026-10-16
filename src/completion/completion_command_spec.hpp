// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_COMPLETION_COMMAND_SPEC_HPP
#define OPENTLV_CLI_COMPLETION_COMPLETION_COMMAND_SPEC_HPP
#include <string>
#include <vector>
#include "completion/completion_option.hpp"

namespace cli {

// One otlv command (or "formats", which has neither options nor a positional
// argument) and, for "completion", its positional argument (a free-form one,
// like "query"'s path or "tag"'s hex, is simply not modeled: has_positional()
// stays false and nothing offers it a completion). Its option list is
// derived from cli::command_options_mask() and cli::option_table() -- the
// same tables options::parse() enforces -- so an option added there
// automatically appears here too.
class completion_command_spec {
public:
    explicit completion_command_spec(std::string name);

    const std::string& name() const {
        return name_;
    }
    const std::vector<completion_option>& options() const {
        return options_;
    }
    bool has_positional() const {
        return has_positional_;
    }
    const std::vector<std::string>& positional_values() const {
        return positional_values_;
    }
    void set_positional_values(std::vector<std::string> values);

private:
    std::string                    name_;
    std::vector<completion_option> options_;
    bool                           has_positional_ = false;
    std::vector<std::string>       positional_values_;
};

} // namespace cli
#endif
