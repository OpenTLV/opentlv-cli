// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/zsh_completer.hpp"
#include "completion/support.hpp"

namespace cli {

void zsh_completer::render(std::ostream& out, const completion_model& model) const {
    out << "#compdef otlv\n"
           "# Install: otlv completion zsh > \"${fpath[1]}/_otlv\"\n"
           "_otlv() {\n"
           "    local -a commands\n"
           "    commands=("
        << join(model.command_names())
        << ")\n"
           "    if (( CURRENT == 2 )); then\n"
           "        _describe 'command' commands\n"
           "        return\n"
           "    fi\n"
           "\n"
           "    local cmd=${words[2]}\n"
           "    local prev=${words[CURRENT-1]}\n"
           "    local cur=${words[CURRENT]}\n"
           "\n"
           "    case \"$cmd\" in\n";
    for (const completion_command_spec& command : model.commands()) {
        if (!command.has_positional() || command.positional_values().empty()) continue;
        out << "        " << command.name()
            << ")\n"
               "            if (( CURRENT == 3 )); then\n"
               "                local -a values; values=("
            << join(command.positional_values())
            << ")\n"
               "                _describe 'value' values\n"
               "                return\n"
               "            fi\n"
               "            ;;\n";
    }
    out << "    esac\n"
           "\n"
           "    case \"$prev\" in\n";
    for (const completion_option& option : model.all_options()) {
        if (!option.has_values() && !option.is_path()) continue;
        if (option.name() == "--output-encoding") {
            out << "        --output-encoding)\n            local -a values\n            case "
                   "\"$cmd\" in\n";
            for (const auto& command : model.commands())
                for (const auto& candidate : command.options())
                    if (candidate.name() == option.name())
                        out << "                " << command.name() << ") values=("
                            << join(candidate.values()) << ");;\n";
            out << "            esac\n            _describe 'value' values\n            return "
                   ";;\n";
            continue;
        }
        out << "        " << option.name() << ")\n";
        if (option.is_path())
            out << "            _files\n";
        else
            out << "            local -a values; values=(" << join(option.values())
                << ")\n"
                   "            _describe 'value' values\n";
        out << "            return\n"
               "            ;;\n";
    }
    out << "    esac\n"
           "\n"
           "    if [[ \"$cur\" == -* ]]; then\n"
           "        local -a opts\n"
           "        case \"$cmd\" in\n";
    for (const completion_command_spec& command : model.commands()) {
        if (command.options().empty()) continue;
        out << "            " << command.name() << ") opts=("
            << join(option_names(command.options())) << ") ;;\n";
    }
    out << "        esac\n"
           "        _describe 'option' opts\n"
           "    fi\n"
           "}\n"
           "\n"
           "_otlv \"$@\"\n";
}

} // namespace cli
