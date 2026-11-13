#!/usr/bin/env python3
"""
ask - The Zero-Dependency Terminal AI Copilot
Works on Linux, macOS, Termux, and WSL.
Pure Python standard library (no external pip dependencies).
v1.1.1: Stabilized default models and made network/API errors fail with one clean line.
"""

import sys
import os
import json
import platform
import subprocess
import argparse
import urllib.request
import urllib.error
import socket
import shutil

VERSION = "1.1.1"
REQUEST_TIMEOUT = 20
CONFIG_DIR = os.path.expanduser("~/.config/ask")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
DIM = "\033[2m"

DEFAULT_CONFIG = {
    "provider": "groq",
    "api_key": "",
    "model": "llama-3.3-70b-versatile",
    "endpoint": "https://api.groq.com/openai/v1/chat/completions"
}

PROVIDERS = {
    "groq": {
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "env_key": "GROQ_API_KEY"
    },
    "openai": {
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY"
    },
    "deepseek": {
        "endpoint": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY"
    },
    "ollama": {
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "default_model": "llama3.2",
        "env_key": ""
    }
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception:
            pass

    provider_env = PROVIDERS.get(config.get("provider", ""), {}).get("env_key", "")
    env_key = os.environ.get("ASK_API_KEY") or (os.environ.get(provider_env) if provider_env else "")
    if env_key and not config.get("api_key"):
        config["api_key"] = env_key

    return config

def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"{GREEN}✓ 설정이 저장되었습니다: {CONFIG_PATH}{RESET}")

def run_config_wizard():
    print(f"\n{BOLD}{CYAN}=== ask CLI 설정 마법사 ==={RESET}\n")
    print("사용할 AI 제공자를 선택하세요:")
    print("1) Groq (초고속, 무료 티어 제공 - 추천)")
    print("2) OpenAI (ChatGPT)")
    print("3) DeepSeek")
    print("4) Ollama (로컬 LLM, API 키 불필요)")
    
    choice = input(f"{BOLD}선택 [1-4] (기본: 1): {RESET}").strip() or "1"
    provider_map = {"1": "groq", "2": "openai", "3": "deepseek", "4": "ollama"}
    provider_name = provider_map.get(choice, "groq")
    p_info = PROVIDERS[provider_name]

    api_key = ""
    if provider_name != "ollama":
        api_key = input(f"{BOLD}{provider_name.upper()} API 키: {RESET}").strip()

    model = input(f"{BOLD}모델 이름 (기본: {p_info['default_model']}): {RESET}").strip() or p_info["default_model"]

    cfg = {
        "provider": provider_name,
        "api_key": api_key,
        "model": model,
        "endpoint": p_info["endpoint"]
    }
    save_config(cfg)
    sys.exit(0)

def detect_env():
    is_termux = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")
    shell_name = os.path.basename(os.environ.get("SHELL", "bash"))
    os_name = "Android (Termux)" if is_termux else f"{platform.system()} {platform.release()}"
    return {
        "os": os_name,
        "shell": shell_name,
        "is_termux": is_termux
    }

