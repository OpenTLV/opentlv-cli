// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/tags_command.hpp"
#include <algorithm>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "commands/emv_dictionary.hpp"
#include "diagnostics.hpp"
#include "presentation.hpp"
#include "tlv/config.h"
#if OPENTLV_EMV
#include "tlv++/builtins/emv/dictionary.hpp"
#include "tlv++/builtins/asn1/ber.hpp"
#endif

namespace cli {

int tags_command::run() {
    const options& o = options_;
#if OPENTLV_EMV
    const tlv::emv::dictionary              dictionary;
    std::vector<tlv::emv::dictionary_entry> matches;
    const std::string                       needle = o.search ? lowercase(o.search) : "";
    for (size_t i = 0; i < dictionary.size(); ++i) {
        const auto definition = dictionary.at(i);
        if (definition && lowercase(definition.name()).find(needle) != std::string::npos)
            matches.push_back(definition);
    }
    std::sort(matches.begin(), matches.end(), emv_tag_less);

    if (!strcmp(o.output, "json")) {
        nlohmann::json document;
        document["module"] = o.module;
        document["tags"] = nlohmann::json::array();
        for (size_t i = 0; i < matches.size(); ++i)
            document["tags"].push_back(emv_definition_json(matches[i].tag(), matches[i]));
        std::cout << document.dump() << "\n";
    } else {
        for (size_t i = 0; i < matches.size(); ++i)
            std::cout << std::left << std::setw(8) << tag_hex_string(matches[i].tag())
                      << matches[i].name() << "\n";
    }
    return flush_stdout();
#else
    (void)o;
    return fail(2, "EMV module is disabled in this build");
#endif
}

} // namespace cli
