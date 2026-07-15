"""Advice rules: translate summary rows into actionable, levelled hints.

Pure functions over already-cleaned summary rows. Each hint carries a rule
id, a confidence label, a severity level, and the evidence it fired on —
never raw transcript text. Hints about a rankable entity carry a target so
the renderer derives all warning colors from advice, keeping graph and list
in agreement. Thresholds come from the AdviceConfig value object.
"""

from __future__ import annotations

from typing import Any

from claudeye.domain import (
    ADVICE_BASE_LEVEL,
    LEVEL_ORDER,
    WASTE_CACHE_EFF_MAX,
    AdviceConfig,
)


def _advice_level(rule: str, evidence: dict[str, Any], cfg: AdviceConfig) -> str:
    """Return info/warn/critical for one fired item.

    Base level comes from ADVICE_BASE_LEVEL; an item escalates to
    critical when its primary metric is a multiple past the threshold
    (2x, or 3x for the noisier duplicate-read count).
    """
    base = ADVICE_BASE_LEVEL.get(rule, "warn")
    escalated = False
    if rule == "dup-read-hotspot":
        escalated = evidence.get("wasted_reads", 0) >= cfg.dup_critical_wasted
    elif rule == "compaction-pressure":
        escalated = evidence.get("worst_compactions", 0) >= cfg.compactions_critical
    elif rule == "huge-tool-result":
        escalated = evidence.get("max_result_bytes", 0) >= cfg.result_bytes_critical
    elif rule == "skill-heavy-turns":
        escalated = evidence.get("new_tokens_per_turn", 0) >= cfg.skill_critical_new_spend_per_turn
    return "critical" if escalated else base


