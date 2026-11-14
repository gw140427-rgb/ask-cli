#!/usr/bin/env python3
"""
ask - The Zero-Dependency Terminal AI Copilot
Works on Linux, macOS, Termux, and WSL.
Pure Python standard library (no external pip dependencies).

v1.2.0: interactive chat (ask chat / -c), session save/resume-listing,
        usage & limit viewer (--limits, /limits), local-first Ollama support,
        2026 model lineup, and a full bug sweep.
"""

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime

VERSION = "1.2.0"

# ASK_HOME lets you move the whole config dir (used by tests and portable installs).
CONFIG_DIR = os.path.expanduser(os.environ.get("ASK_HOME") or "~/.config/ask")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
USAGE_PATH = os.path.join(CONFIG_DIR, "usage.json")
SESSION_DIR = os.path.join(CONFIG_DIR, "sessions")

REQUEST_TIMEOUT = 30       # remote APIs
LOCAL_TIMEOUT = 180        # local Ollama on a phone can think for a while
MAX_HISTORY = 24           # messages of context sent to the model
MAX_SESSIONS = 50          # session files kept on disk
MAX_USAGE_DAYS = 180

# --- ANSI -------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

COLOR = False  # decided by setup_console()


def paint(text, *codes):
    """Wrap text in ANSI codes, or return it unchanged when color is off."""
    if not COLOR or not codes:
        return str(text)
    return "".join(codes) + str(text) + RESET


def disp_width(text):
    """Terminal column width: CJK characters take two columns."""
    width = 0
    for ch in str(text):
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def warn(text):
    """A single non-fatal warning line on stderr."""
    sys.stderr.write(paint("⚠  ", YELLOW) + str(text) + "\n")
    sys.stderr.flush()


def clear_line():
    # Only wipe the spinner on a real terminal; piped output must stay clean.
    if sys.stdout.isatty():
        sys.stdout.write("\r" + " " * 40 + "\r")
        sys.stdout.flush()


def setup_console():
    """Make UTF-8 safe on every terminal (C locale, Termux, Windows) and pick color mode."""
    global COLOR
    for stream, kwargs in (
        (sys.stdout, {"errors": "replace"}),
        (sys.stderr, {"errors": "replace"}),
        (sys.stdin, {"errors": "replace"}),
    ):
        try:
            stream.reconfigure(encoding="utf-8", **kwargs)  # Python 3.7+
        except (AttributeError, ValueError, OSError):
            pass

    if os.environ.get("NO_COLOR") or os.environ.get("ASK_NO_COLOR"):
        COLOR = False
    elif os.environ.get("ASK_FORCE_COLOR"):
        COLOR = True
    else:
        try:
            COLOR = sys.stdout.isatty()
        except Exception:
            COLOR = False


# --- Providers --------------------------------------------------------------
# Model IDs verified on 2026-11-14 against each provider's live docs.
DEFAULT_CONFIG = {
    "provider": "groq",
    "api_key": "",
    "model": "openai/gpt-oss-120b",
    "endpoint": "https://api.groq.com/openai/v1/chat/completions",
}

PROVIDERS = {
    "groq": {
        "label": "Groq",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "openai/gpt-oss-120b",
        "env_key": "GROQ_API_KEY",
        "daily_limit": 1000,          # soft reference limit for the free tier
        "extra": {},
    },
    "gemini": {
        "label": "Gemini",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "default_model": "gemini-4-hydrogen",
        "env_key": "GEMINI_API_KEY",
        "daily_limit": 1000,
        # Gemini 4 ignores sampling params; low thinking keeps CLI answers snappy.
        "extra": {"reasoning_effort": "low"},
    },
    "openai": {
        "label": "OpenAI",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-6.1-sol",
        "env_key": "OPENAI_API_KEY",
        "daily_limit": 0,             # paid: no soft daily cap
        "extra": {},
    },
    "deepseek": {
        "label": "DeepSeek",
        "endpoint": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-flash",
        "env_key": "DEEPSEEK_API_KEY",
        "daily_limit": 0,
        # deepseek-chat was retired 2026-07-24; deepseek-flash thinks by default.
        # Turning thinking off keeps the old deepseek-chat latency and billing shape.
        "extra": {"thinking": {"type": "disabled"}},
    },
    "ollama": {
        "label": "Ollama (로컬 모델)",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "default_model": "qwen3.5:9b",
        "env_key": "",
        "daily_limit": 0,             # unlimited, runs on your own machine
        "extra": {},
    },
    "custom": {
        "label": "사용자 지정 (OpenAI 호환)",
        "endpoint": "",
        "default_model": "gpt-6.1-sol",
        "env_key": "",
        "daily_limit": 0,
        "extra": {},
    },
}

# Old default model IDs -> current replacement, applied to existing configs.
OLD_MODELS = {
    ("openai", "gpt-4o-mini"): "gpt-6.1-sol",
    ("openai", "gpt-4o"): "gpt-6.1-sol",
    ("openai", "gpt-5"): "gpt-6.1-sol",
    ("openai", "gpt-5-mini"): "gpt-6-luna",
    ("openai", "gpt-5-nano"): "gpt-6-luna",
    ("openai", "gpt-6-luna"): None,  # still valid, no change
    ("groq", "llama-3.3-70b-versatile"): "openai/gpt-oss-120b",
    ("groq", "llama-3.1-8b-instant"): "openai/gpt-oss-20b",
    ("groq", "qwen/qwen3.6-27b"): "qwen/qwen3.8-27b",
    ("ollama", "llama3.2"): "qwen3.5:9b",
    ("ollama", "llama3.1"): "qwen3.5:9b",
    ("deepseek", "deepseek-chat"): "deepseek-flash",
    ("deepseek", "deepseek-reasoner"): "deepseek-flash",
}


