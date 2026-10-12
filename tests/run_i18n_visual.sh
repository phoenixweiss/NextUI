#!/bin/sh
# Render production Settings rows and keyboard into software surfaces; no window or audio.
# Only hardware/asset chrome is stubbed. This is not an on-device integration test.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir="${I18N_VISUAL_DIR:-$HOME/.codex/tmp/rg34xxsp/visual}"
mkdir -p "$output_dir"
docker run --rm -i -v "$project_dir:/project:ro" -v "$output_dir:/visual" \
    ghcr.io/loveretro/h700-toolchain:latest /bin/bash -s <<'CONTAINER'
set -eu
sdk=/opt/aarch64-nextui-linux-gnu/aarch64-nextui-linux-gnu/libc/usr
mkdir -p /visual/runtime
for lib in "$sdk"/lib/libSDL2*.so* "$sdk"/lib/libfreetype.so* "$sdk"/lib/libpng*.so*; do ln -sf "$lib" /visual/runtime/; done
python3 /project/tests/render_i18n.py
/opt/aarch64-nextui-linux-gnu/bin/aarch64-nextui-linux-gnu-g++ -std=c++17 -DUSE_SDL2 -DPLATFORM='"h700"' -I/project/workspace/all/settings -I/project/workspace/all/common -I/project/workspace/h700/platform -I"$sdk/include" /visual/render.cpp "$sdk/lib/libSDL2_ttf.so" "$sdk/lib/libSDL2.so" -Wl,-rpath-link,/visual/runtime -o /visual/render
LD_LIBRARY_PATH=/visual/runtime SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy /visual/render

CONTAINER