def advice_rule_catalog(cfg: AdviceConfig) -> dict[str, dict[str, Any]]:
    """Build the human-readable rule catalog from the active thresholds.

    Shown in the report so a reader can see what a rule checks — and why
    something did NOT fire, e.g. a skill with a huge per-turn cost but
    too few turns to clear the floor. Text is derived from cfg, so it can
    never drift from the firing logic.
    """
    return {
        "dup-read-hotspot": {
            "level": ADVICE_BASE_LEVEL["dup-read-hotspot"],
            "title": "Duplicate-read hotspot",
            "definition": (
                f"A file re-read with {cfg.dup_wasted_min}+ wasted reads spread over "
                f"{cfg.dup_sessions_min}+ sessions. Summarize it into CLAUDE.md or a "
                f"skill so it need not be re-read every time. Critical at "
                f"{cfg.dup_critical_wasted}+ wasted."
            ),
            "title_i18n": {"ko": "중복 읽기 집중 지점"},
            "definition_i18n": {
                "ko": (
                    f"{cfg.dup_sessions_min}개 이상 세션에서 같은 파일의 불필요한 재읽기가 "
                    f"{cfg.dup_wasted_min}회 이상 발생합니다. CLAUDE.md나 스킬로 요약하여 "
                    f"반복 읽기를 줄일 수 있습니다. {cfg.dup_critical_wasted}회 이상이면 "
                    "critical입니다."
                )
            },
        },
        "compaction-pressure": {
            "level": ADVICE_BASE_LEVEL["compaction-pressure"],
            "title": "Compaction pressure",
            "definition": (
                f"A session that auto-compacted {cfg.compactions_min}+ times — its "
                "context filled up more than once. Split the work or preserve task "
                f"state earlier. Critical at {cfg.compactions_critical}+."
            ),
            "title_i18n": {"ko": "Compaction 압력"},
            "definition_i18n": {
                "ko": (
                    f"한 세션에서 compaction이 {cfg.compactions_min}회 이상 발생했습니다. "
                    "작업을 나누거나 상태를 더 일찍 보존하는 방안을 검토합니다. "
                    f"{cfg.compactions_critical}회 이상이면 critical입니다."
                )
            },
        },
        "low-cache-pattern": {
            "level": ADVICE_BASE_LEVEL["low-cache-pattern"],
            "title": "Low cache efficiency",
            "definition": (
                f"More than {int(cfg.low_cache_share * 100)}% of rated sessions ran "
                f"below {int(WASTE_CACHE_EFF_MAX * 100)}% cache efficiency, with at "
                f"least {cfg.low_cache_min_sessions} rated sessions. Long resume gaps "
                "defeat the 5-minute prompt cache."
            ),
            "title_i18n": {"ko": "낮은 cache 효율"},
            "definition_i18n": {
                "ko": (
                    f"측정 가능한 세션이 {cfg.low_cache_min_sessions}개 이상일 때, 그중 "
                    f"{int(cfg.low_cache_share * 100)}%보다 많은 세션의 cache 효율이 "
                    f"{int(WASTE_CACHE_EFF_MAX * 100)}% 미만입니다. 긴 재개 간격은 "
                    "5분 prompt cache를 활용하지 못하게 할 수 있습니다."
                )
            },
        },
        "huge-tool-result": {
            "level": ADVICE_BASE_LEVEL["huge-tool-result"],
            "title": "Huge tool result",
            "definition": (
                f"A single tool result of {cfg.result_bytes_min // 1024} KB+ re-entered "
                "the context in one shot. Prefer offset/limit reads, head/tail, or "
                f"narrower queries. Critical at {cfg.result_bytes_critical // 1024} KB+."
            ),
            "title_i18n": {"ko": "큰 도구 결과"},
            "definition_i18n": {
                "ko": (
                    f"한 번의 도구 결과 {cfg.result_bytes_min // 1024}KB 이상이 모델 "
                    "컨텍스트로 들어왔습니다. offset/limit, head/tail 또는 더 좁은 질의를 "
                    f"검토합니다. {cfg.result_bytes_critical // 1024}KB 이상이면 critical입니다."
                )
            },
        },
        "skill-heavy-turns": {
            "level": ADVICE_BASE_LEVEL["skill-heavy-turns"],
            "title": "Skill-heavy turns",
            "definition": (
                f"A skill averaging {cfg.skill_new_spend_per_turn // 1000}k+ new tokens "
                f"per turn (or {cfg.skill_result_bytes_per_turn // 1024} KB+ tool "
                f"results, or {cfg.skill_fanout_per_turn}+ tool calls per turn), "
                f"measured over at least {cfg.skill_min_turns} turns so a tiny sample "
                "cannot trip it. Consider splitting the skill or trimming its "
                f"instructions. Critical at {cfg.skill_critical_new_spend_per_turn // 1000}k+ "
                "new tokens/turn."
            ),
            "title_i18n": {"ko": "스킬 turn의 큰 귀속 사용량"},
            "definition_i18n": {
                "ko": (
                    f"최소 {cfg.skill_min_turns}개 turn에서 스킬의 turn당 귀속 사용량이 "
                    f"{cfg.skill_new_spend_per_turn // 1000}k tokens 이상이거나, 도구 결과가 "
                    f"{cfg.skill_result_bytes_per_turn // 1024}KB 이상이거나, 도구 호출이 "
                    f"{cfg.skill_fanout_per_turn}회 이상입니다. 스킬 분리나 지침 축소를 "
                    f"검토합니다. {cfg.skill_critical_new_spend_per_turn // 1000}k tokens/turn "
                    "이상이면 critical입니다."
                )
            },
        },
    }


