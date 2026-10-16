// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/tag_command.hpp"
#include <cstring>
#include <iostream>
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

int tag_command::run() {
    const options& o = options_;
#if OPENTLV_EMV
    std::vector<uint8_t> bytes;
    tlv::tag             parsed;
    int                  rc = parse_emv_tag(o.tag, bytes, parsed);
    if (rc) return rc;

    tlv::emv::dictionary_entry definition = tlv::emv::dictionary{}.find(parsed);
    const std::string          tag_hex = tag_hex_string(parsed);

    if (!strcmp(o.output, "json")) {
        nlohmann::json document;
        if (definition) document = emv_definition_json(parsed, definition);
        document["tag"] = tag_hex;
        document["module"] = o.module;
        document["known"] = bool(definition);
        std::cout << document.dump() << "\n";
    } else if (!definition) {
        std::cout << "Tag:         " << tag_hex << "\n"
                  << "Result:      Unknown tag in the EMV module (base context)\n";
    } else {
        std::cout << "Tag:         " << tag_hex << "\n"
                  << "Name:        " << definition.name() << "\n"
                  << "Type:        " << tlv::emv::description(definition.kind()) << "\n"
                  << "Form:        "
                  << (tlv::ber::format{}.is_constructed(parsed) ? "Constructed" : "Primitive")
                  << "\n"
                  << "Length:      " << emv_length_range(definition.length()) << "\n";
        if (definition.length_step() != 1)
            std::cout << "Length step: " << definition.length_step() << "\n";
    }
    return flush_stdout();
#else
    (void)o;
    return fail(2, "EMV module is disabled in this build");
#endif
}

} // namespace cli
