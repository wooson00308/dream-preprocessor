---
description: transcript JSONL을 정제하여 메모리 topic 파일과 MEMORY.md 인덱스를 갱신하는 /dream 프로세스. KAIROS autoDream 방식. "/dream" 입력 시 트리거.
---

# /dream — transcript 정제 프로세스

## 개요

클로드 코드가 자동 저장하는 transcript JSONL을 정제하여 메모리 topic 파일로 변환하고 MEMORY.md 인덱스를 갱신한다.

파이프라인:
```
JSONL (수 MB) → 파이썬 전처리 (경량 마크다운) → 본체가 읽고 판단 (메모리 갱신)
```

전처리 스크립트(`dream-prep`)가 도구 호출 합치기, 코드 블록 압축, 시스템 메시지 제거 등 기계적 처리를 담당.
본체는 전처리된 마크다운만 읽고 메모리 갱신 판단에 집중.

## 경로 규칙

- transcript 원본: `~/.claude/projects/{slug}/*.jsonl`
- 전처리 출력: `~/.claude/projects/{slug}/memory/_dream_prep/*.md`
- 메모리: `~/.claude/projects/{slug}/memory/`
- 인덱스: `~/.claude/projects/{slug}/memory/MEMORY.md`
- 메타: `~/.claude/projects/{slug}/memory/dream_meta.md`
- project-slug: CWD 경로의 `/` → `-` 변환. 예) `/Users/yourname` → `-Users-yourname`

## 실행 프로세스

### Phase 1: Orient

1. 현재 프로젝트의 slug 확인 (CWD 기반)
2. MEMORY.md 읽어서 기존 topic 파일 목록 파악
3. dream_meta.md에서 마지막 정제 시점과 처리된 transcript 목록 확인
4. `dream-prep status --slug="{slug}"` 로 미처리 transcript 수 확인
5. 사용자에게 보고: "N개의 미처리 transcript 발견"

### Phase 2: Gather (전처리 스크립트)

transcript JSONL을 직접 읽지 않는다. 전처리 스크립트가 기계적으로 처리한다.

1. Bash로 실행: `dream-prep prep --slug="{slug}" -n 5`
2. 스크립트가 수행하는 처리:
   - JSONL에서 유저 텍스트 + 어시스턴트 텍스트만 추출
   - 시스템 메시지 (`<` 시작) 제거
   - 연속 도구 호출 한 줄로 합치기 (`[도구: Bash, Read x2]`)
   - 코드 블록 3줄 이하 유지, 4줄 이상 첫 줄 + `... (N줄 생략)`
   - 유저 메시지 3자 이하 제거
3. 결과: `memory/_dream_prep/prep_{timestamp}.md`
4. 이 파일을 Read로 읽기

### Phase 3: Consolidate

전처리 파일을 읽고 기억할 가치가 있는 정보를 식별한다.

1. 분류 기준:
   - 사용자 프로필/선호도 변경 → user 타입
   - 작업 방식 피드백/교정 → feedback 타입
   - 프로젝트 상태/결정/일정 → project 타입
   - 외부 리소스 참조 → reference 타입
2. 기존 topic 파일과 대조:
   - 이미 있는 내용 → 스킵
   - 기존과 모순 → 최신 정보로 갱신 (Edit)
   - 새로운 내용 → 기존 topic에 추가 or 새 topic 생성 (Write)
3. 상대 날짜 → 절대 날짜 변환
4. 메모리 frontmatter 규칙:
   ```
   ---
   name: {memory name}
   description: {한 줄 설명}
   type: {user|feedback|project|reference}
   ---
   ```
5. feedback: "규칙 → Why → How to apply" 구조
6. project: "사실/결정 → Why → How to apply" 구조

### Phase 4: Prune & Index

1. MEMORY.md 인덱스 재구성:
   - 실제 파일 없는 포인터 제거
   - 새 topic 파일 포인터 추가
   - 200줄 이하, 라인당 ~150자
   - 형식: `- [파일명.md](파일명.md) — 한 줄 설명`
2. dream_meta.md 갱신:
   - last_dream 타임스탬프 업데이트
   - 처리한 transcript 파일명 추가 (전처리 파일에 세션 ID가 기록됨)
3. _dream_prep/ 디렉토리 정리 (처리 완료된 prep 파일 삭제)
4. 결과 보고: 생성/갱신/삭제된 topic 파일 목록

## 주의사항

- transcript 원본은 절대 수정/삭제하지 않는다
- topic 파일 쓰기 성공 후에만 MEMORY.md 인덱스 업데이트 (Strict Write Discipline)
- 인사이트급 발견은 문샤인에 별도 등록
  - 메모리: "매번 필요한 맥락" (프로필, 피드백, 프로젝트 상태)
  - 문샤인: "필요할 때 꺼내 쓰는 지식" (인사이트, 디버깅 기록, 시행착오)
- 한 번에 5개씩 처리. 미처리가 많으면 여러 라운드로 나눠서 실행
- 모든 내용은 한국어로 작성

## 저장하지 않는 것

- 코드 패턴, 아키텍처, 파일 경로 — 코드에서 직접 확인 가능
- git 히스토리 — git log/blame으로 확인 가능
- 디버깅 솔루션 — 코드와 커밋 메시지에 있음
- CLAUDE.md에 이미 문서화된 내용
- 의미 없는 단답 ("ㅇㅇ", "ㄱㄱ", "ㅎㅇ" 등) — 맥락 없이는 가치 없음
- 단, 성격/취향/감정이 드러나는 잡담은 user 타입으로 저장할 것 (예: 좋아하는 것, 정 드는 성향, 유머 스타일 등)