class AskError(Exception):
    """A failure that should be printed as one clean line, not a traceback."""

    def __init__(self, message, code=1):
        super().__init__(message)
        self.code = code


# --- Small file helpers -----------------------------------------------------
def ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise AskError(f"폴더를 만들 수 없습니다: {path} ({one_line(e)})")


def one_line(text, limit=220):
    """Collapse any text (multi-line JSON bodies included) into a single clean line."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def atomic_write_json(path, data, private=False):
    """Write JSON via a temp file + os.replace so a crash never leaves a half file."""
    ensure_dir(os.path.dirname(path) or ".")
    tmp = f"{path}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        if private:
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
        os.replace(tmp, path)
        return True
    except OSError as e:
        warn(f"저장 실패: {os.path.basename(path)} ({one_line(e)})")
        return False
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read_json_dict(path):
    """Read a JSON object. A corrupt or partial file is backed up, never fatal."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("최상위가 객체가 아님")
        return data
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError, OSError) as e:
        backup = f"{path}.corrupt-{int(time.time())}"
        try:
            os.replace(path, backup)
            warn(f"{os.path.basename(path)} 파일이 손상되어 백업하고 기본값으로 시작합니다 ({one_line(e)}).")
        except OSError:
            warn(f"{os.path.basename(path)} 파일이 손상되었습니다 ({one_line(e)}).")
        return {}


# --- Config -----------------------------------------------------------------
def _clean_str(value, default=""):
    return value.strip() if isinstance(value, str) and value.strip() else default


def load_config():
    """Build the effective config: defaults + saved file + env keys + model migrations."""
    config = dict(DEFAULT_CONFIG)
    raw = read_json_dict(CONFIG_PATH)

    provider = raw.get("provider")
    if isinstance(provider, str) and provider.strip().lower() in PROVIDERS:
        config["provider"] = provider.strip().lower()
    elif provider:
        # Unknown provider name: keep it only if the user gave a working endpoint.
        if _clean_str(raw.get("endpoint")):
            config["provider"] = provider.strip().lower()
        else:
            warn(f"알 수 없는 제공자 '{one_line(provider, 40)}' — groq로 대체합니다.")

    config["model"] = _clean_str(raw.get("model"), config["model"])
    config["endpoint"] = _clean_str(raw.get("endpoint"), "")
    if not config["endpoint"]:
        config["endpoint"] = PROVIDERS.get(config["provider"], {}).get("endpoint", "")

    # Per-provider key store so /model can hop between providers.
    keys = {}
    saved_keys = raw.get("keys")
    if isinstance(saved_keys, dict):
        for k, v in saved_keys.items():
            if isinstance(k, str) and isinstance(v, str) and v.strip():
                keys[k] = v.strip()
    legacy_key = _clean_str(raw.get("api_key"))
    if legacy_key:
        keys.setdefault(config["provider"], legacy_key)
    config["keys"] = keys
    config["api_key"] = keys.get(config["provider"], "")

    # Env vars win only where nothing is stored.
    if not config["api_key"]:
        provider_env = PROVIDERS.get(config["provider"], {}).get("env_key", "")
        env_key = _clean_str(os.environ.get("ASK_API_KEY")) or (
            _clean_str(os.environ.get(provider_env)) if provider_env else ""
        )
        if env_key:
            config["api_key"] = env_key

    for key in ("temperature",):
        if isinstance(raw.get(key), (int, float)) and not isinstance(raw.get(key), bool):
            config[key] = raw.get(key)
    if isinstance(raw.get("daily_limit"), (int, float)) and not isinstance(raw.get("daily_limit"), bool):
        config["daily_limit"] = int(raw["daily_limit"])
    if isinstance(raw.get("timeout"), (int, float)) and not isinstance(raw.get("timeout"), bool):
        config["timeout"] = int(raw["timeout"])
    if isinstance(raw.get("extra"), dict):
        config["extra"] = dict(raw["extra"])

    # Retired model IDs -> current ones (and persist it once).
    migrated = OLD_MODELS.get((config["provider"], config["model"].lower()))
    if migrated and migrated != config["model"]:
        old = config["model"]
        config["model"] = migrated
        warn(f"모델 '{old}' 은(는) 지원이 끝나 '{migrated}' 로 자동 갱신했습니다.")
        save_config(config, quiet=True)

    return config


def save_config(config, quiet=False):
    keys = dict(config.get("keys", {}) or {})
    provider = config.get("provider", "")
    # Only keys the user actually stored are written back; an env-provided key
    # (ASK_API_KEY/..._API_KEY) stays in the environment, not in config.json.
    data = {
        "provider": provider,
        "model": config.get("model", ""),
        "endpoint": config.get("endpoint", ""),
        "api_key": keys.get(provider, ""),
        "keys": keys,
    }
    for key in ("temperature", "daily_limit", "timeout", "extra"):
        if key in config:
            data[key] = config[key]
    ok = atomic_write_json(CONFIG_PATH, data, private=True)
    if ok and not quiet:
        print(paint("✓ 설정이 저장되었습니다: " + CONFIG_PATH, GREEN))
        print(paint("  (파일 권한 600 — API 키가 들어 있으니 공유하지 마세요)", DIM))
    return ok


