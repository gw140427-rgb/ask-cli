#!/usr/bin/env bash
# ask-cli installer — Linux / macOS / Termux / WSL
# usage:
#   curl -fsSL https://raw.githubusercontent.com/gw140427-rgb/ask-cli/main/install.sh | bash
#
# env overrides (optional):
#   ASK_INSTALL_DIR   install folder (default: ~/.local/bin, or $PREFIX/bin on Termux)
#   ASK_INSTALL_SRC   install from a local ask.py instead of downloading (offline/testing)
#   ASK_BRANCH        git branch to fetch (default: main)
set -eu

REPO="https://github.com/gw140427-rgb/ask-cli"
BRANCH="${ASK_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/gw140427-rgb/ask-cli/${BRANCH}"

info() { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m오류: %s\033[0m\n' "$*" >&2; exit 1; }

is_termux() {
    case "${PREFIX:-}" in
        *com.termux*) return 0 ;;
    esac
    [ -d "/data/data/com.termux" ] && return 0
    return 1
}

info "==> ask-cli 설치를 시작합니다..."

# 1. Python 3 ---------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3가 없습니다. (Termux: pkg install python / Debian·Ubuntu: sudo apt install python3)"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)' 2>/dev/null; then
    die "Python 3.7 이상이 필요합니다. 현재: $(python3 -V 2>&1)"
fi

# 2. Install location -------------------------------------------------------
if [ -n "${ASK_INSTALL_DIR:-}" ]; then
    TARGET_DIR="$ASK_INSTALL_DIR"
elif is_termux && [ -n "${PREFIX:-}" ] && [ -d "$PREFIX/bin" ]; then
    # Termux: $PREFIX/bin is already on PATH, so no shell rc editing is needed.
    TARGET_DIR="$PREFIX/bin"
else
    TARGET_DIR="$HOME/.local/bin"
fi
TARGET_BIN="$TARGET_DIR/ask"

mkdir -p "$TARGET_DIR" 2>/dev/null || die "$TARGET_DIR 폴더를 만들 수 없습니다."
[ -w "$TARGET_DIR" ] || die "$TARGET_DIR 에 쓸 권한이 없습니다. ASK_INSTALL_DIR 로 다른 경로를 지정하세요."

# 3. Fetch ask.py (temp file first, so a broken download never leaves half a script)
TMP_FILE="$TARGET_DIR/.ask.tmp.$$"
cleanup() { rm -f "$TMP_FILE"; }
trap cleanup EXIT INT TERM

if [ -n "${ASK_INSTALL_SRC:-}" ]; then
    info "==> 로컬 파일에서 설치: $ASK_INSTALL_SRC"
    cp "$ASK_INSTALL_SRC" "$TMP_FILE" || die "복사 실패: $ASK_INSTALL_SRC"
else
    info "==> 최신 ask.py 다운로드 중... ($BRANCH)"
    downloaded=0
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 2 --connect-timeout 15 "$RAW/ask.py" -o "$TMP_FILE" && downloaded=1 || downloaded=0
    fi
    if [ "$downloaded" -eq 0 ] && command -v wget >/dev/null 2>&1; then
        wget -qO "$TMP_FILE" "$RAW/ask.py" && downloaded=1 || downloaded=0
    fi
    if [ "$downloaded" -eq 0 ]; then
        if is_termux; then
            die "다운로드 실패. curl/wget 설치 후 다시 시도하세요: pkg install curl"
        fi
        die "다운로드 실패. 네트워크와 $RAW/ask.py 접근 가능 여부를 확인하세요."
    fi
fi

[ -s "$TMP_FILE" ] || die "받은 파일이 비어 있습니다. 잠시 후 다시 시도하세요."
head -n 1 "$TMP_FILE" | grep -q '^#!' || die "받은 파일이 ask.py 가 아닌 것 같습니다. 설치를 중단합니다."
grep -q 'ask-cli' "$TMP_FILE" || die "받은 파일에서 ask-cli 서명을 찾지 못했습니다. 설치를 중단합니다."

mv -f "$TMP_FILE" "$TARGET_BIN" || die "$TARGET_BIN 에 설치하지 못했습니다."
chmod +x "$TARGET_BIN"
trap - EXIT INT TERM

# 4. PATH (skipped on Termux, where $PREFIX/bin is already in PATH) ---------
case ":${PATH}:" in
    *":$TARGET_DIR:"*) PATH_OK=1 ;;
    *) PATH_OK=0 ;;
esac

if [ "$PATH_OK" -eq 0 ]; then
    RC_FILE=""
    case "$(basename "${SHELL:-bash}")" in
        zsh) RC_FILE="$HOME/.zshrc" ;;
        bash) RC_FILE="$HOME/.bashrc" ;;
        *) [ -f "$HOME/.profile" ] && RC_FILE="$HOME/.profile" ;;
    esac
    [ -n "$RC_FILE" ] || RC_FILE="$HOME/.profile"
    touch "$RC_FILE" 2>/dev/null || true

    if ! grep -qs "ASK_CLI_PATH" "$RC_FILE"; then
        {
            printf '\n# ASK_CLI_PATH — added by ask-cli installer\n'
            printf 'export PATH="%s:$PATH"\n' "$TARGET_DIR"
        } >> "$RC_FILE" && warn "==> PATH에 $TARGET_DIR 를 추가했습니다 ($RC_FILE)"
    else
        warn "==> $RC_FILE 에 이미 PATH 설정이 있습니다."
    fi
    warn "    새 터미널을 열거나 'source $RC_FILE' 를 실행하세요."
fi

# 5. Done -------------------------------------------------------------------
ok ""
ok "✓ 설치 완료: $TARGET_BIN"
"$TARGET_BIN" --version 2>/dev/null || warn "  (PATH 반영 전이라면: $TARGET_BIN --version)"
ok ""
printf '\033[1;35m  다음 단계\033[0m\n'
printf '    1) 무료 키로 설정:  ask --config   (Groq 무료 · Gemini 무료 · 또는 Ollama 로컬)\n'
printf '    2) 한국어로 질문:    ask "도커 안 쓰는 이미지 정리해줘"\n'
printf '    3) 대화형 채팅:      ask chat\n'
printf '    4) 사용량·한도:      ask --limits\n'
if is_termux; then
    printf '\033[2m  Termux 팁: 클립보드 복사(-k)는 pkg install termux-api 가 필요합니다.\033[0m\n'
fi
printf '\033[2m  문서: %s   제거: rm %s\033[0m\n\n' "$REPO" "$TARGET_BIN"
