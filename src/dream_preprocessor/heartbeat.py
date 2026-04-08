"""Heartbeat daemon — reads ~/.claude/HEARTBEAT.md and runs jobs on schedule.

Generic scheduler that periodically executes claude CLI with configured prompts.
"""

import os
import re
import subprocess
import time
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

HEARTBEAT_FILE = Path.home() / ".claude" / "HEARTBEAT.md"
LOG_DIR = Path.home() / ".claude" / "dream-heartbeat"
PID_FILE = LOG_DIR / "heartbeat.pid"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [heartbeat] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("heartbeat")


def _setup_log_file() -> None:
    """Set up file logging."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"heartbeat_{datetime.now().strftime('%Y%m%d')}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [heartbeat] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(handler)


def _write_pid() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def _is_running() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, OSError):
        _remove_pid()
        return None


def _parse_interval(s: str) -> int:
    """Parse interval string like '3h', '30m', '1d' to seconds."""
    s = s.strip().lower()
    match = re.match(r"^(\d+)\s*(s|m|h|d)$", s)
    if match:
        val, unit = int(match.group(1)), match.group(2)
        return val * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    # Try raw seconds
    try:
        return int(s)
    except ValueError:
        return 3600  # default 1h


def _parse_timeout(s: str) -> int:
    """Parse timeout string to seconds."""
    return _parse_interval(s)


def parse_heartbeat_md() -> list[dict]:
    """Parse ~/.claude/HEARTBEAT.md and return job configs."""
    if not HEARTBEAT_FILE.exists():
        return []

    content = HEARTBEAT_FILE.read_text(encoding="utf-8")
    jobs = []
    current_job = None

    for line in content.split("\n"):
        line = line.strip()

        # New job header: ## job-name
        if line.startswith("## "):
            if current_job:
                jobs.append(current_job)
            current_job = {
                "name": line[3:].strip(),
                "slug": "",
                "prompt": "",
                "interval": 3600,
                "timeout": 600,
                "condition": "",
            }
        elif current_job and line.startswith("- "):
            # Parse key: value
            kv = line[2:]
            if ":" in kv:
                key, val = kv.split(":", 1)
                key = key.strip().lower()
                val = val.strip()
                if key == "slug":
                    current_job["slug"] = val
                elif key == "prompt":
                    current_job["prompt"] = val
                elif key == "interval":
                    current_job["interval"] = _parse_interval(val)
                elif key == "timeout":
                    current_job["timeout"] = _parse_timeout(val)
                elif key == "condition":
                    current_job["condition"] = val

    if current_job:
        jobs.append(current_job)

    return [j for j in jobs if j["slug"] and j["prompt"]]


def _check_condition(job: dict) -> bool:
    """Run condition command. Returns True if job should run."""
    condition = job.get("condition", "")
    if not condition:
        return True

    try:
        result = subprocess.run(
            condition, shell=True, capture_output=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return True  # Run if condition check fails


def _slug_to_cwd(slug: str) -> Path:
    """Convert project slug to CWD path."""
    return Path("/" + slug.lstrip("-").replace("-", "/"))


def run_job(job: dict) -> bool:
    """Execute a single heartbeat job."""
    name = job["name"]
    slug = job["slug"]
    prompt = job["prompt"]
    timeout = job["timeout"]

    # Check condition
    if not _check_condition(job):
        log.info(f"[{name}] condition 불충족, 스킵")
        return False

    cwd = _slug_to_cwd(slug)
    if not cwd.exists():
        log.warning(f"[{name}] CWD {cwd} 존재하지 않음, 스킵")
        return False

    log.info(f"[{name}] 실행: claude -p \"{prompt}\" (cwd: {cwd})")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            log.info(f"[{name}] 완료")
        else:
            log.error(f"[{name}] 실패 (exit {result.returncode}): {result.stderr[:200]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log.error(f"[{name}] 타임아웃 ({timeout}초)")
        return False
    except FileNotFoundError:
        log.error("claude CLI를 찾을 수 없음")
        return False


def heartbeat_loop() -> None:
    """Main heartbeat loop. Re-reads HEARTBEAT.md each cycle."""
    log.info("Heartbeat 데몬 시작")

    # Track last run time per job
    last_run: dict[str, float] = {}

    while True:
        jobs = parse_heartbeat_md()
        if not jobs:
            log.warning("HEARTBEAT.md에 잡이 없음, 60초 후 재확인")
            time.sleep(60)
            continue

        now = time.time()
        for job in jobs:
            name = job["name"]
            interval = job["interval"]
            last = last_run.get(name, 0)

            if now - last >= interval:
                try:
                    run_job(job)
                except Exception as e:
                    log.error(f"[{name}] 에러: {e}")
                last_run[name] = time.time()

        # Sleep in 60s chunks for clean shutdown
        time.sleep(60)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="dream-heartbeat", description="Heartbeat daemon — runs claude jobs on schedule")
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Start heartbeat daemon")
    p_start.add_argument("--foreground", "-f", action="store_true", help="Run in foreground")

    # stop
    sub.add_parser("stop", help="Stop heartbeat daemon")

    # status
    sub.add_parser("status", help="Check heartbeat status")

    # once
    p_once = sub.add_parser("once", help="Run all jobs once and exit")
    p_once.add_argument("--job", "-j", help="Run specific job by name")

    # jobs
    sub.add_parser("jobs", help="List configured jobs from HEARTBEAT.md")

    args = parser.parse_args()

    if args.command == "start":
        existing = _is_running()
        if existing:
            print(f"Heartbeat 이미 실행 중 (PID {existing})")
            sys.exit(1)

        _setup_log_file()

        if args.foreground:
            _write_pid()

            def _shutdown(_sig, _frame):
                log.info("Heartbeat 종료")
                _remove_pid()
                sys.exit(0)

            signal.signal(signal.SIGTERM, _shutdown)
            signal.signal(signal.SIGINT, _shutdown)
            heartbeat_loop()
        else:
            pid = os.fork()
            if pid > 0:
                print(f"Heartbeat 시작 (PID {pid})")
                sys.exit(0)

            os.setsid()
            _write_pid()
            _setup_log_file()

            sys.stdout = open(LOG_DIR / "stdout.log", "a")
            sys.stderr = open(LOG_DIR / "stderr.log", "a")

            def _shutdown(_sig, _frame):
                log.info("Heartbeat 종료")
                _remove_pid()
                sys.exit(0)

            signal.signal(signal.SIGTERM, _shutdown)
            signal.signal(signal.SIGINT, _shutdown)
            heartbeat_loop()

    elif args.command == "stop":
        existing = _is_running()
        if existing:
            os.kill(existing, signal.SIGTERM)
            print(f"Heartbeat 종료 (PID {existing})")
        else:
            print("실행 중인 heartbeat 없음")

    elif args.command == "status":
        existing = _is_running()
        if existing:
            print(f"Heartbeat 실행 중 (PID {existing})")
            log_files = sorted(LOG_DIR.glob("heartbeat_*.log"))
            if log_files:
                last_lines = log_files[-1].read_text(encoding="utf-8").strip().split("\n")[-5:]
                print("최근 로그:")
                for l in last_lines:
                    print(f"  {l}")
        else:
            print("실행 중인 heartbeat 없음")

    elif args.command == "once":
        _setup_log_file()
        jobs = parse_heartbeat_md()
        if args.job:
            jobs = [j for j in jobs if j["name"] == args.job]
        for job in jobs:
            run_job(job)

    elif args.command == "jobs":
        jobs = parse_heartbeat_md()
        if not jobs:
            print("HEARTBEAT.md에 잡이 없음")
        else:
            for j in jobs:
                interval_h = j["interval"] / 3600
                print(f"  {j['name']} — {j['prompt']} (매 {interval_h:.1f}시간, slug: {j['slug']})")

    else:
        parser.print_help()
