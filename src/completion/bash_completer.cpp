// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/bash_completer.hpp"
#include "completion/support.hpp"

namespace cli {

void bash_completer::render(std::ostream& out, const completion_model& model) const {
    out << "# bash completion for otlv\n"
           "# Install: otlv completion bash > ~/.local/share/bash-completion/completions/otlv\n"
           "_otlv() {\n"
           "    local cur prev cmd\n"
           "    COMPREPLY=()\n"
           "    cur=\"${COMP_WORDS[COMP_CWORD]}\"\n"
           "    prev=\"${COMP_WORDS[COMP_CWORD-1]}\"\n"
           "    cmd=\"${COMP_WORDS[1]}\"\n"
           "\n"
           "    if [[ $COMP_CWORD -eq 1 ]]; then\n"
           "        COMPREPLY=( $(compgen -W \""
        << join(model.command_names())
        << "\" -- \"$cur\") )\n"
           "        return 0\n"
           "    fi\n"
           "\n"
           "    case \"$cmd\" in\n";
    for (const completion_command_spec& command : model.commands()) {
        if (!command.has_positional() || command.positional_values().empty()) continue;
        out << "        " << command.name()
            << ")\n"
               "            if [[ $COMP_CWORD -eq 2 ]]; then\n"
               "                COMPREPLY=( $(compgen -W \""
            << join(command.positional_values())
            << "\" -- \"$cur\") )\n"
               "                return 0\n"
               "            fi\n"
               "            ;;\n";
    }
    out << "    esac\n"
           "\n"
           "    case \"$prev\" in\n";
    for (const completion_option& option : model.all_options()) {
        if (!option.has_values() && !option.is_path()) continue;
        if (option.name() == "--output-encoding") {
            out << "        --output-encoding) case \"$cmd\" in\n";
            for (const auto& command : model.commands())
                for (const auto& candidate : command.options())
                    if (candidate.name() == option.name())
                        out << "            " << command.name() << ") COMPREPLY=( $(compgen -W \""
                            << join(candidate.values()) << "\" -- \"$cur\") ); return 0 ;;\n";
            out << "        esac; return 0 ;;\n";
            continue;
        }
        out << "        " << option.name() << ") ";
        if (option.is_path())
            out << "COMPREPLY=( $(compgen -f -- \"$cur\") ); return 0 ;;\n";
        else
            out << "COMPREPLY=( $(compgen -W \"" << join(option.values())
                << "\" -- \"$cur\") ); return 0 ;;\n";
    }
    out << "    esac\n"
           "\n"
           "    if [[ \"$cur\" == -* ]]; then\n"
           "        case \"$cmd\" in\n";
    for (const completion_command_spec& command : model.commands()) {
        if (command.options().empty()) continue;
        out << "            " << command.name() << ") COMPREPLY=( $(compgen -W \""
            << join(option_names(command.options())) << "\" -- \"$cur\") ) ;;\n";
    }
    out << "        esac\n"
           "    fi\n"
           "}\n"
           "complete -F _otlv otlv\n";
}

} // namespace cli
