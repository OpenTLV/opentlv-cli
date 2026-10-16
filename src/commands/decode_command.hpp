// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_DECODE_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_DECODE_COMMAND_HPP
#include "commands/traversal_command.hpp"
#include <iostream>
#include <utility>

namespace cli {

// otlv decode: prints the versioned JSON document (docs/cli/json-schema.md)
// that "encode --input" reads, on success only.
class decode_command : public traversal_command {
public:
    // The same decoder/model serves stdout and generate's CLI-only JSON output.
    decode_command(const options& o, std::vector<uint8_t> data, std::ostream& output = std::cout)
        : traversal_command(o, std::move(data)), output_(output) {}

protected:
    tlv::visit_control visit_element(const tlv::element_view& element, std::size_t depth,
                                     std::size_t offset) override;
    void               render_output() override;

private:
    std::ostream& output_;
};

} // namespace cli
#endif
