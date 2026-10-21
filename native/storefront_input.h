#pragma once
#include "storefront_ui.h"
#include <optional>

struct StoreInput {
 std::string hover,pressed;
 static std::string identity(const StoreButton&b){return b.method+"\n"+b.params;}
 static bool available(const StoreButton&b,bool busy){return !busy||(b.method.rfind("ui.",0)==0&&b.method!="ui.confirm");}
 static std::optional<StoreButton> target(const StoreUI&ui,float x,float y,bool busy){for(const auto&b:ui.buttons)if(b.hit(x,y)&&available(b,busy))return b;return {};}
 bool move(const StoreUI&ui,float x,float y,bool busy){auto b=target(ui,x,y,busy);auto next=b?identity(*b):"";bool changed=next!=hover;hover=next;return changed;}
 void down(const StoreUI&ui,float x,float y,bool busy){move(ui,x,y,busy);pressed=hover;}
 std::optional<StoreButton> up(const StoreUI&ui,float x,float y,bool busy){auto b=target(ui,x,y,busy);auto was=pressed;pressed.clear();move(ui,x,y,busy);return b&&!was.empty()&&identity(*b)==was?b:std::optional<StoreButton>{};}
 void cancel(){hover.clear();pressed.clear();}
};
