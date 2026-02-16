#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
FE_DIR="$ROOT_DIR/apps/web"

if [ ! -d "$FE_DIR" ]; then
  echo "apps/web 디렉터리를 찾을 수 없습니다." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm이 설치되어 있지 않습니다." >&2
  exit 1
fi

NPM_PATH=$(command -v npm)
case "$NPM_PATH" in
  /mnt/c/*|/c/*|/C/*|/Program\ Files/*)
    echo "WSL용 npm이 필요합니다. Windows npm은 WSL 경로에서 동작하지 않습니다." >&2
    echo "WSL에서 node/npm을 설치한 뒤 다시 실행하세요." >&2
    exit 1
    ;;
esac

if [ -f "$FE_DIR/.env" ]; then
  set -a
  . "$FE_DIR/.env"
  set +a
fi

if [ ! -d "$FE_DIR/node_modules" ]; then
  (cd "$FE_DIR" && npm install)
fi

exec sh -c "cd \"$FE_DIR\" && npm run dev"
