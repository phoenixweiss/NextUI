#!/bin/sh
# Run native Linux regression checks using the SDL libraries shipped in the H700 SDK.
# The project mount is read-only. No graphics or audio devices are exposed.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
temp_base="${TMPDIR_I18N:-$HOME/.codex/tmp/rg34xxsp}"
mkdir -p "$temp_base"
test_dir=$(mktemp -d "$temp_base/container-tests.XXXXXX")
trap 'rm -rf "$test_dir"' EXIT HUP INT TERM
docker run --rm \
    -v "$project_dir:/project:ro" -v "$test_dir:/test-tmp" \
    -e I18N_TEST_TMP=/test-tmp -e SDL_VIDEODRIVER=dummy -e SDL_AUDIODRIVER=dummy \
    -e CC=/usr/bin/gcc ghcr.io/loveretro/h700-toolchain:latest /bin/bash -lc '
        sdk=/opt/aarch64-nextui-linux-gnu/aarch64-nextui-linux-gnu/libc/usr
        mkdir -p /test-tmp/includes /test-tmp/runtime
        ln -s "$sdk/include/SDL2" /test-tmp/includes/SDL2
        for lib in "$sdk"/lib/libSDL2*.so* "$sdk"/lib/libfreetype.so* "$sdk"/lib/libpng*.so*; do
            ln -s "$lib" /test-tmp/runtime/
        done
        export I18N_SDL_FLAGS="-I/test-tmp/includes $sdk/lib/libSDL2_ttf.so $sdk/lib/libSDL2.so -Wl,-rpath-link,/test-tmp/runtime"
        export I18N_TEST_LIBRARY_PATH=/test-tmp/runtime
        cd /project
        python3 tests/test_i18n.py
    '
