// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_EMV_DICTIONARY_HPP
#define OPENTLV_CLI_COMMANDS_EMV_DICTIONARY_HPP
#include <cstdint>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "tlv/config.h"
#if OPENTLV_EMV
#include "tlv++/builtins/emv/dictionary.hpp"
#include "tlv++/builtins/asn1/ber.hpp"
#endif

// Small helpers shared by tag_command and tags_command (both look up entries
// in the same EMV base-context dictionary), kept out of either command's own
// file.

namespace cli {

#if OPENTLV_EMV
std::string tag_hex_string(tlv::tag tag);

// "6", "1..10" or "0..unbounded" from the dictionary's inclusive length bounds.
std::string emv_length_range(tlv::bounds entry);

// Metadata object shared by "tag" and "tags" --output json.
nlohmann::json emv_definition_json(tlv::tag tag, tlv::emv::dictionary_entry definition);

std::string lowercase(std::string text);

bool emv_tag_less(tlv::emv::dictionary_entry a, tlv::emv::dictionary_entry b);

// Decodes `text` and requires it to be exactly one complete BER tag. The
// parsed tag borrows `bytes`, which must outlive it.
int parse_emv_tag(const char* text, std::vector<uint8_t>& bytes, tlv::tag& tag);
#endif

} // namespace cli
#endif
