// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_JSON_MODEL_HPP
#define OPENTLV_CLI_JSON_MODEL_HPP
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace cli {
namespace json_model {

// The versioned TLV JSON document shared by "decode" (writer) and
// "encode --input" (reader); see docs/cli/json-schema.md.
extern const char* const schema_name;
enum { schema_version = 1 };

// One element of the document. Exactly one of has_value (a primitive, whose
// raw value bytes are in `value`) and has_children (a constructed element)
// is set. Lengths are never stored: they are derived when encoding.
struct node {
    std::vector<uint8_t> tag;
    bool                 has_value = false;
    std::vector<uint8_t> value;
    bool                 has_children = false;
    bool                 indefinite = false; // BER indefinite length ("length_mode")
    bool                 has_length_mode = false;
    std::vector<node>    children;
};

struct document {
    std::vector<node> elements;
};

// Parses and validates a document against the JSON schema without building
// an intermediate JSON tree. `format` is the --format name: a "format"
// member, when present, must equal it. Unknown or duplicate members,
// wrong types, malformed hexadecimal, an unsupported version and a missing
// required member are rejected (returns 2, diagnostic on stderr). Nesting
// deeper than `max_depth` or more than `max_elements` elements returns 3.
// Returns 0 on success.
int parse(const std::string& text, const char* format, std::size_t max_depth,
          std::size_t max_elements, document& doc);

} // namespace json_model
} // namespace cli
#endif
