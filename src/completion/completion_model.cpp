// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/completion_model.hpp"
#include <utility>
#include "options.hpp"
#include "tlv/config.h"

namespace cli {

completion_model completion_model::build() {
    completion_model model;
    for (const char* name : {"dump", "validate", "decode", "encode", "generate", "query"})
        model.commands_.push_back(completion_command_spec(name));
#if OPENTLV_EMV
    // tag/tags always fail at runtime without the EMV dictionary, so they are
    // not worth completing in a build that lacks it.
    for (const char* name : {"tag", "tags"})
        model.commands_.push_back(completion_command_spec(name));
#endif
#if OPENTLV_DOCUMENT
    model.commands_.push_back(completion_command_spec("diff"));
#endif
    model.commands_.push_back(completion_command_spec("formats"));
    completion_command_spec completion_spec("completion");
    completion_spec.set_positional_values({"bash", "zsh", "fish", "powershell"});
    model.commands_.push_back(std::move(completion_spec));
    return model;
}

std::vector<completion_option> completion_model::all_options() const {
    uint64_t available = 0;
    for (const char* name :
         {"dump", "validate", "decode", "encode", "generate", "query", "diff", "tag", "tags"})
        available |= command_options_mask(name);
    std::size_t                    count = 0;
    const option_entry*            table = option_table(&count);
    std::vector<completion_option> result;
    for (std::size_t i = 0; i < count; ++i)
        if (table[i].bit & available) result.push_back(completion_option(table[i]));
    return result;
}

std::vector<std::string> completion_model::command_names() const {
    std::vector<std::string> names;
    for (const completion_command_spec& command : commands_) names.push_back(command.name());
    names.push_back("--help");
    names.push_back("--version");
    return names;
}

} // namespace cli
