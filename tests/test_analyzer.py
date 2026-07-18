"""Fixture-driven tests for the claudeye package.

Covers the parser leniency contract, usage deduplication across streamed
lines, the alias layer, subagent merging, tool-result attribution,
duplicate-read detection, compaction/error counting, the --since filter,
redaction, and the CLI end to end. Fixtures live under tests/fixtures
and mimic the real ~/.claude/projects layout.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import claudeye as cua  # noqa: E402
import claudeye.cli  # noqa: E402
import claudeye.ingest.cache  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "projects"
CODEX_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "codex" / "sessions"
WEBAPP_KEY = "-Users-tester-webapp/11111111-1111-4111-8111-111111111111"
API_KEY = "-Users-tester-api/22222222-2222-4222-8222-222222222222"
FORK_KEY = "-Users-tester-webapp/33333333-3333-4333-8333-333333333333"


def run_pipeline(project_filter=None, since=None):
    warnings = []
    events = []
    for session_file in cua.iter_session_files(FIXTURES, project_filter):
        events.extend(cua.parse_transcript(session_file, warnings))
    return cua.analyze_events(events, since=since), warnings


def make_summary(result, warnings, **kwargs):
    defaults = dict(input_root=str(FIXTURES), since=None, project_filter=None, redact_paths=False)
    defaults.update(kwargs)
    return cua.build_summary(result, warnings, **defaults)


class DiscoveryTest(unittest.TestCase):
    def test_finds_main_and_subagent_transcripts(self):
        files = list(cua.iter_session_files(FIXTURES))
        self.assertEqual(len(files), 4)
        agents = [f for f in files if f.agent_id]
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0].agent_id, "abc123def456")
        self.assertEqual(agents[0].session_id, "22222222-2222-4222-8222-222222222222")
        self.assertEqual(agents[0].project, "-Users-tester-api")

    def test_project_filter_is_substring_case_insensitive(self):
        files = list(cua.iter_session_files(FIXTURES, "WEBAPP"))
        self.assertEqual(len(files), 2)  # original + fork session
        self.assertTrue(all("webapp" in f.project for f in files))

    def test_missing_root_yields_nothing(self):
        self.assertEqual(list(cua.iter_session_files(FIXTURES / "nope")), [])


class LenientParserTest(unittest.TestCase):
    def test_bad_line_becomes_warning_not_crash(self):
        _, warnings = run_pipeline()
        self.assertEqual(len(warnings), 1)
        self.assertIn("invalid JSON", warnings[0].reason)
        self.assertIn("webapp", warnings[0].file)
        self.assertGreater(warnings[0].line_no, 0)

    def test_irrelevant_line_types_are_skipped_silently(self):
        result, warnings = run_pipeline()
        # queue-operation and mode lines exist in the fixture but produce
        # neither events nor warnings.
        self.assertEqual(len(warnings), 1)
        self.assertEqual(len(result.sessions), 3)


class UsageAggregationTest(unittest.TestCase):
    def test_streamed_lines_dedup_by_message_id(self):
        result, _ = run_pipeline()
        stats = result.sessions[WEBAPP_KEY]
        # msg_A2 spans two JSONL lines with identical usage — counted once.
        self.assertEqual(stats.requests, 6)
        self.assertEqual(stats.usage.input_tokens, 37)
        self.assertEqual(stats.usage.cache_creation_tokens, 2180)
        self.assertEqual(stats.usage.cache_read_tokens, 11350)
        self.assertEqual(stats.usage.output_tokens, 420)

    def test_camel_case_alias_layer(self):
        result, _ = run_pipeline()
        stats = result.sessions[WEBAPP_KEY]
        # msg_A6 carries camelCase usage keys; its cache_read 2400 is part
        # of the 11350 asserted above, and its model is still counted.
        self.assertEqual(sum(stats.models.values()), 6)

    def test_models_counter_excludes_synthetic(self):
        result, _ = run_pipeline()
        stats = result.sessions[API_KEY]
        self.assertNotIn("<synthetic>", stats.models)

    def test_day_usage_matches_local_dates(self):
        result, _ = run_pipeline()
        expected_days = set()
        for raw in (
            "2026-06-30T23:50:05.000Z",
            "2026-07-01T00:10:00.000Z",
            "2026-07-01T09:20:00.000Z",
            "2026-07-01T01:00:05.000Z",
        ):
            ts = cua._parse_timestamp(raw)
            expected_days.add(ts.astimezone().date().isoformat())
        self.assertEqual({day for day, _ in result.day_usage}, expected_days)
        total = cua.Usage()
        for usage in result.day_usage.values():
            total += usage
        # Daily matrix must account for every deduplicated token.
        combined = cua.Usage()
        for stats in result.sessions.values():
            combined += stats.usage + stats.subagent_usage
        self.assertEqual(total.total(), combined.total())


class SubagentMergeTest(unittest.TestCase):
    def test_subagent_folds_into_parent_session(self):
        result, _ = run_pipeline()
        self.assertEqual(len(result.sessions), 3)
        stats = result.sessions[API_KEY]
        self.assertEqual(stats.subagent_ids, {"abc123def456"})
        self.assertEqual(stats.requests, 3)  # synthetic error not a request
        self.assertEqual(stats.subagent_requests, 3)
        self.assertEqual(stats.usage.input_tokens, 45)
        self.assertEqual(stats.usage.cache_creation_tokens, 11100)
        self.assertEqual(stats.usage.cache_read_tokens, 8100)
        self.assertEqual(stats.usage.output_tokens, 500)
        self.assertEqual(stats.subagent_usage.input_tokens, 17)
        self.assertEqual(stats.subagent_usage.cache_creation_tokens, 540)
        self.assertEqual(stats.subagent_usage.cache_read_tokens, 1150)
        self.assertEqual(stats.subagent_usage.output_tokens, 175)


class ToolAttributionTest(unittest.TestCase):
    def test_calls_and_result_bytes_by_tool(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        by_tool = {row["name"]: row for row in summary["by_tool"]}
        self.assertEqual(by_tool["Read"]["calls"], 4)
        self.assertEqual(by_tool["Bash"]["calls"], 1)
        self.assertEqual(by_tool["Agent:Explore"]["calls"], 1)
        self.assertNotIn("(unmatched)", by_tool)
        self.assertGreater(by_tool["Read"]["result_bytes"], by_tool["Bash"]["result_bytes"])
        self.assertGreater(by_tool["Agent:Explore"]["result_bytes"], 0)
        self.assertLessEqual(by_tool["Read"]["max_result_bytes"], by_tool["Read"]["result_bytes"])
        self.assertEqual(sum(r["errors"] for r in summary["by_tool"]), 0)


class DupReadTest(unittest.TestCase):
    def test_same_file_same_context_counts_as_duplicate(self):
        result, _ = run_pipeline()
        webapp = result.sessions[WEBAPP_KEY]
        self.assertEqual(webapp.dup_read_files(), {"/Users/tester/webapp/src/app.py": 2})
        self.assertEqual(webapp.wasted_reads(), 1)
        api = result.sessions[API_KEY]
        self.assertEqual(api.dup_read_files(), {"/Users/tester/api/lib/db.py": 2})
        self.assertEqual(api.wasted_reads(), 1)

    def test_two_reads_do_not_raise_the_flag(self):
        result, _ = run_pipeline()
        for stats in result.sessions.values():
            self.assertNotIn("dup-read", stats.waste_flags())

    def test_summary_lists_both_files(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        paths = {row["path"] for row in summary["dup_reads"]}
        self.assertEqual(paths, {"/Users/tester/webapp/src/app.py", "/Users/tester/api/lib/db.py"})
        for row in summary["dup_reads"]:
            self.assertEqual(row["reads"], 2)
            self.assertEqual(row["wasted_reads"], 1)
            self.assertEqual(row["max_in_one_context"], 2)


class ForkDedupTest(unittest.TestCase):
    """Session 3333... is a fork of 1111...: four lines copied verbatim
    (uuid, message id, tool_use id, usage, timestamps included) plus one
    genuinely new exchange. Convergence-review finding C1: without global
    dedup this inflated real-corpus tokens 8x and tool calls 6x.
    """

    def test_fork_session_reports_only_new_activity(self):
        result, _ = run_pipeline()
        fork = result.sessions[FORK_KEY]
        self.assertEqual(fork.requests, 1)  # msg_F1 only
        self.assertEqual(fork.usage.input_tokens, 2)
        self.assertEqual(fork.usage.output_tokens, 30)
        self.assertEqual(fork.usage.cache_read_tokens, 100)
        self.assertEqual(fork.usage.cache_creation_tokens, 0)
        self.assertEqual(dict(fork.models), {"claude-opus-4-8": 1})
        self.assertEqual(sum(fork.tool_calls.values()), 0)  # copied Read suppressed
        self.assertEqual(fork.wasted_reads(), 0)
        # Timestamp span covers counted lines only, not inherited history.
        self.assertEqual(fork.first_ts.isoformat(), "2026-07-01T01:00:00+00:00")
        self.assertEqual(fork.last_ts.isoformat(), "2026-07-01T01:00:05+00:00")

    def test_original_session_owns_inherited_history(self):
        result, _ = run_pipeline()
        original = result.sessions[WEBAPP_KEY]
        self.assertEqual(original.requests, 6)
        self.assertEqual(original.usage.cache_read_tokens, 11350)
        self.assertEqual(original.wasted_reads(), 1)

    def test_global_metrics_unchanged_by_fork_copies(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        by_tool = {row["name"]: row for row in summary["by_tool"]}
        self.assertEqual(by_tool["Read"]["calls"], 4)  # not 5
        self.assertEqual(summary["totals"]["wasted_reads"], 2)
        self.assertEqual(summary["totals"]["compactions"], 1)
        # Only msg_F1 adds tokens on top of the two base sessions.
        base = 0
        for key in (WEBAPP_KEY, API_KEY):
            stats = result.sessions[key]
            base += stats.usage.total() + stats.subagent_usage.total()
        self.assertEqual(summary["totals"]["total_tokens"], base + (2 + 30 + 100))


class StreamSnapshotTest(unittest.TestCase):
    """Codex round-1 finding X1: a usage-less streamed snapshot must not
    shadow a later usage-bearing line of the same message."""

    @staticmethod
    def _event(uuid, message_id, usage):
        return cua.Event(
            project="p",
            session_id="s",
            kind="assistant",
            timestamp=None,
            uuid=uuid,
            message_id=message_id,
            model="claude-opus-4-8",
            usage=usage,
        )

    def test_usage_less_snapshot_does_not_shadow(self):
        events = [
            self._event("l1", "m1", None),
            self._event("l2", "m1", cua.Usage(input_tokens=7, output_tokens=3)),
            self._event("l3", "m1", cua.Usage(input_tokens=7, output_tokens=3)),
        ]
        result = cua.analyze_events(events)
        stats = result.sessions["p/s"]
        self.assertEqual(stats.requests, 1)
        self.assertEqual(stats.usage.input_tokens, 7)
        self.assertEqual(stats.usage.output_tokens, 3)


class ProjectRollupTest(unittest.TestCase):
    """by_project gives the mid-level view between totals and sessions."""

    def test_rollup_rows_and_values(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        rows = {row["project"]: row for row in summary["by_project"]}
        # project display is now the real cwd path (from fixture cwd), not the slug
        self.assertEqual(set(rows), {"/Users/tester/webapp", "/Users/tester/api"})
        webapp = rows["/Users/tester/webapp"]
        # original session + fork session (fork adds msg_F1 only)
        self.assertEqual(webapp["sessions"], 2)
        self.assertEqual(webapp["requests"], 7)
        self.assertEqual(webapp["total_tokens"], 13987 + 132)
        self.assertEqual(webapp["wasted_reads"], 1)
        api = rows["/Users/tester/api"]
        self.assertEqual(api["sessions"], 1)
        self.assertEqual(api["subagent_requests"], 3)
        # combined = main + subagent usage
        self.assertEqual(api["input_tokens"], 45 + 17)
        self.assertEqual(api["compactions"], 1)
        self.assertEqual(api["errors"], 2)

    def test_rollup_totals_match_grand_totals(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        self.assertEqual(
            sum(row["total_tokens"] for row in summary["by_project"]),
            summary["totals"]["total_tokens"],
        )
        self.assertEqual(
            sum(row["sessions"] for row in summary["by_project"]),
            summary["totals"]["sessions"],
        )

    def test_cache_efficiency_uses_main_conversation_only(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        api = next(row for row in summary["by_project"] if row["project"] == "/Users/tester/api")
        self.assertAlmostEqual(api["cache_efficiency"], round(8100 / (45 + 8100), 4))

    def test_project_display_uses_cwd_path(self):
        # slug -Users-tester-webapp is shown as the real cwd, not decoded
        # from the slug (which would mangle the hyphen in a dir name).
        result, warnings = run_pipeline()
        webapp = result.sessions[WEBAPP_KEY]
        self.assertEqual(webapp.cwd, "/Users/tester/webapp")
        summary = make_summary(result, warnings)
        names = {row["project"] for row in summary["by_project"]}
        self.assertIn("/Users/tester/webapp", names)
        self.assertNotIn("-Users-tester-webapp", names)


class CompactionAndErrorTest(unittest.TestCase):
    def test_compaction_recorded_with_pre_tokens(self):
        result, _ = run_pipeline()
        stats = result.sessions[API_KEY]
        self.assertEqual(stats.compactions, 1)
        self.assertEqual(stats.compact_pre_tokens, [165432])
        self.assertIn("compacted", stats.waste_flags())

    def test_retries_and_synthetic_errors_counted_separately(self):
        result, _ = run_pipeline()
        stats = result.sessions[API_KEY]
        self.assertEqual(stats.retries, 1)  # system api_error with retryAttempt
        self.assertEqual(stats.api_errors, 1)  # synthetic assistant placeholder

    def test_cache_efficiency_main_conversation_only(self):
        result, _ = run_pipeline()
        stats = result.sessions[API_KEY]
        self.assertAlmostEqual(stats.cache_efficiency(), 8100 / (45 + 8100), places=6)


class SinceFilterTest(unittest.TestCase):
    def test_since_drops_older_events(self):
        since = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        result, _ = run_pipeline(since=since)
        webapp = result.sessions[WEBAPP_KEY]
        self.assertEqual(webapp.requests, 2)  # msg_A5, msg_A6 only
        self.assertEqual(webapp.usage.input_tokens, 10)
        self.assertEqual(sum(webapp.tool_calls.values()), 0)
        api = result.sessions[API_KEY]
        self.assertEqual(api.requests, 3)  # untouched

    def test_since_can_drop_whole_sessions(self):
        since = datetime(2026, 7, 1, 9, 30, tzinfo=timezone.utc)
        result, _ = run_pipeline(since=since)
        self.assertEqual(result.sessions, {})


class SummaryAndRenderTest(unittest.TestCase):
    def test_totals_are_consistent(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        totals = summary["totals"]
        self.assertEqual(totals["sessions"], 3)
        self.assertEqual(totals["projects"], 2)
        self.assertEqual(
            totals["total_tokens"],
            sum(row["total_tokens"] for row in summary["sessions"]),
        )
        self.assertEqual(totals["wasted_reads"], 2)
        self.assertEqual(totals["compactions"], 1)
        self.assertEqual(totals["errors"], 2)
        self.assertEqual(summary["meta"]["parse_warnings_total"], 1)

    def test_lang_defaults_to_en_and_is_carried_to_meta(self):
        result, warnings = run_pipeline()
        self.assertEqual(make_summary(result, warnings)["meta"]["lang"], "en")
        self.assertEqual(make_summary(result, warnings, lang="ko")["meta"]["lang"], "ko")
        # The report embeds the Korean strings and the data-i18n hooks.
        html = cua.render_html(make_summary(result, warnings, lang="ko"))
        self.assertIn("data-i18n=", html)
        self.assertIn("모델별 일별 토큰", html)  # STRINGS.ko present

    def test_language_toggle_rerenders_dynamic_report_regions(self):
        result, warnings = run_pipeline()
        html = cua.render_html(make_summary(result, warnings, lang="ko"))
        self.assertIn("let T = STRINGS[lang]", html)
        self.assertIn("T = STRINGS[lang]", html)
        self.assertIn("renderLocalized();", html)
        self.assertIn('data-i18n="brand_sub"', html)
        self.assertIn("const skillWhatifState = {", html)
        self.assertIn("const sessionTableState = {", html)
        self.assertNotIn('let sortKey = "total_tokens"', html)
        self.assertEqual(html.count(".advice-item .conf-tag {"), 1)

    def test_both_languages_cover_the_same_ui_keys(self):
        from claudeye.render.strings import UI_STRINGS

        self.assertEqual(set(UI_STRINGS["en"]), set(UI_STRINGS["ko"]))
        self.assertEqual(UI_STRINGS["ko"]["sec_tools"], "도구 결과 크기")
        for name in (
            "tokens",
            "tool_calls",
            "tool_result_bytes",
            "dup_reads",
            "cache_efficiency",
            "compactions",
            "fork_attribution",
            "subagent_types",
            "skill_chains",
            "per_tool_tokens",
        ):
            self.assertIn(f"confname_{name}", UI_STRINGS["ko"])
            self.assertIn(f"confnote_{name}", UI_STRINGS["ko"])

    def test_redaction_hides_directories_keeps_basenames(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings, redact_paths=True)
        blob = json.dumps(summary, ensure_ascii=False)
        self.assertNotIn("/Users/tester", blob)
        self.assertNotIn(str(FIXTURES), blob)
        # X2 (codex round 1): the input root itself must be redacted too.
        self.assertFalse(summary["meta"]["input_root"].startswith("/"))
        self.assertFalse(summary["meta"]["input_root"].startswith("~"))
        paths = {row["path"] for row in summary["dup_reads"]}
        self.assertTrue(any(p.endswith("/app.py") for p in paths))
        self.assertTrue(any(p.endswith("/db.py") for p in paths))
        for row in summary["sessions"]:
            self.assertNotIn("tester-webapp", row["project"])

    def test_html_report_is_self_contained(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        html_text = cua.render_html(summary)
        self.assertIn("summary-data", html_text)
        self.assertIn("claudeye", html_text)
        self.assertNotIn("http://", html_text.replace("http://www.w3.org", ""))
        self.assertNotIn("https://", html_text)
        # Embedded JSON must not be able to close the script tag early.
        payload = html_text.split('type="application/json">', 1)[1].split("</script>")[0]
        self.assertNotIn("</", payload.replace("<\\/", ""))
        self.assertEqual(json.loads(payload.replace("<\\/", "</"))["totals"]["sessions"], 3)

    def test_daily_chart_uses_adaptive_date_ticks(self):
        """Dense daily charts retain range anchors and month context."""
        result, warnings = run_pipeline()
        html_text = cua.render_html(make_summary(result, warnings))
        self.assertIn("function dateTickIndices(days, maxLabels, minLabelSlots)", html_text)
        self.assertIn("const DATE_LABEL_GAP = 56", html_text)
        self.assertIn("const hasRoom = [...ticks].every", html_text)
        self.assertIn('day.slice(8) !== "01"', html_text)
        self.assertIn("if (!dateLabelIndices.has(i)) return;", html_text)

    def test_render_json_roundtrip(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        self.assertEqual(json.loads(cua.render_json(summary)), summary)

    def test_ui_strings_sentinel_in_data_keeps_summary_json_valid(self):
        # Codex review: report data (a path, project name, warning reason) that
        # contains the literal "__UI_STRINGS__" must not corrupt the embedded
        # summary JSON — the user payload is substituted last, so it is never
        # re-scanned by the UI-strings replacement.
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        summary["meta"]["input_root"] = "/tmp/__UI_STRINGS__/x"
        html_text = cua.render_html(summary)
        payload = html_text.split('type="application/json">', 1)[1].split("</script>")[0]
        parsed = json.loads(payload.replace("<\\/", "</"))
        self.assertEqual(parsed["meta"]["input_root"], "/tmp/__UI_STRINGS__/x")

    def test_empty_corpus_still_renders(self):
        result = cua.analyze_events([])
        summary = make_summary(result, [])
        self.assertEqual(summary["totals"]["sessions"], 0)
        self.assertIn("summary-data", cua.render_html(summary))


class ToolDisplayNameTest(unittest.TestCase):
    """Skill invocations rank per skill; everything else keeps its name."""

    def test_skill_breaks_out_by_skill_name(self):
        self.assertEqual(
            cua._tool_display_name("Skill", {"skill": "codex-review", "args": "x"}),
            "Skill:codex-review",
        )

    def test_skill_without_name_falls_back(self):
        self.assertEqual(cua._tool_display_name("Skill", {}), "Skill")
        self.assertEqual(cua._tool_display_name("Skill", None), "Skill")
        self.assertEqual(cua._tool_display_name("Skill", {"skill": 3}), "Skill")

    def test_agent_breaks_out_by_subagent_type(self):
        self.assertEqual(
            cua._tool_display_name("Agent", {"subagent_type": "Explore"}),
            "Agent:Explore",
        )
        self.assertEqual(cua._tool_display_name("Task", {"subagent_type": "Plan"}), "Task:Plan")
        self.assertEqual(cua._tool_display_name("Agent", {}), "Agent")

    def test_other_tools_unchanged(self):
        self.assertEqual(cua._tool_display_name("Read", {"skill": "x"}), "Read")


class SubagentTypeAttributionTest(unittest.TestCase):
    """Sidechain tokens joined to dispatch subagent_type via
    toolUseResult.agentId (codex-debate F3, measured-only)."""

    def test_fixture_agent_attributed_to_explore(self):
        result, warnings = run_pipeline()
        self.assertEqual(result.agent_types, {"abc123def456": "Explore"})
        summary = make_summary(result, warnings)
        rows = {row["type"]: row for row in summary["by_agent_type"]}
        self.assertEqual(set(rows), {"Explore"})
        explore = rows["Explore"]
        self.assertEqual(explore["agents"], 1)
        self.assertEqual(explore["requests"], 3)
        self.assertEqual(explore["total_tokens"], 17 + 540 + 1150 + 175)

    def test_unlinked_agent_falls_into_unattributed(self):
        events = [
            cua.Event(
                project="p",
                session_id="s",
                kind="assistant",
                timestamp=None,
                uuid="l1",
                agent_id="agent-x",
                message_id="m1",
                model="claude-opus-4-8",
                usage=cua.Usage(input_tokens=5, output_tokens=2),
            )
        ]
        result = cua.analyze_events(events)
        summary = cua.build_summary(result, [], input_root="/x", since=None, project_filter=None)
        rows = {row["type"]: row for row in summary["by_agent_type"]}
        self.assertEqual(set(rows), {"(unattributed)"})
        self.assertEqual(rows["(unattributed)"]["total_tokens"], 7)

    def test_out_of_order_link_resolves_via_pending_pass(self):
        # Sidechain usage arrives BEFORE the dispatching transcript's
        # tool_use/result pair — mirrors directory-before-file discovery.
        events = [
            cua.Event(
                project="p",
                session_id="s",
                kind="assistant",
                timestamp=None,
                uuid="l1",
                agent_id="ag1",
                message_id="m1",
                model="claude-opus-4-8",
                usage=cua.Usage(input_tokens=3),
            ),
            cua.Event(
                project="p",
                session_id="s",
                kind="user",
                timestamp=None,
                uuid="l2",
                tool_results=[cua.ToolResultRecord(tool_use_id="tu1", result_bytes=10)],
                agent_link=("tu1", "ag1"),
            ),
            cua.Event(
                project="p",
                session_id="s",
                kind="assistant",
                timestamp=None,
                uuid="l3",
                message_id="m2",
                model="claude-opus-4-8",
                usage=cua.Usage(input_tokens=1),
                tool_uses=[
                    cua.ToolUseCall(
                        tool_use_id="tu1", name="Agent:Explore", subagent_type="Explore"
                    )
                ],
            ),
        ]
        result = cua.analyze_events(events)
        self.assertEqual(result.agent_types, {"ag1": "Explore"})


class SkillChainTest(unittest.TestCase):
    """Per-skill downstream cost from attributionSkill stamps: msg_A3
    (Read) and msg_A4 (Bash) in the webapp fixture are stamped
    demo-skill; the fork's verbatim copy of the Read line must not
    double anything."""

    def test_chain_tokens_and_tools(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        rows = {row["skill"]: row for row in summary["by_skill_chain"]}
        self.assertEqual(set(rows), {"demo-skill"})
        chain = rows["demo-skill"]
        self.assertEqual(chain["requests"], 2)  # msg_A3 + msg_A4, fork copy gated
        self.assertEqual(chain["total_tokens"], (6 + 50 + 2200 + 40) + (4 + 20 + 2300 + 35))
        self.assertEqual(chain["tool_calls"], 2)
        tools = {t["name"]: t for t in chain["tools"]}
        self.assertEqual(set(tools), {"Read", "Bash"})
        self.assertEqual(tools["Bash"]["result_bytes"], len("app.py\nutils.py"))
        # tools list is uncapped, so per-tool bytes must sum exactly
        self.assertEqual(
            sum(t["result_bytes"] for t in chain["tools"]),
            chain["tool_result_bytes"],
        )

    def test_skill_and_agent_rank_by_new_tokens_not_total(self):
        # Attribution slices exclude ambient cache_read from ranking, so a
        # peak-context regular does not outrank its real footprint. Synthetic
        # summary: skill A has huge cache_read but tiny new tokens; skill B the
        # reverse — B must rank first and carry a new_tokens field.
        big_cache = cua.Usage(input_tokens=1, output_tokens=1, cache_read_tokens=9_000_000)
        real_work = cua.Usage(
            input_tokens=500_000, output_tokens=200_000, cache_creation_tokens=50_000
        )
        result = cua.AnalysisResult(
            sessions={},
            day_usage={},
            skill_chains={
                "peak-context": cua.SkillChainStats(usage=big_cache, requests=40),
                "real-work": cua.SkillChainStats(usage=real_work, requests=5),
            },
        )
        summary = cua.build_summary(result, [], input_root="/x", since=None, project_filter=None)
        order = [r["skill"] for r in summary["by_skill_chain"]]
        self.assertEqual(order[0], "real-work")  # not the cache-heavy one
        rows = {r["skill"]: r for r in summary["by_skill_chain"]}
        self.assertEqual(rows["real-work"]["new_tokens"], 500_000 + 200_000 + 50_000)
        self.assertEqual(rows["peak-context"]["new_tokens"], 2)  # cache_read excluded
        # total_tokens still available (cache_read included) for reference
        self.assertGreater(rows["peak-context"]["total_tokens"], rows["real-work"]["total_tokens"])

    def test_unstamped_turns_are_not_attributed(self):
        result, _ = run_pipeline()
        # Only the two stamped turns exist corpus-wide; everything else
        # (including all api-project turns) stays outside skill chains.
        chain = result.skill_chains["demo-skill"]
        self.assertEqual(len(result.skill_chains), 1)
        self.assertEqual(chain.requests, 2)


class AdviceRulesTest(unittest.TestCase):
    """Rule thresholds from the codex-debate convergence (v0.2③)."""

    @staticmethod
    def _session(**kw):
        base = {
            "session_id": "abcdef012345",
            "compactions": 0,
            "cache_efficiency": None,
        }
        base.update(kw)
        return base

    def test_fixture_corpus_fires_nothing(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        self.assertEqual(summary["advice"], [])

    def test_dup_hotspot_needs_both_thresholds(self):
        dup = [
            {
                "path": "/a.md",
                "reads": 25,
                "wasted_reads": 24,
                "sessions": 3,
                "max_in_one_context": 9,
            }
        ]
        advice = cua._build_advice([], dup, [])
        self.assertEqual(len(advice), 1)
        self.assertEqual(advice[0]["rule"], "dup-read-hotspot")
        self.assertIn("/a.md", advice[0]["message"])
        # below either threshold -> silent
        low_wasted = [dict(dup[0], wasted_reads=19)]
        few_sessions = [dict(dup[0], sessions=2)]
        self.assertEqual(cua._build_advice([], low_wasted, []), [])
        self.assertEqual(cua._build_advice([], few_sessions, []), [])

    def test_compaction_pressure_reports_worst_session(self):
        sessions = [self._session(compactions=2), self._session(compactions=4)]
        advice = cua._build_advice(sessions, [], [])
        self.assertEqual(advice[0]["rule"], "compaction-pressure")
        self.assertIn("x4", advice[0]["message"])

    def test_low_cache_needs_floor_and_share(self):
        low = [self._session(cache_efficiency=0.3) for _ in range(4)]
        ok = [self._session(cache_efficiency=0.9) for _ in range(4)]
        advice = cua._build_advice(low + ok, [], [])
        self.assertEqual(advice[0]["rule"], "low-cache-pattern")
        # floor: 3 low sessions never fire even at 100% share
        self.assertEqual(cua._build_advice([self._session(cache_efficiency=0.1)] * 3, [], []), [])

    def test_huge_result_reports_top_offenders_only(self):
        tools = [
            {
                "name": "Read",
                "calls": 1,
                "errors": 0,
                "result_bytes": 900_000,
                "max_result_bytes": 700_000,
            },
            {
                "name": "Bash",
                "calls": 1,
                "errors": 0,
                "result_bytes": 500_000,
                "max_result_bytes": 300_000,
            },
            {
                "name": "Grep",
                "calls": 1,
                "errors": 0,
                "result_bytes": 250_000,
                "max_result_bytes": 250_000,
            },
        ]
        advice = cua._build_advice([], [], tools)
        self.assertEqual([a["rule"] for a in advice], ["huge-tool-result", "huge-tool-result"])
        self.assertIn("Read", advice[0]["message"])  # largest first, capped at 2

    @staticmethod
    def _chain(skill, turns, new_per_turn=0, bytes_per_turn=0, calls_per_turn=0.0):
        return {
            "skill": skill,
            "requests": turns,
            "input_tokens": new_per_turn * turns,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 999_999,
            "total_tokens": new_per_turn * turns + 999_999,
            "tool_calls": int(calls_per_turn * turns),
            "tool_result_bytes": bytes_per_turn * turns,
            "tools": [],
        }

    def test_skill_heavy_turns_fires_with_target(self):
        chains = [self._chain("fat-skill", 12, new_per_turn=45_000)]
        advice = cua._build_advice([], [], [], chains)
        self.assertEqual(advice[0]["rule"], "skill-heavy-turns")
        self.assertEqual(advice[0]["target"], {"kind": "skill", "name": "fat-skill"})
        self.assertIn("45k new tokens/turn", advice[0]["message"])
        self.assertIn("12 turns", advice[0]["message"])

    def test_skill_rule_floor_blocks_small_basis(self):
        # 9 turns of extreme spend must stay silent (small-basis trap).
        chains = [self._chain("tiny", 9, new_per_turn=900_000)]
        self.assertEqual(cua._build_advice([], [], [], chains), [])
        # cache reads alone never fire: new-spend excludes them.
        quiet = [self._chain("cachey", 50, new_per_turn=1_000)]
        self.assertEqual(cua._build_advice([], [], [], quiet), [])

    def test_skill_signals_combine_and_cap_two(self):
        chains = [
            self._chain("a", 20, new_per_turn=50_000, bytes_per_turn=150_000, calls_per_turn=9.0),
            self._chain("b", 20, new_per_turn=60_000),
            self._chain("c", 20, new_per_turn=70_000),
        ]
        advice = cua._build_advice([], [], [], chains)
        skill_items = [a for a in advice if a["rule"] == "skill-heavy-turns"]
        self.assertEqual(len(skill_items), 2)  # top two by new-spend
        names = {a["target"]["name"] for a in skill_items}
        self.assertEqual(names, {"c", "b"})
        # one item per skill even when several signals fire together
        combo = cua._build_advice([], [], [], [chains[0]])
        self.assertEqual(len(combo), 1)
        self.assertIn("146 KB tool results/turn", combo[0]["message"])  # 150000/1024
        # fanout 9.0/turn stays below the 8-threshold? no — 9 >= 8 fires:
        self.assertIn("tool calls/turn", combo[0]["message"])

    def test_summary_carries_rule_catalog_and_thresholds(self):
        result, warnings = run_pipeline()
        summary = make_summary(result, warnings)
        self.assertEqual(
            set(summary["advice_rules"]),
            {
                "dup-read-hotspot",
                "compaction-pressure",
                "low-cache-pattern",
                "huge-tool-result",
                "skill-heavy-turns",
            },
        )
        for rule in summary["advice_rules"].values():
            self.assertIn("title", rule)
            self.assertIn("definition", rule)
            self.assertIn("ko", rule["title_i18n"])
            self.assertIn("ko", rule["definition_i18n"])
        self.assertEqual(
            summary["advice_thresholds"]["skill_min_turns"],
            cua.AdviceConfig().skill_min_turns,
        )

    def test_every_fired_rule_is_in_catalog(self):
        # Drift guard: no advice item may reference a rule without a definition.
        chains = [self._chain("fat", 12, new_per_turn=50_000)]
        advice = cua._build_advice([], [], [], chains)
        catalog = cua.advice_rule_catalog(cua.AdviceConfig())
        for item in advice:
            self.assertIn(item["rule"], catalog)
            self.assertIn("ko", item["message_i18n"])
            self.assertEqual(len(item["confidence_refs"]), 1)
            self.assertIn(item["confidence_refs"][0]["kind"], {"measured", "inferred"})

    def test_levels_assigned_and_escalated(self):
        # skill at 2x threshold escalates to critical; a modest one stays warn.
        crit = cua._build_advice([], [], [], [self._chain("big", 20, new_per_turn=90_000)])
        self.assertEqual(crit[0]["level"], "critical")
        warn = cua._build_advice([], [], [], [self._chain("mid", 20, new_per_turn=45_000)])
        self.assertEqual(warn[0]["level"], "warn")

    def test_critical_threshold_is_configurable(self):
        chain = [self._chain("s", 20, new_per_turn=50_000)]
        # default critical floor is 80k → 50k stays warn
        self.assertEqual(cua._build_advice([], [], [], chain)[0]["level"], "warn")
        # lower the absolute critical threshold via config → same item critical
        cfg = cua.AdviceConfig(skill_critical_new_spend_per_turn=45_000)
        self.assertEqual(cua._build_advice([], [], [], chain, cfg)[0]["level"], "critical")

    def test_low_cache_is_info_level(self):
        sessions = [self._session(cache_efficiency=0.2) for _ in range(5)]
        advice = cua._build_advice(sessions, [], [])
        low = next(a for a in advice if a["rule"] == "low-cache-pattern")
        self.assertEqual(low["level"], "info")

    def test_critical_sorts_first_and_survives_cap(self):
        sessions = [self._session(compactions=2)] + [
            self._session(cache_efficiency=0.2) for _ in range(5)
        ]
        dup = [
            {
                "path": f"/f{i}.md",
                "reads": 100,
                "wasted_reads": 90,
                "sessions": 5,
                "max_in_one_context": 9,
            }
            for i in range(4)
        ]
        tools = [
            {
                "name": "Read",
                "calls": 1,
                "errors": 0,
                "result_bytes": 1,
                "max_result_bytes": 500_000,
            }
        ]
        advice = cua._build_advice(sessions, dup, tools)
        self.assertLessEqual(len(advice), 5)
        levels = [cua.LEVEL_ORDER.index(a["level"]) for a in advice]
        self.assertEqual(levels, sorted(levels, reverse=True))  # non-increasing severity
        self.assertEqual(advice[0]["level"], "critical")  # 90 wasted >= 3x20

    def test_catalog_carries_base_level(self):
        catalog = cua.advice_rule_catalog(cua.AdviceConfig())
        self.assertEqual(catalog["low-cache-pattern"]["level"], "info")
        self.assertEqual(catalog["skill-heavy-turns"]["level"], "warn")

    def test_huge_result_carries_tool_target(self):
        tools = [
            {
                "name": "Read",
                "calls": 1,
                "errors": 0,
                "result_bytes": 1,
                "max_result_bytes": 900_000,
            }
        ]
        advice = cua._build_advice([], [], tools)
        self.assertEqual(advice[0]["target"], {"kind": "tool", "name": "Read"})

    def test_total_cap_five(self):
        dup = [
            {
                "path": f"/f{i}.md",
                "reads": 30,
                "wasted_reads": 29,
                "sessions": 5,
                "max_in_one_context": 9,
            }
            for i in range(4)
        ]
        sessions = [self._session(compactions=3)] + [self._session(cache_efficiency=0.2)] * 5
        tools = [
            {
                "name": "Read",
                "calls": 1,
                "errors": 0,
                "result_bytes": 1,
                "max_result_bytes": 900_000,
            }
        ] * 3
        advice = cua._build_advice(sessions, dup, tools)
        self.assertLessEqual(len(advice), 5)


class DigestCacheTest(unittest.TestCase):
    """Extraction digest cache (v0.3①): warm results must be identical to
    raw parsing, staleness must invalidate, corruption must fall back."""

    def _run(self, cache_dir):
        warnings = []
        events = []
        source = cua.resolve_source("claude")
        for sf in cua.iter_session_files(FIXTURES):
            events.extend(cua.load_or_parse_transcript(sf, warnings, cache_dir, source=source))
        result = cua.analyze_events(events)
        summary = cua.build_summary(
            result, warnings, input_root=str(FIXTURES), since=None, project_filter=None
        )
        return summary, warnings

    def test_warm_run_equals_cold_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            cold, cold_warnings = self._run(cache)
            self.assertTrue(list(cache.glob("*.jsonl.gz")))  # digests written
            warm, warm_warnings = self._run(cache)
            cold["meta"].pop("generated_at")
            warm["meta"].pop("generated_at")
            self.assertEqual(cold, warm)
            self.assertEqual(len(cold_warnings), len(warm_warnings))
            self.assertEqual(len(warm_warnings), 1)  # invalid-JSON line preserved

    def test_no_cache_dir_means_raw_parse(self):
        summary, warnings = self._run(None)
        self.assertEqual(summary["totals"]["sessions"], 3)
        self.assertEqual(len(warnings), 1)

    def test_stale_digest_reextracts(self):
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            shutil.copytree(FIXTURES, projects)
            cache = Path(tmp) / "cache"
            target = (
                projects / "-Users-tester-webapp" / "11111111-1111-4111-8111-111111111111.jsonl"
            )

            def run():
                warnings = []
                events = []
                source = cua.resolve_source("claude")
                for sf in cua.iter_session_files(projects):
                    events.extend(cua.load_or_parse_transcript(sf, warnings, cache, source=source))
                return cua.analyze_events(events)

            before = run()
            with open(target, "a") as fh:
                fh.write(
                    '{"type":"assistant","sessionId":"11111111-1111-4111-8111-111111111111",'
                    '"requestId":"req_z","message":{"id":"msg_Z","role":"assistant",'
                    '"model":"claude-opus-4-8","content":[{"type":"text","text":"z"}],'
                    '"usage":{"input_tokens":1,"cache_creation_input_tokens":0,'
                    '"cache_read_input_tokens":0,"output_tokens":1}},'
                    '"uuid":"a-zzz","timestamp":"2026-07-01T02:00:00.000Z"}\n'
                )
            after = run()
            key = "-Users-tester-webapp/11111111-1111-4111-8111-111111111111"
            self.assertEqual(after.sessions[key].requests, before.sessions[key].requests + 1)

    def test_corrupt_digest_falls_back_to_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            self._run(cache)
            for digest in cache.glob("*.jsonl.gz"):
                digest.write_bytes(b"not gzip at all")
            summary, warnings = self._run(cache)
            self.assertEqual(summary["totals"]["sessions"], 3)
            self.assertEqual(len(warnings), 1)

    def test_version_bump_invalidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            self._run(cache)  # writes digests stamped with the current version
            # The cache's validity key reads claudeye.ingest.cache.VERSION;
            # bumping it must invalidate every digest and re-extract cleanly.
            original = claudeye.ingest.cache.VERSION
            try:
                claudeye.ingest.cache.VERSION = "999.0.0"
                summary, _ = self._run(cache)  # must silently re-extract
                self.assertEqual(summary["totals"]["sessions"], 3)
            finally:
                claudeye.ingest.cache.VERSION = original

    def test_digest_preserves_line_agent_id(self):
        # A main-transcript line can carry its own raw agentId; the digest
        # must store and restore it (record.get("ag")) rather than fall back
        # to session_file.agent_id (subagent-file only), or warm != cold.
        from claudeye.ingest.cache import _event_to_record, _record_to_event

        session_file = cua.SessionFile(
            path=Path("x.jsonl"),
            project="-Users-tester-webapp",
            session_id="s1",
            agent_id=None,  # main transcript: no file-level agent_id
        )
        event = cua.Event(
            project="-Users-tester-webapp",
            session_id="s1",
            kind="assistant",
            timestamp=None,
            agent_id="agent-from-line",
        )
        restored = _record_to_event(_event_to_record(event), session_file)
        self.assertEqual(restored.agent_id, "agent-from-line")


class AdviceConfigTest(unittest.TestCase):
    """Personal config overrides advice thresholds; the definition text
    follows the config so they never drift."""

    def test_from_dict_overrides_known_keys_only(self):
        cfg = cua.AdviceConfig.from_dict(
            {"advice": {"skill_new_spend_per_turn": 25_000, "bogus": 1, "max_items": 3}}
        )
        self.assertEqual(cfg.skill_new_spend_per_turn, 25_000)
        self.assertEqual(cfg.max_items, 3)
        self.assertEqual(cfg.dup_wasted_min, cua.AdviceConfig().dup_wasted_min)

    def test_from_dict_accepts_flat_or_nested(self):
        self.assertEqual(cua.AdviceConfig.from_dict({"skill_min_turns": 5}).skill_min_turns, 5)
        self.assertEqual(
            cua.AdviceConfig.from_dict("garbage").skill_min_turns,
            cua.AdviceConfig().skill_min_turns,
        )

    def test_lowered_threshold_fires_more(self):
        chains = [self._chain_row("mid", 20, new_per_turn=25_000)]
        self.assertEqual(cua._build_advice([], [], [], chains), [])  # default 40k floor
        loose = cua.AdviceConfig(skill_new_spend_per_turn=20_000)
        fired = cua._build_advice([], [], [], chains, loose)
        self.assertEqual(fired[0]["rule"], "skill-heavy-turns")

    def test_catalog_text_follows_config(self):
        catalog = cua.advice_rule_catalog(cua.AdviceConfig(skill_new_spend_per_turn=25_000))
        self.assertIn("25k+ new tokens", catalog["skill-heavy-turns"]["definition"])

    def test_config_file_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"advice": {"skill_min_turns": 3}}))
            cfg, source = cua.load_advice_config(str(path))
            self.assertEqual(cfg.skill_min_turns, 3)
            self.assertEqual(source, str(path))

    def test_missing_config_is_defaults_no_source(self):
        cfg, source = cua.load_advice_config("/nonexistent/config.json")
        self.assertEqual(cfg.skill_min_turns, cua.AdviceConfig().skill_min_turns)
        self.assertIsNone(source)

    @staticmethod
    def _chain_row(skill, turns, new_per_turn):
        return {
            "skill": skill,
            "requests": turns,
            "input_tokens": new_per_turn * turns,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "total_tokens": new_per_turn * turns,
            "tool_calls": 0,
            "tool_result_bytes": 0,
            "tools": [],
        }


class SincePresetTest(unittest.TestCase):
    """--today/--one-week/--one-month/--all resolve to midnight-aligned
    local cutoffs (or none), and remain mutually exclusive with --since."""

    NOW = datetime(2026, 7, 2, 15, 30, tzinfo=timezone.utc)

    def _resolve(self, *argv):
        args = cua.build_arg_parser().parse_args(["analyze", *argv])
        return cua._resolve_since(args, now=self.NOW)

    def test_today_cuts_at_local_midnight(self):
        since = self._resolve("--today")
        local_now = self.NOW.astimezone()
        self.assertEqual(since.date(), local_now.date())
        self.assertEqual((since.hour, since.minute, since.second), (0, 0, 0))

    def test_week_and_month_are_midnight_aligned_offsets(self):
        today = self._resolve("--today")
        self.assertEqual(self._resolve("--one-week"), today - timedelta(days=7))
        self.assertEqual(self._resolve("--one-month"), today - timedelta(days=30))

    def test_all_and_default_mean_no_cutoff(self):
        self.assertIsNone(self._resolve("--all"))
        self.assertIsNone(self._resolve())

    def test_since_passes_through(self):
        since = self._resolve("--since", "2026-06-01")
        self.assertEqual(since.date().isoformat(), "2026-06-01")

    def test_period_flags_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cua.build_arg_parser().parse_args(["analyze", "--today", "--one-week"])


class CliTest(unittest.TestCase):
    def test_analyze_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.html"
            json_out = Path(tmp) / "summary.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cua.main(
                    [
                        "analyze",
                        "--input",
                        str(FIXTURES),
                        "--out",
                        str(out),
                        "--json",
                        str(json_out),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())
            summary = json.loads(json_out.read_text())
            self.assertEqual(summary["totals"]["sessions"], 3)
            self.assertIn("analyzed 3 sessions", stdout.getvalue())

    def test_analyze_is_the_default_subcommand(self):
        # `claudeye --input ... --out ...` works without typing "analyze".
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.html"
            with contextlib.redirect_stdout(io.StringIO()):
                code = cua.main(["--input", str(FIXTURES), "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

    def test_version_flag_exits_zero(self):
        out = io.StringIO()
        with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stdout(out):
            cua.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("claudeye", out.getvalue())

    def test_open_flag_invokes_browser(self):
        opened = []
        real = claudeye.cli.webbrowser.open
        claudeye.cli.webbrowser.open = lambda uri: opened.append(uri)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "report.html"
                with contextlib.redirect_stdout(io.StringIO()):
                    cua.main(["--input", str(FIXTURES), "--out", str(out), "--open"])
            self.assertEqual(len(opened), 1)
            self.assertTrue(opened[0].startswith("file://"))
        finally:
            claudeye.cli.webbrowser.open = real

    def test_since_skips_files_older_than_cutoff_by_mtime(self):
        # Fast path: a transcript whose last write predates the cutoff is
        # never parsed (no line inside can be newer than the file mtime).
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp) / "projects"
            shutil.copytree(FIXTURES, projects)
            import os

            ancient = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
            for transcript in (projects / "-Users-tester-api").rglob("*.jsonl"):
                os.utime(transcript, (ancient, ancient))
            out = Path(tmp) / "r.html"
            json_out = Path(tmp) / "s.json"
            with contextlib.redirect_stdout(io.StringIO()):
                code = cua.main(
                    [
                        "analyze",
                        "--input",
                        str(projects),
                        "--since",
                        "2026-01-01",
                        "--out",
                        str(out),
                        "--json",
                        str(json_out),
                    ]
                )
            self.assertEqual(code, 0)
            summary = json.loads(json_out.read_text())
            projects_listed = {row["project"] for row in summary["sessions"]}
            self.assertNotIn("/Users/tester/api", projects_listed)
            self.assertIn("/Users/tester/webapp", projects_listed)

    def test_missing_input_dir_fails_cleanly(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cua.main(["analyze", "--input", "/nonexistent/nope"])
        self.assertEqual(code, 2)
        self.assertIn("not found", stderr.getvalue())


class DataDirTest(unittest.TestCase):
    """--data-dir writes one catable file per facet plus INDEX.md/advice.txt."""

    def _summary(self):
        result, warnings = run_pipeline()
        return make_summary(result, warnings)

    def test_writes_one_json_per_facet_plus_index_and_advice(self):
        summary = self._summary()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "facets"
            written = cua.render_data_dir(summary, out)
            names = {p.name for p in written}
            # every top-level summary key becomes <key>.json
            for key in summary:
                self.assertIn(f"{key}.json", names)
            self.assertIn("advice.txt", names)
            self.assertIn("INDEX.md", names)
            # totals.json round-trips to the same object
            loaded = json.loads((out / "totals.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded, summary["totals"])
            # INDEX.md is last and orients the reader
            self.assertEqual(written[-1].name, "INDEX.md")
            index = (out / "INDEX.md").read_text(encoding="utf-8")
            self.assertIn("## files", index)
            self.assertIn("`totals.json`", index)

    def test_advice_txt_has_no_json_braces(self):
        summary = self._summary()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cua.render_data_dir(summary, out)
            text = (out / "advice.txt").read_text(encoding="utf-8")
            self.assertNotIn("{", text)  # plain lines, not JSON

    def test_cli_data_dir_flag_emits_facets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.html"
            data = Path(tmp) / "data"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = cua.main(
                    [
                        "analyze",
                        "--input",
                        str(FIXTURES),
                        "--out",
                        str(out),
                        "--data-dir",
                        str(data),
                        "--no-cache",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue((data / "INDEX.md").exists())
            self.assertTrue((data / "totals.json").exists())
            self.assertIn("facet files", stdout.getvalue())


class SourceAdapterBackCompatTest(unittest.TestCase):
    """The source-adapter seam must not break the public API surface:
    Event's positional field order and load_or_parse_transcript's legacy
    three-argument call are both re-exported and must stay compatible."""

    def test_event_positional_order_preserves_uuid(self):
        # Event(project, session_id, kind, timestamp, uuid) positionally:
        # source must stay a keyword-defaulted trailing field, never shift uuid.
        event = cua.Event("proj", "sess", "assistant", None, "uuid-x")
        self.assertEqual(event.uuid, "uuid-x")
        self.assertEqual(event.source, "claude")

    def test_load_or_parse_transcript_legacy_three_arg(self):
        # The historical (session_file, warnings, cache_dir) call — no source —
        # must still parse, defaulting to the Claude adapter.
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            for sf in cua.iter_session_files(FIXTURES):
                warnings = []
                legacy = list(cua.load_or_parse_transcript(sf, warnings, cache))
                explicit = list(
                    cua.load_or_parse_transcript(sf, [], None, source=cua.resolve_source("claude"))
                )
                self.assertEqual(len(legacy), len(explicit))

    def test_resolve_source_unknown_raises(self):
        self.assertEqual(cua.resolve_source("claude").name, "claude")
        with self.assertRaises(ValueError):
            cua.resolve_source("nope")


def _codex_events():
    src = cua.resolve_source("codex")
    warnings = []
    events = []
    for sf in src.iter_session_files(CODEX_FIXTURES):
        events.extend(src.parse(sf, warnings))
    return events, warnings


class CodexSourceTest(unittest.TestCase):
    """CodexSource over a synthetic rollout fixture: discovery/dedup, envelope
    parsing, cumulative-token mapping, and forward-compat tolerance."""

    def _summary(self, cache_dir=None):
        src = cua.resolve_source("codex")
        warnings = []
        events = []
        for sf in src.iter_session_files(CODEX_FIXTURES):
            events.extend(cua.load_or_parse_transcript(sf, warnings, cache_dir, source=src))
        summary = cua.build_summary(
            cua.analyze_events(events),
            warnings,
            input_root=str(CODEX_FIXTURES),
            since=None,
            project_filter=None,
        )
        return summary, warnings

    def test_registered(self):
        self.assertEqual(cua.resolve_source("codex").name, "codex")

    def test_detect_finds_codex_root(self):
        src = cua.resolve_source("codex")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertIsNone(src.detect(home))
            (home / ".codex" / "sessions").mkdir(parents=True)
            self.assertEqual(src.detect(home), home / ".codex" / "sessions")

    def test_discovery_dedups_archived(self):
        src = cua.resolve_source("codex")
        files = list(src.iter_session_files(CODEX_FIXTURES))
        # the archived same-stem copy is skipped; the active copy wins
        self.assertEqual(len(files), 1)
        # project is fixed at discovery from the session_meta cwd
        self.assertEqual(files[0].project, "-Users-tester-webapp")

    def test_events_tagged_codex(self):
        events, _ = _codex_events()
        self.assertTrue(events)
        self.assertTrue(all(e.source == "codex" for e in events))

    def test_totals(self):
        summary, warnings = self._summary()
        t = summary["totals"]
        self.assertEqual(t["sessions"], 1)
        self.assertEqual(t["projects"], 1)
        # three counted turns: 120 + 230 + 50; the repeated token_count that
        # re-reports an unchanged cumulative contributes nothing, and the
        # archived duplicate's 1998 is deduped out at discovery
        self.assertEqual(t["requests"], 3)
        self.assertEqual(t["total_tokens"], 400)
        # (100-40) + (200-150) + 50 — the breakdown-less import event's
        # measured total is attributed to plain input
        self.assertEqual(t["input_tokens"], 160)
        self.assertEqual(t["output_tokens"], 35)  # (20-5) + (30-10)
        self.assertEqual(t["cache_read_tokens"], 190)  # 40 + 150
        self.assertEqual(t["cache_creation_tokens"], 0)
        self.assertEqual(t["tool_calls"], 2)  # shell + web_search
        self.assertEqual(t["compactions"], 1)

    def test_reasoning_tokens_mapped(self):
        events, _ = _codex_events()
        reasoning = sum(e.usage.reasoning_tokens for e in events if e.usage)
        self.assertEqual(reasoning, 15)  # 5 + 10, peeled out of output
        # total reconciles: the four split counters plus reasoning == total
        totals = self._summary()[0]["totals"]
        self.assertEqual(
            totals["input_tokens"]
            + totals["output_tokens"]
            + totals["cache_read_tokens"]
            + totals["cache_creation_tokens"]
            + reasoning,
            totals["total_tokens"],
        )

    def test_tool_result_attributed(self):
        tools = {r["name"]: r for r in self._summary()[0]["by_tool"]}
        self.assertIn("shell", tools)
        self.assertIn("web_search", tools)
        self.assertEqual(tools["shell"]["result_bytes"], len(b"file1\nfile2"))

    def test_multi_root_input_root_cleaned_per_root(self):
        # --source auto passes several roots; each must be home-relativized
        # independently (a joined string would leave later roots absolute)
        home = str(Path.home())
        summary = cua.build_summary(
            cua.analyze_events([]),
            [],
            input_root=[home + "/.claude/projects", home + "/.codex/sessions"],
            since=None,
            project_filter=None,
        )
        self.assertEqual(
            summary["meta"]["input_root"],
            "~/.claude/projects, ~/.codex/sessions",
        )

    def test_unknown_records_tolerated(self):
        _, warnings = self._summary()
        # world_state (unknown record) and token_count info:null must not warn;
        # only the deliberately invalid-JSON line does.
        self.assertEqual(len(warnings), 1)
        self.assertIn("invalid JSON", warnings[0].reason)

    def test_warm_cache_preserves_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            cold, _ = self._summary(cache)
            self.assertTrue(list(cache.glob("*.jsonl.gz")))
            warm, _ = self._summary(cache)
            cold["meta"].pop("generated_at")
            warm["meta"].pop("generated_at")
            self.assertEqual(cold, warm)
            # the cwd-derived project must survive the cache round-trip,
            # not collapse to the "codex" placeholder
            self.assertEqual(warm["totals"]["projects"], 1)
            # the row displays the real cwd (not the "codex" placeholder),
            # proving the cwd-derived project survived the cache round-trip
            self.assertEqual(warm["by_project"][0]["project"], "/Users/tester/webapp")


if __name__ == "__main__":
    unittest.main()
