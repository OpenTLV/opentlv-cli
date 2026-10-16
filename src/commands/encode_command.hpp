// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_ENCODE_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_ENCODE_COMMAND_HPP
#include <cstdint>
#include <vector>
#include "command.hpp"
#include "options.hpp"

namespace cli {

// One TLV element to write: raw tag bytes in wire order and raw value bytes.
// --tag/--value build a single-element list of these; a JSON document
// (--input) is encoded recursively, with children written into their parent's
// value bytes, and does not use this type.
struct element_spec {
    std::vector<uint8_t> tag;
    std::vector<uint8_t> value;
};

// otlv encode: builds the elements from --tag/--value or a JSON document
// (--input), writes them with the selected format's OpenTLV writer,
// validates the result (using validate_command internally), and prints it as
// uppercase hex plus newline or as raw bytes (to stdout or --output-file).
class encode_command : public command {
public:
    explicit encode_command(const options& o) : options_(o) {}
    int run() override;

private:
    options options_;
};

} // namespace cli
#endif
