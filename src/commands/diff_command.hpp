// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel
#ifndef OPENTLV_CLI_DIFF_COMMAND_HPP
#define OPENTLV_CLI_DIFF_COMMAND_HPP
#include "command.hpp"
#include "options.hpp"
#include <vector>
namespace cli {
class diff_command : public command {
public:
    diff_command(const options& options, std::vector<uint8_t> input)
        : options_(options), input_(std::move(input)) {}
    int run() override;

private:
    options              options_;
    std::vector<uint8_t> input_;
};
} // namespace cli
#endif
