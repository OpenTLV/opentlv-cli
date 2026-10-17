// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "completion/powershell_completer.hpp"
#include "completion/support.hpp"

namespace cli {

void powershell_completer::render(std::ostream& out, const completion_model& model) const {
    out << "# PowerShell completion for otlv\n"
           "# Install: otlv completion powershell >> $PROFILE\n"
           "Register-ArgumentCompleter -Native -CommandName otlv -ScriptBlock {\n"
           "    param($wordToComplete, $commandAst, $cursorPosition)\n"
           "\n"
           "    function Complete-Values([string[]]$Values) {\n"
           "        $Values | Where-Object { $_ -like \"$wordToComplete*\" } | ForEach-Object {\n"
           "            [System.Management.Automation.CompletionResult]::new($_, $_, "
           "'ParameterValue', $_)\n"
           "        }\n"
           "    }\n"
           "    function Complete-Files() {\n"
           "        Get-ChildItem -Path \"$wordToComplete*\" -ErrorAction SilentlyContinue | "
           "ForEach-Object {\n"
           "            [System.Management.Automation.CompletionResult]::new($_.Name, $_.Name, "
           "'ParameterValue', $_.Name)\n"
           "        }\n"
           "    }\n"
           "\n"
           "    $raw = @($commandAst.CommandElements | ForEach-Object { $_.Extent.Text })\n"
           "    if ($wordToComplete -ne '' -and $raw.Count -gt 0 -and "
           "$raw[$raw.Count - 1] -eq $wordToComplete) {\n"
           "        $raw = @($raw | Select-Object -SkipLast 1)\n"
           "    }\n"
           "    $words = @($raw | Select-Object -Skip 1)\n"
           "    $cmd = if ($words.Count -ge 1) { $words[0] } else { $null }\n"
           "    $prev = if ($words.Count -ge 1) { $words[$words.Count - 1] } else { $null }\n"
           "\n"
           "    if (-not $cmd) {\n"
           "        Complete-Values @('"
        << join(model.command_names())
        << "'.Split(' '))\n"
           "        return\n"
           "    }\n"
           "\n"
           "    switch ($prev) {\n";
    for (const completion_option& option : model.all_options()) {
        if (!option.has_values() && !option.is_path()) continue;
        if (option.name() == "--output-encoding") {
            out << "        '--output-encoding' { switch ($cmd) {\n";
            for (const auto& command : model.commands())
                for (const auto& candidate : command.options())
                    if (candidate.name() == option.name())
                        out << "            '" << command.name() << "' { Complete-Values @('"
                            << join(candidate.values()) << "'.Split(' ')); return }\n";
            out << "        }; return }\n";
            continue;
        }
        out << "        '" << option.name() << "' { ";
        if (option.is_path())
            out << "Complete-Files; return }\n";
        else
            out << "Complete-Values @('" << join(option.values()) << "'.Split(' ')); return }\n";
    }
    out << "    }\n"
           "\n"
           "    switch ($cmd) {\n";
    for (const completion_command_spec& command : model.commands()) {
        if (command.has_positional() && !command.positional_values().empty())
            out << "        '" << command.name()
                << "' { if ($words.Count -eq 1) { Complete-Values @('"
                << join(command.positional_values()) << "'.Split(' ')); return } }\n";
    }
    out << "    }\n"
           "\n"
           "    if ($wordToComplete -like '-*') {\n"
           "        switch ($cmd) {\n";
    for (const completion_command_spec& command : model.commands()) {
        if (command.options().empty()) continue;
        out << "            '" << command.name() << "' { Complete-Values @('"
            << join(option_names(command.options())) << "'.Split(' ')) }\n";
    }
    out << "        }\n"
           "    }\n"
           "}\n";
}

} // namespace cli
