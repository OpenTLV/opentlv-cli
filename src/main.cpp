// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include <memory>
#include <new>
#include "command.hpp"
#include "command_factory.hpp"
#include "diagnostics.hpp"

int main(int argc, char** argv) {
    try {
        int                           error_code = 0;
        std::unique_ptr<cli::command> command =
            cli::command_factory::create(argc, argv, &error_code);
        return command ? command->run() : error_code;
    } catch (const std::bad_alloc&) {
        return cli::fail(3, "cannot allocate CLI memory");
    }
}
