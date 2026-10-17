// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_OPTIONS_HPP
#define OPENTLV_CLI_OPTIONS_HPP
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>
#include <string>
#include "tlv/config.h"
#include "tlv++/query/query.hpp"

namespace cli {

// Parses and validates otlv's command-line arguments.
// Fields are set to their command-line defaults on construction and
// overwritten by parse(); on failure it prints a diagnostic (via cli::fail)
// and returns a nonzero exit code, matching this CLI's exit-code contract.
enum { emv_check_structure = 1, emv_check_dictionary = 2 };

class options {
public:
    int         parse(int argc, char** argv);
    static void usage();

    const char* command = nullptr;
    const char* format = nullptr;
    const char* input = nullptr;
    const char* hex = nullptr;
    const char* module = nullptr;
    std::size_t max_input = 16777216;
    std::size_t max_depth = 64;
    std::size_t max_elements = 100000;
    uint64_t    seed = 0;
    uint64_t    count = 0;
    const char* output_dir = nullptr;
    bool        json_output = false;
    std::size_t max_value_size = 256;
    std::size_t max_case_size = 4096;
    int         tree = 0;
    int         pretty = 0;
    int         describe = 0;
    int         color = 0;
    int         hex_input = 0;
    int         pdol = 0;
    int         decode = 0;
    // dump/decode only: resynchronize after damaged data instead of failing.
    int recover = 0;
    // EMV dictionary context (tlv_emv_context_t) the top-level elements start in.
    int emv_context = 0;
    // validate --module emv only: bit mask of emv_check_* (0 = default).
    int         emv_check = 0;
    const char* output = "text";
    // dump/validate/decode/query only: shape of the diagnostic printed on
    // failure, or of a --recover skipped range.
    const char* diagnostics = "human";
    // encode only: tag/value hex text and whether to emit raw bytes.
    const char* tag = nullptr;
    const char* value = nullptr;
    int         binary_output = 0;
    // encode only: write the encoded bytes to this file instead of stdout.
    const char* output_file = nullptr;
    // tags only: case-insensitive name filter.
    const char* search = nullptr;
    // query only: the path text, its parsed form and whether to print only
    // the values of the addressed elements.
    const char*                       path = nullptr;
    std::shared_ptr<const tlv::query> query;
    int                               value_only = 0;
    bool                              query_count = false;
    bool                              query_exists = false;
    bool                              query_explain = false;
    const char*                       query_backend = "auto";
    std::vector<std::string>          query_variables;
    const char*                       against = nullptr;
    const char*                       where = nullptr;
    // --format fixed only: tag width, length width and length byte order.
    std::size_t fixed_tag_size = 1;
    std::size_t fixed_length_size = 1;
    const char* fixed_byte_order = "big";
};

// One "--name" option recognized by options::parse(), and the bit it sets.
// Exposed (with command_options_mask() and flag_options_mask() below) so
// `otlv completion` can derive its per-command option lists from the same
// tables parse() enforces, instead of a separately maintained copy.
struct option_entry {
    const char* name;
    uint64_t    bit;
};
const option_entry* option_table(std::size_t* count);

// The bitmask of options valid for `command` (one of "generate", "dump", "validate",
// "decode", "encode", "query", "tag" or "tags"; 0 for any other name),
// narrowed to this build: EMV-only options are removed unless
// OPENTLV_EMV. Fixed format options are always available.
uint64_t command_options_mask(const char* command);

// The bitmask of options that never take a following value (booleans such as
// --tree or --recover). Every other option in option_table() takes one,
// except --value under the "query" command, where it means --value's other,
// flag-only sense (print only the addressed elements' values).
uint64_t flag_options_mask();

#if OPENTLV_EMV
// The command-line names of the EMV dictionary contexts (tlv_emv_context_t)
// --emv-context accepts, in the same order as options.cpp's own table.
const char* const* emv_context_names(std::size_t* count);
#endif

} // namespace cli
#endif
