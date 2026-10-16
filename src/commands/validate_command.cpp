// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/validate_command.hpp"
#include <cstring>
#include <sstream>
#include "commands/support.hpp"
#include "tlv/config.h"
#include "bluetooth.hpp"
#if OPENTLV_BLUETOOTH
#include "tlv++/builtins/bluetooth/metadata.hpp"
#endif
#if OPENTLV_EMV
#include "tlv++/builtins/emv/dictionary.hpp"
#endif

namespace cli {

void validate_command::run_module_checks() {
#if OPENTLV_BLUETOOTH
    if (bluetooth_module(options_)) {
        const auto input = tlv::bytes(reinterpret_cast<const tlv::byte*>(data()), size());
        const auto container = tlv::bluetooth::validate_container(input);
        if (!container) {
            result_ = container.error().status();
            reader_diag_.diagnostic.location = container.error().location();
            return;
        }
        const size_t              significant = *container;
        tlv::validation_report<1> report;
        const auto                validated = report.validate(
            tlv::bytes(input.data(), significant), *format_, tlv::bluetooth::structural_schema(),
            tlv::unknown_policy::by_schema, options_.max_depth, options_.max_elements);
        if (!validated) {
            result_ = validated.error().status();
            reader_diag_.diagnostic.location = validated.error().location();
        } else if (report.size()) {
            schema_diag_ = report.at(0);
            has_schema_diag_ = true;
            result_ = schema_diag_.error().status();
        }
        if (result_ != tlv::errc::ok) {
            stage_ = "schema ";
            return;
        }
        const auto visitor = [](const tlv::element_view* element, size_t, size_t offset,
                                void* context) -> tlv::visit_control {
            auto&      self = *static_cast<validate_command*>(context);
            const auto decoded = decode_bluetooth_value(element);
            if (decoded.status != decode_status::error) return tlv::visit_control::next;
            self.result_ = tlv::errc::invalid_value;
            tlv::set_location(self.reader_diag_.diagnostic, tlv::location_domain::input,
                              tlv::location_kind::point, offset, offset);
            self.reader_diag_.detail.has_tag = 1;
            tlv::set_tag(self.reader_diag_, element->tag());
            self.stage_ = "codec ";
            return tlv::visit_control::stop;
        };
        const traversal_env env = {&options_, format_, is_der_};
        const auto          rc =
            visit_slice(env, data(), significant, 0, options_.max_elements, visitor, this);
        if (rc != tlv::errc::ok) result_ = rc;
        return;
    }
#endif
#if OPENTLV_EMV
    check_.presentation = cli_presentation_t();
    check_.presentation.ends.resize(1);
    check_.presentation.contexts.resize(1);
    check_.data = data();
    check_.predicate = format_;
    diagnostic_scope_init(check_.scope, size());
    check_.result = tlv::errc::ok;
    check_.offset = 0;
    check_.field_name = nullptr;

    if (options_.emv_check & emv_check_structure) {
        tlv::validation_report<1> report;
        const auto                validated =
            report.validate({reinterpret_cast<const tlv::byte*>(data()), size()}, *format_,
                            tlv::emv::structural_schema(), tlv::unknown_policy::by_schema,
                            options_.max_depth, options_.max_elements);
        if (!validated) {
            result_ = validated.error().status();
            reader_diag_.diagnostic.location = validated.error().location();
            stage_ = "schema ";
        } else if (report.size()) {
            schema_diag_ = report.at(0);
            has_schema_diag_ = true;
            result_ = schema_diag_.error().status();
            stage_ = "schema ";
        }
    }
    if (result_ == tlv::errc::ok && (options_.emv_check & emv_check_dictionary)) {
        check_.presentation.data = data();
        check_.presentation.ends[0] = size();
        check_.presentation.contexts[0] = options_.emv_context;
        const traversal_env env = {&options_, format_, is_der_};
        result_ = visit_slice(env, data(), size(), 0, options_.max_elements,
                              check_dictionary_trampoline, this, &reader_diag_);
        if (result_ == tlv::errc::ok && check_.result != tlv::errc::ok) {
            result_ = check_.result;
            stage_ = "dictionary ";
        }
    }
#endif
}

std::string validate_command::render_failure_diagnostic(diagnostic_format  diag_format,
                                                        const char*        tag_hex_ptr,
                                                        const std::string& stage_name) {
#if OPENTLV_EMV
    if (stage_name == "dictionary" && check_.result == result_) {
        tlv::diagnostic diag = tlv::make_diagnostic(result_, tlv::severity::error);
        tlv::set_location(diag, tlv::location_domain::input, tlv::location_kind::point,
                          check_.offset, check_.offset);
        if (check_.scope.path.length) tlv::set_path(diag, check_.scope.path);
        if (!check_.expected.empty()) diag.expected = check_.expected.c_str();
        if (!check_.actual.empty()) diag.actual = check_.actual.c_str();
        if (check_.field_name)
            tlv::add_context(diag, check_.field_context, "dictionary", "field", check_.field_name);
        return format_diagnostic(diag, diag_format, "dictionary", check_.tag.c_str());
    }
#endif
    return traversal_command::render_failure_diagnostic(diag_format, tag_hex_ptr, stage_name);
}

#if OPENTLV_EMV
tlv::visit_control validate_command::check_dictionary_trampoline(const tlv::element_view* element,
                                                                 std::size_t              depth,
                                                                 std::size_t              offset,
                                                                 void*                    context) {
    return static_cast<validate_command*>(context)->check_dictionary_element(element, depth,
                                                                             offset);
}

tlv::visit_control validate_command::check_dictionary_element(const tlv::element_view* element,
                                                              std::size_t              depth,
                                                              std::size_t              offset) {
    diagnostic_scope_visit(check_.scope, check_.data, element, depth, *check_.predicate);
    cli_presentation_visit(&check_.presentation, element, depth, 0);
    const auto definition =
        tlv::emv::dictionary(static_cast<tlv::emv::context>(check_.presentation.contexts[depth]))
            .find(element->tag());
    // A tag without a dictionary entry in its context is preserved unchecked.
    if (!definition) return tlv::visit_control::next;
    const size_t    value_length = cli_element_value_size(element);
    const auto      valid = definition.validate_length(value_length);
    const tlv::errc rc = valid ? tlv::errc::ok : valid.error().status();
    if (rc == tlv::errc::ok) return tlv::visit_control::next;
    check_.tag = hex_string(element->tag().as_bytes());
    check_.result = rc;
    check_.offset = offset;
    std::ostringstream expected;
    expected << definition.length().minimum << ".." << definition.length().maximum;
    if (definition.length_step() > 1) expected << " (step " << definition.length_step() << ")";
    check_.expected = expected.str();
    check_.actual = std::to_string(value_length);
    check_.field_name = definition.symbol(); // borrowed from the immutable dictionary tables
    return tlv::visit_control::stop;
}
#else
tlv::visit_control validate_command::check_dictionary_trampoline(const tlv::element_view*,
                                                                 std::size_t, std::size_t, void*) {
    return tlv::visit_control::next;
}

tlv::visit_control validate_command::check_dictionary_element(const tlv::element_view*, std::size_t,
                                                              std::size_t) {
    return tlv::visit_control::next;
}
#endif

} // namespace cli
