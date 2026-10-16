// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_VALIDATE_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_VALIDATE_COMMAND_HPP
#include "commands/traversal_command.hpp"

namespace cli {

// otlv validate: traverses the whole input, checking structure only (no display),
// plus the selected module schema/value checks. Also used
// internally by "encode" to validate its own freshly encoded output under
// the same limits as a standalone "otlv validate" run.
class validate_command : public traversal_command {
public:
    using traversal_command::traversal_command;

protected:
    void        run_module_checks() override;
    std::string render_failure_diagnostic(diagnostic_format diag_format, const char* tag_hex_ptr,
                                          const std::string& stage_name) override;

private:
    // State for the EMV dictionary length check: the first element whose
    // length the dictionary, in that element's context, does not permit,
    // plus enough detail -- independent of `presentation`, which exists only
    // for display bookkeeping -- to report it richly.
    struct dictionary_check {
        cli_presentation_t      presentation = {};
        const uint8_t*          data = nullptr;
        const tlv::format*      predicate = nullptr;
        diagnostic_scope        scope = {};
        tlv::errc               result = tlv::errc::ok;
        std::size_t             offset = 0;
        std::string             tag;
        std::string             expected;
        std::string             actual;
        const char*             field_name = nullptr;
        tlv::diagnostic_context field_context = {};
    };
    static tlv::visit_control check_dictionary_trampoline(const tlv::element_view* element,
                                                          std::size_t depth, std::size_t offset,
                                                          void* context);
    tlv::visit_control check_dictionary_element(const tlv::element_view* element, std::size_t depth,
                                                std::size_t offset);

    dictionary_check check_;
};

} // namespace cli
#endif
