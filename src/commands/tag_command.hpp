// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_TAG_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_TAG_COMMAND_HPP
#include "command.hpp"
#include "options.hpp"

namespace cli {

// otlv tag: decodes the hexadecimal BER tag, looks it up in the selected
// module's dictionary (base context) and prints its metadata as text or
// JSON. An unknown tag is reported as a result with exit code 0; a malformed
// tag is a usage error (exit code 2).
class tag_command : public command {
public:
    explicit tag_command(const options& o) : options_(o) {}
    int run() override;

private:
    options options_;
};

} // namespace cli
#endif