# --- Usage tracking ---------------------------------------------------------
def date_key(ts=None):
    return (ts or datetime.now()).strftime("%Y-%m-%d")


def _num(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def empty_bucket():
    return {
        "requests": 0,
        "ok": 0,
        "errors": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated": False,
    }


def load_usage():
    data = read_json_dict(USAGE_PATH)
    return {k: v for k, v in data.items() if re.match(r"^\d{4}-\d{2}-\d{2}$", k) and isinstance(v, dict)}


def record_usage(provider, model, ok, usage=None, prompt_chars=0, answer_chars=0):
    """Count one API call for today. Never fatal: usage stats must not break a request."""
    try:
        data = load_usage()
        day = data.setdefault(date_key(), {})
        for scope in (day.setdefault("total", empty_bucket()), day.setdefault("by_provider", {}).setdefault(provider, empty_bucket())):
            scope["requests"] = _num(scope.get("requests")) + 1
            scope["ok"] = _num(scope.get("ok")) + (1 if ok else 0)
            scope["errors"] = _num(scope.get("errors")) + (0 if ok else 1)

        usage = usage if isinstance(usage, dict) else {}
        prompt_tokens = _num(usage.get("prompt_tokens")) or _num(usage.get("input_tokens"))
        completion_tokens = _num(usage.get("completion_tokens")) or _num(usage.get("output_tokens"))
        estimated = False
        if not prompt_tokens and not completion_tokens and ok:
            prompt_tokens = max(1, prompt_chars // 4)
            completion_tokens = max(1, answer_chars // 4)
            estimated = True

        for scope in (day["total"], day["by_provider"][provider]):
            scope["prompt_tokens"] = _num(scope.get("prompt_tokens")) + prompt_tokens
            scope["completion_tokens"] = _num(scope.get("completion_tokens")) + completion_tokens
            scope["estimated"] = bool(scope.get("estimated")) or estimated
        if model:
            models = day.setdefault("by_model", {})
            models[model] = _num(models.get(model)) + 1

        # prune very old days so the file cannot grow forever
        cutoff = datetime.now().toordinal() - MAX_USAGE_DAYS
        for key in list(data.keys()):
            try:
                if datetime.strptime(key, "%Y-%m-%d").toordinal() < cutoff:
                    del data[key]
            except ValueError:
                del data[key]

        atomic_write_json(USAGE_PATH, data)
    except Exception as e:  # never let bookkeeping kill a request
        warn(f"사용량 기록을 건너뜁니다 ({one_line(e, 80)}).")


def _gauge(used, limit, width=30):
    ratio = (used / limit) if limit else 0.0
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    if ratio < 0.7:
        color = GREEN
    elif ratio < 0.9:
        color = YELLOW
    else:
        color = RED
    return paint(f"[{bar}]", color) + f" {ratio * 100:5.1f}%"


def render_limits(config):
    """The --limits / /limits view: provider, model, today's calls and a gauge."""
    today = date_key()
    data = load_usage()
    day = data.get(today, {})
    total = day.get("total") if isinstance(day.get("total"), dict) else {}
    by_provider = day.get("by_provider") if isinstance(day.get("by_provider"), dict) else {}
    provider = config.get("provider", "groq")
    model = config.get("model", "")
    mine = by_provider.get(provider) if isinstance(by_provider.get(provider), dict) else {}

    info = PROVIDERS.get(provider, {})
    limit = config.get("daily_limit")
    if not isinstance(limit, (int, float)):
        limit = info.get("daily_limit", 0) or 0
    limit = int(limit)

    requests = _num(mine.get("requests"))
    ok_calls = _num(mine.get("ok"))
    errors = _num(mine.get("errors"))
    ptok = _num(mine.get("prompt_tokens"))
    ctok = _num(mine.get("completion_tokens"))
    estimated = bool(mine.get("estimated"))

    rule = paint("─" * 54, DIM)
    print()
    print(rule)
    print(f" {paint('⚡ ask-cli 사용량', BOLD)} · {today} ({'월화수목금토일'[datetime.now().weekday()]})")
    print(rule)
    print(f"  제공자   {paint(provider, CYAN, BOLD)} · {model}")
    print(f"  오늘 요청 {paint(f'{requests:,}', BOLD)}회  (성공 {ok_calls} / 실패 {errors})")

    if provider == "ollama":
        print(f"  한도     {paint('무제한 (로컬 모델)', GREEN, BOLD)} — 내 기기에서 돌아갑니다")
    elif limit > 0:
        print(f"  한도     {requests:,} / {limit:,}회  (참고용 소프트 한도)")
        print(f"  게이지   {_gauge(requests, limit)}")
    else:
        print(f"  한도     {paint('제한 없음 (유료/사용량 과금)', DIM)}")

    token_label = "추정치" if estimated else "API 보고값"
    print(f"  토큰     입력 {ptok:,} / 출력 {ctok:,}  {paint('(' + token_label + ')', DIM)}")

    others = [(p, s) for p, s in by_provider.items() if p != provider and isinstance(s, dict) and _num(s.get("requests"))]
    if others:
        print(f"  {paint('다른 제공자', DIM)}")
        for p, s in sorted(others, key=lambda kv: -_num(kv[1].get("requests"))):
            print(f"    • {p}: {_num(s.get('requests')):,}회 / tok {_num(s.get('prompt_tokens')) + _num(s.get('completion_tokens')):,}")
    summed_requests = sum(_num(s.get("requests")) for s in by_provider.values() if isinstance(s, dict))
    summed_tokens = sum(_num(s.get("prompt_tokens")) + _num(s.get("completion_tokens")) for s in by_provider.values() if isinstance(s, dict))
    today_requests = max(summed_requests, _num(total.get("requests")))
    if today_requests:
        print(f"  {paint('오늘 합계', DIM)}  {today_requests:,}회 · tok {summed_tokens or (_num(total.get('prompt_tokens')) + _num(total.get('completion_tokens'))):,}")

    print(rule)
    print(paint(f"  기록: {USAGE_PATH}", DIM))
    print(paint("  한도 숫자는 참고값입니다. config.json 의 \"daily_limit\" 으로 직접 지정하세요.", DIM))
    print()


# --- HTTP -------------------------------------------------------------------
def provider_timeout(config):
    t = config.get("timeout")
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        return int(t)
    return LOCAL_TIMEOUT if config.get("provider") == "ollama" else REQUEST_TIMEOUT


def extract_error_message(body):
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return one_line(body)
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            for key in ("message", "detail", "msg"):
                if isinstance(err.get(key), str) and err[key].strip():
                    return one_line(err[key])
        if isinstance(err, str) and err.strip():
            return one_line(err)
        for key in ("message", "detail", "msg"):
            if isinstance(data.get(key), str) and data[key].strip():
                return one_line(data[key])
    return one_line(body)


def http_error_message(e, provider, model, endpoint):
    try:
        body = e.read().decode("utf-8", "replace")
    except Exception:
        body = ""
    detail = extract_error_message(body) if body else one_line(getattr(e, "reason", ""))

    if e.code == 401:
        hint = "API 키가 유효하지 않습니다 — ask --config 로 다시 확인하세요"
    elif e.code == 403:
        hint = "권한이 없습니다 — 이 키로 해당 모델을 쓸 수 있는지 확인하세요"
    elif e.code == 404:
        hint = f"모델 또는 엔드포인트를 찾을 수 없습니다 (모델: {model})"
    elif e.code == 429:
        hint = "요청 한도(rate limit)를 넘었습니다 — 잠시 뒤 다시 시도하세요"
    elif e.code == 400 and ("model" in (detail or "").lower()):
        hint = f"모델 이름을 확인하세요 (모델: {model})"
    elif e.code >= 500:
        hint = "제공자 서버 오류입니다 — 잠시 뒤 다시 시도하세요"
    else:
        hint = "요청이 거부되었습니다"

    msg = f"API 오류 {e.code}: {hint}"
    if detail and detail not in hint:
        msg += f" — {one_line(detail, 140)}"
    if provider == "ollama" and not endpoint.startswith("http://localhost"):
        msg += " (Ollama는 보통 localhost:11434 에서 실행됩니다)"
    return msg


def _network_chat(messages, config):
    """One POST to an OpenAI-compatible chat endpoint. Returns (content, usage)."""
    provider = config.get("provider", "groq")
    info = PROVIDERS.get(provider, {})
    endpoint = _clean_str(config.get("endpoint")) or info.get("endpoint", "")
    model = _clean_str(config.get("model")) or info.get("default_model", "")
    api_key = _clean_str(config.get("api_key"))

    if not endpoint:
        raise AskError("엔드포인트가 비어 있습니다 — ask --config 로 다시 설정하세요.")
    if not model:
        raise AskError("모델 이름이 비어 있습니다 — ask --config 또는 /model 로 지정하세요.")
    if not api_key and provider not in ("ollama", "custom"):
        raise AskError(
            "API 키가 없습니다 — `ask --config` 로 넣거나 export ASK_API_KEY='...' 하세요. "
            "로컬 모델을 쓰려면 /model ollama"
        )
    if not endpoint.startswith(("http://", "https://")):
        raise AskError(f"엔드포인트 형식이 올바르지 않습니다: {one_line(endpoint, 80)}")

    payload = {"model": model, "messages": messages}
    temperature = config.get("temperature")
    if isinstance(temperature, (int, float)) and not isinstance(temperature, bool):
        payload["temperature"] = temperature
    extra = dict(info.get("extra") or {})
    if isinstance(config.get("extra"), dict):
        extra.update(config["extra"])
    for key, value in extra.items():
        payload.setdefault(key, value)

    headers = {"Content-Type": "application/json", "User-Agent": f"ask-cli/{VERSION}"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    timeout = provider_timeout(config)
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(http_error_message(e, provider, model, endpoint))
    except urllib.error.URLError as e:
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        reason = getattr(e, "reason", e)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise AskError(f"응답 시간 초과 ({timeout}초) — 네트워크를 확인하거나 config.json 의 \"timeout\" 을 늘리세요.")
        raise AskError(f"네트워크 오류: {one_line(reason)} — {endpoint} 연결을 확인하세요.")
    except (socket.timeout, TimeoutError):
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"응답 시간 초과 ({timeout}초) — 네트워크를 확인하세요.")
    except (ConnectionResetError, BrokenPipeError) as e:
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"연결이 끊겼습니다: {one_line(e)}")
    except KeyboardInterrupt:
        raise AskError("요청을 취소했습니다.", code=130)
    except Exception as e:
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"요청 실패: {one_line(e)}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        snippet = one_line(raw, 120) if raw.strip() else "빈 응답"
        raise AskError(f"응답을 해석할 수 없습니다 (모델: {model}) — {snippet}")

    if not isinstance(data, dict):
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"예상과 다른 응답 형식입니다 (모델: {model}).")

    if data.get("error"):
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"API 오류: {extract_error_message(raw)}")

    choices = data.get("choices")
    content = ""
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict):
            content = message.get("content") or message.get("reasoning_content") or ""
        if not content and isinstance(choices[0].get("text"), str):
            content = choices[0]["text"]
    if not isinstance(content, str):
        content = str(content)
    if not content.strip():
        record_usage(provider, model, ok=False, prompt_chars=prompt_chars)
        raise AskError(f"모델이 빈 응답을 돌려줬습니다 (모델: {model}) — /model 로 다른 모델을 시도해 보세요.")

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    record_usage(
        provider, model, ok=True, usage=usage,
        prompt_chars=prompt_chars, answer_chars=len(content),
    )
    return content, usage


