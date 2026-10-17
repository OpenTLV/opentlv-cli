// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/fish_completer.hpp"
#include "completion/support.hpp"

namespace cli {

void fish_completer::render(std::ostream& out, const completion_model& model) const {
    out << "# fish completion for otlv\n"
           "# Install: otlv completion fish > ~/.config/fish/completions/otlv.fish\n"
           "complete -c otlv -f\n"
           "complete -c otlv -n '__fish_use_subcommand' -a '"
        << join(model.command_names()) << "'\n";
    for (const completion_command_spec& command : model.commands()) {
        const std::string condition = "__fish_seen_subcommand_from " + command.name();
        if (command.has_positional() && !command.positional_values().empty())
            out << "complete -c otlv -n '" << condition << "' -a '"
                << join(command.positional_values()) << "'\n";
        for (const completion_option& option : command.options()) {
            // "-l name" registers the long option (otlv has no short options).
            out << "complete -c otlv -n '" << condition << "' -l " << option.name().substr(2);
            if (option.is_path())
                out << " -r -F";
            else if (option.has_values())
                out << " -r -f -a '" << join(option.values()) << "'";
            else if (option.takes_value())
                out << " -r -f";
            out << "\n";
        }
    }
}

} // namespace cli
