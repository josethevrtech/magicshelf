// Offline media capture of the real native renderer. No running services change.
#include "storefront_ui.h"
#include <filesystem>
int main(int argc,char**argv){
 if(argc!=3)return 1;
 auto*state=json_object_from_file(argv[1]);if(!state)return 2;
 std::filesystem::create_directories(argv[2]);
 auto save=[&](const std::string&name,StoreUI&ui,const std::string&status=""){
  Canvas c(StoreUI::W*2,StoreUI::H*2);cairo_scale(c.c,2,2);
  ui.draw(c,state,false,status);c.png(std::string(argv[2])+"/"+name+".png");
 };
 StoreUI ui;save("collection",ui);
 ui.selected="org.magicshelf.android-phone";save("android-phone",ui);
 ui.gallery=1;save("phone-settings",ui);
 ui.selected="org.magicshelf.digital-partner";ui.gallery=0;ui.tab="credits";save("artist-credits",ui);
 ui.selected.clear();ui.view="settings";ui.settingsTab="shelf";save("shelf-settings",ui);
 ui.settingsTab="placement";save("placement",ui);
 ui.settingsTab="app";save("app-settings",ui);
 // Explicitly illustrative install/download states, using current package data.
 ui.view="discover";ui.selected="org.magicshelf.android-phone";ui.tab="about";ui.reviewId=ui.selected;ui.reviewMethod="module.subscribe";
 save("permissions-example",ui,"Installation preview");ui.reviewId.clear();
 for(int percent=0;percent<=100;percent++){
  auto*t=json_object_new_object();
  json_object_object_add(t,"id",json_object_new_string(ui.selected.c_str()));
  json_object_object_add(t,"name",json_object_new_string("Android Phone (Virtual)"));
  json_object_object_add(t,"stage",json_object_new_string(percent<94?"downloading":percent<97?"checking":percent<100?"installing":"complete"));
  json_object_object_add(t,"received_bytes",json_object_new_int(percent<94?percent*33554432LL/93:33554432));
  json_object_object_add(t,"total_bytes",json_object_new_int(33554432));
  json_object_object_add(t,"active",json_object_new_boolean(percent<100));
  json_object_object_add(state,"transfer",t);
  char name[40];snprintf(name,sizeof(name),"download-%03d",percent);save(name,ui,"Download flow example");
 }
 json_object_put(state);
}
