# ⚡ ask-cli

> **The Zero-Dependency Terminal AI Copilot**  
> 터미널에서 한국어로 묻고, 바로 실행하는 가장 가벼운 AI 도구.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version: 1.1.0](https://img.shields.io/badge/version-1.1.0-blue.svg)](#)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-brightgreen.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)](#)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Termux%20%7C%20macOS%20%7C%20WSL-orange.svg)](#)

---

## 📸 미리보기

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

실행 중: docker system prune -a --volumes
...
Total reclaimed space: 1.42GB
```

---

## ✨ 왜 `ask` 인가요?

- 🪶 **의존성 0개 (Zero Dependencies):** 외부 라이브러리(`pip`) 설치 필요 없이 파이썬 기본 내장 모듈만으로 동작합니다. 빌드 에러 걱정 끝!
- 📱 **안드로이드 Termux 공식 지원:** 스마트폰이나 태블릿(Termux)에서도 PC와 100% 동일하게 쌩쌩 돌아갑니다.
- ⚡️ **압도적인 속도:** Groq 초고속 무료 티어(`llama-3.3-70b-versatile`), OpenAI(`gpt-6-luna`), DeepSeek(`deepseek-chat`), 로컬 Ollama까지 완벽 지원 (보통 1초 안에 응답).
- 🔍 **옵션 상세 해설 (-e):** 초보자도 안심하고 쓸 수 있게 각 명령어 플래그의 역할을 한국어로 꼼꼼히 분해해 줍니다.
- 📋 **클립보드 복사 (-k):** Termux, Linux, macOS, WSL 어디서든 명령어를 클립보드에 원클릭으로 담아줍니다.
- 🛡 **안전 제일:** 위험할 수 있는 쉘 명령어를 실행하기 전 반드시 확인 절차(`[y/N]`)를 거칩니다.

---

## 🚀 빠른 시작 (1초 설치)

터미널에 아래 명령어를 복사해서 붙여넣으세요:

```bash
curl -fsSL https://raw.githubusercontent.com/gw140427-rgb/ask-cli/main/install.sh | bash
```

### 최초 설정

설치 후 설정 마법사를 실행해 무료 API 키를 등록합니다:

```bash
ask --config
```

> **꿀팁:** [Groq](https://console.groq.com/keys)에서 무료 API 키를 발급받아 등록하면 0.3초 만에 번개처럼 응답합니다! (OpenAI, DeepSeek, Ollama도 지원)

### 설정 파일

설정은 `~/.config/ask/config.json`에 저장됩니다. 마법사 없이 직접 고치거나 환경변수로 넣어도 됩니다.

```bash
export ASK_API_KEY="gsk_..."        # 어떤 제공자든 이 이름으로 넣으면 됩니다
# export GROQ_API_KEY=... / OPENAI_API_KEY=... / DEEPSEEK_API_KEY=... 도 인식합니다
```

| 제공자 | 기본 모델 | 무료 사용 |
| --- | --- | --- |
| `groq` | `llama-3.3-70b-versatile` | 무료 플랜 지원 |
| `openai` | `gpt-6-luna` | 유료 |
| `deepseek` | `deepseek-chat` | 유료 |
| `ollama` | `llama3.2` | 로컬, 키 불필요 |

---

## 💡 사용법

### 1. 기본 질문
```bash
ask "8080 포트 쓰고 있는 프로세스 찾아서 죽여줘"
ask "현재 폴더에서 가장 큰 용량 차지하는 파일 상위 5개"
ask "최근 3개 커밋 하나로 합치는 깃 명령어"
```

### 2. 옵션 상세 해설 모드 (`-e`, v1.1 신기능)
명령어 옵션들이 각각 무엇을 뜻하는지 배우고 싶을 때:
```bash
ask -e "tar.gz 압축 풀기"
```

### 3. 클립보드 복사 (`-k`, v1.1 신기능)
실행하지 않고 명령어만 클립보드로 복사하고 싶을 때:
```bash
ask -k "깃 이전 커밋으로 강제 되돌리기"
```

### 4. 바로 실행 (`-y`)
확인 절차 없이 바로 실행하고 싶을 때:
```bash
ask -y "nginx 서비스 재시작해줘"
```

### 5. 명령어만 출력 (`-d`)
스크립트 등에서 파이프라인으로 연동할 때:
```bash
ask -d "현재 IP 주소 확인"
```

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
