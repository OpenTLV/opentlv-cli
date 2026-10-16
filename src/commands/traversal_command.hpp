// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Marek Cingel

#ifndef OPENTLV_CLI_COMMANDS_TRAVERSAL_COMMAND_HPP
#define OPENTLV_CLI_COMMANDS_TRAVERSAL_COMMAND_HPP
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "command.hpp"
#include "commands/support.hpp"
#include "diagnostic_collect.hpp"
#include "diagnostic_render.hpp"
#include "options.hpp"
#include "presentation.hpp"
#include "tlv++/types.hpp"
#include "tlv++/visitor.hpp"
#include "tlv++/schema/report.hpp"

namespace cli {

// Shared skeleton for "dump", "validate", "decode" and "query", which all
// traverse the same TLV tree with the selected format under --pdol/--recover.
// Owns the decoded input and the traversal/diagnostic state a visitor needs (what
// used to be threaded through as a separate output_context_t and a
// hand-picked free-function pointer); subclasses (one per file alongside
// this one) override the small set of hooks that actually differ between
// the four commands.
class traversal_command : public command {
public:
    traversal_command(const options& o, std::vector<uint8_t> data);
    int run() override;

protected:
    // Called for each element the traversal visits, in preorder. The base
    // implementation only keeps the diagnostic scope current (used as-is by
    // "validate", which has no display of its own).
    virtual tlv::visit_control visit_element(const tlv::element_view& element, std::size_t depth,
                                             std::size_t offset);

    // Called once, before the traversal starts. The base implementation does
    // nothing; "query" uses it to initialize its path matcher, returning a
    // nonzero exit code (and printing its own diagnostic) to abort early.
    virtual int prepare();

    // "validate --module" only: runs the selected module schema/value
    // checks once the format traversal itself succeeded (called from run() only
    // when result_ == tlv::errc::ok, options_.module and !options_.pdol). May
    // update result_/stage_ and either has_schema_diag_ with
    // schema_diag_, or stage_ alone, for render_failure_diagnostic() below.
    // The base implementation does nothing.
    virtual void run_module_checks();

    // Called once the traversal (and, for "validate", the module checks) are done,
    // regardless of the outcome: prints the command's own output. Most
    // overrides only print on result_ == tlv::errc::ok, except "dump" --output
    // json, which (like the original implementation) prints whatever
    // elements were collected even after a failure. The base implementation
    // does nothing (used as-is by "validate", which never prints on success).
    virtual void render_output();

    // Called only once result_ == tlv::errc::ok is confirmed (after the failure
    // diagnostic has already been handled): returns a nonzero exit code to
    // override the default of 0. "query" uses this for its exit code 5 (no
    // element matched).
    virtual int after_success();

    // Renders the diagnostic for a failed run (result_ != tlv::errc::ok). The base
    // implementation covers a schema violation (has_schema_diag_) and the
    // generic wire-level/result-code cases; "validate" overrides it to also
    // cover its own EMV dictionary check violation.
    virtual std::string render_failure_diagnostic(diagnostic_format  diag_format,
                                                  const char*        tag_hex_ptr,
                                                  const std::string& stage_name);

    // --pdol only: whether to print each DOL tag/requested-length pair as
    // it's read ("dump"), versus reading it silently to validate its shape
    // ("validate").
    virtual bool prints_pdol_annotations() const;

    // --recover only: whether a skipped range is also reported inline, as
    // dump's normal text output is printed ("dump", text output only).
    virtual bool prints_skipped_inline() const;

    void json_flush(std::size_t target_depth);
    void document_flush(std::size_t target_depth);

    const uint8_t* data() const {
        return data_.data();
    }
    std::size_t size() const {
        return data_.size();
    }

    options            options_;
    format_selection   format_storage_;
    std::size_t        base_;
    int                ber_;
    cli_presentation_t presentation_;
    const tlv::format* format_;
    bool               is_der_;
    diagnostic_scope   scope_;
    // --output json only: elements not yet attached to their parent's nested
    // "elements" array, one per currently open depth, and the finished
    // document's top-level array.
    std::vector<nlohmann::json> json_stack_;
    nlohmann::json              json_root_ = nlohmann::json::array();
    // "decode" only: the same structure for the versioned document, whose
    // constructed elements carry "children".
    std::vector<nlohmann::ordered_json> document_stack_;
    nlohmann::ordered_json              document_root_ = nlohmann::ordered_json::array();
    // "query" only: the matcher deciding which elements are addressed and how
    // many were.
    std::size_t matches_;

    tlv::errc                  result_;
    std::vector<skipped_range> skipped_;
    // Names the separate EMV pass ("schema ", "dictionary ") a failure came
    // from, as opposed to the format/framing traversal.
    const char*           stage_;
    tlv::validation_issue schema_diag_;
    bool                  has_schema_diag_;
    // Failure evidence of the traversal and module checks; its location is the
    // only failure position the generic rendering uses.
    tlv::reader_diagnostic reader_diag_{};

private:
    static tlv::visit_control visit_trampoline(const tlv::element_view* element, std::size_t depth,
                                               std::size_t offset, void* context);
    // --pdol: raw DOL tag/one-byte-length pairs (BER only), not full TLV.
    tlv::errc visit_pdol();
    // --recover: scans past damaged top-level elements instead of failing.
    tlv::errc visit_recovering();

    std::vector<uint8_t> data_;
};

} // namespace cli
#endif
