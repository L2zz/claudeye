# claudeye

[English](README.md) · **한국어**

claudeye로 Claude Code를 깊이 들여다보세요! Claude Code와 Codex의 세션 기록을
읽어 컨텍스트가 어디서 낭비되는지 한 장의 리포트로 보여줍니다. 정적 스크립트로
로컬에서만 동작하며, 개인 데이터를 외부로 내보내지 않습니다.

claudeye는 자기개선 하네스에 필요한 측정 계층입니다. 세션 기록을 에이전트가
읽을 수 있는 측정값으로 바꿔 회고와 개선의 근거를 제공합니다.

**목차**

1. [배경](#1-배경)
2. [설치](#2-설치)
3. [빠른 시작](#3-빠른-시작)
4. [리포트](#4-리포트)
5. [에이전트용 facet 파일 (`--data-dir`)](#5-에이전트용-facet-파일---data-dir)
6. [개인 설정](#6-개인-설정)
7. [Metric](#7-metric)
8. [문서](#8-문서)
9. [개발 · 기여](#9-개발--기여)
10. [라이선스](#10-라이선스)

## 1. 배경

claudeye는 Claude Code 하네스를 관찰하고, 그 관찰을 하네스 개선의 데이터 원천으로
활용하기 위해 시작되었습니다.

### 하네스 모니터링

세션·스킬·서브에이전트가 쌓이면 어디서 토큰이 새는지, 어떤 파일을 반복해 읽는지,
어떤 스킬이 무거운지 감을 잡기 어렵습니다. claudeye는 무엇이 컨텍스트를 오염시키는지
한 장으로 보여줍니다.

### 자기개선 루프의 측정 계층

자기개선 하네스는 측정 → 회고 → 수정의 반복으로 발전합니다. claudeye는 이 중
측정을 담당합니다. 회고 루틴은 `--data-dir` facet을 읽고, 수정 결과는
스킬·룰·CLAUDE.md에 반영됩니다.

대화에서 사용자가 교정한 내용을 기록하는 도구가 정성적 근거를 제공한다면,
claudeye는 세션 기록에서 측정한 정량적 근거를 제공합니다.

예를 들어 주간 회고 스킬이 `--data-dir` 산출물을 읽어 반복되는 낭비를 룰·스킬 개선안으로
정리합니다:

```md
---
name: weekly-harness-evolve
description: 지난 주 claudeye 산출물을 읽고 하네스 개선점을 제안한다
---

1. `claudeye --one-week --data-dir /tmp/claudeye` 로 지난 주를 분석한다.
2. `cat /tmp/claudeye/advice.txt` 로 낭비 조언을 읽는다.
3. 반복되는 낭비 패턴을 CLAUDE.md·스킬 규칙 개선안으로 제안한다.
```

> 자세한 배경은 [docs/concept.md](docs/concept.md)를 참고하세요.

## 2. 설치

- 유일 의존성: Python 3.9+

claudeye는 3가지 설치 방법을 제공합니다.

### Homebrew

```bash
brew install L2zz/tap/claudeye
```

### curl 설치 스크립트 (uv / pipx / pip 중 있는 것으로)

```bash
curl -fsSL https://raw.githubusercontent.com/L2zz/claudeye/main/install.sh | bash
```

### uv / pipx / pip 직접

```bash
uv tool install git+https://github.com/L2zz/claudeye
# 또는
pipx install git+https://github.com/L2zz/claudeye
# 또는
pip install git+https://github.com/L2zz/claudeye
```

## 3. 빠른 시작

`claudeye` 는 누적 사용 기록(기본값: 전체)를 분석해 현재 폴더에 `report.html` 을 만듭니다. 
기간·출력은 옵션으로 제어가능합니다:

```bash
claudeye                          # 전체 기간 → report.html
claudeye --today --open           # 오늘자 리포트를 만들어 바로 열기
claudeye --one-week --project myproject  # 최근 7일, 특정 프로젝트만
claudeye --json summary.json      # 요약 JSON도 함께
claudeye --data-dir facets/       # 에이전트용 facet 파일도 함께
```

| 옵션 | 의미 |
|---|---|
| `--source` | 분석할 에이전트: `claude` · `codex` · `auto`(루트가 있는 모든 에이전트); 기본 `claude` |
| `--input` | 스캔할 세션 루트 (기본: 소스별 루트 — `~/.claude/projects` 또는 `~/.codex/sessions`); `--source auto` 와는 무시됨 |
| `--out` | HTML 리포트 경로 (기본 `report.html`) |
| `--open` | 완료 후 리포트를 브라우저로 열기 |
| `--json PATH` | 요약 JSON 아티팩트 추가 출력 |
| `--data-dir DIR` | facet별 파일 추가 출력 (`INDEX.md`·`<facet>.json`·`advice.txt`) — 에이전트가 `cat` 하기 좋게 |
| `--today` / `--one-week` / `--one-month` / `--all` | 기간 프리셋 (로컬 자정 정렬) |
| `--since ISO` | 이 로컬 날짜/시각 이후만 (프리셋과 배타) |
| `--project SUBSTR` | 프로젝트 디렉터리명 부분 일치 필터 |
| `--redact-paths` | 디렉터리를 해시로 치환 (공유용) |
| `--no-cache` | 추출 digest 캐시 우회 |
| `--config PATH` / `--no-config` | advice 임계 오버라이드 / 기본 config 무시 |

첫 실행은 코퍼스 크기에 따라 십수 초 걸릴 수 있지만, 파일 캐시가 붙어 이후 실행은
빠릅니다. 바뀐 파일만 다시 읽습니다.

## 4. 리포트

리포트는 요약 카드 + Advice + 진단 섹션으로 구성됩니다.

### 상단 카드

- `규모` — 전체 토큰, 캐시 제외 토큰, cache 재사용, 도구 활동, 최다 사용일, 모델 구성.
- `낭비 신호` — 도구 결과 크기, 낭비 신호, 파싱 경고. 값이 있으면 경고색이 되고,
  클릭하면 해당 섹션으로 이동합니다.

### Advice

낭비로 추정되는 데이터를 근거로 조언을 제시하는 섹션입니다.

- 각 항목에 레벨(info / warn / critical)과 룰 정의가 붙고, 임계의 배수를 넘으면 critical로 승격합니다.
- 조언이 지목한 스킬·도구는 그래프에서도 경고색으로 표시돼 목록과 그래프가 일치합니다.
- per-rule 토글, min-level 필터, 룰 카탈로그, what-if 임계 탐색을 제공합니다.

### 진단 섹션

각각 한 가지 낭비 축을 확인합니다.

- `모델별 일별 토큰` — 날짜별 토큰. 진한색은 캐시 제외 토큰, 흐린색은 cache 재사용.
- `도구 결과 크기` — 모델에 반환된 결과 payload의 도구별 크기.
- `Skill & subagent chains` — 스킬·서브에이전트별 토큰. 행을 누르면 도구 구성.
- `Duplicate reads` — 여러 세션에서 반복해 읽은 파일.
- `Projects` — 프로젝트별 롤업(실제 작업 경로 cwd로 표기).
- `Sessions` — 세션별 통계(정렬 가능, cache 효율·낭비 플래그).

리포트에는 요약 숫자만 들어갑니다 — 프롬프트·도구 출력·파일 내용은 담기지 않습니다.

## 5. 에이전트용 facet 파일 (`--data-dir`)

HTML 리포트가 사람용이라면, `--data-dir DIR`은 같은 데이터를 에이전트가 쓰기 좋은
파일로도 내놓습니다. summary의 facet마다 파일 하나로 떨어지므로, 루틴이 전체를
파싱하지 않고 필요한 조각만 `cat` 할 수 있습니다.

- `INDEX.md` — 각 파일이 뭘 담는지 + 헤드라인 수치.
- `<facet>.json` — summary 키별 파일 (`totals`·`by_project`·`sessions`·`advice` …).
- `advice.txt` — 조언을 JSON 파싱 없이 읽는 평문.

## 6. 개인 설정

튜닝한 advice 임계를 영속화하려면 JSON config로 저장합니다.
리포트의 what-if copy 버튼이 이 스니펫을 만들어 줍니다:

```jsonc
// ~/.config/claudeye/config.json
{ "advice": { "skill_min_turns": 3, "skill_new_spend_per_turn": 30000 } }
```

> 명시한 키만 오버라이드하고 오타는 기본값으로 떨어집니다. `AdviceConfig`의 모든
> 필드를 이렇게 조정할 수 있고, 룰 정의·리포트가 config를 따라가 어긋나지 않습니다.

## 7. Metric

각 지표는 세가지 신뢰도로 구분됩니다.

- `measured` — 토큰(라인 uuid + message id로 중복 제거), 도구 호출, 결과 크기, cache 효율, 서브에이전트 타입 귀속.
- `inferred` — 중복 read, fork 귀속, advice 처방.
- `approximate` — 도구별 토큰 귀속은 설계상 하지 않습니다(usage는 API 응답 단위).

## 8. 문서

- [concept](docs/concept.md) — 동기와 스코프.
- [architecture](docs/architecture.md) — 레이어드 설계.

## 9. 개발 · 기여

런타임은 무의존이고, dev 툴은 [uv](https://docs.astral.sh/uv/)로 관리합니다.

```bash
make sync     # dev 툴 설치 (ruff · mypy · pytest)
make check    # CI 게이트: lint + mypy + test
make report   # report.html 생성 후 열기
```

기여 방법·프로젝트 원칙은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

## 10. 라이선스

[MIT](LICENSE).
