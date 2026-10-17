// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMAND_HPP
#define OPENTLV_CLI_COMMAND_HPP

namespace cli {

// One otlv invocation (dump, validate, encode, completion, ...): an object
// that owns everything it needs to run and knows how to run itself, instead
// of a free function taking a parsed-arguments struct.
class command {
public:
    virtual ~command() = default;

    // Runs the command and returns the process exit code.
    virtual int run() = 0;
};

} // namespace cli
#endif
