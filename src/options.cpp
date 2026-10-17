// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "options.hpp"
#include "diagnostics.hpp"
#include <cstdint>
#include <cstring>
#include <iostream>
#include "tlv/config.h"
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"
#if OPENTLV_EMV
#include "tlv++/builtins/emv/dictionary.hpp"
#endif

namespace {

// Option bits, matched by name in options::parse().
enum : uint64_t {
    opt_tree = 1,
    opt_format = 2,
    opt_input = 4,
    opt_hex = 8,
    opt_max_input = 16,
    opt_max_depth = 32,
    opt_max_elements = 64,
    opt_pretty = 128,
    opt_describe = 256,
    opt_force_color = 512,
    opt_no_color = 1024,
    opt_module = 2048,
    opt_input_encoding = 4096,
    opt_pdol = 8192,
    opt_decode = 16384,
    opt_output = 32768,
    opt_tag = 65536,
    opt_value = 131072,
    opt_output_encoding = 262144,
    opt_search = 524288,
    opt_recover = 1048576,
    opt_emv_context = 2097152,
    opt_emv_check = 4194304,
    opt_output_file = 8388608,
    opt_diagnostics = 16777216,
    opt_fixed_tag_size = 33554432,
    opt_fixed_length_size = 67108864,
    opt_fixed_byte_order = 134217728,
    opt_seed = UINT64_C(1) << 28,
    opt_count = UINT64_C(1) << 29,
    opt_output_dir = UINT64_C(1) << 30,
    opt_max_value = UINT64_C(1) << 31,
    opt_max_case = UINT64_C(1) << 32,
    opt_exists = UINT64_C(1) << 33,
    opt_explain = UINT64_C(1) << 34,
    opt_var = UINT64_C(1) << 35,
    opt_backend = UINT64_C(1) << 36,
    opt_query = UINT64_C(1) << 37,
    opt_against = UINT64_C(1) << 38,
    opt_where = UINT64_C(1) << 39,
    generate_only = opt_seed | opt_count | opt_output_dir | opt_max_value | opt_max_case,
    // Options only encode takes.
    encode_only = opt_tag | opt_value | opt_output_encoding | opt_output_file,
    // --format fixed only.
    fixed_only = opt_fixed_tag_size | opt_fixed_length_size | opt_fixed_byte_order,
    // EMV-only presentation and validation options.
    emv_only = opt_describe | opt_emv_context | opt_emv_check,
    // Every option bit, used to build dump's and validate's masks below by
    // exclusion, the same way their validity checks in parse() do.
    all_options = opt_tree | opt_format | opt_input | opt_hex | opt_max_input | opt_max_depth |
        opt_max_elements | opt_pretty | opt_describe | opt_force_color | opt_no_color | opt_module |
        opt_input_encoding | opt_pdol | opt_decode | opt_output | opt_tag | opt_value |
        opt_output_encoding | opt_search | opt_recover | opt_emv_context | opt_emv_check |
        opt_output_file | opt_diagnostics | opt_fixed_tag_size | opt_fixed_length_size |
        opt_fixed_byte_order,
    // Options that are plain flags: every other option in the table below
    // takes a following value, except --value under "query" (see
    // flag_options_mask()'s doc comment in options.hpp).
    flag_only = opt_tree | opt_pdol | opt_decode | opt_pretty | opt_describe | opt_force_color |
        opt_no_color | opt_recover | opt_exists | opt_explain
};

// Options valid for each command, matched by options::parse() below and
// reused by command_options_mask() for `otlv completion`.
const uint64_t generate_options = opt_format | fixed_only | opt_max_depth | opt_max_elements |
                                  generate_only | opt_output_encoding;
const uint64_t lookup_options = opt_module | opt_output;
const uint64_t listing_options = opt_module | opt_output | opt_search;
const uint64_t query_options = opt_format | opt_input | opt_hex | opt_max_input | opt_max_depth |
                               opt_max_elements | opt_input_encoding | opt_output | opt_value |
                               opt_diagnostics | fixed_only | opt_count | opt_exists | opt_explain |
                               opt_var | opt_backend | opt_query;
const uint64_t diff_options = opt_format | opt_input | opt_against | opt_where | fixed_only |
                              opt_max_input | opt_max_depth | opt_max_elements | opt_output |
                              opt_diagnostics;
const uint64_t encode_options = opt_format | opt_input | opt_max_input | opt_max_depth |
                                opt_max_elements | encode_only | fixed_only;
const uint64_t decode_options = opt_format | opt_input | opt_hex | opt_max_input | opt_max_depth |
                                opt_max_elements | opt_describe | opt_module | opt_input_encoding |
                                opt_decode | opt_recover | opt_emv_context | opt_diagnostics |
                                fixed_only;
const uint64_t dump_options = all_options & ~(encode_only | opt_search | opt_emv_check);
const uint64_t validate_options = all_options & ~(encode_only | opt_search | opt_recover);

int number(const char* text, std::size_t* out) {
    std::size_t n = 0;
    if (!*text) return 0;
    for (; *text; ++text) {
        unsigned digit = (unsigned)(*text - '0');
        if (digit > 9 || n > (SIZE_MAX - digit) / 10) return 0;
        n = n * 10 + digit;
    }
    *out = n;
    return 1;
}

#if OPENTLV_EMV
struct context_name {
    const char* name;
    int         context;
};

// Command-line names of the EMV dictionary contexts (tlv_emv_context_t).
const context_name context_names[] = {
    {"base", static_cast<int>(tlv::emv::context::base)},
    {"bit", static_cast<int>(tlv::emv::context::bit)},
    {"bht", static_cast<int>(tlv::emv::context::bht)},
    {"bht-format", static_cast<int>(tlv::emv::context::bht_format)},
    {"bit-group", static_cast<int>(tlv::emv::context::bit_group)},
    {"biometric-counters", static_cast<int>(tlv::emv::context::biometric_counters)},
    {"biometric-attempts", static_cast<int>(tlv::emv::context::biometric_attempts)},
    {"biometric-verification", static_cast<int>(tlv::emv::context::biometric_verification)},
};

int context_by_name(const char* text, int* out) {
    for (const context_name& entry : context_names) {
        if (!strcmp(text, entry.name)) {
            *out = entry.context;
            return 1;
        }
    }
    return 0;
}
#endif

// Every "--name" option options::parse() recognizes, and the bit it sets.
// Shared by option_bit() below and, via cli::option_table(), by `otlv
// completion`'s per-command option lists.
const cli::option_entry option_table_data[] = {
    {"--against", opt_against},
    {"--where", opt_where},
    {"--exists", opt_exists},
    {"--explain", opt_explain},
    {"--var", opt_var},
    {"--backend", opt_backend},
    {"--query", opt_query},
    {"--seed", opt_seed},
    {"--count", opt_count},
    {"--output-dir", opt_output_dir},
    {"--max-value-size", opt_max_value},
    {"--max-case-size", opt_max_case},
    {"--tree", opt_tree},
    {"--format", opt_format},
    {"--input", opt_input},
    {"--hex", opt_hex},
    {"--max-input-size", opt_max_input},
    {"--max-depth", opt_max_depth},
    {"--max-elements", opt_max_elements},
    {"--pretty", opt_pretty},
    {"--describe", opt_describe},
    {"--force-color", opt_force_color},
    {"--no-color", opt_no_color},
    {"--module", opt_module},
    {"--input-encoding", opt_input_encoding},
    {"--pdol", opt_pdol},
    {"--decode", opt_decode},
    {"--output", opt_output},
    {"--tag", opt_tag},
    {"--value", opt_value},
    {"--output-encoding", opt_output_encoding},
    {"--search", opt_search},
    {"--recover", opt_recover},
    {"--emv-context", opt_emv_context},
    {"--emv-check", opt_emv_check},
    {"--output-file", opt_output_file},
    {"--diagnostics", opt_diagnostics},
    {"--fixed-tag-size", opt_fixed_tag_size},
    {"--fixed-length-size", opt_fixed_length_size},
    {"--fixed-byte-order", opt_fixed_byte_order},
};
constexpr std::size_t option_table_count = sizeof(option_table_data) / sizeof(option_table_data[0]);

uint64_t option_bit(const char* arg) {
    for (const cli::option_entry& entry : option_table_data)
        if (!strcmp(arg, entry.name)) return entry.bit;
    return 0;
}

} // namespace

