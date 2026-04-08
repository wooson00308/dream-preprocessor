# claude-heartbeat

_세션 사이에서도 Claude를 살려두세요._

**[English](../README.md)**

---

Claude Code는 반응형입니다. 대화할 때만 작동합니다.
Heartbeat는 이를 능동형으로 바꿔줍니다.

주기적으로 Claude를 깨워 스킬을 실행하고 다시 잠드는 경량 데몬입니다. 할 일이 없으면 토큰 비용이 발생하지 않습니다.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  HEARTBEAT  │     │   condition  │     │  claude -p  │
│  .md        │────►│   check      │────►│  "{prompt}" │
│ (job config)│     │  (shell cmd) │     │  (skill run)│
└─────────────┘     └──────────────┘     └─────────────┘
                      할 일 없으면          필요할 때만
                      스킵 (비용 0)         깨움
```

---

## 동작 방식

1. Heartbeat 데몬이 백그라운드에서 실행됩니다 (launchd 기반)
2. 60초마다 등록된 잡을 확인합니다
3. interval이 경과한 잡에 대해 condition을 체크합니다
4. condition을 통과하면 `claude -p "{prompt}"`로 Claude를 깨웁니다
5. Claude가 스킬을 실행하고 다시 잠듭니다

데몬 자체는 LLM을 호출하지 않습니다. 언제 깨울지만 판단합니다.

## 무엇을 실행할 수 있나요?

`prompt` 필드에는 무엇이든 넣을 수 있습니다. 평문 한 줄, 스킬 명령어, 문서 참조 등 형식에 제한이 없습니다. Heartbeat는 그 내용을 그대로 `claude -p`에 전달합니다.

### 평문 프롬프트

```markdown
## daily-summary
- slug: -Users-yourname-Git-myproject
- prompt: 지난 24시간 git log 확인하고 변경사항 요약해줘
- interval: 1d
- timeout: 5m

## lint-check
- slug: -Users-yourname-Git-myproject
- prompt: npm run lint 돌려보고 에러 있으면 정리해줘
- interval: 6h
- timeout: 3m
```

### 스킬

Claude Code는 [사용자 정의 스킬](https://docs.anthropic.com/en/docs/claude-code)을 지원합니다. 재사용 가능한 프롬프트를 만들어 Claude가 필요할 때 실행할 수 있는 프로토콜입니다. 더 복잡하거나 여러 단계가 필요한 작업은 스킬로 작성하여 prompt 필드에서 참조할 수 있습니다.

`dream` 스킬은 이 조합의 예시로 포함되어 있습니다.

```bash
heartbeat skills              # 사용 가능한 스킬 목록
heartbeat install dream       # 스킬 설치
```

### dream (예시 스킬)

세션 transcript를 자동으로 정제하여 장기 기억에 반영합니다. Claude Code는 매 대화를 JSONL로 저장하지만 다음 세션에서 다시 읽지 않습니다. dream 스킬이 이 transcript를 처리하여, 다음 세션이 시작될 때 이전 맥락을 이미 알고 있는 상태로 만들어줍니다.

자세한 내용은 [skills/dream/README.md](../skills/dream/README.md)를 참고하세요.

---

## 요구사항

- macOS (launchd 기반 자동화)
- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)

## 빠른 시작

```bash
pip install claude-heartbeat

# dream 스킬 설치 (SKILL.md 복사 + heartbeat 잡 자동 등록)
heartbeat install dream

# 확인
heartbeat jobs

# 테스트 실행
heartbeat once

# 데몬 시작
heartbeat start
```

launchd 등록 등 상세 설정은 [설정 가이드](setup.md)를 참고하세요.

## 설정

`~/.claude/HEARTBEAT.md`에 잡을 등록합니다:

```markdown
# HEARTBEAT

- tick: 60s

## daily-summary
- slug: -Users-yourname-Git-myproject
- prompt: 지난 24시간 git log 확인하고 변경사항 요약해줘
- interval: 1d
- timeout: 5m
- notify: failure

## lint-check
- slug: -Users-yourname-Git-myproject
- prompt: npm run lint 돌려보고 에러 있으면 정리해줘
- interval: 6h
- timeout: 3m
- condition: test -f package.json
- notify: failure
```

| 필드 | 설명 | 기본값 |
|------|------|--------|
| slug | 프로젝트 슬러그 (`~/.claude/projects/` 하위 디렉토리명) | 필수 |
| prompt | claude -p에 전달할 프롬프트 | 필수 |
| interval | 실행 간격 (s/m/h/d) | 1h |
| timeout | 타임아웃 (s/m/h/d) | 600s |
| condition | 실행 전 체크 (exit 0이면 실행) | 없음 |
| notify | macOS 알림 수준: `all`, `failure`, `none` | all |

## CLI

```bash
heartbeat start           # 데몬 시작 (백그라운드)
heartbeat start -f        # 포그라운드 실행
heartbeat stop            # 데몬 중지
heartbeat status          # 상태 + 잡별 이력 + 최근 로그
heartbeat jobs            # 등록된 잡 목록
heartbeat once            # 모든 잡 1회 실행
heartbeat once -j "name"  # 특정 잡 1회 실행
heartbeat skills          # 사용 가능한 스킬 목록
heartbeat install <name>  # 스킬 설치
```

## v0.1에서 마이그레이션

`dream-preprocessor` v0.1에서 업그레이드하는 경우:

- `dream-heartbeat`은 `heartbeat`의 별칭으로 계속 동작합니다
- `dream-prep`도 기존과 동일하게 동작합니다
- `HEARTBEAT.md`나 launchd plist를 수정할 필요가 없습니다

## 라이선스

MIT

---

_under the moonlight, Claude dreams._
