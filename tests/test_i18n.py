"""Headless regression checks for configuration compatibility and UTF-8 rendering.

Run: python3 tests/test_i18n.py
Requires a C compiler and SDL2_ttf (pkg-config); never opens a window.
"""
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "workspace/all/common"


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get("I18N_TEST_TMP", str(Path.home() / ".codex/tmp/rg34xxsp")))
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="locale-test-", dir=base)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def compile_and_run(self, source, extra_sources=(), flags=()):
        path = self.work / "test.c"
        path.write_text(source)
        exe = self.work / "test"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-D_POSIX_C_SOURCE=200809L", "-Wall", "-Wextra",
                        "-I" + str(COMMON), "-I" + str(self.work), str(path),
                        *map(str, extra_sources), *flags, "-o", str(exe)], check=True)
        env = dict(os.environ)
        if "I18N_TEST_LIBRARY_PATH" in env:
            env["LD_LIBRARY_PATH"] = env["I18N_TEST_LIBRARY_PATH"]
        subprocess.run([str(exe)], check=True, timeout=60, env=env)

    def test_configuration_roundtrip_and_fallback(self):
        card = self.work / "card"
        shared = card / ".userdata/shared"
        shared.mkdir(parents=True)
        (self.work / "platform.h").write_text("#define SDCARD_PATH " + json.dumps(str(card)) + "\n")
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "defines.h"
#include "i18n.h"
int clamp(int x, int lo, int hi) { return x < lo ? lo : x > hi ? hi : x; }
double clampd(double x, double lo, double hi) { return x < lo ? lo : x > hi ? hi : x; }
static void config(const char *text) {
    FILE *f = fopen(SHARED_USERDATA_PATH "/minuisettings.txt", "w");
    assert(f); fputs(text, f); fclose(f);
}
int main(void) {
    setenv("SHARED_USERDATA_PATH", SHARED_USERDATA_PATH, 1);
    config("font=1\nshowclock=1\nradius=13\n");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "en") == 0);
    assert(CFG_getShowClock() && CFG_getThumbnailRadius() == 13);
    assert(strcmp(I18N_translate("Settings"), "Settings") == 0);
    CFG_setLanguage("ru");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "ru") == 0);
    assert(CFG_getShowClock() && CFG_getThumbnailRadius() == 13);
    assert(strcmp(I18N_translate("Appearance"), "Оформление") == 0);
    const char *user_text = "My game (USA).gba";
    assert(I18N_translate(user_text) == user_text);
    assert(I18N_translate(NULL) == NULL);
    CFG_setLanguage("en");
    CFG_init(NULL, NULL);
    assert(strcmp(I18N_translate("Appearance"), "Appearance") == 0);
    config("language=ru\r\nfont=1\n");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "ru") == 0);
    config("language=unsupported-language\nfont=1\n");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "en") == 0);
    CFG_setLanguage(NULL);
    assert(strcmp(CFG_getLanguage(), "en") == 0);
    config("font=1\n");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "en") == 0);
    config("showclock=1\nfuture_key=preserve-me\nlanguage=ru\nradius=19\n");
    CFG_init(NULL, NULL);
    assert(strcmp(CFG_getLanguage(), "ru") == 0 && CFG_getThumbnailRadius() == 19);
    FILE *readback = fopen(SHARED_USERDATA_PATH "/minuisettings.txt", "r");
    char bytes[256] = {0}; assert(readback); fread(bytes,1,sizeof(bytes)-1,readback); fclose(readback);
    assert(strcmp(bytes,"showclock=1\nfuture_key=preserve-me\nlanguage=ru\nradius=19\n") == 0);
    puts("Configuration: legacy, roundtrip, CRLF, unknown language and fallback passed.");
}
'''
        self.compile_and_run(source, [COMMON / "config.c"], ['-DPLATFORM="test"'])

    def test_actual_entry_display_preserves_names_and_paths(self):
        frontend = (ROOT / "workspace/all/nextui/nextui.c").read_text()
        start = frontend.index("static const char* Entry_displayName(")
        end = frontend.index("\nstatic Array* getQuickToggles", start)
        (self.work / "platform.h").write_text('#define SDCARD_PATH "/card"\n')
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "defines.h"
#include "i18n.h"
static const char *language = "ru";
const char *CFG_getLanguage(void) { return language; }
enum { ENTRY_DIR, ENTRY_PAK, ENTRY_ROM, ENTRY_DIP };
typedef struct { char *path; char *name; int type; } Entry;
''' + frontend[start:end] + r'''
int main(void) {
    Entry game = {"/card/Roms/GBA/Sleep.gba", "Sleep", ENTRY_ROM};
    assert(Entry_displayName(&game) == game.name);
    assert(strcmp(game.path, "/card/Roms/GBA/Sleep.gba") == 0);
    Entry custom = {"/card/Tools/test/Other.pak", "Settings", ENTRY_PAK};
    assert(Entry_displayName(&custom) == custom.name);
    Entry settings = {"/card/Tools/test/Settings.pak", "Settings", ENTRY_PAK};
    assert(strcmp(Entry_displayName(&settings), "Настройки") == 0);
    assert(strcmp(settings.name, "Settings") == 0);
    Entry recent = {FAUX_RECENT_PATH, "Recently Played", ENTRY_DIR};
    assert(strcmp(Entry_displayName(&recent), "Недавние") == 0);
    recent.name = "My history";
    assert(Entry_displayName(&recent) == recent.name);
    Entry action = {"Sleep", "Sleep", ENTRY_DIP};
    assert(strcmp(Entry_displayName(&action), "Сон") == 0);
    assert(strcmp(action.name, "Sleep") == 0);
    language = "en";
    assert(strcmp(Entry_displayName(&settings), "Settings") == 0);
    assert(strcmp(Entry_displayName(&action), "Sleep") == 0);
    puts("Entries: built-in labels localized; action IDs, aliases and user paths preserved.");
}
'''
        self.compile_and_run(source, flags=['-DPLATFORM="test"'])

    def test_catalog_integrity_and_format_arguments(self):
        literal = r'"(?:[^"\\]|\\.)*"'
        pairs = re.findall(r'\{(' + literal + r'),\s*(' + literal + r')\}',
                           (COMMON / "i18n.h").read_text())
        self.assertGreater(len(pairs), 300)
        catalog = {}
        fmt = re.compile(r'%(?:[-+#0 ]*)(?:[0-9]+|\*)?(?:\.(?:[0-9]+|\*))?(?:hh|ll|[hljztL])?[diuoxXfFeEgGaAcspn%]')
        for english_literal, russian_literal in pairs:
            english, russian = json.loads(english_literal), json.loads(russian_literal)
            self.assertNotIn(english, catalog, "Duplicate translation: " + english)
            self.assertTrue(russian.strip(), "Empty translation: " + english)
            self.assertEqual(fmt.findall(english), fmt.findall(russian), english)
            catalog[english] = russian
        # Every explicitly marked literal has a translation; dynamic user values stay unmarked.
        for folder in (ROOT / "workspace/all/settings", ROOT / "workspace/all/nextui", ROOT / "workspace/all/minarch"):
            for path in list(folder.glob("*.c")) + list(folder.glob("*.cpp")):
                for key in re.findall(r'I18N_translate\((' + literal + r')\)', path.read_text()):
                    self.assertIn(json.loads(key), catalog, str(path))

    def test_native_core_translation_keeps_canonical_values(self):
        options = (ROOT / "workspace/all/minarch/ma_options.c").read_text()
        helper = options[options.index("static void localizeOption("):options.index("void OptionList_init(")]
        source = r'''
#include "ma_internal.h"
#include <assert.h>
struct Config config = {0};
GFX_Fonts font = {0};
int DEVICE_WIDTH=720;
int panel_w=720, panel_h=480, hdmi_active=0;
int GFX_wrapText(TTF_Font *f, char *s, int w, int n) { (void)f;(void)s;(void)w;(void)n;return 0; }
''' + helper + r'''
int main(void) {
    char *values[] = {strdup("disabled"),strdup("enabled"),NULL};
    char *labels[] = {values[0],strdup("Enabled"),NULL};
    Option option = {.key=strdup("core_test"),.name=strdup("English name"),
        .desc=strdup("English help"),.full=strdup("English help"),
        .count=2,.value=1,.default_value=0,.values=values,.labels=labels};
    config.core.count=1;config.core.options=&option;
    struct retro_core_option_definition local[] = {
        {.key="core_test",.desc="Русское имя",.info=NULL,
         .values={{"enabled","Включено"},{"wrong_key","Wrong translation"},{NULL,NULL}}},
        {.key="missing_option",.desc="Не добавлять"},{0}};
    OptionList_localize(local);
    assert(strcmp(option.name,"Русское имя")==0);
    assert(strcmp(option.desc,"English help")==0);
    assert(strcmp(option.key,"core_test")==0 && option.value==1 && option.default_value==0);
    assert(strcmp(values[1],"enabled")==0 && strcmp(labels[1],"Включено")==0);
    assert(labels[0]==values[0]);
    OptionCategory cats[]={{strdup("video"),strdup("Video"),NULL},{0}};
    config.core.categories=cats;
    struct retro_core_option_v2_definition defs[] = {
        {.key="core_test",.desc="Имя v2",.info="Описание",.values={{"disabled","Выключено"},{0}}},{0}};
    struct retro_core_option_v2_category localized_cats[]={{"video","Изображение",NULL},{0}};
    struct retro_core_options_v2 v2={localized_cats,defs};
    OptionList_v2_localize(&v2);
    assert(strcmp(option.name,"Имя v2")==0 && strcmp(option.full,"Описание")==0);
    assert(strcmp(cats[0].key,"video")==0 && strcmp(cats[0].desc,"Изображение")==0);
    assert(strcmp(labels[0],"Выключено")==0 && strcmp(values[0],"disabled")==0);
    OptionList_localize(NULL);OptionList_v2_localize(NULL);
    free(option.key);free(option.name);free(option.desc);free(option.full);
    free(labels[0]);free(labels[1]);free(values[0]);free(values[1]);free(cats[0].key);free(cats[0].desc);
    puts("Core metadata: v1/v2 localization, partial fallback, canonical IDs and defaults preserved.");
}
'''
        flags = ["-DUSE_SDL2", "-DPLATFORM=\"h700\"", "-I"+str(ROOT/"workspace/h700/platform"),
                 "-I"+str(ROOT/"workspace/all/minarch"),
                 "-I"+str(ROOT/"workspace/all/minarch/libretro-common/include")]
        flags += shlex.split(os.environ["I18N_SDL_FLAGS"])
        self.compile_and_run(source, flags=[*flags, "-fsanitize=address,undefined"])

    def test_actual_description_helpers_with_long_utf8_lines(self):
        if sys.platform == "darwin":
            self.skipTest("Use the isolated Linux container for SDL checks.")
        api = (COMMON / "api.c").read_text()
        start = api.index("#define MAX_TEXT_LINES")
        end = api.index("\nSDL_Color GFX_mapColor", start)
        source = r'''
#include <SDL2/SDL_ttf.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
''' + api[start:end] + r'''
int main(void) {
    assert(TTF_Init() == 0);
    TTF_Font *f = TTF_OpenFont(FONT_PATH, 20); assert(f);
    SDL_Surface *surface = SDL_CreateRGBSurfaceWithFormat(0,720,480,32,SDL_PIXELFORMAT_RGBA32);
    assert(surface);
    char str[4096] = "";
    for (int i=0;i<250;i++) strcat(str, "Ёжик ");
    strcat(str, "\nСледующая строка");
    int w=0,h=0; GFX_sizeText(f,str,24,&w,&h);
    assert(w > 0 && h == 48);
    SDL_Rect rect = {0,0,720,480};
    GFX_blitText(f,str,24,(SDL_Color){255,255,255,255},surface,&rect);
    SDL_FreeSurface(surface); TTF_CloseFont(f); TTF_Quit();
    puts("Descriptions: long UTF-8 lines render safely under ASan/UBSan.");
}
'''
        flags = shlex.split(os.environ["I18N_SDL_FLAGS"])
        font = ROOT / "skeleton/SYSTEM/res/font1.ttf"
        self.compile_and_run(source, flags=[*flags, '-DFONT_PATH=' + json.dumps(str(font)),
                                          "-fsanitize=address,undefined"])

    def test_actual_truncation_and_cyrillic_font(self):
        if sys.platform == "darwin":
            self.skipTest("Run SDL checks in the Linux container; macOS SDL compatibility may open dialogs.")
        # Compile the actual production function, without hardware or window creation.
        api = (COMMON / "api.c").read_text()
        start = api.index("int GFX_truncateText(")
        end = api.index("\nint GFX_getTextHeight", start)
        function = api[start:end]
        literals = re.findall(r'\{"(?:[^"\\]|\\.)*",\s*("(?:[^"\\]|\\.)*")\}',
                              (COMMON / "i18n.h").read_text())
        glyphs = sorted({ord(c) for literal in literals for c in json.loads(literal) if ord(c) > 32})
        glyph_check = "unsigned glyphs[] = {" + ",".join(map(str, glyphs)) + "};\n"
        glyph_check += "for (unsigned i = 0; i < sizeof(glyphs)/sizeof(*glyphs); ++i) { if (!TTF_GlyphIsProvided(font, glyphs[i])) { fprintf(stderr, \"Missing catalog glyph U+%04X\\n\", glyphs[i]); return 1; } }\n"
        source = r'''
#include <SDL2/SDL_ttf.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
''' + function + r'''
static int valid_utf8(const unsigned char *s) {
    while (*s) {
        unsigned c = *s++;
        if (c < 0x80) continue;
        int n = c >= 0xf0 ? 3 : c >= 0xe0 ? 2 : c >= 0xc2 ? 1 : -1;
        if (n < 0) return 0;
        while (n--) if ((*s++ & 0xc0) != 0x80) return 0;
    }
    return 1;
}
int main(void) {
    assert(TTF_Init() == 0);
    TTF_Font *font = TTF_OpenFont(FONT_PATH, 24);
    assert(font);
    for (unsigned c = 0x410; c <= 0x44f; ++c) assert(TTF_GlyphIsProvided(font, c));
    assert(TTF_GlyphIsProvided(font, 0x401) && TTF_GlyphIsProvided(font, 0x451));
''' + glyph_check + r'''
    const char *samples[] = {"", "A", "AB", "ABC", "English interface",
        "Я", "Ёё", "Сохранить настройки", "Русский English 日本語", NULL};
    for (int i = 0; samples[i]; ++i) {
        for (int width = 0; width <= 720; ++width) {
            char out[512];
            GFX_truncateText(font, samples[i], out, width, 0);
            assert(valid_utf8((const unsigned char *)out));
            int measured = 0;
            TTF_SizeUTF8(font, out, &measured, NULL);
            assert(measured <= width);
            int full = 0;
            TTF_SizeUTF8(font, samples[i], &full, NULL);
            if (full <= width) assert(strcmp(out, samples[i]) == 0);
        }
    }
    TTF_CloseFont(font); TTF_Quit();
    puts("Rendering: Cyrillic glyphs and 6489 truncation cases passed.");
}
'''
        flags = shlex.split(os.environ["I18N_SDL_FLAGS"]) if "I18N_SDL_FLAGS" in os.environ else shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "sdl2", "SDL2_ttf"], text=True))
        font = ROOT / "skeleton/SYSTEM/res/font1.ttf"
        self.compile_and_run(source, flags=[*flags, '-DFONT_PATH=' + json.dumps(str(font)),
                                             "-fsanitize=address,undefined"])


if __name__ == "__main__":
    unittest.main()