# --- Command mode -----------------------------------------------------------
def detect_env():
    is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")
    shell_name = os.path.basename(os.environ.get("SHELL", "bash")) or "bash"
    os_name = "Android (Termux)" if is_termux else f"{platform.system()} {platform.release()}"
    return {"os": os_name, "shell": shell_name, "is_termux": is_termux}


def command_system_prompt(env_info):
    return f"""You are a precise command-line assistant.
User Environment:
- OS: {env_info['os']}
- Shell: {env_info['shell']}

Given a user's natural language request, return ONLY a valid JSON object in this exact format:
{{
  "command": "the exact single-line shell command to execute",
  "explanation": "한 문장의 한국어 설명 (무엇을 하는 명령어인지 명확하고 짧게)",
  "breakdown": [
    {{"flag": "옵션이나 인자", "desc": "해당 옵션의 역할 설명"}}
  ]
}}

Rules:
1. Do not wrap in markdown fences if possible, or return raw JSON.
2. The command MUST be tailored for {env_info['os']} and {env_info['shell']}.
3. Never output dangerous irreversible commands without flags.
4. Keep the explanation to exactly 1 concise Korean sentence.
5. In breakdown, explain 2-4 key flags or parts of the command concisely in Korean.
"""


CHAT_SYSTEM_PROMPT = """You are ask, a concise terminal AI assistant talking with the user inside their terminal.
User Environment:
- OS: {os}
- Shell: {shell}

Rules:
1. Answer in Korean unless the user writes in another language. Keep it short: no filler, no long preambles.
2. When you give a shell command, put exactly that command in one fenced code block.
3. Say plainly when you are unsure instead of inventing facts, versions, or model names.
4. The user is on a phone or a small terminal as often as a desktop; keep answers scannable.
"""


