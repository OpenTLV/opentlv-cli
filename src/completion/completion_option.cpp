// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/completion_option.hpp"
#include "commands/formats_command.hpp"
#include "tlv/config.h"

namespace cli {

completion_option::completion_option(const option_entry& entry, const char* command)
    : name_(entry.name) {
    if (name_ == "--format") {
        values_ = enabled_formats();
    } else if (name_ == "--output-encoding") {
        if (command && std::string(command) == "generate")
            values_ = {"bin", "json"};
        else if (command)
            values_ = {"binary", "hex"};
        else
            values_ = {"binary", "hex", "bin", "json"};
    } else if (name_ == "--input-encoding") {
        values_ = {"binary", "hex"};
    } else if (name_ == "--output") {
        values_ = {"text", "json"};
    } else if (name_ == "--diagnostics") {
        values_ = {"human", "compact", "json"};
    } else if (name_ == "--backend") {
        values_ = {"auto", "streaming", "document"};
    } else if (name_ == "--fixed-byte-order") {
        values_ = {"big", "little"};
    } else if (name_ == "--module") {
#if OPENTLV_EMV
        values_.push_back("emv");
#endif
#if OPENTLV_BLUETOOTH
        values_.push_back("bluetooth");
#endif
    } else if (name_ == "--emv-check") {
        values_ = {"structure", "dictionary", "all"};
    } else if (name_ == "--emv-context") {
#if OPENTLV_EMV
        std::size_t        count = 0;
        const char* const* names = emv_context_names(&count);
        for (std::size_t i = 0; i < count; ++i) values_.push_back(names[i]);
#endif
    } else if (name_ == "--input" || name_ == "--output-file" || name_ == "--output-dir") {
        is_path_ = true;
    }
}

} // namespace cli
