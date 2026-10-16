// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "command_factory.hpp"
#include <cstring>
#include <utility>
#include <vector>
#include "commands/decode_command.hpp"
#include "commands/dump_command.hpp"
#include "commands/encode_command.hpp"
#include "commands/generate_command.hpp"
#include "commands/formats_command.hpp"
#include "commands/help_command.hpp"
#include "commands/query_command.hpp"
#include "commands/diff_command.hpp"
#include "commands/tag_command.hpp"
#include "commands/tags_command.hpp"
#include "commands/validate_command.hpp"
#include "commands/version_command.hpp"
#include "completion/completion_command.hpp"
#include "diagnostics.hpp"
#include "input.hpp"
#include "options.hpp"

namespace cli {

std::unique_ptr<command> command_factory::create(int argc, char** argv, int* error_code) {
    if (argc == 2 && !strcmp(argv[1], "--help"))
        return std::unique_ptr<command>(new help_command());
    if (argc == 2 && !strcmp(argv[1], "--version"))
        return std::unique_ptr<command>(new version_command());
    if (argc == 2 && !strcmp(argv[1], "formats"))
        return std::unique_ptr<command>(new formats_command());
    if (argc >= 2 && !strcmp(argv[1], "completion")) {
        if (argc > 3) {
            *error_code = fail(2, "completion takes exactly one shell argument");
            return nullptr;
        }
        return std::unique_ptr<command>(new completion_command(argc == 3 ? argv[2] : ""));
    }
    if (argc < 2) {
        *error_code = fail(2, "missing command; use --help");
        return nullptr;
    }

    options o;
    int     rc = o.parse(argc, argv);
    if (rc) {
        *error_code = rc;
        return nullptr;
    }

    if (!strcmp(o.command, "generate")) return std::unique_ptr<command>(new generate_command(o));
    if (!strcmp(o.command, "encode")) return std::unique_ptr<command>(new encode_command(o));
    if (!strcmp(o.command, "tag")) return std::unique_ptr<command>(new tag_command(o));
    if (!strcmp(o.command, "tags")) return std::unique_ptr<command>(new tags_command(o));

    std::vector<uint8_t> data;
    rc = read_input(o, data);
    if (rc) {
        *error_code = rc;
        return nullptr;
    }

    if (!strcmp(o.command, "validate"))
        return std::unique_ptr<command>(new validate_command(o, std::move(data)));
    if (!strcmp(o.command, "decode"))
        return std::unique_ptr<command>(new decode_command(o, std::move(data)));
    if (!strcmp(o.command, "query"))
        return std::unique_ptr<command>(new query_command(o, std::move(data)));
    if (!strcmp(o.command, "diff"))
        return std::unique_ptr<command>(new diff_command(o, std::move(data)));
    // options::parse() only accepts "dump", "validate", "decode", "encode",
    // "generate", "tag", "tags" or "query"; every other case returned above.
    return std::unique_ptr<command>(new dump_command(o, std::move(data)));
}

} // namespace cli