def parse_command_json(content):
    """Pull the JSON object out of a model reply, tolerating fences and prose."""
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    obj = None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                obj = None
    if obj is None:
        raise AskError("모델이 명령어를 JSON으로 돌려주지 않았습니다. 다시 시도해 보세요.")
    if not isinstance(obj, dict):
        raise AskError("모델 응답이 JSON 객체가 아닙니다. 다시 시도해 보세요.")
    return obj


def copy_to_clipboard(text):
    """Copy text to the system clipboard across Termux, Linux, macOS, WSL."""
    candidates = [
        ("termux-clipboard-set", []),
        ("pbcopy", []),
        ("wl-copy", []),
        ("xclip", ["-selection", "clipboard"]),
        ("xsel", ["--clipboard", "--input"]),
        ("clip.exe", []),
    ]
    for tool, extra in candidates:
        if not shutil.which(tool):
            continue
        try:
            proc = subprocess.Popen([tool] + extra, stdin=subprocess.PIPE)
            proc.communicate(input=text.encode("utf-8"), timeout=5)
            if proc.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return False


def confirm_run():
    """Ask before running. Returns False on 'n', Ctrl+C, or EOF (piped stdin)."""
    try:
        answer = input("\n" + paint("🚀 바로 실행할까요? [y/N]: ", BOLD))
    except (KeyboardInterrupt, EOFError):
        print()
        return False
    return answer.strip().lower() in ("y", "yes")


