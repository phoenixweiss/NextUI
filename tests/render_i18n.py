from pathlib import Path
import json,re
# Run inside the isolated visual-check container; never create a window.
r=Path('/project')
menu=(r/'workspace/all/settings/menu.cpp').read_text()
start=menu.index('namespace\n{\n    static inline void rgba_unpack')
end=menu.index('\nvoid MenuList::drawInput(',start)
api=(r/'workspace/all/common/api.c').read_text()
a=api.index('int GFX_truncateText(');b=api.index('\nint GFX_getTextHeight',a)
keyboard = (r/'workspace/all/settings/keyboardprompt.cpp').read_text()
globals = keyboard[keyboard.index('constexpr int keyboardRows'):keyboard.index('KeyboardPrompt::KeyboardPrompt(')]
keyboard_stub = r'''
KeyboardPrompt::KeyboardPrompt(const std::string &title, MenuListCallback cb):MenuList(MenuItemType::Custom,title,{},nullptr,cb){state.keyboard.title=title;}
KeyboardPrompt::~KeyboardPrompt(){}
InputReactionHint KeyboardPrompt::handleInput(int&,int&){return NoOp;}
void KeyboardPrompt::drawCustom(SDL_Surface*s,const SDL_Rect&,const SDL_Rect&){drawKeyboard(s,state);}
'''
s=r'''#include "menu.hpp"
#include "keyboardprompt.hpp"
extern "C" {
#include "i18n.h"
}
#include <cstdio>
#include <cmath>
#include <sstream>
int panel_w=720, panel_h=480, hdmi_active=0;
GFX_Fonts font={};
uint32_t RGB_WHITE=0xffffffff, THEME_COLOR4_255=0xffffffff, THEME_COLOR5_255=0x000000ff;
const char *language="ru";
extern "C" const char *CFG_getLanguage(void) {return language;}
extern "C" uint32_t CFG_getColor(int id) {static uint32_t c[]={0xffffffff,0x9b2257ff,0x777777ff,0xffffffff,0x000000ff,0xccccccff,0x000000ff};return c[id-1];}
extern "C" SDL_Color uintToColour(uint32_t c){return SDL_Color{(Uint8)(c>>24),(Uint8)(c>>16),(Uint8)(c>>8),(Uint8)c};}
// Hardware and asset atlas are replaced by software pill fills; production row drawing and fonts are used.
void pill(SDL_Surface *s, SDL_Rect *rect,uint32_t rgba) {
    SDL_Color c=uintToColour(rgba); Uint32 rgb=SDL_MapRGBA(s->format,c.r,c.g,c.b,c.a);
    int radius=rect->h/2;
    for(int y=0;y<rect->h;y++) {int dy=radius-y;int inset=radius-(int)std::sqrt(std::max(0,radius*radius-dy*dy));SDL_Rect row={rect->x+inset,rect->y+y,rect->w-2*inset,1};SDL_FillRect(s,&row,rgb);}
}
extern "C" void GFX_blitPillLight(int,SDL_Surface*s,SDL_Rect*r){pill(s,r,CFG_getColor(COLOR_ACCENT));}
extern "C" void GFX_blitPillDark(int,SDL_Surface*s,SDL_Rect*r){pill(s,r,CFG_getColor(COLOR_MAIN));}
MenuList::MenuList(MenuItemType t,const std::string &d,std::vector<AbstractMenuItem*> i,MenuListCallback c,MenuListCallback f):type(t),desc(d),items(i),on_change(c),on_confirm(f){}
MenuList::~MenuList(){}
InputReactionHint MenuList::handleInput(int&,int&){return NoOp;}
class Row:public AbstractMenuItem {std::string label;public:
 Row(const char *n,const char *l):AbstractMenuItem(ListItemType::Generic,I18N_translate(n),""),label(l){}
 const std::any getValue()const override{return std::string(label);}
 const std::string getLabel()const override{return label;}
};
class ViewportMenu:public MenuList {public:
 ViewportMenu(std::vector<AbstractMenuItem*> rows):MenuList(MenuItemType::Fixed,"",rows) {
  scope={0,8,(int)rows.size(),8,8,0};
 }
 void check(int selected,int start,int end) {assert(scope.selected==selected);assert(scope.start==start);assert(scope.end==end);assert(scope.max_visible_options==8);}
};
''' + api[a:b] + '\n'+menu[start:end]+menu[menu.index("void MenuList::drawMainItem("):menu.index("void MenuList::resetAllItems()")]+menu[menu.index("bool MenuList::selectByName("):menu.index("// returns true if the input was handled",menu.index("bool MenuList::selectByName("))]+globals+keyboard_stub+r'''
void text(SDL_Surface *s,TTF_Font*f,const char*t,int x,int y){SDL_Surface*p=TTF_RenderUTF8_Blended(f,t,SDL_Color{255,255,255,255});if(p){SDL_Rect d={x,y,0,0};SDL_BlitSurface(p,NULL,s,&d);SDL_FreeSurface(p);}}
extern "C" int GFX_blitButtonGroup(char**hints,int,SDL_Surface *s,int){
    int x=430; for(int i=0;hints[i];i+=2){text(s,font.tiny,hints[i],x,438);text(s,font.tiny,hints[i+1],x+28,438);x+=125;}return x-430;
}
__KEYBOARD_BODY__
int main(){
 if(TTF_Init())return 1;
 font.small=TTF_OpenFont("/project/skeleton/SYSTEM/res/font1.ttf",24);
 font.tiny=TTF_OpenFont("/project/skeleton/SYSTEM/res/font1.ttf",20);
 font.medium=TTF_OpenFont("/project/skeleton/SYSTEM/res/font1.ttf",28);
 font.large=TTF_OpenFont("/project/skeleton/SYSTEM/res/font1.ttf",32);
 if(!font.small || !font.tiny || !font.medium || !font.large) return 2;
 TTF_SetFontStyle(font.small,TTF_STYLE_BOLD);TTF_SetFontStyle(font.tiny,TTF_STYLE_BOLD);
 TTF_SetFontStyle(font.medium,TTF_STYLE_BOLD);TTF_SetFontStyle(font.large,TTF_STYLE_BOLD);
 int overflows=0;
 {std::vector<AbstractMenuItem*> rows; for(int i=0;i<18;i++)rows.push_back(new Row(std::to_string(i).c_str(),""));
  ViewportMenu choices(rows); assert(choices.selectByName("17"));choices.check(17,10,18);
  assert(choices.selectByName("0"));choices.check(0,0,8);assert(!choices.selectByName("missing"));choices.check(0,0,8);
  for(auto row:rows)delete row;}
 MenuList m(MenuItemType::Fixed,"",{});
'''
rows=[('Save state format','Retroarch-ish (uncompressed)'),('Rewind Compression Speed','12 (fastest)'),('Game switcher curtain opacity','100%'),('Set time and date automatically','On'),('Time zone','Europe/Moscow'),('Font','My extremely long custom font name with Cyrillic Кириллица.otf')]
for lang in ['en','ru']:
 s+=f'language="{lang}";\nSDL_Surface *screen_{lang}=SDL_CreateRGBSurfaceWithFormat(0,720,480,32,SDL_PIXELFORMAT_RGBA32);\n'
 s+=f'SDL_FillRect(screen_{lang},NULL,SDL_MapRGBA(screen_{lang}->format,0,0,0,255));\n'
 for i,(name,value) in enumerate(rows):
  s+=f'{{ Row row({json.dumps(name)},I18N_translate({json.dumps(value,ensure_ascii=False)})); m.drawFixedItem(screen_{lang}, SDL_Rect{{20,{80+i*40},680,40}},row,{str(i==0).lower()}); }}\n'
 s+=f'text(screen_{lang},font.large,I18N_translate("System"),32,20);\nSDL_SaveBMP(screen_{lang},"/visual/rows-{lang}.bmp");SDL_FreeSurface(screen_{lang});\n'