def _build_advice(
    sessions: list[dict[str, Any]],
    dup_reads: list[dict[str, Any]],
    by_tool: list[dict[str, Any]],
    by_skill_chain: list[dict[str, Any]] | None = None,
    cfg: AdviceConfig | None = None,
) -> list[dict[str, Any]]:
    """Translate summary rows into at most five actionable hints.

    Pure function over already-cleaned summary rows (paths arrive
    redacted when redaction is on). Each hint carries the rule id, a
    confidence label consistent with CONFIDENCE_NOTES, and the evidence
    numbers it fired on — never raw transcript text. Hints about a
    rankable entity also carry a target (kind + name); the renderer
    derives all warning colors from targets, so the graphs and this
    list can never disagree. Rules fire in priority order and the list
    is truncated to cfg.max_items.
    """
    cfg = cfg or AdviceConfig()
    advice: list[dict[str, Any]] = []

    for row in dup_reads:
        if row["wasted_reads"] >= cfg.dup_wasted_min and row["sessions"] >= cfg.dup_sessions_min:
            advice.append(
                {
                    "rule": "dup-read-hotspot",
                    "confidence": "inferred",
                    "confidence_refs": [{"metric": "dup_reads", "kind": "inferred"}],
                    "message": (
                        f"{row['path']} was re-read {row['reads']}x across "
                        f"{row['sessions']} sessions — consider summarizing it into "
                        "CLAUDE.md or a skill"
                    ),
                    "evidence": {
                        "path": row["path"],
                        "reads": row["reads"],
                        "wasted_reads": row["wasted_reads"],
                        "sessions": row["sessions"],
                    },
                }
            )
        if len(advice) >= 2:
            break

    compacted = [s for s in sessions if s["compactions"] >= cfg.compactions_min]
    if compacted:
        worst = max(compacted, key=lambda s: s["compactions"])
        advice.append(
            {
                "rule": "compaction-pressure",
                "confidence": "measured",
                "confidence_refs": [{"metric": "compactions", "kind": "measured"}],
                "message": (
                    f"{len(compacted)} session(s) compacted "
                    f"{cfg.compactions_min}+ times (worst: "
                    f"{worst['session_id'][:8]} x{worst['compactions']}) — split the "
                    "work or preserve task state earlier"
                ),
                "evidence": {
                    "sessions": len(compacted),
                    "worst_session": worst["session_id"][:8],
                    "worst_compactions": worst["compactions"],
                },
            }
        )

    flagged_skills = []
    for row in by_skill_chain or []:
        turns = row["requests"]
        if turns < cfg.skill_min_turns:
            continue
        new_spend = (
            row["input_tokens"] + row["output_tokens"] + row["cache_creation_tokens"]
        ) / turns
        bytes_per_turn = row["tool_result_bytes"] / turns
        fanout = row["tool_calls"] / turns
        signals = []
        if new_spend >= cfg.skill_new_spend_per_turn:
            signals.append(f"{round(new_spend / 1000)}k new tokens/turn")
        if bytes_per_turn >= cfg.skill_result_bytes_per_turn:
            signals.append(f"{round(bytes_per_turn / 1024)} KB tool results/turn")
        if fanout >= cfg.skill_fanout_per_turn:
            signals.append(f"{round(fanout, 1)} tool calls/turn")
        if signals:
            flagged_skills.append((new_spend, row, signals))
    flagged_skills.sort(key=lambda item: item[0], reverse=True)
    for new_spend, row, signals in flagged_skills[:2]:
        advice.append(
            {
                "rule": "skill-heavy-turns",
                "confidence": "measured",
                "confidence_refs": [{"metric": "skill_chains", "kind": "measured"}],
                "message": (
                    f"skill {row['skill']} averages {' · '.join(signals)} over "
                    f"{row['requests']} turns — consider splitting the skill or "
                    "trimming its instructions"
                ),
                "target": {"kind": "skill", "name": row["skill"]},
                "evidence": {
                    "turns": row["requests"],
                    "new_tokens_per_turn": round(new_spend),
                    "signals": signals,
                },
            }
        )

    rated = [s for s in sessions if s["cache_efficiency"] is not None]
    low = [s for s in rated if s["cache_efficiency"] < WASTE_CACHE_EFF_MAX]
    if (
        len(low) >= cfg.low_cache_min_sessions
        and rated
        and len(low) / len(rated) > cfg.low_cache_share
    ):
        advice.append(
            {
                "rule": "low-cache-pattern",
                "confidence": "measured",
                "confidence_refs": [{"metric": "cache_efficiency", "kind": "measured"}],
                "message": (
                    f"{round(100 * len(low) / len(rated))}% of sessions "
                    f"({len(low)}/{len(rated)}) ran below "
                    f"{int(WASTE_CACHE_EFF_MAX * 100)}% cache efficiency — long resume "
                    "gaps defeat the 5-minute prompt cache"
                ),
                "evidence": {"low_sessions": len(low), "rated_sessions": len(rated)},
            }
        )

    offenders = [row for row in by_tool if row["max_result_bytes"] >= cfg.result_bytes_min]
    offenders.sort(key=lambda row: row["max_result_bytes"], reverse=True)
    for row in offenders[:2]:
        advice.append(
            {
                "rule": "huge-tool-result",
                "confidence": "measured",
                "confidence_refs": [{"metric": "tool_result_bytes", "kind": "measured"}],
                "message": (
                    f"a single {row['name']} result of "
                    f"{row['max_result_bytes'] // 1024} KB re-entered the context — "
                    "prefer offset/limit reads, head/tail, or narrower queries"
                ),
                "target": {"kind": "tool", "name": row["name"]},
                "evidence": {
                    "tool": row["name"],
                    "max_result_bytes": row["max_result_bytes"],
                },
            }
        )

    for item in advice:
        item["level"] = _advice_level(item["rule"], item.get("evidence", {}), cfg)
        _attach_korean_copy(item, cfg)
    # Most severe first (stable within a level preserves rule priority),
    # so the cap keeps critical items over merely-notable ones.
    advice.sort(key=lambda it: LEVEL_ORDER.index(it["level"]), reverse=True)
    return advice[: cfg.max_items]


