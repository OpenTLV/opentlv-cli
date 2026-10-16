// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#include "commands/traversal_command.hpp"
#include <cstring>
#include <iostream>
#include <utility>
#include <nlohmann/json.hpp>
#include "commands/support.hpp"
#include "diagnostic_collect.hpp"
#include "diagnostic_render.hpp"
#include "diagnostics.hpp"
#include "tlv/config.h"
#include "bluetooth.hpp"
#if OPENTLV_BLUETOOTH
#include "tlv++/builtins/bluetooth/metadata.hpp"
#endif
#if OPENTLV_FORMAT_BER
#include "tlv++/builtins/asn1/ber.hpp"
#endif
#if OPENTLV_FORMAT_DER
#endif

using cli::fail;

namespace {

tlv::visit_control count_element(const tlv::element_view*, size_t, size_t, void* context) {
    ++*static_cast<size_t*>(context);
    return tlv::visit_control::next;
}

// Prints a text-mode "skipped" line inline, where the range sits in the input.
void print_skipped(const cli::skipped_range& range) {
    std::cout << "skipped offset=" << range.offset << " length=" << range.length
              << " error=" << cli::error_name(range.error)
              << " error-location=" << cli::location_text(range.diagnostic.diagnostic.location)
              << "\n";
}

// Attaches every element on `stack` deeper than target_depth to its parent's
// `key` array (or `root`, for a closing top-level element), converting the
// preorder traversal into a nested document as each element's subtree
// finishes.
template <class Json>
void flush_stack(std::vector<Json>& stack, Json& root, size_t target_depth, const char* key) {
    while (stack.size() > target_depth) {
        Json child = std::move(stack.back());
        stack.pop_back();
        if (stack.empty())
            root.push_back(std::move(child));
        else
            stack.back()[key].push_back(std::move(child));
    }
}

} // namespace