namespace cli {

int options::parse(int argc, char** argv) {
    uint64_t seen = 0;
    int      i;
    command = argv[1];
    const bool generating = argc > 1 && !strcmp(command, "generate");
    if (generating) {
        max_depth = 4;
        max_elements = 32;
    }
    const bool encoding = argc > 1 && !strcmp(command, "encode");
    const bool lookup = argc > 1 && !strcmp(command, "tag");
    const bool listing = argc > 1 && !strcmp(command, "tags");
    const bool decoding = argc > 1 && !strcmp(command, "decode");
    const bool validating = argc > 1 && !strcmp(command, "validate");
    const bool querying = argc > 1 && !strcmp(command, "query");
    const bool diffing = argc > 1 && !strcmp(command, "diff");
    if (strcmp(command, "dump") && !validating && !decoding && !encoding && !lookup && !listing &&
        !querying && !generating && !diffing)
        return fail(2, "unknown command; use --help");
    i = 2;
    if (querying) {
        // query takes the path as a positional argument: otlv query 6F/A5/50 --format ber ...
        if (argc >= 3 && strncmp(argv[2], "--", 2)) {
            path = argv[2];
            i = 3;
        }
    }
    if (lookup) {
        // tag takes the tag bytes as a positional argument: otlv tag 9F02 --module emv
        if (argc < 3 || !strncmp(argv[2], "--", 2)) return fail(2, "tag requires a hex tag");
        tag = argv[2];
        i = 3;
    }
    for (; i < argc; ++i) {
        const uint64_t bit = option_bit(argv[i]);
        if (!bit) return fail(2, "unknown option; use --help");
        if ((bit & (opt_against | opt_where)) && !diffing) return fail(2, "option requires diff");
        if ((bit & (opt_exists | opt_explain | opt_var | opt_backend | opt_query)) && !querying)
            return fail(2, "option requires query");
        // Each command accepts only its own options. dump and validate share
        // the input, limit and presentation options; decode takes the subset
        // that makes sense for a JSON export. The per-command masks are the
        // file-scope constants above, shared with command_options_mask() for
        // `otlv completion`.
        if (!generating && (bit & generate_only) && !(querying && bit == opt_count))
            return fail(2, "option requires generate");
        if (generating   ? !(bit & generate_options)
            : diffing    ? !(bit & diff_options)
            : lookup     ? !(bit & lookup_options)
            : listing    ? !(bit & listing_options)
            : querying   ? !(bit & query_options)
            : encoding   ? !(bit & encode_options)
            : decoding   ? !(bit & decode_options)
            : validating ? (bit & (encode_only | opt_search | opt_recover))
                         : (bit & (encode_only | opt_search | opt_emv_check)))
            return fail(2, generating            ? "option is not valid for generate"
                           : lookup              ? "option is not valid for tag"
                           : listing             ? "option is not valid for tags"
                           : querying            ? "option is not valid for query"
                           : encoding            ? "option is not valid for encode"
                           : decoding            ? "option is not valid for decode"
                           : (bit & encode_only) ? "option requires encode"
                           : (bit & opt_search)  ? "option requires tags"
                           : (bit & opt_recover) ? "--recover requires dump or decode"
                                                 : "--emv-check requires validate");
        if ((seen & bit) && bit != opt_var) return fail(2, "duplicate option");
        seen |= bit;
        if (querying && bit == opt_count) {
            query_count = true;
            continue;
        }
        if (bit == opt_exists) {
            query_exists = true;
            continue;
        }
        if (bit == opt_explain) {
            query_explain = true;
            continue;
        }
        if (bit == opt_tree) {
            tree = 1;
            continue;
        }
        if (bit == opt_pdol) {
            pdol = 1;
            continue;
        }
        if (bit == opt_decode) {
            decode = 1;
            continue;
        }
        if (bit == opt_pretty) {
            pretty = tree = 1;
            continue;
        }
        if (bit == opt_describe) {
            describe = 1;
            continue;
        }
        if (bit == opt_force_color || bit == opt_no_color) {
            color = bit == opt_force_color ? 1 : -1;
            continue;
        }
        if (bit == opt_recover) {
            recover = 1;
            continue;
        }
        if (bit == opt_value && querying) {
            value_only = 1;
            continue;
        }
        if (++i == argc) return fail(2, "missing option value");
        if (bit == opt_var)
            query_variables.emplace_back(argv[i]);
        else if (bit == opt_against)
            against = argv[i];
        else if (bit == opt_where)
            where = argv[i];
        else if (bit == opt_backend)
            query_backend = argv[i];
        else if (bit == opt_query) {
            if (path) return fail(2, "query text specified twice");
            path = argv[i];
        } else if (bit == opt_format)
            format = argv[i];
        else if (bit == opt_output_dir)
            output_dir = argv[i];
        else if (bit == opt_seed || bit == opt_count) {
            uint64_t    n = 0;
            const char* text = argv[i];
            if (!*text) return fail(2, "seed/count must be decimal uint64 integers");
            for (; *text; ++text) {
                unsigned digit = static_cast<unsigned>(*text - '0');
                if (digit > 9 || n > (UINT64_MAX - digit) / 10)
                    return fail(2, "seed/count must be decimal uint64 integers");
                n = n * 10 + digit;
            }
            if (bit == opt_seed)
                seed = n;
            else
                count = n;
        } else if (bit == opt_input)
            input = argv[i];
        else if (bit == opt_hex)
            hex = argv[i];
        else if (bit == opt_module)
            module = argv[i];
        else if (bit == opt_tag)
            tag = argv[i];
        else if (bit == opt_search)
            search = argv[i];
        else if (bit == opt_value)
            value = argv[i];
        else if (bit == opt_output_file)
            output_file = argv[i];
        else if (bit == opt_emv_context) {
#if OPENTLV_EMV
            if (!context_by_name(argv[i], &emv_context))
                return fail(2, "unknown EMV context; use base, bit, bht, bht-format, bit-group, "
                               "biometric-counters, biometric-attempts or biometric-verification");
#else
            return fail(2, "EMV module is disabled in this build");
#endif
        } else if (bit == opt_emv_check) {
            if (!strcmp(argv[i], "structure"))
                emv_check = emv_check_structure;
            else if (!strcmp(argv[i], "dictionary"))
                emv_check = emv_check_dictionary;
            else if (!strcmp(argv[i], "all"))
                emv_check = emv_check_structure | emv_check_dictionary;
            else
                return fail(2, "EMV check must be structure, dictionary or all");
        } else if (bit == opt_output_encoding) {
            if (generating) {
                if (strcmp(argv[i], "bin") && strcmp(argv[i], "json"))
                    return fail(2, "generate output encoding must be bin or json");
                json_output = !strcmp(argv[i], "json");
                continue;
            }
            if (strcmp(argv[i], "binary") && strcmp(argv[i], "hex"))
                return fail(2, "output encoding must be binary or hex");
            binary_output = !strcmp(argv[i], "binary");
        } else if (bit == opt_input_encoding) {
            if (strcmp(argv[i], "binary") && strcmp(argv[i], "hex"))
                return fail(2, "input encoding must be binary or hex");
            hex_input = !strcmp(argv[i], "hex");
        } else if (bit == opt_output) {
            if (strcmp(argv[i], "text") && strcmp(argv[i], "json"))
                return fail(2, "output must be text or json");
            output = argv[i];
        } else if (bit == opt_diagnostics) {
            if (strcmp(argv[i], "human") && strcmp(argv[i], "compact") && strcmp(argv[i], "json"))
                return fail(2, "diagnostics must be human, compact or json");
            diagnostics = argv[i];
        } else if (bit == opt_fixed_tag_size) {
            if (!number(argv[i], &fixed_tag_size) || fixed_tag_size < 1)
                return fail(2, "--fixed-tag-size must be a positive decimal integer");
        } else if (bit == opt_fixed_length_size) {
            if (!number(argv[i], &fixed_length_size) || fixed_length_size < 1 ||
                fixed_length_size > 8)
                return fail(2, "--fixed-length-size must be between 1 and 8");
        } else if (bit == opt_fixed_byte_order) {
            if (strcmp(argv[i], "big") && strcmp(argv[i], "little"))
                return fail(2, "--fixed-byte-order must be big or little");
            fixed_byte_order = argv[i];
        } else if (!number(argv[i], bit == opt_max_input   ? &max_input
                                    : bit == opt_max_value ? &max_value_size
                                    : bit == opt_max_case  ? &max_case_size
                                    : bit == opt_max_depth ? &max_depth
                                                           : &max_elements))
            return fail(2, "limits must be nonnegative decimal integers fitting size_t");
    }
    if (generating) {
        if (!format || !output_dir || !*output_dir || !(seen & opt_seed) || !(seen & opt_count))
            return fail(2, "generate requires --format, --seed, --count and --output-dir");
        if (!count || !max_elements || !max_case_size || max_depth > 64)
            return fail(2,
                        "generate requires positive count/elements/case size and depth at most 64");
        if ((seen & fixed_only) && strcmp(format, "fixed"))
            return fail(2, "fixed options require --format fixed");
        return 0;
    }
    if (lookup || listing) {
        if (!module)
            return fail(2, listing ? "tags requires --module emv" : "tag requires --module emv");
        if (strcmp(module, "emv")) return fail(2, "unknown module");
#if !OPENTLV_EMV
        return fail(2, "EMV module is disabled in this build");
#endif
        return 0;
    }
    if (encoding) {
        if (!format) return fail(2, "encode requires --format");
        if (tag && input) return fail(2, "encode takes --tag/--value or --input, not both");
        if (value && !tag) return fail(2, "--value requires --tag");
        // Neither --tag nor --input: read the JSON document from stdin.
        if (!tag && !input) input = "-";
        if ((seen & fixed_only) && strcmp(format, "fixed"))
            return fail(2, "--fixed-tag-size/--fixed-length-size/--fixed-byte-order require "
                           "--format fixed");
        return 0;
    }
    if (!format) return fail(2, "requires --format");
    if (diffing) {
#if !OPENTLV_DOCUMENT
        return fail(2, "diff requires the Document component");
#endif
        if (!input || !against || !strcmp(input, "-") || !strcmp(against, "-"))
            return fail(2, "diff requires --input LEFT and --against RIGHT file paths");
    }
    if (input && hex) return fail(2, "--input and --hex cannot both be given");
    // Neither --input nor --hex: read the input from stdin.
    if (!input && !hex) input = "-";
    if ((seen & fixed_only) && strcmp(format, "fixed"))
        return fail(2, "--fixed-tag-size/--fixed-length-size/--fixed-byte-order require "
                       "--format fixed");
    if (querying) {
        if (!path) return fail(2, "query requires a path or --query expression");
        if (query_count && query_exists)
            return fail(2, "--count and --exists are mutually exclusive");
        if (strcmp(query_backend, "auto") && strcmp(query_backend, "streaming") &&
            strcmp(query_backend, "document"))
            return fail(2, "unknown Query backend");
        auto parsed_query = tlv::query::parse(path);
        if (parsed_query) query = std::make_shared<tlv::query>(std::move(*parsed_query));
        if (query && query->size() > 1 && strcmp(format, "ber") && strcmp(format, "der") &&
            strcmp(format, "emv"))
            return fail(2, "a query with nested tags requires --format ber, der or emv");
        if (value_only && strcmp(output, "text"))
            return fail(2, "--value cannot be combined with --output json");
        return 0;
    }
    if (tree && strcmp(command, "dump")) return fail(2, "--tree requires dump");
    if (pdol && (strcmp(format, "ber") || tree || decode))
        return fail(2, "--pdol requires --format ber and cannot use --tree, --pretty, or --decode");
    if ((seen & opt_force_color) && (seen & opt_no_color))
        return fail(2, "conflicting color options");
    if ((seen & opt_input_encoding) && hex) return fail(2, "--input-encoding requires --input");
    if ((describe || color || decode || strcmp(output, "text")) && validating)
        return fail(2, "presentation options require dump or decode");
    if (recover && pdol) return fail(2, "--recover cannot be combined with --pdol");
    if (describe && !module) return fail(2, "--describe requires --module emv");
    if (decode && !module) return fail(2, "--decode requires --module emv or bluetooth");
    if ((seen & opt_emv_context) && !module) return fail(2, "--emv-context requires --module emv");
    if ((seen & opt_emv_check) && !module) return fail(2, "--emv-check requires --module emv");
    if (module && !strcmp(module, "bluetooth")) {
#if !OPENTLV_BLUETOOTH
        return fail(2, "Bluetooth module is disabled in this build");
#endif
        if (strcmp(format, "bluetooth-ltv"))
            return fail(2, "Bluetooth module requires --format bluetooth-ltv");
        if (seen & (opt_emv_context | opt_emv_check))
            return fail(2, "EMV options require --module emv");
        if (recover) return fail(2, "Bluetooth module cannot use --recover");
        if (describe) return fail(2, "--describe requires --module emv");
    } else if (module) {
        if (strcmp(module, "emv")) return fail(2, "unknown module");
        if (strcmp(format, "ber") && strcmp(format, "emv"))
            return fail(2, "EMV module requires --format ber or emv");
#if !OPENTLV_EMV
        return fail(2, "EMV module is disabled in this build");
#endif
        if (pdol && (seen & (opt_emv_context | opt_emv_check)))
            return fail(2, "--pdol cannot use --emv-context or --emv-check");
        if (validating && !emv_check) emv_check = emv_check_structure;
        if (validating && (emv_check & emv_check_structure) && emv_context)
            return fail(2, "the structure check requires the base EMV context; use --emv-check "
                           "dictionary with --emv-context");
    }
    return 0;
}

void options::usage() {
    std::cout
        << "Usage: otlv dump|validate|decode --format NAME [--input PATH|- | --hex BYTES] "
           "[OPTIONS]\n"
           "       otlv generate --format NAME --seed N --count N --output-dir PATH [OPTIONS]\n"
           "       otlv encode --format NAME --tag HEX [--value HEX] "
           "[--output-encoding hex|binary]\n"
           "       otlv encode --format NAME [--input JSON_PATH|-] "
           "[--output-encoding hex|binary] [--output-file PATH]\n"
           "       otlv query PATH --format NAME [--input PATH|- | --hex BYTES] [--value] "
           "[--output text|json]\n"
           "       otlv query --query EXPR --format NAME [--var NAME:TYPE=VALUE] "
           "[--count|--exists] [--backend auto|streaming|document] [--explain]\n"
           "       otlv diff --format NAME --input LEFT --against RIGHT [--where EXPR] "
           "[--output text|json]\n"
           "       otlv tag HEX --module emv [--output text|json]\n"
           "       otlv tags --module emv [--search TEXT] [--output text|json]\n"
           "       otlv completion bash|zsh|fish|powershell\n"
           "       otlv formats | --help | --version\n"
           "Formats: fixed, ber, der, emv, bluetooth-ltv, nfc-type2 (when enabled in this build)\n"
           "Options:\n"
           "  --fixed-tag-size N     --format fixed: tag width in bytes (default 1)\n"
           "  --fixed-length-size N  --format fixed: length width in bytes, 1..8 (default 1)\n"
           "  --fixed-byte-order NAME --format fixed: length byte order, big (default) or "
           "little\n"
           "  --pdol                 Read raw DOL tag/one-byte-length pairs (BER)\n"
           "  --tree                 Print nested BER/DER elements (dump only)\n"
           "  --pretty               Print a graphical UTF-8 tree (implies --tree)\n"
           "  --module emv           Annotate BER tags (dump, decode) or check EMV data "
           "(validate)\n"
           "  --describe             Include EMV type and length descriptions\n"
           "  --module bluetooth     Annotate Bluetooth AD types; validate schema and codecs\n"
           "  --decode               Decode known values (requires --module emv or bluetooth)\n"
           "  --emv-context NAME     EMV dictionary context of the top-level elements: base "
           "(default), bit, bht, bht-format, bit-group, biometric-counters, "
           "biometric-attempts, biometric-verification\n"
           "  --emv-check NAME       validate: structure (default), dictionary or all\n"
           "  --recover              dump, decode: skip damaged bytes and keep reading; the "
           "output is marked incomplete and the exit code is 4\n"
           "  --output text|json     Print text (default) or a hierarchical JSON document\n"
           "  --diagnostics NAME     Shape of a failure diagnostic: human (default), compact "
           "or json\n"
           "  --input-encoding NAME  binary (default) or hex, for --input\n"
           "  --force-color          Emit ANSI colors even when redirected\n"
           "  --no-color             Disable colors (default: auto for terminals)\n"
           "  --max-input-size N     Maximum input bytes (default 16777216)\n"
           "  --max-depth N          Maximum child depth (default 64)\n"
           "  --max-elements N       Maximum visited elements (default 100000)\n"
           "  --search TEXT          tags: only tags whose name contains TEXT "
           "(case-insensitive)\n"
           "  --value                query: print only the values of the addressed elements\n"
           "  --tag HEX              encode: tag bytes in wire order\n"
           "  --value HEX            encode: value bytes (default: empty)\n"
           "  --output-encoding NAME encode: hex (default, one line) or binary\n"
           "  --output-file PATH     encode: write the result to PATH instead of stdout\n"
           "  --output-encoding NAME generate: bin (default) or json; one file per case\n"
           "  --seed N               generate: explicit uint64 seed (zero is valid)\n"
           "  --count N              generate: number of complete cases/files\n"
           "  --output-dir PATH      generate: create directories; never overwrite case files\n"
           "  --max-value-size N     generate: maximum Value bytes (default 256)\n"
           "  --max-case-size N      generate: maximum case bytes (default 4096)\n"
           "generate defaults: --max-depth 4, --max-elements 32; flat formats use depth 0.\n"
           "decode prints the versioned JSON document that encode --input reads.\n"
           "query prints every element addressed by a path of hexadecimal tags such as "
           "6F/A5/50 (a top-level 6F, its child A5, its child 50); nested paths need "
           "--format ber or der. Exit code 5 means nothing matched.\n"
           "tag looks up one BER tag in the EMV dictionary; an unknown tag is a result "
           "(exit 0), not an error; tags lists the dictionary.\n"
           "completion prints a shell completion script to stdout for the given shell.\n"
           "dump, validate, decode, query and encode (without --tag) read binary stdin when "
           "neither --input nor --hex (--tag for encode) is given, the same as --input -, so "
           "they compose in a shell pipeline; command output always goes to stdout and "
           "diagnostics to stderr.\n"
           "Input is binary; hex accepts contiguous bytes or whitespace between pairs.\n"
           "Validation accepts empty input and checks all concatenated elements.\n"
           "With --module emv, validate also checks the EMV schema structure "
           "(mandatory/forbidden/duplicate tags, lengths, and nesting) and reports a "
           "schema-labeled diagnostic distinct from format errors; --pdol skips it.\n"
           "Exit codes: 0 success, 1 invalid TLV (or element rejected by encode), 2 invalid "
           "usage/hex/JSON/format, 3 I/O/resource error, 4 damaged data skipped by --recover.\n";
}

const option_entry* option_table(std::size_t* count) {
    *count = option_table_count;
    return option_table_data;
}

uint64_t command_options_mask(const char* command) {
    uint64_t mask = 0;
    if (!strcmp(command, "generate"))
        mask = generate_options;
    else if (!strcmp(command, "tag"))
        mask = lookup_options;
    else if (!strcmp(command, "tags"))
        mask = listing_options;
    else if (!strcmp(command, "query"))
        mask = query_options;
    else if (!strcmp(command, "diff"))
        mask = diff_options;
    else if (!strcmp(command, "encode"))
        mask = encode_options;
    else if (!strcmp(command, "decode"))
        mask = decode_options;
    else if (!strcmp(command, "validate"))
        mask = validate_options;
    else if (!strcmp(command, "dump"))
        mask = dump_options;
#if !OPENTLV_EMV
    mask &= ~emv_only;
#endif
#if !OPENTLV_EMV && !OPENTLV_BLUETOOTH
    mask &= ~(opt_module | opt_decode);
#endif
#if !OPENTLV_DOCUMENT
    if (!strcmp(command, "diff")) mask = 0;
#endif
    return mask;
}

uint64_t flag_options_mask() {
    return flag_only;
}

#if OPENTLV_EMV
const char* const* emv_context_names(std::size_t* count) {
    static const char* names[sizeof(context_names) / sizeof(context_names[0])];
    for (std::size_t i = 0; i < sizeof(context_names) / sizeof(context_names[0]); ++i)
        names[i] = context_names[i].name;
    *count = sizeof(context_names) / sizeof(context_names[0]);
    return names;
}
#endif

} // namespace cli
