# /dream 자동 정제 시스템 구축 기록

날짜: 2026-04-08

## 배경

클로드 코드가 매 세션마다 transcript JSONL을 자동 저장하지만, 이 데이터는 raw 상태로만 쌓임.
KAIROS(유출된 미공개 기능)의 /dream처럼 transcript를 주기적으로 정제하여 메모리에 반영하는 시스템을 구현.

## 진행 과정

### 1차 시도: MCP 서버 + Stop 훅 (폐기)

- session-logger MCP 서버 (Python, 3개 도구) + CLI
- Stop 훅으로 매 응답마다 chat 자동 기록
- 가드레일 스킬 (alwaysApply) + 정제 스킬

문제점:
- 클로드가 이미 transcript JSONL로 전체 대화를 저장하고 있음 → 이중 기록
- 매 응답마다 훅 발동 → 노이즈 도배
- goal/decision/change 등 수동 기록 → 문샤인과 역할 겹침

### 2차 시도: transcript 기반 정제만 (채택)

핵심 깨달음: 별도 기록 불필요. 기존 transcript를 정제하면 됨.

## 최종 아키텍처

```
[클로드 대화] → transcript JSONL 자동 저장 (클로드 자체 기능)
       ↓
[heartbeat 데몬] 3시간마다 체크
       ↓
[dream-prep] 파이썬 전처리 (JSONL → 경량 마크다운)
       ↓
[claude -p "/dream"] LLM이 깨어나서 /dream 스킬 실행
       ↓
[메모리 갱신] topic 파일 생성/수정 + MEMORY.md 인덱스 업데이트
```

## 구성요소

### 1. /dream 스킬
- 경로: `~/.claude/skills/dream/SKILL.md`
- KAIROS autoDream 4단계: Orient → Gather → Consolidate → Prune & Index
- Phase 2에서 dream-prep CLI 호출 (LLM이 직접 JSONL 안 읽음)

### 2. dream-prep CLI (파이썬 전처리)
- 경로: `~/Git/mcp-session-logger/src/dream_preprocessor/preprocess.py`
- JSONL에서 유저 텍스트 + 어시스턴트 텍스트만 추출
- 코드 블록 압축 (3줄 이하 유지, 4줄 이상 첫 줄 + 생략)
- 연속 도구 호출 합치기 (`[도구: Bash, Read x2]`)
- 시스템 메시지 제거
- 명령어: `dream-prep list`, `dream-prep prep --slug="..." -n 5`, `dream-prep status --slug="..."`

### 3. heartbeat 데몬
- 경로: `~/Git/mcp-session-logger/src/dream_preprocessor/heartbeat.py`
- `~/.claude/HEARTBEAT.md` 파싱하여 잡 실행
- 잡별로 interval, timeout, condition 설정 가능
- condition: 쉘 커맨드로 실행 여부 판단 (비용 절약)
- 명령어: `dream-heartbeat start`, `stop`, `status`, `jobs`, `once`

### 4. HEARTBEAT.md
- 경로: `~/.claude/HEARTBEAT.md`
- 잡 목록을 마크다운으로 관리
- 코드 수정 없이 잡 추가/변경 가능

### 5. launchd 등록
- 경로: `~/Library/LaunchAgents/com.dream-heartbeat.plist`
- 부팅 시 자동 시작 (RunAtLoad + KeepAlive)

## 역할 분리

| 시스템 | 역할 |
|--------|------|
| 클로드 transcript | 대화 원본 (Layer 3) |
| /dream | transcript → 메모리 정제 (Layer 3 → 2) |
| 클로드 메모리 | 정제된 지식 (Layer 2, topic 파일) |
| MEMORY.md | 인덱스 (Layer 1, 항상 로드) |
| 문샤인 | 인사이트/시행착오 (별도 지식 저장소) |

## 폐기된 것

- mcp-session-logger MCP 서버 (pip uninstall, settings.json에서 제거)
- session-logger 스킬, session-summarizer 스킬 (삭제)
- Stop 훅 (settings.json에서 제거)
- session-logs 디렉토리 (삭제)

## heartbeat 동작 원리

```
[macOS 부팅]
     ↓
[launchd] com.dream-heartbeat 자동 실행 (KeepAlive)
     ↓
[dream-heartbeat] 데몬 프로세스 상주
     ↓  ← 60초마다 깨어남 (sleep/wake 대응)
[매 주기(3h)] HEARTBEAT.md 파싱 → 잡 목록 확인
     ↓
[잡별로]
  1. condition 체크 (쉘 커맨드)
     → dream-prep status로 미처리 transcript 있는지 확인
     → 없으면 스킵 (토큰 비용 0)
  2. 미처리 있으면 claude -p "/dream" 실행
     → 새 claude 인스턴스가 뜸
     → /dream 스킬 로드
     → dream-prep prep 호출 (전처리)
     → 전처리 결과 읽고 메모리 갱신
     → 종료
  3. 다음 잡으로
     ↓
[대기] 다음 주기까지 sleep
```

핵심 포인트:
- 데몬 자체는 LLM 호출 안 함 → 상주해도 비용 0
- condition으로 "할 일 있나?" 먼저 체크 → 없으면 claude 안 깨움
- claude -p는 비대화형 → 스킬 프롬프트가 자기완결적이어야 함
- 60초 단위 sleep → macOS sleep/wake 후에도 타이머 정상 작동
- launchd KeepAlive → 프로세스 죽어도 자동 재시작

## 참고

- KAIROS /dream 4단계: Orient → Gather → Consolidate → Prune & Index
- KAIROS 3계층 메모리: MEMORY.md(L1) → topic 파일(L2) → transcript(L3)
- OpenClaw heartbeat: Node.js setTimeout 기반 주기적 에이전트 턴 실행
- Claude Code 소스 유출 사건 (2026-03-31): 44개 피처 플래그 발견, KAIROS/BUDDY 등
