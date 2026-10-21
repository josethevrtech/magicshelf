#include "storefront_input.h"
#include <cassert>
#include <iostream>
void check(StoreUI&ui,Canvas&c,json_object*state){ui.draw(c,state,false,"Ready");for(size_t i=0;i<ui.buttons.size();i++){auto&a=ui.buttons[i];assert(a.x>=0&&a.y>=0&&a.x+a.w<=StoreUI::W&&a.y+a.h<=StoreUI::H);assert(a.w>=36&&a.h>=36);assert(a.hit(a.x+a.w/2,a.y+a.h/2));for(size_t j=0;j<i;j++){auto&b=ui.buttons[j];bool overlap=a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;if(overlap)std::cerr<<ui.key()<<" overlap "<<a.method<<" at "<<a.x<<","<<a.y<<" with "<<b.method<<" at "<<b.x<<","<<b.y<<"\n";assert(!overlap);}}}
int main(){auto*state=json_tokener_parse(R"({"version":"0.2.0","modules":[{"id":"org.test.phone","name":"Phone","author":"josethevrtech","category":"Utilities","description":"A creation","installed":true,"adapter":true,"enabled":false,"permissions":["vr-overlay"],"credits":[{"name":"Artist","role":"3D model","url":"https://x.com/artist"}],"links":[{"label":"Project","url":"https://github.com/a/b"},{"label":"Source","url":"https://github.com/a/c"},{"label":"Issues","url":"https://github.com/a/b/issues"},{"label":"Guide","url":"https://github.com/a/b/wiki"}]},{"id":"org.test.download","name":"A free creation","author":"josethevrtech","category":"Companions","description":"Downloaded creation","installed":false,"subscription_available":true,"permissions":["vr-overlay","network"]}]})");Canvas c(StoreUI::W,StoreUI::H);StoreUI ui;check(ui,c,state);std::string method,params;
assert(!ui.local({0,0,0,0,"ui.detail",argsFor("org.test.download")},state,method,params));assert(ui.selected=="org.test.download");check(ui,c,state);
assert(!ui.local({0,0,0,0,"ui.subscribe",argsFor(ui.selected)},state,method,params));check(ui,c,state);assert(ui.reviewId==ui.selected);assert(ui.local({0,0,0,0,"ui.confirm","{}"},state,method,params));assert(method=="module.subscribe");auto*p=json_tokener_parse(params.c_str());assert(textfield(p,"id")=="org.test.download");assert(boolfield(p,"subscribed"));assert(json_object_array_length(field(p,"permissions"))==2);json_object_put(p);
ui.selected="org.test.phone";for(auto t:{"about","settings","credits","links"}){ui.tab=t;check(ui,c,state);}assert(ui.local({0,0,0,0,"module.toggle",argsFor(ui.selected,"enabled",json_object_new_boolean(true))},state,method,params));assert(method=="module.toggle");
ui.selected.clear();auto*list=field(state,"modules");for(int i=0;i<9;i++){auto*m=json_tokener_parse(R"({"name":"A very long creation name to check clipping","description":"Long descriptions remain inside their own creation card and never cover another card's controls.","category":"Creations","installed":true})");json_object_object_add(m,"id",json_object_new_string(("org.test.extra"+std::to_string(i)).c_str()));json_object_array_add(list,m);}for(auto v:{"discover","library"}){ui.view=v;for(int page=0;page<4;page++){ui.page=page;check(ui,c,state);}}
// Trigger presses commit on release over the same target. Page navigation stays
// available while manager actions are pending; a changed target never fires.
ui.selected="org.test.phone";ui.tab="settings";check(ui,c,state);StoreInput input;
auto findButton=[&](const std::string&method){for(auto b:ui.buttons)if(b.method==method)return b;assert(false);return StoreButton{};};
auto toggle=findButton("module.toggle"),nav=findButton("ui.tab.credits");
auto px=[](const StoreButton&b){return b.x+b.w/2.f;};auto py=[](const StoreButton&b){return b.y+b.h/2.f;};
input.down(ui,px(toggle),py(toggle),false);assert(input.up(ui,px(toggle),py(toggle),false));assert(!input.up(ui,px(toggle),py(toggle),false));
input.down(ui,px(toggle),py(toggle),false);assert(!input.up(ui,0,0,false));
input.down(ui,px(toggle),py(toggle),false);input.cancel();assert(!input.up(ui,px(toggle),py(toggle),false));
input.down(ui,px(toggle),py(toggle),false);assert(!input.up(ui,px(toggle),py(toggle),true));
input.down(ui,px(nav),py(nav),true);assert(input.up(ui,px(nav),py(nav),true));
input.down(ui,px(toggle),py(toggle),false);for(auto&b:ui.buttons)if(b.method=="module.toggle")b.params="changed";assert(!input.up(ui,px(toggle),py(toggle),false));
json_object_put(state);std::cout<<"Storefront navigation, subscription requests and non-overlapping hit targets passed\n";}