def single_shot(query, config, args):
    env_info = detect_env()
    messages = [
        {"role": "system", "content": command_system_prompt(env_info)},
        {"role": "user", "content": query},
    ]

    if sys.stdout.isatty():
        sys.stdout.write(paint("⚡ AI 생각 중...", DIM) + "\r")
        sys.stdout.flush()
    try:
        content, _usage = _network_chat(messages, config)
    finally:
        clear_line()

    result = parse_command_json(content)
    cmd = result.get("command")
    cmd = cmd.strip() if isinstance(cmd, str) else ""
    exp = result.get("explanation")
    exp = exp.strip() if isinstance(exp, str) else ""
    breakdown = result.get("breakdown")
    breakdown = breakdown if isinstance(breakdown, list) else []

    if not cmd:
        raise AskError("적절한 명령어를 찾지 못했습니다. 질문을 조금 더 구체적으로 적어 보세요.")

    width = 51
    print(paint("╭" + "─" * width + "╮", CYAN))
    print(paint("│", CYAN) + f" {paint('질문:', BOLD)} {one_line(query, width - 8)}")
    print(paint("╰" + "─" * width + "╯", CYAN))
    print(f"  {paint('▶ 명령어:', BOLD)} {paint(cmd, GREEN, BOLD)}")
    if exp:
        print(f"  {paint('ℹ️  설명:', DIM)} {exp}")

    if args.explain:
        rows = [b for b in breakdown if isinstance(b, dict) and (b.get("flag") or b.get("desc"))]
        if rows:
            print(f"\n  {paint('[옵션 상세 해설]', BOLD, MAGENTA)}")
            for item in rows:
                print(f"    • {paint(str(item.get('flag', '')), CYAN, BOLD)}: {item.get('desc', '')}")
            print()

    if args.copy:
        if copy_to_clipboard(cmd):
            print(f"  {paint('📋 클립보드에 복사되었습니다!', GREEN)}")
        else:
            print(f"  {paint('⚠️  클립보드 도구를 찾을 수 없습니다.', YELLOW)}")

    if args.dry_run:
        return 0

    should_run = True if args.yes else confirm_run()
    if not should_run:
        print(paint("실행을 건너뛰었습니다.", YELLOW))
        return 0

    print(f"\n{paint('실행 중:', BOLD)} {paint(cmd, DIM)}\n")
    sys.stdout.flush()
    try:
        return subprocess.run(cmd, shell=True).returncode
    except KeyboardInterrupt:
        print(paint("\n중단되었습니다.", YELLOW))
        return 130
    except OSError as e:
        raise AskError(f"명령을 실행할 수 없습니다: {one_line(e)}")


# --- Chat mode --------------------------------------------------------------
def new_session(config):
    now = datetime.now()
    session = {
        "id": now.strftime("%Y%m%d-%H%M%S") + f"-{int(now.microsecond / 1000):03d}",
        "created": now.isoformat(timespec="seconds"),
        "updated": now.isoformat(timespec="seconds"),
        "provider": config.get("provider", ""),
        "model": config.get("model", ""),
        "messages": [],
    }
    return session


def save_session(session):
    if not session.get("messages"):
        return
    if len(session["messages"]) > 200:
        session["messages"] = session["messages"][-200:]
    session["updated"] = datetime.now().isoformat(timespec="seconds")
    path = os.path.join(SESSION_DIR, f"{session['id']}.json")
    if atomic_write_json(path, session):
        prune_sessions()


def prune_sessions():
    try:
        files = [os.path.join(SESSION_DIR, f) for f in os.listdir(SESSION_DIR) if f.endswith(".json")]
    except OSError:
        return
    if len(files) <= MAX_SESSIONS:
        return
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for path in files[MAX_SESSIONS:]:
        try:
            os.remove(path)
        except OSError:
            pass


