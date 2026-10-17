// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/query_command.hpp"
#include <iostream>
#include "commands/support.hpp"
#include "diagnostics.hpp"
#include "diagnostic_render.hpp"
#include "tlv++/query/program.hpp"
#include "tlv++/codec/dynamic.hpp"
#include <cstring>
#include <limits>
#if OPENTLV_FORMAT_BER
#include "tlv++/builtins/asn1/query.hpp"
#endif
#if OPENTLV_EMV
#include "tlv++/builtins/emv/query.hpp"
#endif
#if OPENTLV_DOCUMENT
#include "tlv++/document/document.hpp"
#endif

namespace {

// The query path as text: uppercase hex tags joined by "/", however the user
// spelled it.
std::string query_path(const tlv::query& query) {
    return query.format();
}

} // namespace

namespace cli {

int query_command::run() {
    // Plain path queries use the V1 traversal, output shape and validation rules.
    if (options_.query && !options_.query_count && !options_.query_exists &&
        !options_.query_explain && options_.query_variables.empty() &&
        !strcmp(options_.query_backend, "auto"))
        return traversal_command::run();
    auto selected_format = format_storage_.get();
    if (!selected_format) return fail(2, "unknown or disabled format; use otlv formats");
    auto report = [&](const tlv::query_failure& failure, int status) {
        const auto&    d = failure.diagnostic;
        nlohmann::json detail = {{"error", tlv::message(failure.status())},
                                 {"code", failure.status()},
                                 {"kind", d.kind},
                                 {"kind_name", tlv::message(failure.kind())},
                                 {"cause", tlv::message(failure.cause())}};
        if (tlv::domain(d.diagnostic.location) == tlv::location_domain::input &&
            tlv::kind(d.diagnostic.location) != tlv::location_kind::unknown)
            detail["source_offset"] = d.diagnostic.location.begin;
        detail["location"] = {{"domain", tlv::message(tlv::domain(d.diagnostic.location))},
                              {"kind", tlv::message(tlv::kind(d.diagnostic.location))}};
        if (tlv::kind(d.diagnostic.location) != tlv::location_kind::unknown) {
            detail["location"]["begin"] = d.diagnostic.location.begin;
            detail["location"]["end"] = d.diagnostic.location.end;
        }
        if (tlv::kind(d.expression) != tlv::location_kind::unknown)
            detail["expression"] = {{"begin", d.expression.begin}, {"end", d.expression.end}};
        if (d.limit) {
            detail["limit"] = d.limit;
            detail["configured"] = d.configured;
        }
        detail["diagnostic"] = nlohmann::json::parse(
            format_diagnostic(d.diagnostic, diagnostic_format::json, "query", nullptr));
        if (failure.cause() == tlv::query_cause::codec) {
            const auto& codec = d.detail.codec;
            detail["codec_detail"] = {
                {"operation", tlv::message(static_cast<tlv::codec_phase>(codec.operation))},
                {"cause", tlv::message(static_cast<tlv::codec_cause>(codec.cause))},
                {"violation", tlv::message(static_cast<tlv::codec_violation>(codec.violation))},
                {"reason", tlv::message(static_cast<tlv::codec_reason>(codec.reason))},
                {"reported", codec.reported}};
            if (codec.representation)
                detail["codec_detail"]["representation"] = codec.representation;
            if (static_cast<tlv::codec_cause>(codec.cause) == tlv::codec_cause::reader) {
                tlv::reader_diagnostic reader{};
                reader.diagnostic = d.diagnostic;
                reader.detail = codec.detail.reader;
                detail["codec_detail"]["reader"] = nlohmann::json::parse(
                    format_reader_diagnostic(reader, diagnostic_format::json));
            }
            if (static_cast<tlv::codec_cause>(codec.cause) == tlv::codec_cause::schema) {
                detail["codec_detail"]["schema"] = {
                    {"kind",
                     tlv::message(static_cast<tlv::schema_issue>(codec.detail.schema.kind))},
                    {"definition_kind", tlv::message(static_cast<tlv::schema_definition_kind>(
                                            codec.detail.schema.definition.kind))},
                    {"definition_index", codec.detail.schema.definition.index}};
            }
        }
        if (failure.cause() == tlv::query_cause::reader) {
            tlv::reader_diagnostic reader{};
            reader.diagnostic = d.diagnostic;
            reader.detail = d.detail.reader;
            detail["reader"] =
                nlohmann::json::parse(format_reader_diagnostic(reader, diagnostic_format::json));
        }
        if (!strcmp(options_.diagnostics, "json"))
            std::cerr << detail.dump() << '\n';
        else {
            std::cerr << "otlv: "
                      << format_diagnostic(d.diagnostic, diagnostic_format::compact, "query",
                                           nullptr)
                      << "; kind=" << tlv::message(failure.kind());
            if (failure.cause() != tlv::query_cause::none)
                std::cerr << "; cause=" << tlv::message(failure.cause());
            if (tlv::kind(d.expression) != tlv::location_kind::unknown)
                std::cerr << "; expression=" << d.expression.begin << ':' << d.expression.end;
            if (failure.cause() == tlv::query_cause::codec)
                std::cerr << "; codec="
                          << tlv::message(static_cast<tlv::codec_phase>(d.detail.codec.operation))
                          << "; violation="
                          << tlv::message(
                                 static_cast<tlv::codec_violation>(d.detail.codec.violation));
            std::cerr << '\n';
        }
        return status;
    };
    struct variable {
        std::string     name, value;
        tlv::query_type type;
        int64_t         integer = 0;
    };
    std::vector<variable> variables;
    for (const auto& text : options_.query_variables) {
        auto colon = text.find(':');
        auto equals = text.find('=', colon);
        if (colon == std::string::npos || equals == std::string::npos || !colon)
            return fail(2, "--var requires NAME:int=DECIMAL, NAME:bytes=HEX or NAME:string=UTF8");
        variable v;
        v.name = text.substr(0, colon);
        v.value = text.substr(equals + 1);
        auto type = text.substr(colon + 1, equals - colon - 1);
        if (type == "int") {
            v.type = tlv::query_type::integer;
            size_t end = 0;
            if (v.value.empty() || v.value.find_first_not_of("-0123456789") != std::string::npos)
                return fail(2, "invalid int variable");
            try {
                v.integer = std::stoll(v.value, &end, 10);
            } catch (...) {
                return fail(2, "int variable outside int64 range");
            }
            if (end != v.value.size()) return fail(2, "invalid int variable");
        } else if (type == "bytes") {
            v.type = tlv::query_type::bytes;
            if (v.value.size() % 2)
                return fail(2, "bytes variable requires even-length hexadecimal");
            auto digit = [](char c) {
                return c >= '0' && c <= '9'   ? c - '0'
                       : c >= 'a' && c <= 'f' ? c - 'a' + 10
                       : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                              : -1;
            };
            std::string decoded;
            for (size_t i = 0; i < v.value.size(); i += 2) {
                int a = digit(v.value[i]), b = digit(v.value[i + 1]);
                if (a < 0 || b < 0) return fail(2, "invalid hexadecimal bytes variable");
                decoded.push_back(static_cast<char>(a * 16 + b));
            }
            v.value = std::move(decoded);
        } else if (type == "string")
            v.type = tlv::query_type::string;
        else
            return fail(2, "unknown variable type; use int, bytes or string");
        variables.push_back(std::move(v));
    }
    tlv::query_environment environment(*selected_format);
#if OPENTLV_FORMAT_BER
    if (!std::strcmp(options_.format, "ber") || !std::strcmp(options_.format, "der") ||
        !std::strcmp(options_.format, "cer"))
        tlv::asn1::configure_query(environment);
#endif
    tlv::query_options compile_options(&environment);
#if OPENTLV_EMV
    if (!std::strcmp(options_.format, "emv")) tlv::emv::configure_query(compile_options);
#endif
    for (const auto& v : variables)
        compile_options.declare(v.name.c_str(), static_cast<tlv::query_type>(v.type));
    std::string text = options_.path;
    if (options_.query_count) text = "count(" + text + ")";
    if (options_.query_exists) text = "exists(" + text + ")";
    auto program = tlv::query_program::compile(text, compile_options);
    if (!program) return report(program.error(), 2);
    bool document_backend =
        !strcmp(options_.query_backend, "document") ||
        (program->level() == tlv::query_level::document && !strcmp(options_.query_backend, "auto"));
    if (program->level() == tlv::query_level::document && !document_backend)
        return fail(2, "Query requires Document; streaming backend does not materialize input");
    if (options_.value_only && program->result_type() != tlv::query_type::nodes)
        return fail(2, "--value requires a node selection");
    auto execution = tlv::query_execution::create(*program, options_.max_depth,
                                                  options_.max_elements, 100000000, environment);
    if (!execution) return report(execution.error(), 2);
    for (const auto& v : variables) {
        auto bound =
            v.type == tlv::query_type::integer
                ? execution->bind(v.name.c_str(), v.integer)
                : execution->bind(v.name.c_str(),
                                  tlv::bytes(reinterpret_cast<const tlv::byte*>(v.value.data()),
                                             v.value.size()),
                                  v.type == tlv::query_type::string);
        if (!bound) return report(bound.error(), 2);
    }
    if (options_.query_explain) {
        const auto&    info = program->info();
        nlohmann::json explanation = {
            {"query", program->format()},
            {"language", info.language_version},
            {"result_kind", info.result_kind},
            {"level", info.level},
            {"backend", document_backend ? "document" : "streaming-retained"},
            {"program_bytes", info.program_size},
            {"program_alignment", info.program_alignment},
            {"scratch_bytes", info.scratch_size},
            {"scratch_alignment", info.scratch_alignment},
            {"max_depth", options_.max_depth},
            {"candidates", options_.max_elements},
            {"max_work", 100000000},
            {"validation", "complete structural traversal"},
            {"stable_input_required", true},
            {"ir_unstable", program->explain()}};
        std::cerr << explanation.dump() << '\n';
    }
    nlohmann::json matches = nlohmann::json::array();
    auto           emit = [&](const tlv::element_view& element, bool source, size_t offset) {
        ++matches_;
        if (is_json(options_))
            matches.push_back(
                {{"path", program->format()},
                 {"offset", source ? nlohmann::json(offset) : nlohmann::json(nullptr)},
                 {"tag", hex_string(element.tag().as_bytes())},
                 {"length", element.value().size()},
                 {"value", hex_string(element.value().as_bytes())}});
        else {
            if (!options_.value_only) {
                std::cout << "offset=" << (source ? std::to_string(offset) : "unavailable")
                          << " tag=";
                print_hex(element.tag().as_bytes());
                std::cout << " length=" << element.value().size() << " value=";
            }
            print_hex(element.value().as_bytes());
            std::cout << '\n';
        }
    };
    std::vector<tlv::byte> value_snapshot, scratch;
#if OPENTLV_DOCUMENT
    std::unique_ptr<tlv::document> document;
#endif
    if (document_backend) {
#if OPENTLV_DOCUMENT
        tlv::document_format settings(*selected_format);
        settings.max_depth = options_.max_depth;
        settings.max_elements = options_.max_elements;
        // The CLI owns the wire input, so Document matches keep their input coordinates.
        settings.retain_source_locations = true;
        auto parsed = tlv::document::parse(
            tlv::bytes(reinterpret_cast<const tlv::byte*>(data()), size()), settings);
        if (!parsed) return fail(3, tlv::message(parsed.error().status()));
        document.reset(new tlv::document(std::move(*parsed)));
        std::vector<tlv::writer_frame> frames(options_.max_depth + 1);

        if (program->info().constructed_values_required) {
            auto encoded = document->encode();
            if (!encoded) return fail(3, tlv::message(encoded.error().status()));
            value_snapshot.resize(encoded->size());
            scratch.resize(encoded->size());
        }
        const tlv::writer_workspace staging({frames.data(), frames.size()},
                                            {scratch.data(), scratch.size()});
        auto                        evaluated =
            document->evaluate(*execution, {value_snapshot.data(), value_snapshot.size()},
                               program->info().constructed_values_required ? &staging : nullptr);
        if (!evaluated) return report(evaluated.error(), 3);
        if (program->result_type() == tlv::query_type::nodes)
            for (;;) {
                auto node = document->next(*execution);
                if (!node && node.error().status() == tlv::errc::end) break;
                if (!node) return report(node.error(), 3);
                // Constructed Value output is obtained through the normal Document encoder.
                auto                   value = node->value();
                std::vector<tlv::byte> children;
                if (node->is_constructed())
                    for (auto child : node->children()) {
                        auto encoded = child.encode();
                        if (!encoded) return fail(3, tlv::message(encoded.error().status()));
                        children.insert(children.end(), encoded->begin(), encoded->end());
                    }
                const auto source = node->source_location();
                emit(tlv::element_view(node->tag(), node->is_constructed()
                                                        ? tlv::value_view(tlv::bytes(
                                                              children.data(), children.size()))
                                                        : value),
                     source.has_offset != 0, source.offset);
            }
#else
        return fail(2, "Document backend is disabled in this build");
#endif
    } else {
        std::vector<tlv::tree_frame> frames(options_.max_depth + 1);
        tlv::tree_reader reader(tlv::bytes(reinterpret_cast<const tlv::byte*>(data()), size()),
                                *selected_format, {frames.data(), frames.size()},
                                options_.max_depth, options_.max_elements);
        auto             visited = execution->visit(reader, [&](const tlv::tree_event& event) {
            emit(event.element, true, event.offset);
            return tlv::visit_control::next;
        });
        if (!visited) return report(visited.error(), 3);
    }
    auto result = execution->scalar();
    if (!result) return report(result.error(), 3);
    if (result->kind == tlv::query_type::nodes) {
        if (is_json(options_)) std::cout << nlohmann::json({{"matches", matches}}).dump() << '\n';
        if (!matches_) return fail(5, ("no match for query " + program->format()).c_str());
    } else {
        nlohmann::json value;
        if (result->kind == tlv::query_type::boolean)
            value = result->boolean != 0;
        else if (result->kind == tlv::query_type::integer)
            value = result->integer;
        else if (result->kind == tlv::query_type::bytes)
            value = hex_string(result->data);
        else
            value = std::string(
                result->data.size() ? reinterpret_cast<const char*>(result->data.data()) : "",
                result->data.size());
        if (is_json(options_))
            std::cout << nlohmann::json({{"type", result->kind}, {"value", value}}).dump() << '\n';
        else if (result->kind == tlv::query_type::bytes || result->kind == tlv::query_type::string)
            std::cout << value.get<std::string>() << '\n';
        else
            std::cout << value.dump() << '\n';
    }
    return std::cout ? 0 : 3;
}

int query_command::prepare() {
    if (!options_.query) return fail(2, "invalid query");
    matcher_.reset(new tlv::query_matcher(*options_.query));
    return 0;
}

// query's visitor: prints each element the path addresses. Text output is
// the dump line without nesting, --value prints only the value bytes, and
// --output json collects the elements into one document printed at the end.
tlv::visit_control query_command::visit_element(const tlv::element_view& element, std::size_t depth,
                                                std::size_t offset) {
    diagnostic_scope_visit(scope_, data(), &element, depth, *format_);
    if (!matcher_->matches(element.tag(), depth)) return tlv::visit_control::next;
    ++matches_;
    if (is_json(options_)) {
        nlohmann::json object;
        object["path"] = query_path(*options_.query);
        object["offset"] = offset;
        object["tag"] = hex_string(element.tag().as_bytes());
        object["length"] = (uint64_t)element.value().size();
        object["value"] = hex_string(element.value().as_bytes());
        json_root_.push_back(std::move(object));
        return tlv::visit_control::next;
    }
    if (options_.value_only) {
        print_hex(element.value().as_bytes());
    } else {
        std::cout << "offset=" << offset << " tag=";
        print_hex(element.tag().as_bytes());
        std::cout << " length=" << element.value().size() << " value=";
        print_hex(element.value().as_bytes());
    }
    std::cout << "\n";
    return std::cout ? tlv::visit_control::next : tlv::visit_control::error;
}

void query_command::render_output() {
    if (result_ != tlv::errc::ok || !is_json(options_)) return;
    nlohmann::json document;
    document["matches"] = std::move(json_root_);
    std::cout << document.dump() << "\n";
}

int query_command::after_success() {
    if (matches_) return 0;
    std::cerr << "otlv: no match for query " << query_path(*options_.query) << "\n";
    return 5;
}

} // namespace cli
