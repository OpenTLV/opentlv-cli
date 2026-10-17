// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel
#ifndef OPENTLV_CLI_GENERATE_COMMAND_HPP
#define OPENTLV_CLI_GENERATE_COMMAND_HPP
#include "command.hpp"
#include "options.hpp"
namespace cli {
class generate_command : public command {
public:
    explicit generate_command(const options& o) : options_(o) {}
    int run() override;

private:
    options options_;
};
} // namespace cli
#endif
