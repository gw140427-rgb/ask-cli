# ⚡ ask-cli

> **The Zero-Dependency Terminal AI Copilot**  
> 터미널에서 한국어로 묻고, 바로 실행하는 가장 가벼운 AI 도구.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: 1.2.0](https://img.shields.io/badge/version-1.2.0-blue.svg)](#)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-brightgreen.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](#)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Termux%20%7C%20macOS%20%7C%20WSL-orange.svg)](#)

---

## 📸 미리보기

**① 한 번 묻고 바로 실행**

```bash
$ ask -e "도커 안 쓰는 컨테이너랑 이미지 싹 청소해줘"

╭───────────────────────────────────────────────────╮
│ 질문: 도커 안 쓰는 컨테이너랑 이미지 싹 청소해줘
╰───────────────────────────────────────────────────╯
  ▶ 명령어: docker system prune -a --volumes
  ℹ️  설명: 중지된 모든 컨테이너와 미사용 이미지, 볼륨을 완전히 삭제합니다.

  [옵션 상세 해설]
    • system prune: 미사용 도커 리소스 일괄 정리
    • -a (--all): 태그 없는 이미지뿐 아니라 모든 미사용 이미지 포함
    • --volumes: 컨테이너와 연결되지 않은 미사용 볼륨까지 삭제

🚀 바로 실행할까요? [y/N]: y
```

**② 대화형 채팅 (v1.2 신기능)**

```bash
$ ask chat
╭ ask chat ─ ollama · qwen3.5:9b
╰  /help 도움말 · /limits 사용량 · /exit 종료

ask› 방금 만든 스크립트에 실행 권한 주는 명령어 뭐야?
  chmod +x 파일이름.sh  ← 이 한 줄이면 됩니다.
  · 214 tokens

ask› /limits
──────────────────────────────────────────────────────
 ⚡ ask-cli 사용량 · 2026-11-14 (토)
──────────────────────────────────────────────────────
  제공자   ollama · qwen3.5:9b
  오늘 요청 4회  (성공 4 / 실패 0)
  한도     무제한 (로컬 모델) — 내 기기에서 돌아갑니다
  토큰     입력 2,410 / 출력 380  (API 보고값)
──────────────────────────────────────────────────────
```

---

## ✨ 왜 `ask` 인가요?

- 🪶 **의존성 0개 (Zero Dependencies):** 외부 라이브러리(`pip`) 없이 파이썬 기본 모듈만으로 동작합니다.
- 🏠 **로컬 우선 (Local-First):** `ollama`만 있으면 API 키도, 요금도, 한도도 없습니다. 폰에서도 돕니다.
- 📱 **안드로이드 Termux 공식 지원:** 설치 스크립트가 Termux의 `$PREFIX/bin`에 바로 넣습니다.
- 💬 **대화형 채팅 (`ask chat`):** 여러 턴으로 이어 묻고, 세션은 `~/.config/ask/sessions/`에 저장됩니다.
- 📊 **사용량·한도 게이지 (`--limits`):** 오늘 몇 번 불렀는지, 토큰은 얼마나 썼는지 한눈에.
- 🧠 **2026 현역 모델 기본값:** 폐기된 모델이 걸려 있으면 새 기본값으로 자동 갱신합니다.
- ⚡️ **빠른 응답:** Groq, Gemini 무료 티어에서 1초 안쪽 응답.
- 🔍 **옵션 상세 해설 (`-e`) · 클립보드 복사 (`-k`) · 확인 후 실행 (`[y/N]`)** 은 그대로.

---

## 🚀 빠른 시작 (1초 설치)

```bash
curl -fsSL https://raw.githubusercontent.com/gw140427-rgb/ask-cli/main/install.sh | bash
```

### 최초 설정

```bash
ask --config
```

```
1) Groq     — 초고속·무료 티어 (openai/gpt-oss-120b)  추천
2) Gemini   — 구글 무료 티어 (gemini-4-hydrogen)
3) OpenAI   — 유료 (gpt-6.1-sol)
4) DeepSeek — 유료·저렴 (deepseek-flash)
5) Ollama   — 로컬 모델, API 키 불필요 (qwen3.5:9b)  로컬 우선
6) 사용자 지정 — OpenAI 호환 엔드포인트 직접 입력
```

> **꿀팁:** [Groq](https://console.groq.com/keys) 무료 키나 Gemini 무료 키로 시작하고, 기기에서 돌릴 수 있으면 5번 Ollama를 고르세요. 한도·요금이 아예 없습니다.

### 설정 파일

`~/.config/ask/config.json` (권한 `600`) — 마법사 없이 직접 고쳐도 됩니다.

```json
{
  "provider": "ollama",
  "model": "qwen3.5:9b",
  "endpoint": "http://localhost:11434/v1/chat/completions",
  "api_key": "",
  "keys": { "groq": "gsk_...", "gemini": "AIza..." },
  "timeout": 180,
  "daily_limit": 1000
}
```

| 키 | 뜻 |
| --- | --- |
| `keys` | 제공자별 API 키. `/model` 로 제공자를 바꿔도 키가 유지됩니다 |
| `timeout` | 요청 제한 시간(초). 기본 30초, 로컬 Ollama는 180초 |
| `daily_limit` | `--limits` 게이지의 **참고** 하루 한도 (실제 제공자 정책과 다를 수 있음) |
| `temperature` | 직접 넣을 때만 전송합니다 (추론 모델은 이 값을 거부하는 경우가 있음) |
| `extra` | 엔드포인트별 추가 파라미터를 직접 넣을 때 |

환경변수도 됩니다.

```bash
export ASK_API_KEY="gsk_..."        # 어떤 제공자든 이 이름으로 넣을 수 있음
# export GROQ_API_KEY=... / GEMINI_API_KEY=... / OPENAI_API_KEY=... / DEEPSEEK_API_KEY=...
export ASK_HOME="$HOME/.config/ask" # 설정 폴더를 옮길 때 (기본값 그대로면 불필요)
```

---

## 🧠 2026 기본 모델 (2026-11-14 확인)

| 제공자 | 기본 모델 | 무료 | 메모 |
| --- | --- | --- | --- |
| `ollama` | `qwen3.5:9b` | 로컬·무제한 | 키 불필요. `qwen3.5:2b`/`4b`는 더 가볍습니다 |
| `gemini` | `gemini-4-hydrogen` | 무료 티어 | 2026-11-12 공개. 대안 `gemini-4-carbon`, `gemini-4-argon` |
| `groq` | `openai/gpt-oss-120b` | 무료 티어 | 대안 `openai/gpt-oss-20b`(더 빠름), `qwen/qwen3.8-27b` |
| `openai` | `gpt-6.1-sol` | 유료 | 대안 `gpt-6-astra`(최상위), `gpt-6-luna`(저렴) |
| `deepseek` | `deepseek-flash` | 유료 | thinking은 기본 OFF로 요청합니다(구 `deepseek-chat`과 같은 지연) |

**폐기된 모델은 자동으로 바뀝니다.** v1.1.1 이하 설정에 남아 있던 값은 첫 실행 때 새 기본값으로 갱신되고 한 줄로 알려줍니다.

| 폐기된 모델 | 상태 | 대체 |
| --- | --- | --- |
| `gpt-5`, `gpt-5-mini` | 2026-12-11 종료 예정 | `gpt-6.1-sol` / `gpt-6-luna` |
| `gpt-4o-mini` | 지원 종료 | `gpt-6.1-sol` |
| `llama-3.3-70b-versatile` | 2026-08-16 종료 | `openai/gpt-oss-120b` |
| `deepseek-chat` / `deepseek-reasoner` | 2026-07-24 종료 (400 Model Not Exist) | `deepseek-flash` |
| `llama3.2` (Ollama) | 구세대 | `qwen3.5:9b` |

---

## 💡 사용법

### 1. 단발 질문 (명령어 모드)

```bash
ask "8080 포트 쓰고 있는 프로세스 찾아서 죽여줘"
ask "현재 폴더에서 가장 큰 용량 차지하는 파일 상위 5개"
ask -e "tar.gz 압축 풀기"     # 옵션 상세 해설
ask -k "깃 이전 커밋으로 강제 되돌리기"   # 클립보드 복사
ask -d "현재 IP 주소 확인"    # 명령어만 출력 (스크립트 연동)
ask -y "nginx 서비스 재시작해줘"         # 확인 없이 실행
```

### 2. 대화형 채팅 (`ask chat` / `ask -c`)

```bash
ask chat              # 대화 시작
ask -c                # 같은 뜻 (구 -c 는 --config 로 옮겼습니다)
ask -c "첫 질문"       # 첫 질문을 바로 던지고 대화로 진입
ask "chat 로그가 뭐야" # 'chat' 뒤에 말이 붙으면 채팅이 아니라 일반 질문입니다
```

| 명령 | 하는 일 |
| --- | --- |
| `/new` | 새 세션 시작 (지금 대화는 저장됨) |
| `/history` | 최근 저장된 세션 10개 |
| `/limits` | 오늘 사용량·한도 게이지 |
| `/model` | 현재 모델과 제공자별 기본값 보기 |
| `/model ollama` | 제공자 전환 (키가 없으면 로컬로) |
| `/model gpt-6-luna` | 모델만 교체 |
| `/help` | 명령 목록 |
| `/exit` `/quit` | 종료 (Ctrl+C / Ctrl+D 도 됨) |

- 세션은 `~/.config/ask/sessions/<id>.json`에 턴마다 저장되고, 최근 50개만 남깁니다.
- 대화 오류(키 오류·한도 초과·타임아웃)는 채팅을 끝내지 않고 **한 줄로 알려주고 계속**됩니다.
- 문맥은 최근 24개 메시지만 모델로 보냅니다(토큰·지연 절약).

### 3. 사용량·한도 보기

```bash
ask --limits      # 또는 ask -l, 채팅 안에서는 /limits
```

- `~/.config/ask/usage.json`에 날짜별로 요청 수·성공/실패·토큰을 쌓습니다(최근 180일).
- API가 `usage`를 주면 그 값을, 없으면 글자 수로 추정해 `(추정치)`로 표시합니다.
- `ollama`는 **무제한 (로컬 모델)** 로 나오고, 오늘 로컬 호출 수는 그대로 집계됩니다.

### 4. 로컬 모델 (Ollama)

```bash
# 1) Ollama 설치: https://ollama.com/download  (Termux 는 pkg install ollama 후 ollama serve)
ollama pull qwen3.5:9b
ollama serve

# 2) ask 를 로컬로 전환
ask --config      # 5번 선택
# 또는 채팅에서: /model ollama
```

- 엔드포인트 기본: `http://localhost:11434/v1/chat/completions`
- 다른 기기·다른 포트에서 돌리면 `ask --config` → 6번(사용자 지정)에서 URL을 넣으세요.
- 로컬은 타임아웃이 180초로 넉넉합니다 (`config.json`의 `timeout`으로 조정).

---

## 🆕 변경 내역

### v1.2.0 — 대화 · 사용량 · 로컬 모델
**신기능**
- `ask chat` / `ask -c` 대화형 채팅: 멀티턴, 세션 자동 저장(`~/.config/ask/sessions/`), `/new` `/history` `/limits` `/model` `/help` `/exit`
- `ask --limits` / `/limits`: 오늘 요청·토큰, ASCII 게이지, 로컬 모델은 `무제한 (로컬 모델)`
- 로컬 우선 지원: `ollama`(키 불필요) + 사용자 지정 OpenAI 호환 엔드포인트를 마법사에 추가
- 2026 현역 라인업: `gemini-4-hydrogen`, `openai/gpt-oss-120b`, `gpt-6.1-sol`, `deepseek-flash`, `qwen3.5:9b`

**버그 수정**
- `ask chat`(서브커맨드)과 `ask "chat …"`(질의)가 충돌하지 않도록 정리. 이전 `-c`(설정)는 `--config`로 이동
- 손상되거나 잘린 `config.json`/`usage.json`을 백업하고 기본값으로 계속 (이전에는 조용히 무시)
- 빈 응답·`null` content·형식이 다른 응답을 각각 한 줄 오류로 처리 (이전엔 `AttributeError` 트레이스백)
- HTTP 401/403/404/429/5xx, 모델 오류(400)를 원인별 한 줄 안내로 분리
- 설정 저장을 원자적으로(temp + `os.replace`) 바꾸고 `config.json` 권한을 `600`으로 (API 키 노출 방지)
- `Ctrl+C`/`Ctrl+D`(EOF) 처리: 명령 모드·채팅·마법사 어디서든 트레이스백 없이 종료
- UTF-8 고정: `LANG=C` 같은 환경이나 Termux에서도 한글 출력이 깨지거나 죽지 않음
- 모델이 JSON 앞뒤에 설명·코드펜스를 붙여도 명령어를 추출
- 타임아웃·`temperature`·`extra` 파라미터를 설정으로 조정 가능 (추론 모델의 400 회피)
- `install.sh`: Termux는 `$PREFIX/bin`에 설치해 PATH 편집 불필요, 재설치해도 PATH 중복 없음, 임시 파일 후 원자적 교체, 받은 파일 검증(`#!`·서명), python3 없음/다운로드 실패를 명확히 안내, `ASK_INSTALL_DIR`/`ASK_INSTALL_SRC` 지원
- 클립보드 도구 선택지 확대(`xsel` 포함)와 실패 시 안전한 안내

<details>
<summary>이전 버전</summary>

**v1.1.1** — 모델 안정화, 네트워크/API 오류를 한 줄로, `Ctrl+C` 정리  
**v1.1.0** — 옵션 상세 해설 모드(`-e`), 클립보드 복사(`-k`), 모델 지원 확장

</details>

---

## 🧪 검증

`v1.2.0`은 실제 네트워크 없이 모의 OpenAI 호환 서버로 검사했습니다.

```bash
python3 -m py_compile ask.py     # 구문
bash -n install.sh               # 설치 스크립트
python3 ask.py --version         # 1.2.0
python3 ask.py --limits          # 게이지
ask chat  <<< $'/limits\n/new\n/help\n/exit\n'
```

45개 항목 통과: 채팅 슬래시 명령·세션 저장, 사용량 집계, 손상 파일 복구, 401/429/400/timeout/빈 응답 문구, 모델 자동 갱신, 페이로드 계약(`temperature` 미전송·`thinking:disabled`·`reasoning_effort`), `LANG=C` 한글 출력, `install.sh` Termux/재설치/실패 경로.

---

## 🛠 지원 환경

- **Linux** (Ubuntu, Debian, Fedora, Arch 등)
- **Android** (Termux, PRoot)
- **macOS** (zsh / bash)
- **Windows** (WSL2, Git Bash)

---

## ⭐️ Star History

이 프로젝트가 마음에 드셨다면 상단의 **Star ⭐️**를 눌러주세요! 개발자에게 큰 힘이 됩니다.

## 📄 라이선스

MIT License © 2026 [gw140427-rgb](https://github.com/gw140427-rgb)