namespace cli {

traversal_command::traversal_command(const options& o, std::vector<uint8_t> data)
    : options_(o), format_storage_(options_), base_(0), ber_(0), presentation_(), format_(NULL),
      is_der_(false), scope_(), matches_(0), result_(tlv::errc::ok), stage_(""), schema_diag_(),
      has_schema_diag_(false), data_(std::move(data)) {}

tlv::visit_control traversal_command::visit_trampoline(const tlv::element_view* element,
                                                       std::size_t depth, std::size_t offset,
                                                       void* context) {
    return static_cast<traversal_command*>(context)->visit_element(*element, depth, offset);
}

tlv::visit_control traversal_command::visit_element(const tlv::element_view& element,
                                                    std::size_t              depth, std::size_t) {
    // validate has no display visitor of its own; this one exists solely to
    // keep the diagnostic scope current, so a failure the traversal doesn't itself
    // annotate (a value that overruns its own container, not the whole
    // buffer) can still be reported with the path and boundary enclosing it.
    diagnostic_scope_visit(scope_, data(), &element, depth, *format_);
    return tlv::visit_control::next;
}

int traversal_command::prepare() {
    return 0;
}

void traversal_command::run_module_checks() {}

void traversal_command::render_output() {}

int traversal_command::after_success() {
    return 0;
}

void traversal_command::json_flush(std::size_t target_depth) {
    flush_stack(json_stack_, json_root_, target_depth, "elements");
}

void traversal_command::document_flush(std::size_t target_depth) {
    flush_stack(document_stack_, document_root_, target_depth, "children");
}

bool traversal_command::prints_pdol_annotations() const {
    return false;
}

bool traversal_command::prints_skipped_inline() const {
    return false;
}

std::string traversal_command::render_failure_diagnostic(diagnostic_format  diag_format,
                                                         const char*        tag_hex_ptr,
                                                         const std::string& stage_name) {
    if (has_schema_diag_) return format_schema_diagnostic(schema_diag_, diag_format);
    if (static_cast<tlv::errc>(reader_diag_.diagnostic.code) == result_) {
        if (scope_.path.length) tlv::set_path(reader_diag_.diagnostic, scope_.path);
        return format_reader_diagnostic(reader_diag_, diag_format);
    }
    tlv::diagnostic diag = tlv::make_diagnostic(result_, tlv::severity::error);
    diag.location = reader_diag_.diagnostic.location;
    return format_diagnostic(diag, diag_format, stage_name.c_str(), tag_hex_ptr);
}

// A DOL length is a single unsigned byte, not a BER length field. No value
// bytes follow it. Reuse the public BER tag reader without fabricating TLVs.
tlv::errc traversal_command::visit_pdol() {
#if OPENTLV_FORMAT_BER
    size_t pos = 0, count = 0;
    // A DOL failure is located at the byte its failing step reads.
    auto at = [this](size_t offset) {
        tlv::set_location(reader_diag_.diagnostic, tlv::location_domain::input,
                          tlv::location_kind::point, offset, offset);
    };
    while (pos < size()) {
        size_t   used, start = pos;
        unsigned requested;
        at(pos);
        if (count == options_.max_elements) return tlv::errc::limit;
        const auto identifier = tlv::ber::read_identifier(
            {reinterpret_cast<const tlv::byte*>(data() + pos), size() - pos}, used);
        if (!identifier) return identifier.error().status();
        if (identifier->size() > 2) return tlv::errc::invalid_tag_size;
        const tlv::element_view element(*identifier, tlv::value_view{});
        pos += used;
        at(pos);
        if (pos == size()) return tlv::errc::truncated;
        requested = data()[pos++];
        ++count;
        if (!prints_pdol_annotations()) continue;
        // Annotation uses only the tag, never a requested length as a value element.
        if (is_json(options_)) {
            nlohmann::json object;
            object["offset"] = start;
            object["tag"] = hex_string(element.tag().as_bytes());
            object["requested_length"] = requested;
            if (options_.module) json_emv(object, presentation_, &element, 0, options_.describe);
            json_root_.push_back(std::move(object));
            continue;
        }
        std::cout << "offset=" << start << " tag=";
        print_tag(element.tag(), presentation_.color != 0);
        std::cout << " requested-length=" << requested;
        if (options_.module) cli_presentation_emv(&presentation_, &element, 0, options_.describe);
        std::cout << "\n";
        if (!std::cout) return tlv::errc::visitor;
    }
    reader_diag_.diagnostic.location = tlv::location{};
    return tlv::errc::ok;
#else
    return tlv::errc::invalid_argument;
#endif
}

// Recovery scan over the top-level elements. Each element that reads cleanly
// and whose whole subtree validates is traversed (and printed) like normal
// input; where one does not, the CLI looks for the next offset a
// plausible element starts at, and the bytes in between are recorded as
// skipped. Resource limits are not damage and still fail the run.
tlv::errc traversal_command::visit_recovering() {
    const traversal_env env = {&options_, format_, is_der_};
    const bool          inline_text = prints_skipped_inline();
    size_t              pos = 0, budget = options_.max_elements;
    bool                skipping = false;
    skipped_range       current{};

    auto close_range = [&](size_t end) {
        current.length = end - current.offset;
        skipped_.push_back(current);
        if (inline_text) print_skipped(current);
        skipping = false;
    };
    while (pos < size()) {
        size_t                 consumed = 0, count = 0;
        tlv::reader_diagnostic attempt{};
        auto decoded = tlv::read({reinterpret_cast<const tlv::byte*>(data() + pos), size() - pos},
                                 *format_, consumed, &attempt);
        tlv::errc rc = decoded ? tlv::errc::ok : decoded.error().status();
        if (rc != tlv::errc::ok) {
            tlv::translate_location(attempt.diagnostic.location, pos);
            if (attempt.detail.has_tag_offset) attempt.detail.tag_offset += pos;
            if (attempt.detail.has_length_offset) attempt.detail.length_offset += pos;
            if (attempt.detail.has_value_offset) attempt.detail.value_offset += pos;
            if (attempt.detail.has_enclosing_end) attempt.detail.enclosing_end += pos;
        }
        if (rc == tlv::errc::ok) {
            rc = visit_slice(env, data() + pos, consumed, pos, budget, count_element, &count,
                             &attempt);
            // A limit without a deeper location belongs to this top-level element.
            const tlv::location& at = attempt.diagnostic.location;
            const bool top = tlv::kind(at) == tlv::location_kind::unknown || at.begin == pos;
            if ((rc == tlv::errc::limit || rc == tlv::errc::out_of_memory) && top) {
                reader_diag_.detail.has_tag = 1;
                tlv::set_tag(reader_diag_, decoded->element.tag());
            }
        }
        if (rc == tlv::errc::limit || rc == tlv::errc::out_of_memory) return rc;
        if (rc == tlv::errc::ok) {
            if (skipping) close_range(pos);
            base_ = pos;
            rc = visit_slice(env, data() + pos, consumed, pos, budget, visit_trampoline, this);
            if (rc != tlv::errc::ok) return rc;
            budget -= count;
            pos += consumed;
            continue;
        }
        if (!skipping) {
            skipping = true;
            current.offset = pos;
            current.error = rc;
            current.diagnostic = attempt;
        }
        // Resynchronization is CLI policy, built on single-element decoding.
        ++pos;
        for (; pos < size(); ++pos) {
            size_t next_size = 0;
            if (tlv::read({reinterpret_cast<const tlv::byte*>(data() + pos), size() - pos},
                          *format_, next_size))
                break;
        }
    }
    if (skipping) close_range(size());
    return tlv::errc::ok;
}

int traversal_command::run() {
    auto selected = format_storage_.get();
    if (!selected) return fail(2, "unknown or disabled format; use otlv formats");
    const tlv::format* format = &*selected;
    tlv::errc          result;
    int                is_ber = 0, is_der = 0, structured;
    diagnostic_format  diag_format;
    parse_diagnostic_format(options_.diagnostics, &diag_format);
    stage_ = "";
    has_schema_diag_ = false;

    if (!format) return fail(2, "unknown or disabled format; use otlv formats");
#if OPENTLV_FORMAT_BER
    is_ber = !std::strcmp(options_.format, "ber");
#endif
#if OPENTLV_FORMAT_DER
    is_der = !std::strcmp(options_.format, "der");
#endif
    structured = format->has_constructed_classifier();
    if (options_.tree && !structured)
        return fail(2, "--tree requires a format with a constructed indicator");

    format_ = format;
    is_der_ = is_der != 0;
    base_ = 0;
    ber_ = is_ber;
    cli_presentation_init(&presentation_, data(), size(), options_.color, options_.pretty);
    presentation_.contexts[0] = options_.emv_context;
    matches_ = 0;

    const int prepared = prepare();
    if (prepared) return prepared;

    diagnostic_scope_init(scope_, size());
    const traversal_env env = {&options_, format_, is_der_};
    std::size_t         significant = size();
    result = tlv::errc::ok;
#if OPENTLV_BLUETOOTH
    if (bluetooth_module(options_)) {
        const auto container = tlv::bluetooth::validate_container(
            {reinterpret_cast<const tlv::byte*>(data()), size()}, &reader_diag_);
        if (container)
            significant = *container;
        else
            result = container.error().status();
    }
#endif
    if (result != tlv::errc::ok) {
        stage_ = "container ";
    } else if (options_.pdol)
        result = visit_pdol();
    else if (options_.recover)
        result = visit_recovering();
    else
        result = visit_slice(env, data(), significant, 0, options_.max_elements, visit_trampoline,
                             this, &reader_diag_);
    result_ = result;

    if (result_ == tlv::errc::ok && options_.module && !options_.pdol) run_module_checks();

    render_output();

    cli_presentation_restore(&presentation_);
    int rc = flush_stdout();
    if (rc) return rc;
    if (result_ != tlv::errc::ok) {
        std::string stage_name(stage_);
        if (!stage_name.empty() && stage_name.back() == ' ') stage_name.pop_back();
        std::string tag_hex;
        if (reader_diag_.detail.has_tag)
            tag_hex = hex_string(tlv::diagnostic_tag(reader_diag_).as_bytes());
        const char* tag_hex_ptr = tag_hex.empty() ? nullptr : tag_hex.c_str();

        const std::string rendered =
            render_failure_diagnostic(diag_format, tag_hex_ptr, stage_name);
        if (diag_format == diagnostic_format::json)
            std::cerr << rendered << "\n";
        else
            std::cerr << "otlv: " << rendered << "\n";
        return result_ == tlv::errc::limit || result_ == tlv::errc::out_of_memory ? 3 : 1;
    }
    const int extra = after_success();
    if (extra) return extra;
    if (!skipped_.empty()) {
        size_t bytes = 0;
        // Every skipped range starts as its own top-level element (see
        // visit_recovering()), so this scope's path stays empty; a range
        // whose recorded failure is actually nested in that element's
        // subtree (not the top-level read itself) simply won't reproduce
        // through the derivation below and falls back to the plain form.
        // Never attempted for DER; see the same rationale where the final
        // wire-error case above excludes it.
        for (const skipped_range& range : skipped_) {
            tlv::reader_diagnostic reader_diag;
            std::string            rendered;
            if (static_cast<tlv::errc>(range.diagnostic.diagnostic.code) == range.error) {
                reader_diag = range.diagnostic;
                tlv::set_severity(reader_diag.diagnostic, tlv::severity::warning);
                rendered = format_reader_diagnostic(reader_diag, diag_format);
            } else {
                tlv::diagnostic diag = tlv::make_diagnostic(range.error, tlv::severity::warning);
                diag.location = range.diagnostic.diagnostic.location;
                rendered = format_diagnostic(diag, diag_format, "", nullptr);
            }
            if (diag_format == diagnostic_format::json) {
                nlohmann::json wrapper = nlohmann::json::parse(rendered);
                wrapper["skipped_offset"] = range.offset;
                wrapper["skipped_length"] = range.length;
                std::cerr << wrapper.dump() << "\n";
            } else {
                std::cerr << "otlv: skipped " << range.length << " byte(s) at offset "
                          << range.offset << ": " << rendered << "\n";
            }
            bytes += range.length;
        }
        std::cerr << "otlv: output is incomplete: recovery skipped " << skipped_.size()
                  << " range(s), " << bytes << " byte(s) in total\n";
        return 4;
    }
    return 0;
}

} // namespace cli
