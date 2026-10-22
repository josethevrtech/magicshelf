#include "storefront_input.h"
#include <cassert>
#include <iostream>
void check(StoreUI&ui,Canvas&c,json_object*state){ui.draw(c,state,false,"Ready");for(size_t i=0;i<ui.buttons.size();i++){auto&a=ui.buttons[i];assert(a.x>=0&&a.y>=0&&a.x+a.w<=StoreUI::W&&a.y+a.h<=StoreUI::H);assert(a.w>=36&&a.h>=36);assert(a.hit(a.x+a.w/2,a.y+a.h/2));for(size_t j=0;j<i;j++){auto&b=ui.buttons[j];bool overlap=a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;if(overlap)std::cerr<<ui.key()<<" overlap "<<a.method<<" at "<<a.x<<","<<a.y<<" with "<<b.method<<" at "<<b.x<<","<<b.y<<"\n";assert(!overlap);}}}
int main(){auto*state=json_tokener_parse(R"({"version":"0.2.0","modules":[{"id":"org.test.phone","name":"Phone","author":"josethevrtech","category":"Utilities","description":"A creation","installed":true,"adapter":true,"enabled":false,"permissions":["vr-overlay"],"credits":[{"name":"Artist","role":"3D model","url":"https://x.com/artist"}],"links":[{"label":"Project","url":"https://github.com/a/b"},{"label":"Source","url":"https://github.com/a/c"},{"label":"Issues","url":"https://github.com/a/b/issues"},{"label":"Guide","url":"https://github.com/a/b/wiki"}]},{"id":"org.test.download","name":"A test creation","author":"josethevrtech","category":"Companions","description":"Downloaded creation","installed":false,"subscription_available":true,"permissions":["vr-overlay","network"]}]})");Canvas c(StoreUI::W,StoreUI::H);StoreUI ui;check(ui,c,state);std::string method,params;
// Home-card power controls are separate from the card's navigation target.
for(auto view:{"discover","library"}){
 ui.view=view;check(ui,c,state);bool found=false;StoreInput cardInput;
 for(auto b:ui.buttons)if(b.method=="module.toggle"){
  float x=b.x+b.w/2.f,y=b.y+b.h/2.f;auto hit=StoreInput::target(ui,x,y,false);assert(hit&&hit->method=="module.toggle");
  cardInput.down(ui,x,y,false);auto released=cardInput.up(ui,x,y,false);assert(released);
  assert(ui.local(*released,state,method,params));auto*p=json_tokener_parse(params.c_str());assert(boolfield(p,"enabled"));json_object_put(p);
  assert(ui.selected.empty());assert(!StoreInput::target(ui,x,y,true));found=true;
 }
 assert(found);
}
auto*phone=ui.find(state,"org.test.phone");json_object_object_add(phone,"enabled",json_object_new_boolean(true));check(ui,c,state);
for(auto b:ui.buttons)if(b.method=="module.toggle"){auto*p=json_tokener_parse(b.params.c_str());assert(!boolfield(p,"enabled"));json_object_put(p);}
json_object_object_add(phone,"enabled",json_object_new_boolean(false));ui.view="discover";
auto*transfer=json_tokener_parse(R"({"id":"org.test.phone","name":"Phone","stage":"downloading","received_bytes":50,"total_bytes":100,"active":true})");json_object_object_add(state,"transfer",transfer);
assert(ui.fraction(transfer)==.5);check(ui,c,state);for(auto b:ui.buttons)assert(b.method!="module.toggle");
for(auto stage:{"checking","installing","complete","failed"}){json_object_object_add(transfer,"stage",json_object_new_string(stage));check(ui,c,state);}
json_object_object_del(state,"transfer");
assert(!ui.local({0,0,0,0,"ui.detail",argsFor("org.test.download")},state,method,params));assert(ui.selected=="org.test.download");check(ui,c,state);
assert(!ui.local({0,0,0,0,"ui.subscribe",argsFor(ui.selected)},state,method,params));check(ui,c,state);assert(ui.reviewId==ui.selected);assert(ui.local({0,0,0,0,"ui.confirm","{}"},state,method,params));assert(method=="module.subscribe");auto*p=json_tokener_parse(params.c_str());assert(textfield(p,"id")=="org.test.download");assert(boolfield(p,"subscribed"));assert(json_object_array_length(field(p,"permissions"))==2);json_object_put(p);
ui.selected="org.test.phone";for(auto t:{"about","settings","credits","links"}){ui.tab=t;check(ui,c,state);}assert(ui.local({0,0,0,0,"module.toggle",argsFor(ui.selected,"enabled",json_object_new_boolean(true))},state,method,params));assert(method=="module.toggle");
// Ready, retry and recovery actions stay distinct, including subscribed updates.
auto*download=ui.find(state,"org.test.download");json_object_object_add(download,"installed",json_object_new_boolean(true));json_object_object_add(download,"subscribed",json_object_new_boolean(true));json_object_object_add(download,"can_configure",json_object_new_boolean(true));json_object_object_add(download,"previous_version",json_object_new_string("1.0.0"));json_object_object_add(download,"update",json_tokener_parse(R"({"version":"1.2.0","permissions":["vr-overlay","network"]})"));
ui.selected="org.test.download";ui.tab="settings";
for(auto status:{"ready","review","failed","held","available"}){json_object_object_add(download,"update_status",json_object_new_string(status));check(ui,c,state);bool restore=false,update=false;for(auto b:ui.buttons){restore|=b.method=="ui.rollback";update|=b.method=="ui.update";}assert(restore&&update);}
ui.local({0,0,0,0,"ui.update",argsFor(ui.selected)},state,method,params);check(ui,c,state);assert(ui.reviewMethod=="module.subscribe");ui.local({0,0,0,0,"ui.confirm","{}"},state,method,params);assert(method=="module.subscribe");
ui.local({0,0,0,0,"ui.rollback",argsFor(ui.selected)},state,method,params);check(ui,c,state);ui.local({0,0,0,0,"ui.confirm","{}"},state,method,params);assert(method=="module.rollback");auto*restoreArgs=json_tokener_parse(params.c_str());assert(textfield(restoreArgs,"id")=="org.test.download");json_object_put(restoreArgs);
// Missing Steam prerequisites lead directly to a single setup action.
json_object_object_add(download,"setup",json_tokener_parse(R"({"ready":false,"steps":[{"appid":123,"title":"Game support","ready":false,"received_bytes":20,"total_bytes":100}]})"));
ui.selected.clear();check(ui,c,state);bool setupFound=false;for(auto b:ui.buttons)if(b.method=="ui.setup"){ui.local(b,state,method,params);setupFound=true;break;}assert(setupFound&&ui.tab=="settings");check(ui,c,state);
int setupActions=0;
for(auto b:ui.buttons){
 assert(b.method!="ui.setup"&&b.method!="ui.settings"&&b.method!="module.toggle"&&b.method.rfind("ui.tab.",0)!=0&&b.method.rfind("ui.photo-",0)!=0);
 if(b.method=="module.setup"){setupActions++;assert(ui.local(b,state,method,params));auto*p=json_tokener_parse(params.c_str());assert(json_object_get_int(field(p,"appid"))==123);json_object_put(p);}
}
assert(setupActions==1);
// Finishing one dependency advances the same action; completion restores controls.
auto*setup=field(download,"setup");auto*steps=field(setup,"steps");json_object_object_add(json_object_array_get_idx(steps,0),"ready",json_object_new_boolean(true));json_object_array_add(steps,json_tokener_parse(R"({"appid":456,"ready":false})"));check(ui,c,state);
setupActions=0;for(auto b:ui.buttons)if(b.method=="module.setup"){setupActions++;auto*p=json_tokener_parse(b.params.c_str());assert(json_object_get_int(field(p,"appid"))==456);json_object_put(p);}assert(setupActions==1);
json_object_object_add(setup,"ready",json_object_new_boolean(true));check(ui,c,state);bool powerRestored=false;for(auto b:ui.buttons){assert(b.method!="module.setup");powerRestored|=b.method=="module.toggle";}assert(powerRestored);
json_object_object_del(download,"setup");
ui.selected.clear();auto*list=field(state,"modules");for(int i=0;i<9;i++){auto*m=json_tokener_parse(R"({"name":"A very long creation name to check clipping","description":"Long descriptions remain inside their own creation card and never cover another card's controls.","category":"Creations","installed":true})");json_object_object_add(m,"id",json_object_new_string(("org.test.extra"+std::to_string(i)).c_str()));json_object_array_add(list,m);}for(auto v:{"discover","library"}){ui.view=v;for(int page=0;page<4;page++){ui.page=page;check(ui,c,state);}}
// Trigger presses commit on release over the same target. Page navigation stays
// available while manager actions are pending; a changed target never fires.
// App settings use the same navigation and hit-target contract as creations.
auto*prefs=json_tokener_parse(R"({"values":{"opacity":0.72,"launcher_only":true},"controls":[{"key":"opacity","group":"shelf","label":"Shelf opacity","description":"Transparency","min":0.2,"max":1.0,"step":0.1,"unit":"%"},{"key":"launcher_only","group":"shelf","label":"Show shelf","description":"Where","choices":[{"label":"Steam home","value":true},{"label":"Every page","value":false}]}],"credits":[{"name":"josethevrtech","role":"Creator"}]})");
json_object_object_add(state,"preferences",prefs);
assert(!ui.local({0,0,0,0,"ui.preferences","{}"},state,method,params));assert(ui.view=="settings"&&ui.selected.empty());
for(auto group:{"shelf","placement","app","credits"}){ui.settingsTab=group;check(ui,c,state);}
for(auto stage:{"current","downloading","ready","failed","installing"}){json_object_object_add(state,"framework_update",json_tokener_parse((std::string("{\"stage\":\"")+stage+"\",\"message\":\"Update status\",\"received_bytes\":20,\"total_bytes\":100}").c_str()));ui.settingsTab="app";check(ui,c,state);}
ui.local({0,0,0,0,"ui.appupdates","{}"},state,method,params);assert(ui.view=="settings"&&ui.settingsTab=="app"&&ui.selected.empty());
ui.settingsTab="shelf";check(ui,c,state);bool changed=false;
for(auto b:ui.buttons)if(b.method=="settings.update"){
 assert(ui.local(b,state,method,params));assert(method=="settings.update");auto*p=json_tokener_parse(params.c_str());assert(field(p,"changes"));json_object_put(p);changed=true;
}
assert(changed);
ui.view="discover";ui.selected="org.test.phone";ui.tab="settings";check(ui,c,state);StoreInput input;
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