def _attach_korean_copy(item: dict[str, Any], cfg: AdviceConfig) -> None:
    """Attach Korean presentation copy without changing rule semantics."""
    evidence = item.get("evidence", {})
    rule = item["rule"]
    if rule == "dup-read-hotspot":
        message = (
            f"{evidence['path']}을 {evidence['sessions']}개 세션에서 "
            f"{evidence['reads']}회 읽었습니다. CLAUDE.md나 스킬로 요약하는 방안을 "
            "검토하세요."
        )
    elif rule == "compaction-pressure":
        message = (
            f"{evidence['sessions']}개 세션에서 compaction이 {cfg.compactions_min}회 이상 "
            f"발생했습니다. 최다는 {evidence['worst_session']} 세션의 "
            f"{evidence['worst_compactions']}회입니다. 작업 분리나 조기 상태 보존을 "
            "검토하세요."
        )
    elif rule == "skill-heavy-turns":
        signals = (
            " · ".join(evidence.get("signals", []))
            .replace("new tokens/turn", "귀속 사용 tokens/turn")
            .replace("tool results/turn", "도구 결과/turn")
            .replace("tool calls/turn", "도구 호출/turn")
        )
        message = (
            f"스킬 {item['target']['name']}에서 {evidence['turns']}개 turn 동안 평균 "
            f"{signals}가 관측됐습니다. 스킬 분리나 지침 축소를 검토하세요."
        )
    elif rule == "low-cache-pattern":
        share = round(100 * evidence["low_sessions"] / evidence["rated_sessions"])
        message = (
            f"전체 대비 {share}%의 세션({evidence['low_sessions']}/"
            f"{evidence['rated_sessions']})에서 cache 효율이 "
            f"{int(WASTE_CACHE_EFF_MAX * 100)}% 미만입니다. 긴 재개 간격이 5분 "
            "prompt cache를 벗어났을 수 있습니다."
        )
    else:
        message = (
            f"{evidence['tool']}의 단일 결과 {evidence['max_result_bytes'] // 1024}KB가 "
            "모델 컨텍스트로 들어왔습니다. offset/limit, head/tail 또는 더 좁은 "
            "질의를 검토하세요."
        )
    item["message_i18n"] = {"ko": message}
