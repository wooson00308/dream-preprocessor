# dream-preprocessor

_잠을 자야 기억이 남는다._

**[English](../README.md)**

---

```
  Transcript        dream-prep         /dream             Memory
  (raw JSONL)       (preprocess)       (consolidate)      (topic files)

  Session 1 ─┐
  Session 2 ─┤
  Session 3 ─┼─────► Markdown ─────► ┌─ Orient ─────────►  MEMORY.md
  Session 4 ─┤       (compact)       │  Gather             user.md
  Session 5 ─┘                       │  Consolidate        feedback.md
                                     └─ Prune              project.md

      L3                                L2                     L1
  (raw logs)                        (knowledge)              (index)
```

---

## 문제

Claude Code는 대화할 때마다 모든 내용을 transcript JSONL로 저장한다.
파일은 쌓인다. 아무도 안 읽는다.

새 세션이 시작되면 Claude는 백지 상태다.
어제 4시간 동안 같이 디버깅한 내용도, 지난주에 내린 아키텍처 결정도 모른다.

Claude Code가 세션 간에 기억하는 건 딱 두 가지뿐이다:

| 저장소 | 자동 로드 | 한계 |
|--------|-----------|------|
| CLAUDE.md | 전체 | 사용자가 직접 작성/관리해야 함 |
| MEMORY.md | 처음 200줄만 | topic 파일은 수동으로 열어야 읽힘 |

transcript에는 모든 맥락이 들어있다.
메모리 시스템은 이미 존재한다.
둘 사이를 연결하는 것만 없다.

## 해결

사람은 낮에 경험하고, 밤에 잠을 자면서 기억을 정리한다.
해마가 하루치 경험을 훑으며 쓸 만한 건 장기기억으로 보내고, 나머지는 버린다.

dream은 Claude에게 같은 일을 시킨다.

주기적으로 transcript를 읽어서, 노이즈를 걷어내고,
다음 대화에서 바로 쓸 수 있는 기억으로 만든다.

"기억해"라고 말하지 않아도 기억하고,
"정리해"라고 말하지 않아도 정리한다.

그래서 이름이 dream이다.

---

## 과정

### 1. Heartbeat --- 깨울지 말지 판단

```
[heartbeat daemon]
     │
     ├─ 60초마다 깨어남
     ├─ HEARTBEAT.md에서 잡 목록 파싱
     ├─ 잡별 interval 확인 (예: 3시간)
     └─ condition 체크
         └─ "미처리 transcript 있나?"
              ├─ 없으면 → 스킵 (비용 0)
              └─ 있으면 → 다음 단계
```

데몬 자체는 LLM을 호출하지 않는다. 상주해도 토큰 비용은 0이다.
할 일이 있을 때만 Claude를 깨운다.

### 2. dream-prep --- 전처리

transcript JSONL은 그대로 읽기엔 너무 크고 노이즈가 많다.

dream-prep이 하는 일:
- 유저/어시스턴트 텍스트만 추출
- 코드 블록 압축 (4줄 이상 → 첫 줄 + 생략 표시)
- 연속 도구 호출 합치기 (`[도구: Bash, Read x2]`)
- 시스템 메시지 제거

수천 줄짜리 JSONL이 읽을 수 있는 경량 마크다운으로 바뀐다.

### 3. /dream --- 정제

Claude가 깨어나서 `/dream` 스킬을 실행한다.
KAIROS autoDream의 4단계를 따른다:

| 단계 | 이름 | 하는 일 |
|------|------|---------|
| 1 | Orient | 현재 메모리 상태 파악 |
| 2 | Gather | 전처리된 마크다운 읽기 |
| 3 | Consolidate | 기존 메모리와 병합, topic 파일 생성/수정 |
| 4 | Prune & Index | 중복 제거, MEMORY.md 인덱스 갱신 |

### 4. Memory --- 결과

정제가 끝나면 메모리가 갱신된 상태다.
다음 세션에서 Claude는 이전 대화의 맥락을 알고 있다.

```
Before dream:
  "이 프로젝트 구조가 어떻게 되어있어?"  ← 매 세션마다 반복

After dream:
  (이미 알고 있음. 바로 작업 시작.)
```

---

## 메모리 계층

```
┌─────────────────────────────────────────┐
│  L1: MEMORY.md                          │
│  항상 로드. 200줄 인덱스.               │
├─────────────────────────────────────────┤
│  L2: Topic Files                        │
│  정제된 지식. 필요할 때 참조.           │
│  user.md, feedback.md, project.md ...   │
├─────────────────────────────────────────┤
│  L3: Transcript JSONL                   │
│  대화 원본.                             │
│  자동 저장. 자동 정제. 수동 개입 없음.  │
└─────────────────────────────────────────┘
```

---

## 요구사항

- macOS (launchd 기반 자동화)
- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)

## 빠른 시작

```bash
git clone https://github.com/wooson00308/dream-preprocessor.git
cd dream-preprocessor
pip3 install -e .

# 스킬 등록
mkdir -p ~/.claude/skills/dream
cp skill/SKILL.md ~/.claude/skills/dream/SKILL.md

# 테스트
dream-prep list
dream-heartbeat once
```

launchd 등록 등 상세 설정은 [설정 가이드](setup.md) 참고.

## 설정

`~/.claude/HEARTBEAT.md`에 잡을 등록한다:

```markdown
## my-project
- slug: -Users-yourname-Git-myproject
- prompt: /dream
- interval: 3h
- timeout: 10m
- condition: dream-prep status --slug="..." | grep -q "미처리: 0" && exit 1 || exit 0
```

| 필드 | 설명 | 기본값 |
|------|------|--------|
| slug | 프로젝트 슬러그 (`~/.claude/projects/` 하위 디렉토리명) | 필수 |
| prompt | claude -p에 전달할 프롬프트 | 필수 |
| interval | 실행 간격 (s/m/h/d) | 1h |
| timeout | 타임아웃 (s/m/h/d) | 600s |
| condition | 실행 전 체크 (exit 0이면 실행) | 없음 |

## 라이선스

MIT

---

_under the moonlight, Claude dreams._
