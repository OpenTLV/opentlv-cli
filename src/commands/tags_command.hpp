// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_TAGS_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_TAGS_COMMAND_HPP
#include "command.hpp"
#include "options.hpp"

namespace cli {

// otlv tags: lists every base-context dictionary entry of the selected
// module, optionally filtered by a case-insensitive name substring
// (--search), in dictionary order, as text or JSON. An empty result is still
// success (exit code 0).
class tags_command : public command {
public:
    explicit tags_command(const options& o) : options_(o) {}
    int run() override;

private:
    options options_;
};

} // namespace cli
#endif