def copy_to_clipboard(text):
    """Copies text to system clipboard across Termux, Linux, macOS, WSL."""
    if shutil.which("termux-clipboard-set"):
        p = subprocess.Popen(["termux-clipboard-set"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    elif shutil.which("pbcopy"):
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    elif shutil.which("wl-copy"):
        p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    elif shutil.which("xclip"):
        p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    elif shutil.which("clip.exe"):
        p = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
        return True
    return False

def one_line(text, limit=200):
    """Collapses any text (multi-line JSON bodies included) into a single clean line."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"

def clean_http_error(e):
    """Pulls the human-readable message out of an HTTPError body, on one line."""
    try:
        body = e.read().decode("utf-8", "replace")
    except Exception:
        body = ""
    try:
        msg = json.loads(body)["error"]["message"]
    except Exception:
        msg = body or str(getattr(e, "reason", "")) or "알 수 없는 오류"
    return one_line(msg)

def query_ai(prompt, config, env_info, explain_mode=False):
    api_key = config.get("api_key")
    endpoint = config.get("endpoint")
    model = config.get("model")

    if not api_key and config.get("provider") != "ollama":
        print(f"{YELLOW}⚠️  API 키가 설정되지 않았습니다.{RESET}")
        print(f"다음 중 하나를 실행하세요:")
        print(f"  1. {CYAN}ask --config{RESET} (설정 마법사 실행)")
        print(f"  2. {CYAN}export ASK_API_KEY='your-key'{RESET} (환경변수 설정)\n")
        sys.exit(1)

    system_prompt = f"""You are a precise command-line assistant.
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

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"ask-cli/{VERSION}"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    # --- Network: every failure path prints exactly one line ---
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
            raw = res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"{RED}❌ API 오류 ({e.code}): {clean_http_error(e)}{RESET}")
        sys.exit(1)
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            print(f"{RED}❌ 응답 시간 초과 ({REQUEST_TIMEOUT}초): 네트워크 상태를 확인하고 다시 시도하세요.{RESET}")
        else:
            print(f"{RED}❌ 네트워크 오류: {one_line(reason)} — 엔드포인트({endpoint})와 연결을 확인하세요.{RESET}")
        sys.exit(1)
    except (socket.timeout, TimeoutError):
        print(f"{RED}❌ 응답 시간 초과 ({REQUEST_TIMEOUT}초): 네트워크 상태를 확인하고 다시 시도하세요.{RESET}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}취소되었습니다.{RESET}")
        sys.exit(130)
    except Exception as e:
        print(f"{RED}❌ 요청 실패: {one_line(e)}{RESET}")
        sys.exit(1)

    # --- Response: shape failures get their own clean message ---
    try:
        res_data = json.loads(raw)
        content = res_data["choices"][0]["message"]["content"].strip()
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        print(f"{RED}❌ 응답을 해석할 수 없습니다: 예상과 다른 응답 형식입니다 (모델: {model}).{RESET}")
        sys.exit(1)

    # Clean possible markdown block
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print(f"{RED}❌ 모델이 명령어를 JSON으로 돌려주지 않았습니다. 다시 시도해 보세요.{RESET}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="ask",
        description="터미널에서 말로 물어보고 바로 실행하는 초경량 AI 도구 (v1.1.1)"
    )
    parser.add_argument("prompt", nargs="*", help="수행하고 싶은 작업을 자연어로 입력 (예: 도커 컨테이너 정리해줘)")
    parser.add_argument("-y", "--yes", action="store_true", help="확인 절차 없이 바로 명령어 실행")
    parser.add_argument("-d", "--dry-run", action="store_true", help="명령어와 설명만 출력하고 실행하지 않음")
    parser.add_argument("-e", "--explain", action="store_true", help="명령어 옵션 및 각 플래그의 상세 해설 출력")
    parser.add_argument("-k", "--copy", action="store_true", help="생성된 명령어를 클립보드에 자동 복사")
    parser.add_argument("-c", "--config", action="store_true", help="API 키 및 제공자 설정 마법사 실행")
    parser.add_argument("-v", "--version", action="store_true", help="버전 정보 출력")

    args = parser.parse_args()

    if args.version:
        print(f"{BOLD}ask-cli{RESET} v{VERSION} ⚡ The Zero-Dependency Terminal AI Copilot")
        sys.exit(0)

    if args.config:
        run_config_wizard()

    if not args.prompt:
        parser.print_help()
        sys.exit(0)

    user_query = " ".join(args.prompt).strip()
    config = load_config()
    env_info = detect_env()

    # Query AI
    sys.stdout.write(f"{DIM}⚡ AI 생각 중...{RESET}\r")
    sys.stdout.flush()
    result = query_ai(user_query, config, env_info, explain_mode=args.explain)
    sys.stdout.write(" " * 25 + "\r")
    sys.stdout.flush()

    cmd = result.get("command", "").strip()
    exp = result.get("explanation", "").strip()
    breakdown = result.get("breakdown", [])

    if not cmd:
        print(f"{RED}적절한 명령어를 찾지 못했습니다.{RESET}")
        sys.exit(1)

    # Print Result
    print(f"{CYAN}╭───────────────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}질문:{RESET} {user_query}")
    print(f"{CYAN}╰───────────────────────────────────────────────────╯{RESET}")
    print(f"  {BOLD}▶ 명령어:{RESET} {GREEN}{BOLD}{cmd}{RESET}")
    if exp:
        print(f"  {DIM}ℹ️  설명:{RESET} {exp}")

    # Flag-by-flag explain mode
    if args.explain and breakdown:
        print(f"\n  {BOLD}{MAGENTA}[옵션 상세 해설]{RESET}")
        for item in breakdown:
            flag = item.get("flag", "")
            desc = item.get("desc", "")
            print(f"    • {CYAN}{BOLD}{flag}{RESET}: {desc}")
        print()

    # Clipboard copy
    if args.copy:
        if copy_to_clipboard(cmd):
            print(f"  {GREEN}📋 클립보드에 복사되었습니다!{RESET}")
        else:
            print(f"  {YELLOW}⚠️  클립보드 도구를 찾을 수 없습니다.{RESET}")

    if args.dry_run:
        sys.exit(0)

    if args.yes:
        should_run = True
    else:
        try:
            choice = input(f"\n{BOLD}🚀 바로 실행할까요? [y/N]: {RESET}").strip().lower()
            should_run = (choice == "y" or choice == "yes")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}취소되었습니다.{RESET}")
            sys.exit(0)

    if should_run:
        print(f"\n{BOLD}실행 중:{RESET} {DIM}{cmd}{RESET}\n")
        sys.stdout.flush()
        ret = subprocess.run(cmd, shell=True)
        sys.exit(ret.returncode)
    else:
        print(f"{YELLOW}실행을 건너뛰었습니다.{RESET}")

if __name__ == "__main__":
    main()
