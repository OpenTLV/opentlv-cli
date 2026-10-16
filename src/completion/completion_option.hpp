// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMPLETION_COMPLETION_OPTION_HPP
#define OPENTLV_CLI_COMPLETION_COMPLETION_OPTION_HPP
#include <string>
#include <vector>
#include "options.hpp"

namespace cli {

// One option valid for some command, and how to complete its value: a finite
// set of values, a file/path hint, or neither (free-form text, e.g. --hex).
class completion_option {
public:
    explicit completion_option(const option_entry& entry, const char* command = nullptr);

    const std::string& name() const {
        return name_;
    }
    bool takes_value() const {
        return takes_value_;
    }
    void set_takes_value(bool value) {
        takes_value_ = value;
    }
    bool is_path() const {
        return is_path_;
    }
    bool has_values() const {
        return !values_.empty();
    }
    const std::vector<std::string>& values() const {
        return values_;
    }

private:
    std::string              name_;
    bool                     takes_value_ = true;
    bool                     is_path_ = false;
    std::vector<std::string> values_;
};

} // namespace cli
#endif
