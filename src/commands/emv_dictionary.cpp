// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/emv_dictionary.hpp"
#include "commands/support.hpp"
#include <cctype>
#include <cstring>
#include "diagnostics.hpp"
#include "input.hpp"
#include "presentation.hpp"
#if OPENTLV_EMV
#endif

using cli::fail;

namespace cli {

#if OPENTLV_EMV

std::string tag_hex_string(tlv::tag tag) {
    return hex_string(tag.as_bytes());
}

std::string emv_length_range(tlv::bounds entry) {
    std::string text = std::to_string(entry.minimum);
    if (entry.maximum == SIZE_MAX)
        text += "..unbounded";
    else if (entry.maximum != entry.minimum)
        text += ".." + std::to_string(entry.maximum);
    return text;
}

nlohmann::json emv_definition_json(tlv::tag tag, tlv::emv::dictionary_entry definition) {
    nlohmann::json object;
    object["tag"] = tag_hex_string(tag);
    object["known"] = true;
    object["name"] = definition.name();
    object["symbol"] = definition.symbol();
    object["type"] = tlv::emv::description(definition.kind());
    object["constructed"] = tlv::ber::format{}.is_constructed(tag);
    object["min_length"] = (uint64_t)definition.length().minimum;
    if (definition.length().maximum != SIZE_MAX)
        object["max_length"] = (uint64_t)definition.length().maximum;
    object["length_step"] = (uint64_t)definition.length_step();
    return object;
}

std::string lowercase(std::string text) {
    for (size_t i = 0; i < text.size(); ++i) text[i] = (char)tolower((unsigned char)text[i]);
    return text;
}

bool emv_tag_less(tlv::emv::dictionary_entry a, tlv::emv::dictionary_entry b) {
    return a.tag() < b.tag();
}

int parse_emv_tag(const char* text, std::vector<uint8_t>& bytes, tlv::tag& tag) {
    size_t used = 0;
    int    rc = decode_hex(text, tlv::ber::max_tag_size, bytes);
    if (rc == 3) return fail(2, "tag is longer than the longest tag a supported format accepts");
    if (rc) return rc;
    if (bytes.empty()) return fail(2, "tag must not be empty");
    const auto parsed = tlv::ber::read_identifier(
        tlv::bytes(reinterpret_cast<const tlv::byte*>(bytes.data()), bytes.size()), used);
    if (!parsed || used != bytes.size()) return fail(2, "tag is not a single complete BER tag");
    tag = *parsed;
    return 0;
}

#endif

} // namespace cli
