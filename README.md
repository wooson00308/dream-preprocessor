# dream-preprocessor

클로드 코드가 매 세션마다 transcript JSONL을 자동 저장하지만, 이 데이터는 raw 상태로만 쌓임.
KAIROS(유출된 미공개 기능)의 /dream처럼 transcript를 주기적으로 정제하여 메모리에 반영하는 시스템을 구현.

## 아키텍처

```
[클로드 대화] → transcript JSONL 자동 저장 (클로드 자체 기능)
       ↓
[heartbeat 데몬] 주기적으로 체크
       ↓
[dream-prep] 파이썬 전처리 (JSONL → 경량 마크다운)
       ↓
[claude -p "/dream"] LLM이 깨어나서 /dream 스킬 실행
       ↓
[메모리 갱신] topic 파일 생성/수정 + MEMORY.md 인덱스 업데이트
```

- 데몬은 LLM 호출 안 함 → 상주해도 비용 0
- condition으로 "할 일 있나?" 먼저 체크 → 없으면 claude 안 깨움

## 요구사항

- macOS (launchd 기반 자동화)
- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` 명령어)
- `/dream` 스킬 (별도 설정 필요 — 아래 참고)

## macOS 세팅 가이드

### 1. 클론 및 설치

```bash
git clone https://github.com/wooson00308/dream-preprocessor.git
cd dream-preprocessor
pip3 install -e .
```

설치 확인:

```bash
dream-prep list
dream-heartbeat --help
```

### 2. /dream 스킬 등록

레포에 포함된 스킬 파일을 복사한다:

```bash
mkdir -p ~/.claude/skills/dream
cp skill/SKILL.md ~/.claude/skills/dream/SKILL.md
```

스킬 내용은 [`skill/SKILL.md`](skill/SKILL.md) 참고. 필요에 따라 커스터마이징 가능.

### 3. HEARTBEAT.md 작성

`~/.claude/HEARTBEAT.md`에 잡을 등록한다.  
프로젝트 슬러그는 `~/.claude/projects/` 아래 디렉토리명 (예: `-Users-yourname`).

```markdown
# HEARTBEAT

## dream-home
- slug: -Users-yourname
- prompt: /dream
- interval: 3h
- timeout: 10m
- condition: dream-prep status --slug="-Users-yourname" | grep -q "미처리: 0" && exit 1 || exit 0
```

잡을 여러 개 등록하려면 `## 잡이름` 블록을 추가하면 된다.

### 4. 수동 테스트

자동화 걸기 전에 한번 돌려본다:

```bash
# 전처리만 테스트
dream-prep prep --slug="-Users-yourname" -n 3

# 잡 1회 실행 (claude가 깨어나서 /dream 실행)
dream-heartbeat once
```

### 5. launchd로 자동 실행 등록

dream-heartbeat의 실제 경로를 확인한다:

```bash
which dream-heartbeat
# 예: /Users/yourname/.pyenv/versions/3.11.9/bin/dream-heartbeat
```

plist 작성:

```bash
cat > ~/Library/LaunchAgents/com.dream-heartbeat.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dream-heartbeat</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/yourname/.pyenv/versions/3.11.9/bin/dream-heartbeat</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/yourname/.claude/dream-heartbeat/launchd_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourname/.claude/dream-heartbeat/launchd_stderr.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/yourname</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/Users/yourname/.pyenv/versions/3.11.9/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/yourname</string>
    </dict>
</dict>
</plist>
EOF
```

> `/Users/yourname` 부분과 python 경로를 자기 환경에 맞게 수정할 것.  
> PATH에 `claude` CLI가 포함된 경로가 있어야 함 (보통 `/opt/homebrew/bin`).

등록 및 시작:

```bash
launchctl load ~/Library/LaunchAgents/com.dream-heartbeat.plist
```

확인:

```bash
dream-heartbeat status
```

해제:

```bash
launchctl unload ~/Library/LaunchAgents/com.dream-heartbeat.plist
```

> launchd는 `--foreground` 모드로 실행해야 정상 동작한다.  
> KeepAlive가 켜져있으므로 프로세스가 죽어도 자동 재시작된다.

---

## dream-prep (전처리 CLI)

transcript JSONL에서 유저/어시스턴트 텍스트만 추출하여 경량 마크다운으로 변환.

- 코드 블록 압축 (3줄 이하 유지, 4줄 이상은 첫 줄 + 생략)
- 연속 도구 호출 합치기 (`[도구: Bash, Read x2]`)
- 시스템 메시지 제거

```bash
dream-prep list                          # 프로젝트별 transcript 수
dream-prep status --slug="-Users-yourname"  # 처리 현황
dream-prep prep --slug="-Users-yourname" -n 5  # 전처리 실행
```

## dream-heartbeat (스케줄러 데몬)

`~/.claude/HEARTBEAT.md`를 파싱하여 잡을 주기적으로 실행하는 범용 스케줄러.

```bash
dream-heartbeat start       # 데몬 시작 (백그라운드)
dream-heartbeat start -f    # 포그라운드 실행
dream-heartbeat stop        # 데몬 중지
dream-heartbeat status      # 상태 + 최근 로그
dream-heartbeat jobs        # 잡 목록
dream-heartbeat once        # 모든 잡 1회 실행
dream-heartbeat once -j "잡이름"  # 특정 잡 1회 실행
```

### HEARTBEAT.md 형식

```markdown
## auto-dream

- slug: -Users-yourname
- prompt: /dream
- interval: 3h
- timeout: 600
- condition: dream-prep status --slug="-Users-yourname" 2>&1 | grep -q "미처리: [1-9]"
```

| 필드 | 설명 | 기본값 |
|------|------|--------|
| slug | 프로젝트 슬러그 (클로드 projects 디렉토리명) | 필수 |
| prompt | claude -p에 전달할 프롬프트 | 필수 |
| interval | 실행 간격 (s/m/h/d) | 1h |
| timeout | 타임아웃 (s/m/h/d) | 600s |
| condition | 실행 전 체크 쉘 커맨드 (exit 0이면 실행) | 없음 (항상 실행) |

## /dream 스킬

이 도구는 전처리만 담당. 실제 정제 로직은 Claude Code의 `/dream` 스킬에서 수행.  
스킬 전문은 [`skill/SKILL.md`](skill/SKILL.md)에 포함되어 있다.

스킬이 하는 일 (KAIROS autoDream 4단계):
1. Orient — 현재 메모리 상태 파악
2. Gather — dream-prep으로 전처리된 마크다운 읽기
3. Consolidate — 기존 메모리와 병합하여 topic 파일 생성/수정
4. Prune & Index — 중복 제거 + MEMORY.md 인덱스 갱신

## 메모리 계층

| 계층 | 시스템 | 역할 |
|------|--------|------|
| L1 | MEMORY.md | 인덱스 (항상 로드) |
| L2 | topic 파일 | 정제된 지식 |
| L3 | transcript JSONL | 대화 원본 |

## 라이선스

MIT