for lang in ['en','ru']:
 s+=f'language="{lang}"; {{ SDL_Surface *root=SDL_CreateRGBSurfaceWithFormat(0,720,480,32,SDL_PIXELFORMAT_RGBA32); SDL_FillRect(root,NULL,SDL_MapRGBA(root->format,0,0,0,255));\n'
 for i,name in enumerate(['System','Appearance','WiFi','Bluetooth','In-Game']):
  s+=f'{{ Row row({json.dumps(name)},""); m.drawMainItem(root, SDL_Rect{{20,{80+i*60},680,60}},row,{str(i==0).lower()}); }}\n'
 s+=f'SDL_SaveBMP(root,"/visual/settings-root-{lang}.bmp");SDL_FreeSurface(root); }}\n'
for lang in ['en','ru']:
 s+=f'language="{lang}"; {{ SDL_Surface *kbd=SDL_CreateRGBSurfaceWithFormat(0,720,480,32,SDL_PIXELFORMAT_RGBA32); KeyboardPrompt prompt(I18N_translate("Enter WiFi passcode")); prompt.drawCustom(kbd,SDL_Rect{{0,0,720,480}},SDL_Rect{{}}); SDL_SaveBMP(kbd,"/visual/keyboard-{lang}.bmp");SDL_FreeSurface(kbd); }}\n'
# Check description lines with the actual bold tiny font used by H700.
pairs = re.findall(r'\{("(?:[^"\\]|\\.)*"),\s*("(?:[^"\\]|\\.)*")\}', (r/'workspace/all/common/i18n.h').read_text())
for key, value in pairs:
 english, russian = json.loads(key), json.loads(value)
 if len(english)>40 or '\n' in english:
  for line in russian.splitlines():
   s+= '{ int width=0; TTF_SizeUTF8(font.tiny,' + json.dumps(line,ensure_ascii=False) + ',&width,NULL); if(width>680) { ++overflows; fprintf(stderr,"Description overflows: %d pixels: %s\\n",width,' + json.dumps(line,ensure_ascii=False) + '); } }\n'
s+='return overflows ? 1 : 0;}'
s=s.replace('__KEYBOARD_BODY__', keyboard[keyboard.index('void KeyboardPrompt::drawKeyboard('):])
Path('/visual/render.cpp').write_text(s)