def list_sessions(limit=10):
    try:
        names = [f for f in os.listdir(SESSION_DIR) if f.endswith(".json")]
    except OSError:
        return []
    items = []
    for name in names:
        path = os.path.join(SESSION_DIR, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        items.append((mtime, path))
    items.sort(reverse=True)
    sessions = []
    for _mtime, path in items[:limit]:
        data = read_json_dict(path)
        if not data:
            continue
        messages = data.get("messages") if isinstance(data.get("messages"), list) else []
        first_user = next((m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "user"), "")
        sessions.append({
            "id": data.get("id") or os.path.basename(path)[:-5],
            "updated": data.get("updated", ""),
            "provider": data.get("provider", ""),
            "model": data.get("model", ""),
            "count": len(messages),
            "preview": one_line(first_user, 40),
        })
    return sessions


def show_history():
    sessions = list_sessions()
    print()
    if not sessions:
        print(paint("  저장된 세션이 없습니다.", DIM))
        print(paint(f"  위치: {SESSION_DIR}", DIM))
        print()
        return
    print(f"  {paint('최근 세션', BOLD)} {paint(f'(최대 10개 · {SESSION_DIR})', DIM)}")
    for item in sessions:
        stamp = item["updated"].replace("T", " ")[:16] or "-"
        print(f"  • {paint(item['id'], CYAN)}  {stamp}  {item['provider']}/{item['model']}  {item['count']}개 메시지")
        if item["preview"]:
            print(f"      {paint(item['preview'], DIM)}")
    print()


def chat_help():
    print()
    print(f"  {paint('사용 가능한 명령', BOLD)}")
    rows = [
        ("/new", "새 세션 시작 (지금 대화는 저장됩니다)"),
        ("/history", "최근 저장된 세션 목록"),
        ("/limits", "오늘 사용량 · 한도 게이지"),
        ("/model [이름]", "모델 보기 또는 즉시 전환 (예: /model ollama, /model gpt-6-luna)"),
        ("/help", "이 도움말"),
        ("/exit, /quit", "종료 (Ctrl+C / Ctrl+D 도 됩니다)"),
    ]
    for cmd, desc in rows:
        pad = " " * max(1, 22 - disp_width(cmd))
        print(f"    {paint(cmd, CYAN, BOLD)}{pad}{desc}")
    print()
    print(paint("  그냥 문장을 입력하면 바로 대화가 이어집니다.", DIM))
    print()


def switch_model(config, arg):
    """Handle /model [name]. Returns the config (mutated) or raises AskError."""
    arg = arg.strip()
    if not arg:
        print()
        print(f"  현재: {paint(config.get('provider', ''), CYAN, BOLD)} / {config.get('model', '')}")
        print(f"  {paint('제공자 기본값', DIM)}")
        for name, info in PROVIDERS.items():
            if name == "custom":
                continue
            mark = "←" if name == config.get("provider") else " "
            key_note = "" if name == "ollama" else (" 키 있음" if config.get("keys", {}).get(name) or os.environ.get(info["env_key"], "") else " 키 필요")
            print(f"    {mark} {paint(name, CYAN)}: {info['default_model']}" + (paint(key_note, DIM) if key_note else ""))
        print()
        return config

    if arg.lower() in PROVIDERS:
        name = arg.lower()
        info = PROVIDERS[name]
        if name not in ("ollama", "custom"):
            has_key = bool(config.get("keys", {}).get(name) or os.environ.get(info["env_key"], "") or os.environ.get("ASK_API_KEY"))
            if not has_key:
                raise AskError(f"{name} 키가 없습니다 — `ask --config` 로 넣은 뒤 다시 전환하세요.")
        config["provider"] = name
        config["model"] = info["default_model"]
        config["endpoint"] = config.get("endpoint") if name == "custom" else info["endpoint"]
        config["api_key"] = config.get("keys", {}).get(name, "") or os.environ.get(info["env_key"], "")
        print(f"  {paint('✓ 제공자 전환:', GREEN)} {name} / {config['model']}")
    else:
        config["model"] = arg
        print(f"  {paint('✓ 모델 전환:', GREEN)} {config.get('provider')} / {arg}")
    save_config(config, quiet=True)
    return config


def chat_turn(session, config, text):
    """One user turn: send, print, persist. Errors stay inside the chat."""
    env_info = detect_env()
    system = {"role": "system", "content": CHAT_SYSTEM_PROMPT.format(**env_info)}
    history = [m for m in session["messages"] if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    messages = [system] + history[-MAX_HISTORY:] + [{"role": "user", "content": text}]

    if sys.stdout.isatty():
        sys.stdout.write(paint("⚡ 생각 중...", DIM) + "\r")
        sys.stdout.flush()
    try:
        content, usage = _network_chat(messages, config)
    except AskError as e:
        clear_line()
        print(paint("✖ " + str(e), RED))
        if e.code == 130:
            print(paint("  (세션은 그대로 이어집니다)", DIM))
        return
    finally:
        clear_line()

    session["messages"].append({"role": "user", "content": text})
    session["messages"].append({"role": "assistant", "content": content})
    session["provider"] = config.get("provider", "")
    session["model"] = config.get("model", "")
    save_session(session)

    print()
    print(content)
    if isinstance(usage, dict):
        total = _num(usage.get("total_tokens")) or (
            _num(usage.get("prompt_tokens")) + _num(usage.get("completion_tokens")) +
            _num(usage.get("input_tokens")) + _num(usage.get("output_tokens"))
        )
        if total:
            print(paint(f"  · {total:,} tokens", DIM))
    print()


def read_chat_line():
    if sys.stdin.isatty():
        return input(paint("ask", BOLD, CYAN) + paint("› ", DIM))
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    line = line.rstrip("\n")
    print(f"{paint('ask›', DIM)} {line}")
    return line


def chat_loop(config, initial=None):
    session = new_session(config)
    key_missing = config.get("provider") not in ("ollama", "custom") and not config.get("api_key")

    print()
    print(paint("╭ ask chat", BOLD, CYAN) + paint(f" ─ {config.get('provider')} · {config.get('model')}", DIM))
    print(paint("╰", CYAN) + paint("  /help 도움말 · /limits 사용량 · /exit 종료", DIM))
    if key_missing:
        print(paint("  ⚠ API 키가 없습니다. ask --config 로 넣거나 /model ollama 로 로컬 모델을 쓰세요.", YELLOW))
    print()

    if initial:
        print(paint(f"› {initial}", DIM))
        chat_turn(session, config, initial)

    while True:
        try:
            line = read_chat_line()
        except KeyboardInterrupt:
            print()
            print(paint("채팅을 종료합니다. 세션은 저장했습니다.", YELLOW))
            break
        except EOFError:
            print()
            break

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            head, _, rest = line.partition(" ")
            head = head.lower()
            if head in ("/exit", "/quit", "/q"):
                break
            if head == "/help":
                chat_help()
            elif head == "/new":
                save_session(session)
                session = new_session(config)
                print(paint(f"✓ 새 세션 시작: {session['id']}", GREEN))
            elif head == "/history":
                show_history()
            elif head == "/limits":
                render_limits(config)
            elif head == "/model":
                try:
                    config = switch_model(config, rest)
                    session["provider"] = config.get("provider", "")
                    session["model"] = config.get("model", "")
                except AskError as e:
                    print(paint("✖ " + str(e), RED))
            else:
                print(paint(f"  알 수 없는 명령: {head} — /help 를 입력해 보세요.", YELLOW))
            continue

        try:
            chat_turn(session, config, line)
        except KeyboardInterrupt:
            print()
            print(paint("  요청을 취소했습니다.", YELLOW))

    had_messages = bool(session.get("messages"))
    save_session(session)
    if had_messages:
        print(paint(f"  세션 저장: {os.path.join(SESSION_DIR, session['id'] + '.json')}", DIM))
    return 0


# --- Config wizard ----------------------------------------------------------
def prompt_input(label, default=""):
    try:
        value = input(label).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        raise AskError("설정을 취소했습니다.", code=130)
    return value or default


def run_config_wizard():
    print()
    print(paint("=== ask CLI 설정 마법사 ===", BOLD, CYAN))
    print()
    print("사용할 AI 제공자를 선택하세요:")
    print(f"  {paint('1', CYAN, BOLD)}) Groq     — 초고속·무료 티어 (openai/gpt-oss-120b) {paint('추천', GREEN)}")
    print(f"  {paint('2', CYAN, BOLD)}) Gemini   — 구글 무료 티어 (gemini-4-hydrogen)")
    print(f"  {paint('3', CYAN, BOLD)}) OpenAI   — 유료 (gpt-6.1-sol)")
    print(f"  {paint('4', CYAN, BOLD)}) DeepSeek — 유료·저렴 (deepseek-flash)")
    print(f"  {paint('5', CYAN, BOLD)}) Ollama   — 로컬 모델, API 키 불필요 (qwen3.5:9b) {paint('로컬 우선', MAGENTA)}")
    print(f"  {paint('6', CYAN, BOLD)}) 사용자 지정 — OpenAI 호환 엔드포인트 직접 입력")
    print()

    choice = prompt_input(paint("선택 [1-6] (기본: 1): ", BOLD), "1")
    provider_map = {"1": "groq", "2": "gemini", "3": "openai", "4": "deepseek", "5": "ollama", "6": "custom"}
    provider = provider_map.get(choice, "groq")
    info = PROVIDERS[provider]

    config = load_config()
    endpoint = info["endpoint"]
    api_key = ""

    if provider == "custom":
        endpoint = prompt_input(paint("엔드포인트 URL (예: http://192.168.0.10:11434/v1/chat/completions): ", BOLD))
        if not endpoint.startswith(("http://", "https://")):
            raise AskError("http:// 또는 https:// 로 시작하는 URL이 필요합니다.")
        api_key = prompt_input(paint("API 키 (없으면 그냥 Enter): ", BOLD))
    elif provider == "ollama":
        print(paint("  · Ollama는 내 기기에서 돌아갑니다 (무제한·키 없음).", DIM))
    else:
        api_key = prompt_input(paint(f"{info['label']} API 키 (나중에 넣어도 됩니다): ", BOLD))
        if not api_key:
            print(paint(f"  · 키를 비워 두면 환경변수 {info['env_key']} 또는 ASK_API_KEY 를 씁니다.", DIM))

    model = prompt_input(paint(f"모델 이름 (기본: {info['default_model']}): ", BOLD), info["default_model"])
    if provider == "ollama":
        print(paint(f"  · 미리 `ollama pull {model}` 로 모델을 받아 두세요.", DIM))

    keys = dict(config.get("keys", {}))
    if api_key:
        keys[provider] = api_key

    new_config = {
        "provider": provider,
        "model": model,
        "endpoint": endpoint,
        "api_key": api_key or keys.get(provider, ""),
        "keys": keys,
    }
    save_config(new_config)
    return 0


# --- Entry point ------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        prog="ask",
        description=f"터미널에서 말로 물어보고 바로 실행하는 초경량 AI 도구 (v{VERSION})",
        epilog=(
            "예시:\n"
            "  ask \"도커 안 쓰는 이미지 정리해줘\"     한 번 묻고 명령어 실행\n"
            "  ask chat                             대화형 채팅 (ask -c 와 같음)\n"
            "  ask --limits                         오늘 사용량·한도 보기\n"
            "  ask --config                         API 키·모델 설정 마법사"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("prompt", nargs="*", help="수행할 작업을 자연어로 입력 ('chat' 한 단어만 주면 채팅 모드)")
    parser.add_argument("-y", "--yes", action="store_true", help="확인 없이 바로 실행")
    parser.add_argument("-d", "--dry-run", action="store_true", help="명령어만 보여주고 실행하지 않음")
    parser.add_argument("-e", "--explain", action="store_true", help="명령어 옵션 상세 해설 출력")
    parser.add_argument("-k", "--copy", action="store_true", help="생성된 명령어를 클립보드에 복사")
    parser.add_argument("-c", "--chat", action="store_true", help="대화형 채팅 모드 (ask chat 과 같음)")
    parser.add_argument("-l", "--limits", action="store_true", help="오늘 사용량과 한도 게이지 보기")
    parser.add_argument("--config", action="store_true", help="API 키·제공자 설정 마법사 (구 -c)")
    parser.add_argument("-v", "--version", action="store_true", help="버전 출력")
    return parser


def main(argv=None):
    setup_console()
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    words = list(args.prompt or [])

    # `ask chat` (one bare word) opens chat; `ask "chat something"` stays a query.
    chat_requested = bool(args.chat)
    if not chat_requested and len(words) == 1 and words[0].strip().lower() == "chat":
        chat_requested = True
        words = []

    if args.version:
        print(f"{paint('ask-cli', BOLD)} v{VERSION} ⚡ The Zero-Dependency Terminal AI Copilot")
        return 0

    if args.config:
        return run_config_wizard() or 0

    config = load_config()

    if args.limits:
        render_limits(config)
        return 0

    if chat_requested:
        return chat_loop(config, initial=" ".join(words).strip() or None)

    if not words:
        parser.print_help()
        return 0

    return single_shot(" ".join(words).strip(), config, args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AskError as err:
        sys.stderr.write(paint("❌ ", RED) + str(err) + "\n")
        sys.exit(err.code)
    except KeyboardInterrupt:
        sys.stderr.write("\n" + paint("취소되었습니다.", YELLOW) + "\n")
        sys.exit(130)
    except BrokenPipeError:
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        sys.exit(0)
