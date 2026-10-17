// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_DUMP_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_DUMP_COMMAND_HPP
#include "commands/traversal_command.hpp"

namespace cli {

// otlv dump: prints every visited element (top-level only, or the whole
// nested BER/DER tree with --tree/--pretty) as text or, with --output json,
// a JSON document.
class dump_command : public traversal_command {
public:
    using traversal_command::traversal_command;

protected:
    tlv::visit_control visit_element(const tlv::element_view& element, std::size_t depth,
                                     std::size_t offset) override;
    void               render_output() override;
    bool               prints_pdol_annotations() const override;
    bool               prints_skipped_inline() const override;
};

} // namespace cli
#endif
