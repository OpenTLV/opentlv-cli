// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_PRESENTATION_H
#define OPENTLV_CLI_PRESENTATION_H
#include <string>
#include <vector>
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"

// Structured EMV dictionary metadata for one element, shared by the text
// renderer (cli_presentation_emv, below) and the CLI's JSON output so both
// present the same lookup without duplicating it. `known` is false for a tag
// with no dictionary entry in the element's context, in which case `name`
// and `description` are unset.
struct cli_emv_info {
    bool        known = false;
    std::string name;
    bool        has_description = false;
    std::string description;
};

// Authoritative descriptive name from the composed generic Definition.
// Shared by dump annotations and the tag command.
// Available only when the EMV module is enabled.

typedef struct cli_presentation {
    const uint8_t*      data;
    std::vector<size_t> ends;
    std::vector<int>    more;
    std::vector<int>    contexts;
    int                 color;
    unsigned long       console_mode;
    unsigned int        console_codepage;
    int                 restore_mode, restore_codepage;
} cli_presentation_t;

// Requires a successful reader-produced element. Checks native representability;
// an invariant violation terminates rather than allowing truncated memory access.
size_t cli_element_value_size(const tlv::element_view* element);

void cli_presentation_init(cli_presentation_t* p, const uint8_t* data, size_t size, int color,
                           int pretty);
void cli_presentation_restore(cli_presentation_t* p);
void cli_presentation_visit(cli_presentation_t* p, const tlv::element_view* element, size_t depth,
                            int indefinite);
void cli_presentation_prefix(const cli_presentation_t* p, size_t depth);
void cli_presentation_emv(const cli_presentation_t* p, const tlv::element_view* element,
                          size_t depth, int describe);
cli_emv_info cli_presentation_emv_info(const cli_presentation_t* p,
                                       const tlv::element_view* element, size_t depth,
                                       int describe);
#endif
