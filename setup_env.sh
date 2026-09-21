#!/usr/bin/env bash
# setup_env.sh —— html-explainer 一次性环境自检/安装（可反复跑）。
# 适配：Windows(Git Bash) / macOS / Linux。全部装用户级，不需要管理员。
#
# 用法：
#   bash setup_env.sh            # 自检，缺什么报告什么
#   bash setup_env.sh --install  # 自检 + 联网安装缺的依赖
#
# 依赖清单：
#   Python ≥3.9 + edge-tts(7.2.8 钉死) numpy pillow imageio-ffmpeg
#   Node ≥18（渲染器 .mjs）
#   playwright-core（装在技能 node/ 下，纯 JS，可随技能打包带走）
#   浏览器：Chrome 或 Edge（几乎必有）；都没有才下载 playwright chromium
#   ffmpeg：PATH 有就用；没有则用 imageio-ffmpeg 的静态二进制（自动回退）

set -u
SKILL_ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL=0
[ "${1:-}" = "--install" ] && INSTALL=1

# 计数口径：MISSING 表示「自检结束时仍缺的项」。
# 安装成功的项不计数 —— 所以先尝试装、装完再判定，不要在安装前就 miss。
MISSING=0
ok()   { echo "  ✓ $1"; }
miss() { echo "  ✗ $1"; MISSING=$((MISSING + 1)); }
warn() { echo "  ⚠ $1"; }
info() { echo "  → $1"; }

echo "== html-explainer 环境自检 =="

# ---------- Python ----------
PY=""
for c in "$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
         "$HOME/.workbuddy/binaries/python/envs/default/bin/python" \
         python3 python; do
  if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  miss "找不到 Python ≥3.9"
else
  ok "Python: $PY ($("$PY" -V 2>&1))"
  if ! "$PY" -c "import edge_tts, numpy, PIL, imageio_ffmpeg" >/dev/null 2>&1; then
    if [ $INSTALL -eq 1 ]; then
      info "pip 安装 Python 依赖（钉死 edge-tts==7.2.8：7.x 升级常有破坏性）…"
      "$PY" -m pip install --user "edge-tts==7.2.8" numpy pillow imageio-ffmpeg >/dev/null 2>&1 \
        || "$PY" -m pip install "edge-tts==7.2.8" numpy pillow imageio-ffmpeg >/dev/null 2>&1 \
        || warn "pip 安装失败，请手动装"
    fi
    # 装完再判定
    if "$PY" -c "import edge_tts, numpy, PIL, imageio_ffmpeg" >/dev/null 2>&1; then
      ok "Python 依赖齐全（edge-tts / numpy / pillow / imageio-ffmpeg）"
    else
      miss "Python 依赖缺（edge-tts numpy pillow imageio-ffmpeg）"
    fi
  else
    ok "Python 依赖齐全（edge-tts / numpy / pillow / imageio-ffmpeg）"
  fi
fi

# ---------- Node ----------
node_major() { node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1; }
if command -v node >/dev/null 2>&1; then
  NV="$(node_major)"
  if [ "${NV:-0}" -ge 18 ]; then ok "Node: $(node -v)"; else miss "Node ≥18 需要，当前 $(node -v)"; fi
else
  for d in "$HOME/.workbuddy/binaries/node/versions"/*/; do
    if [ -x "$d/node.exe" ] || [ -x "$d/node" ]; then
      export PATH="$d:$PATH"; ok "Node(托管): $(node -v)"; break
    fi
  done
  command -v node >/dev/null 2>&1 || miss "找不到 Node ≥18（渲染器需要）"
fi

# ---------- playwright-core ----------
if [ ! -d "$SKILL_ROOT/node/node_modules/playwright-core" ] && [ $INSTALL -eq 1 ]; then
  if command -v npm >/dev/null 2>&1; then
    info "npm 安装 playwright-core（npmmirror 优先）…"
    (cd "$SKILL_ROOT/node" && \
      npm install playwright-core --registry https://registry.npmmirror.com --no-audit --no-fund) || \
      (cd "$SKILL_ROOT/node" && npm install playwright-core --no-audit --no-fund) || \
      warn "npm 安装失败（检查 npm/corepack 或换 registry）"
  else
    warn "没有 npm —— 无法自动安装 playwright-core"
  fi
fi
# 装完再判定
if [ -d "$SKILL_ROOT/node/node_modules/playwright-core" ]; then
  ok "playwright-core（技能内置 node/）"
else
  miss "playwright-core 缺失"
fi

# ---------- 浏览器 ----------
BROWSER=""
for p in "/c/Program Files/Google/Chrome/Application/chrome.exe" \
         "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
         "$LOCALAPPDATA/Google/Chrome/Application/chrome.exe" \
         "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
         "/c/Program Files/Microsoft/Edge/Application/msedge.exe" \
         "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
         "/usr/bin/google-chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser"; do
  [ -f "$p" ] && BROWSER="$p" && break
done
if [ -n "$BROWSER" ]; then
  ok "浏览器: $BROWSER（渲染直接用，无需下载）"
else
  warn "没找到本机 Chrome/Edge —— 渲染时会回退 playwright 自带 chromium（首次 ~115MB 下载）"
  if [ $INSTALL -eq 1 ]; then
    echo "  → 可预下载：npx playwright install chromium（或设 BROWSER_PATH 指向任一 Chromium 系浏览器）"
  fi
fi

# ---------- ffmpeg ----------
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg: $(command -v ffmpeg)"
elif [ -n "${PY:-}" ] && "$PY" -c "import imageio_ffmpeg" >/dev/null 2>&1; then
  ok "ffmpeg 回退: imageio-ffmpeg 静态二进制（$("$PY" -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null | head -1)）"
else
  miss "ffmpeg（PATH 或 imageio-ffmpeg 二者其一）"
fi

# ---------- GSAP ----------
if [ -f "$SKILL_ROOT/assets/gsap.min.js" ]; then
  ok "GSAP 内置: assets/gsap.min.js（离线可用）"
else
  miss "assets/gsap.min.js（被打包脚本删了？从 gsap npm 包 dist/ 恢复）"
fi

echo "----------------------------------------"
if [ $MISSING -eq 0 ]; then
  echo "环境就绪 ✓（重跑加 --install 可自动装缺项）"
else
  echo "缺 $MISSING 项 —— bash setup_env.sh --install 联网安装"
  exit 1
fi
