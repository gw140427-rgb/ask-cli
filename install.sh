#!/usr/bin/env bash
# ask-cli one-line installer
set -e

REPO_RAW="https://raw.githubusercontent.com/gw140427-rgb/ask-cli/main"
TARGET_DIR="$HOME/.local/bin"
TARGET_BIN="$TARGET_DIR/ask"

echo -e "\033[1;36m==> ask-cli 설치를 시작합니다...\033[0m"

# 1. Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "\033[1;31m오류: python3가 설치되어 있지 않습니다.\033[0m"
    exit 1
fi

# 2. Create Target Directory
mkdir -p "$TARGET_DIR"

# 3. Download ask.py
echo -e "==> 최신 ask.py 스크립트 다운로드 중..."
if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$REPO_RAW/ask.py" -o "$TARGET_BIN"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$TARGET_BIN" "$REPO_RAW/ask.py"
else
    echo -e "\033[1;31m오류: curl 또는 wget이 필요합니다.\033[0m"
    exit 1
fi

chmod +x "$TARGET_BIN"

# 4. Check PATH
case ":$PATH:" in
    *":$TARGET_DIR:"*) ;;
    *)
        SHELL_RC=""
        if [ -n "$BASH_VERSION" ]; then
            SHELL_RC="$HOME/.bashrc"
        elif [ -n "$ZSH_VERSION" ]; then
            SHELL_RC="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        fi

        if [ -n "$SHELL_RC" ]; then
            echo "export PATH=\"$TARGET_DIR:\$PATH\"" >> "$SHELL_RC"
            echo -e "\033[33m==> PATH에 $TARGET_DIR 경로를 추가했습니다 ($SHELL_RC)\033[0m"
            echo -e "\033[33m    터미널을 다시 열거나 'source $SHELL_RC'를 실행하세요.\033[0m"
        fi
        ;;
esac

echo -e "\n\033[1;32m✓ 설치 완료! ask --help 를 입력해 시작하세요.\033[0m"
echo -e "\033[1;35m  처음 실행 시: ask --config 로 API 키를 설정하세요.\033[0m\n"
