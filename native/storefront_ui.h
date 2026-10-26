#pragma once
#include "storefront_theme.h"
#include <json-c/json.h>
#include <sstream>
#include <filesystem>
#include <map>

inline json_object* field(json_object*j,const char*k){json_object*v=nullptr;if(j)json_object_object_get_ex(j,k,&v);return v;}
inline std::string textfield(json_object*j,const char*k){auto*v=field(j,k);return v?json_object_get_string(v):"";}
inline bool boolfield(json_object*j,const char*k){return json_object_get_boolean(field(j,k));}
inline std::string argsFor(const std::string&id,const char*key=nullptr,json_object*value=nullptr){auto*j=json_object_new_object();json_object_object_add(j,"id",json_object_new_string(id.c_str()));if(key)json_object_object_add(j,key,value);std::string s=json_object_to_json_string(j);json_object_put(j);return s;}
inline std::string noticeArgs(json_object*n,const char*action){auto*j=json_object_new_object();json_object_object_add(j,"id",json_object_new_string(textfield(n,"id").c_str()));json_object_object_add(j,"token",json_object_new_string(textfield(n,"token").c_str()));json_object_object_add(j,"action",json_object_new_string(action));std::string out=json_object_to_json_string(j);json_object_put(j);return out;}
struct StoreButton{int x,y,w,h;std::string method,params;bool hit(float a,float b)const{return a>=x&&a<x+w&&b>=y&&b<y+h;}};
struct StoreUI{
 static constexpr int W=1280,H=900;
 std::string view="discover",selected,tab="about",settingsTab="shelf",reviewId,reviewMethod;
 int page=0,gallery=0,creditPage=0,linkPage=0,aboutPage=0,noticePage=0;bool working=false;
 std::vector<StoreButton> buttons;
 std::string hover,pressed;
 std::map<std::string,cairo_surface_t*> images;
 size_t imageBytes=0;
 ~StoreUI(){for(auto&entry:images)cairo_surface_destroy(entry.second);}
 cairo_surface_t* image(const std::string&path){
  auto existing=images.find(path);if(existing!=images.end())return existing->second;
  auto*s=cairo_image_surface_create_from_png(path.c_str());
  size_t bytes=size_t(cairo_image_surface_get_stride(s))*cairo_image_surface_get_height(s);
  if(imageBytes+bytes>24*1024*1024){for(auto&entry:images)cairo_surface_destroy(entry.second);images.clear();imageBytes=0;}
  images[path]=s;imageBytes+=bytes;return s;
 }
 void feedback(Canvas&c,int x,int y,int w,int h,const std::string&method,const std::string&params){
  std::string id=method+"\n"+params;
  bool available=!working||(method.rfind("ui.",0)==0&&method!="ui.confirm");
  if(!available){cairo_save(c.c);cairo_set_source_rgba(c.c,0,0,0,.42);cairo_rectangle(c.c,x,y,w,h);cairo_fill(c.c);cairo_restore(c.c);return;}
  if(hover!=id)return;
  cairo_save(c.c);ShelfTheme::source(c,ShelfTheme::accent,pressed==id?.19:.08);cairo_rectangle(c.c,x+2,y+2,w-4,h-4);cairo_fill(c.c);
  ShelfTheme::source(c,ShelfTheme::accent);cairo_set_line_width(c.c,pressed==id?3:2);cairo_rectangle(c.c,x+2,y+2,w-4,h-4);cairo_stroke(c.c);cairo_restore(c.c);
 }
 std::string key()const{return view+selected+tab+settingsTab+reviewId+reviewMethod+std::to_string(page)+":"+std::to_string(gallery)+":"+std::to_string(creditPage)+":"+std::to_string(linkPage)+":"+std::to_string(aboutPage)+":"+std::to_string(noticePage);}
 json_object* find(json_object*state,const std::string&id){auto*a=field(state,"modules");for(size_t i=0;a&&i<json_object_array_length(a);i++){auto*m=json_object_array_get_idx(a,i);if(textfield(m,"id")==id)return m;}return nullptr;}
 void round(Canvas&c,double x,double y,double w,double h,double r,ShelfTheme::Color color){cairo_new_sub_path(c.c);cairo_arc(c.c,x+w-r,y+r,r,-M_PI/2,0);cairo_arc(c.c,x+w-r,y+h-r,r,0,M_PI/2);cairo_arc(c.c,x+r,y+h-r,r,M_PI/2,M_PI);cairo_arc(c.c,x+r,y+r,r,M_PI,3*M_PI/2);cairo_close_path(c.c);ShelfTheme::source(c,color);cairo_fill(c.c);}
 void text(Canvas&c,int x,int y,const std::string&s,int size=20,bool muted=false,int width=1000){cairo_save(c.c);cairo_rectangle(c.c,x,y-size,width,size+9);cairo_clip(c.c);auto color=muted?ShelfTheme::muted:ShelfTheme::text;c.text(x,y,s,size,color.r,color.g,color.b);cairo_restore(c.c);}
 void wrap(Canvas&c,int x,int y,int width,const std::string&s,int size,int lines=4,bool muted=true){std::istringstream words(s);std::string word,line;int n=0;cairo_set_font_size(c.c,size);while(words>>word){auto next=line.empty()?word:line+" "+word;cairo_text_extents_t e{};cairo_text_extents(c.c,next.c_str(),&e);if(e.x_advance>width&&!line.empty()){text(c,x,y+n*(size+9),line,size,muted,width);line=word;if(++n>=lines)return;}else line=next;}if(!line.empty()&&n<lines)text(c,x,y+n*(size+9),line,size,muted,width);}
 std::vector<std::string> aboutLines(Canvas&c,const std::string&value){
  std::istringstream words(value);std::vector<std::string> lines;std::string word,line;
  cairo_save(c.c);cairo_select_font_face(c.c,"sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_NORMAL);cairo_set_font_size(c.c,18);
  while(words>>word){auto next=line.empty()?word:line+" "+word;cairo_text_extents_t ext{};cairo_text_extents(c.c,next.c_str(),&ext);if(ext.x_advance>508&&!line.empty()){lines.push_back(line);line=word;}else line=next;}
  if(!line.empty())lines.push_back(line);cairo_restore(c.c);return lines;
 }
 std::string buttonLabel(Canvas&c,std::string label,int width){
  cairo_save(c.c);cairo_select_font_face(c.c,"sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_NORMAL);cairo_set_font_size(c.c,19);
  auto fits=[&](const std::string&s){cairo_text_extents_t e{};cairo_text_extents(c.c,s.c_str(),&e);return e.x_advance<=width;};
  if(!fits(label)){
   do{size_t end=label.size()-1;while(end>0&&(static_cast<unsigned char>(label[end])&0xc0)==0x80)--end;label.resize(end);}while(!label.empty()&&!fits(label+"…"));
   label+="…";
  }
  cairo_restore(c.c);return label;
 }
 void button(Canvas&c,int x,int y,int w,const std::string&label,const std::string&method,const std::string&params="{}",bool primary=false,int h=48){auto display=buttonLabel(c,label,w-32);round(c,x,y,w,h,9,primary?ShelfTheme::accent:ShelfTheme::secondary);if(primary){cairo_save(c.c);cairo_rectangle(c.c,x+14,y+8,w-28,h-10);cairo_clip(c.c);c.text(x+16,y+h/2+7,display,19,0,0,0);cairo_restore(c.c);}else text(c,x+16,y+h/2+7,display,19,false,w-28);buttons.push_back({x,y,w,h,method,params});feedback(c,x,y,w,h,method,params);}
 void art(Canvas&c,json_object*m,int x,int y,int w,int h,int index=0){round(c,x,y,w,h,14,ShelfTheme::artwork);auto*pics=field(m,"screenshots");int n=pics?json_object_array_length(pics):0;if(!n){text(c,x+w/2-20,y+h/2+18,"M",56);return;}auto*p=json_object_array_get_idx(pics,index%n);auto path=textfield(p,"path");auto*s=image(path);if(cairo_surface_status(s)==CAIRO_STATUS_SUCCESS){int iw=cairo_image_surface_get_width(s),ih=cairo_image_surface_get_height(s);double scale=std::min(double(w)/iw,double(h-12)/ih);cairo_save(c.c);cairo_translate(c.c,x+(w-iw*scale)/2,y+(h-ih*scale)/2);cairo_scale(c.c,scale,scale);cairo_set_source_surface(c.c,s,0,0);cairo_paint(c.c);cairo_restore(c.c);}else text(c,x+30,y+70,"Preview unavailable",20,true,w-60);}
 std::string transferLabel(json_object*t){auto stage=textfield(t,"stage");return stage=="downloading"?"Downloading":stage=="checking"?"Checking download":stage=="installing"?"Installing":stage=="ready"?"Ready when Off":stage=="complete"?"Installed · Ready":stage=="setting_up"?"Setting up":stage=="setup_failed"?"Setup needs retry":"Download needs retry";}
 std::string updateLabel(json_object*m){auto status=textfield(m,"update_status");return status=="ready"?"Update ready":status=="review"?"Review update":status=="failed"?"Update needs retry":status=="held"?"Previous version kept":status=="available"?"Update available":"Installed";}
 double fraction(json_object*t){double total=json_object_get_double(field(t,"total_bytes"));return total>0?std::clamp(json_object_get_double(field(t,"received_bytes"))/total,0.,1.):0.;}
 void progressBar(Canvas&c,json_object*t,int x,int y,int width){
  round(c,x,y,width,7,3,ShelfTheme::track);double fill=width*fraction(t);if(fill>0)ShelfTheme::rect(c,x,y,std::max(1,int(fill)),7,ShelfTheme::accent);
 }
 void power(Canvas&c,json_object*m,int x,int y){
  if(auto*setup=field(m,"setup");setup&&!boolfield(setup,"ready")){button(c,x,y,116,(textfield(setup,"stage")=="queued"||textfield(setup,"stage")=="running")?"View setup":"Set up","ui.setup",argsFor(textfield(m,"id")),true);return;}
  bool on=boolfield(m,"enabled");auto params=argsFor(textfield(m,"id"),"enabled",json_object_new_boolean(!on));
  text(c,x+6,y+31,on?"On":"Off",18,false,40);
  round(c,x+58,y+10,52,28,14,on?ShelfTheme::accent:ShelfTheme::track);
  cairo_arc(c.c,x+(on?96:72),y+24,10,0,2*M_PI);ShelfTheme::source(c,ShelfTheme::text);cairo_fill(c.c);
  buttons.push_back({x,y,116,48,"module.toggle",params});feedback(c,x,y,116,48,"module.toggle",params);
 }
 void sidebar(Canvas&c,json_object*state){
  ShelfTheme::rect(c,0,0,222,H,ShelfTheme::background);ShelfTheme::rect(c,221,0,1,H,ShelfTheme::border);
  ShelfTheme::logo(c,10,18,64);text(c,76,63,"MagicShelf",24);
  button(c,20,141,180,"Discover","ui.discover","{}",view=="discover");
  button(c,20,199,180,"My Shelf","ui.library","{}",view=="library");
  button(c,20,257,180,"Settings","ui.preferences","{}",view=="settings");
  if(auto*n=field(state,"update_notices");n&&json_object_array_length(n))button(c,20,375,182,"Updates ready","ui.updates","{}",view=="updates");
  if(textfield(field(state,"framework_update"),"stage")=="ready")button(c,20,475,182,"App update ready","ui.appupdates");
  if(auto*t=field(state,"transfer");t&&textfield(t,"stage")!="complete"&&!setupFocused(find(state,selected))){
   text(c,27,587,"DOWNLOADS",13,true,170);wrap(c,27,618,168,textfield(t,"name"),18,2,false);
   wrap(c,27,684,174,transferLabel(t),16,2);progressBar(c,t,27,723,168);
   if(textfield(t,"stage")=="downloading"||(textfield(t,"stage")=="setting_up"&&json_object_get_double(field(t,"total_bytes"))>0)){
    char amount[70];snprintf(amount,sizeof(amount),"%.1f / %.1f MB · %.0f%%",json_object_get_double(field(t,"received_bytes"))/1048576.,json_object_get_double(field(t,"total_bytes"))/1048576.,std::floor(fraction(t)*100));text(c,27,753,amount,12,true,172);
   }
  }
  button(c,20,779,182,boolfield(state,"checking_updates")?"Checking...":"Check updates","catalog.refresh");text(c,27,861,"MagicShelf "+textfield(state,"version"),13,true,175);
 }
 bool setupFocused(json_object*m)const{return tab=="settings"&&boolfield(m,"installed")&&field(m,"setup")&&!boolfield(field(m,"setup"),"ready");}
 void draw(Canvas&c,json_object*state,bool busy,const std::string&message,bool actionFailed=false){
  working=busy;buttons.clear();c.fill(ShelfTheme::background.r,ShelfTheme::background.g,ShelfTheme::background.b);sidebar(c,state);
  auto*m=find(state,selected);if(!selected.empty()&&!m)selected.clear();
  bool setup=setupFocused(m)&&reviewId.empty();
  if(m&&!setup)text(c,254,55,"Collection / "+textfield(m,"name"),17,true,670);
  button(c,1094,25,154,"Close panel","ui.close","{}",false,44);
  ShelfTheme::rect(c,254,94,994,1,ShelfTheme::border);
  if(!reviewId.empty())review(c,state);else if(m)detail(c,m,state);else if(view=="settings")preferences(c,state);else if(view=="updates")updateNotices(c,state);else collection(c,state);
  auto*t=field(state,"transfer");std::string status=boolfield(t,"active")?transferLabel(t)+" · "+textfield(t,"name"):busy?"Updating your shelf... You can keep browsing.":message;
  if(!setup||actionFailed){ShelfTheme::rect(c,254,848,994,1,ShelfTheme::border);text(c,254,869,actionFailed?message:status,14,true,994);if(!setup)text(c,254,891,textfield(state,"update_message"),12,true,994);}
 }
 void collection(Canvas&c,json_object*state){
  text(c,254,171,view=="discover"?"Explore the Collection":"My Shelf",38);
  std::vector<json_object*>items;auto*list=field(state,"modules");
  for(size_t i=0;list&&i<json_object_array_length(list);i++){auto*m=json_object_array_get_idx(list,i);if(view=="discover"||boolfield(m,"installed")||boolfield(m,"subscribed"))items.push_back(m);}
  page=std::clamp(page,0,std::max(0,(int(items.size())-1)/4));text(c,1102,171,std::to_string(items.size())+" creations",16,true,145);
  int count=std::min(4,int(items.size())-page*4);bool big=count<=2;int cardH=big?548:270,artH=big?340:124;
  for(int n=0;n<count;n++){
   auto*m=items[page*4+n];int x=254+(n%2)*510,y=220+(n/2)*288;
   round(c,x,y,484,cardH,14,ShelfTheme::panel);art(c,m,x,y,484,artH);
   text(c,x+21,y+artH+29,textfield(m,"category"),13,true,445);text(c,x+21,y+artH+61,textfield(m,"name"),25,false,445);
   if(big)wrap(c,x+21,y+artH+92,442,textfield(m,"description"),17,2);
   auto params=argsFor(textfield(m,"id"));buttons.push_back({x,y,484,cardH-72,"ui.detail",params});feedback(c,x,y,484,cardH-72,"ui.detail",params);
   auto*t=field(state,"transfer");bool active=boolfield(t,"active")&&textfield(t,"id")==textfield(m,"id");int footer=y+cardH-60;
   if(active){text(c,x+21,footer+23,transferLabel(t),18,false,442);progressBar(c,t,x+21,footer+36,442);}
   else if(boolfield(m,"installed")){text(c,x+21,footer+30,field(m,"setup")&&!boolfield(field(m,"setup"),"ready")?(textfield(field(m,"setup"),"stage")=="queued"||textfield(field(m,"setup"),"stage")=="running"?"Setting up":"Setup needed"):updateLabel(m),17,true,300);power(c,m,x+347,footer);}
   else button(c,x+21,footer,442,"View creation >","ui.detail",params);
  }
  if(!count){text(c,280,375,"Your shelf starts here.",30);wrap(c,280,420,820,"Explore Discover and subscribe to a creation you like.",22,3);}
  if(page>0)button(c,254,792,150,"< Previous","ui.prev");if((page+1)*4<int(items.size()))button(c,1098,792,150,"Next >","ui.next");
 }
 std::string settingArgs(const std::string&key,json_object*value){
  auto*p=json_object_new_object();auto*changes=json_object_new_object();json_object_object_add(changes,key.c_str(),value);json_object_object_add(p,"changes",changes);
  std::string out=json_object_to_json_string(p);json_object_put(p);return out;
 }
 std::string settingValue(json_object*control,json_object*value){
  double n=json_object_get_double(value);auto unit=textfield(control,"unit");char number[40];
  if(unit=="m")snprintf(number,sizeof(number),"%.1f m",n);
  else if(unit=="degrees")snprintf(number,sizeof(number),"%.0f deg",n);
  else snprintf(number,sizeof(number),"%.0f%s",n*100,unit=="%"?"%":" cm");return number;
 }
 void preferences(Canvas&c,json_object*state){
  text(c,254,171,"Settings",38);
  int tx=254;for(auto name:{"shelf","placement","app","credits"}){
   std::string label=name;label[0]=toupper(label[0]);button(c,tx,204,180,label,std::string("ui.pref.")+name,"{}",settingsTab==name);tx+=194;
  }
  auto*p=field(state,"preferences");auto*values=field(p,"values");
  if(settingsTab=="credits"){
   text(c,278,304,"MagicShelf",28);text(c,278,340,"Created by josethevrtech",21,true);
   auto*credits=field(p,"credits");
   for(size_t i=0;credits&&i<json_object_array_length(credits);i++){
    auto*credit=json_object_array_get_idx(credits,i);int y=382+int(i)*110;
    text(c,278,y+25,textfield(credit,"name"),23);text(c,278,y+57,textfield(credit,"role"),17,true,665);
    auto*arg=json_object_new_object();json_object_object_add(arg,"index",json_object_new_int(i));std::string params=json_object_to_json_string(arg);json_object_put(arg);
    button(c,1010,y,238,"Open project >","app.link",params);
   }
   text(c,278,706,"Download statistics & privacy",22);
   wrap(c,278,742,950,"Download totals come from GitHub. Updates and repeat downloads count too. MagicShelf sends no playtime or device-usage analytics.",18,3);
   text(c,278,824,"Creation artists and contributors are credited on each creation's page.",16,true,950);return;
  }
  auto*controls=field(p,"controls");int row=0;
  for(size_t i=0;controls&&i<json_object_array_length(controls);i++){
   auto*control=json_object_array_get_idx(controls,i);if(textfield(control,"group")!=settingsTab)continue;
   auto key=textfield(control,"key");auto*value=field(values,key.c_str());int y=281+row++*92;
   text(c,278,y+24,textfield(control,"label"),22,false,590);text(c,278,y+52,textfield(control,"description"),16,true,590);
   if(auto*choices=field(control,"choices")){
    int count=json_object_array_length(choices),width=count?340/count:0;
    for(int j=0;j<count;j++){auto*choice=json_object_array_get_idx(choices,j);auto*v=field(choice,"value");button(c,900+j*(width+8),y,width-8,textfield(choice,"label"),"settings.update",settingArgs(key,json_object_get(v)),json_object_equal(value,v));}
   }else{
    double n=json_object_get_double(value),step=json_object_get_double(field(control,"step")),lo=json_object_get_double(field(control,"min")),hi=json_object_get_double(field(control,"max"));
    if(n>lo+.000001)button(c,925,y,54,"-","settings.update",settingArgs(key,json_object_new_double(std::clamp(std::round((n-step)*1000000)/1000000,lo,hi))));
    text(c,1004,y+31,settingValue(control,value),23,false,174);
    if(n<hi-.000001)button(c,1194,y,54,"+","settings.update",settingArgs(key,json_object_new_double(std::clamp(std::round((n+step)*1000000)/1000000,lo,hi))));
   }
   ShelfTheme::rect(c,278,y+78,970,1,ShelfTheme::border);
  }
  if(settingsTab=="app"){
   text(c,278,518,"Updates",24);wrap(c,278,553,650,"Creations stay up to date automatically. Downloaded updates install while Off.",18,3);
   button(c,1010,522,238,"Check updates","subscriptions.sync");
   auto*app=field(state,"framework_update");auto stage=textfield(app,"stage");
   text(c,278,661,"MagicShelf "+textfield(state,"version"),24);
   wrap(c,278,703,650,textfield(app,"message"),18,3);
   if(stage=="downloading"){progressBar(c,app,278,754,650);}
   else if(stage=="ready")button(c,970,687,278,"Update and reopen","framework.install","{}",true);
   else if(stage=="failed")button(c,1010,687,238,"Try again","catalog.refresh");
  }
  button(c,254,782,238,"Restore defaults","settings.reset",std::string("{\"group\":\"")+settingsTab+"\"}");
  text(c,518,812,settingsTab=="app"?"Changes save automatically.":"Layout changes return creations to the dock.",17,true,730);
 }
 void updateNotices(Canvas&c,json_object*state){
  text(c,254,171,"Updates ready",38);
  wrap(c,254,209,994,"Keep playing. Running creations are never restarted automatically for an update.",19,2);
  auto*notices=field(state,"update_notices");int count=notices?json_object_array_length(notices):0;
  noticePage=std::clamp(noticePage,0,std::max(0,(count-1)/2));
  for(int i=noticePage*2;i<std::min(count,noticePage*2+2);i++){
   auto*n=json_object_array_get_idx(notices,i);int y=265+(i%2)*235;
   round(c,254,y,994,211,16,ShelfTheme::panel);
   text(c,278,y+40,textfield(n,"name")+" · "+textfield(n,"version"),25,false,940);
   wrap(c,278,y+78,925,"The update is downloaded. It installs automatically when you turn this creation Off. Update now restarts it after you confirm.",18,3);
   if(!boolfield(n,"dismissed"))button(c,738,y+153,245,"Later","notifications.ack",noticeArgs(n,"later"),false,44);
   else text(c,278,y+182,"Waiting until Off. No more reminders for this update.",16,true,700);
   button(c,1003,y+153,245,"Update now","ui.update",argsFor(textfield(n,"id")),true,44);
  }
  if(!count)wrap(c,278,319,925,"No running creations have a downloaded update waiting. Your shelf stays up to date automatically.",22,3);
  if(count>2){button(c,738,782,245,"< Previous","ui.notices-prev");button(c,1003,782,245,"Next >","ui.notices-next");}
 }
 void setupPage(Canvas&c,json_object*m){
  button(c,254,112,130,"< Back","ui.back");art(c,m,254,183,450,534);
  text(c,738,300,textfield(m,"name"),34,false,510);
  auto*steps=field(field(m,"setup"),"steps");json_object*next=nullptr;size_t index=0,total=steps?json_object_array_length(steps):0;
  for(;index<total;index++){auto*s=json_object_array_get_idx(steps,index);if(!boolfield(s,"ready")){next=s;break;}}
  if(!next)return;
  if(total>1)text(c,738,338,"Step "+std::to_string(index+1)+" of "+std::to_string(total),15,true,510);
  auto*setup=field(m,"setup");auto stage=textfield(setup,"stage");bool active=stage=="queued"||stage=="running",failed=stage=="failed";
  bool downloading=json_object_get_double(field(next,"total_bytes"))>0;
  text(c,738,410,failed?"Setup paused":active?"Setting up":"Finish setup",28);
  if(failed)wrap(c,738,450,510,textfield(setup,"error"),18,2);
  else if(downloading){progressBar(c,next,738,448,440);text(c,738,486,fraction(next)>=1?"Finishing up...":std::to_string(int(std::floor(fraction(next)*100)))+"%",17,true,510);}
  else text(c,738,450,active?"Getting everything ready.":"MagicShelf will handle the downloads.",18,true,510);
  if(!active)button(c,738,514,230,failed?"Retry":"Set up","module.setup",argsFor(textfield(m,"id")),true);
  if(failed)button(c,986,514,258,"Open Steam","module.setup.open",argsFor(textfield(m,"id"),"appid",json_object_new_int(json_object_get_int(field(next,"appid")))));
 }
 void detail(Canvas&c,json_object*m,json_object*state){if(setupFocused(m)){setupPage(c,m);return;}auto id=textfield(m,"id");button(c,254,112,163,"< Collection","ui.back");
  art(c,m,254,183,450,534,gallery);auto*pics=field(m,"screenshots");int n=pics?json_object_array_length(pics):0;if(n){auto*p=json_object_array_get_idx(pics,gallery%n);wrap(c,266,749,428,textfield(p,"caption"),16,2);if(n>1){button(c,254,790,150,"< Previous","ui.photo-prev");button(c,554,790,150,"Next >","ui.photo-next");text(c,452,820,std::to_string(gallery%n+1)+" / "+std::to_string(n),17,true);}}
  text(c,738,200,textfield(m,"category"),14,true,510);text(c,738,247,textfield(m,"name"),37,false,510);text(c,738,277,"by "+textfield(m,"author"),17,true,510);wrap(c,738,316,504,textfield(m,"tagline").empty()?textfield(m,"description"):textfield(m,"tagline"),21,2,false);
  text(c,738,392,boolfield(m,"adapter")?"Installed locally":boolfield(m,"subscribed")?"Installed · automatic updates":boolfield(m,"installed")?"Installed":"Ready to download",16,true,510);
  auto*t=field(state,"transfer");bool active=boolfield(t,"active")&&textfield(t,"id")==id;
  if(active){text(c,738,438,transferLabel(t),21);progressBar(c,t,738,452,510);}
  else if(boolfield(m,"installed")){power(c,m,738,416);button(c,1003,416,245,"Manage creation","ui.settings");}
  else if(boolfield(m,"needs_framework_update"))button(c,738,416,510,"Update MagicShelf to continue","ui.appupdates","{}",true);
  else if(boolfield(m,"subscription_available"))button(c,738,416,510,"Subscribe & download","ui.subscribe",argsFor(id),true);
  std::string note=boolfield(m,"adapter")?"Local build. Downloadable releases are still being prepared.":!textfield(m,"update_note").empty()?textfield(m,"update_note"):"Subscribe to download this creation and receive updates.";wrap(c,738,488,508,note,16,2);
  int tx=738;for(auto t:{"about","settings","credits","links"}){std::string name=t==std::string("settings")?"Manage":t;name[0]=toupper(name[0]);button(c,tx,541,120,name,std::string("ui.tab.")+t,"{}",false,42);if(tab==t)ShelfTheme::rect(c,tx+10,581,100,3,ShelfTheme::accent);tx+=130;}
  if(tab=="about"){
   auto lines=aboutLines(c,textfield(m,"about"));int pages=std::max(1,(int(lines.size())+5)/6);aboutPage=std::clamp(aboutPage,0,pages-1);
   for(int i=aboutPage*6;i<std::min(int(lines.size()),aboutPage*6+6);i++)text(c,738,616+(i%6)*27,lines[i],18,true,508);
   if(pages>1){button(c,738,797,190,"< Previous","ui.about-prev","{}",false,40);text(c,943,823,std::to_string(aboutPage+1)+" / "+std::to_string(pages),16,true,100);button(c,1058,797,190,"Next >","ui.about-next","{}",false,40);}
  }
  else if(tab=="settings"){
   if(!boolfield(m,"installed")){wrap(c,738,625,508,"Subscribe and download this creation to manage it.",20,3);return;}
   text(c,738,621,"Version "+textfield(m,"version"),21);text(c,738,650,boolfield(m,"enabled")?"On. Use the creation's own controls to change its settings.":"Ready to use. Turn it On above to begin.",16,true,508);
   if(!boolfield(m,"adapter")){
    if(field(m,"update"))button(c,738,728,245,textfield(m,"update_status")=="ready"?"Update now":"Review update","ui.update",argsFor(id),false,44);
    if(boolfield(m,"subscribed"))button(c,1003,728,245,"Unsubscribe","module.subscribe",argsFor(id,"subscribed",json_object_new_boolean(false)),false,44);
    else if(boolfield(m,"subscription_available"))button(c,1003,728,245,"Subscribe for updates","ui.subscribe",argsFor(id),false,44);
    if(!textfield(m,"previous_version").empty())button(c,738,786,245,"Restore previous","ui.rollback",argsFor(id),false,44);
    button(c,1003,786,245,"Remove download","ui.remove",argsFor(id),false,44);
   }
  }else if(tab=="links"){
   auto*links=field(m,"links");int total=links?json_object_array_length(links):0;linkPage=std::clamp(linkPage,0,std::max(0,(total-1)/3));
   for(int i=linkPage*3;i<std::min(total,linkPage*3+3);i++){auto*l=json_object_array_get_idx(links,i);button(c,738,607+(i%3)*60,510,textfield(l,"label")+" >","module.link",argsFor(id,"index",json_object_new_int(i)));}
   if(!total)text(c,738,632,"No project links supplied yet.",20,true,508);
   if(total>3){button(c,738,797,245,"< Previous links","ui.links-prev","{}",false,40);button(c,1003,797,245,"Next links >","ui.links-next","{}",false,40);}
  }else credits(c,m);
 }
 void credits(Canvas&c,json_object*m){auto*credits=field(m,"credits");int n=credits?json_object_array_length(credits):0;auto*links=field(m,"links");int index=links?json_object_array_length(links):0;std::vector<std::pair<std::string,int>>buttonsFor;for(int i=0;i<n;i++){auto*a=json_object_array_get_idx(credits,i);if(i==creditPage){text(c,738,619,textfield(a,"name"),24);wrap(c,738,652,508,textfield(a,"role"),17,2);wrap(c,738,709,508,textfield(a,"license"),16,2);}if(!textfield(a,"url").empty()){if(i==creditPage)buttonsFor.push_back({"Artist / creator profile",index});index++;}if(!textfield(a,"support_url").empty()){if(i==creditPage)buttonsFor.push_back({"Support creator",index});index++;}}
  if(!n)wrap(c,738,627,508,"By "+textfield(m,"author")+". "+textfield(m,"license"),20,4);for(size_t i=0;i<buttonsFor.size();i++)button(c,738+int(i)*260,752,248,buttonsFor[i].first,"module.link",argsFor(textfield(m,"id"),"index",json_object_new_int(buttonsFor[i].second)),false,44);
  if(n>1){button(c,738,803,245,"< Previous credit","ui.credit-prev","{}",false,36);button(c,1003,803,245,"Next credit >","ui.credit-next","{}",false,36);}
 }
 void review(Canvas&c,json_object*state){
  auto*m=find(state,reviewId);if(!m){reviewId.clear();return;}bool remove=reviewMethod=="module.remove",restore=reviewMethod=="module.rollback",update=boolfield(m,"installed")&&field(m,"update");auto*target=field(m,"update");if(!target)target=m;
  text(c,278,169,remove||restore?"MANAGE YOUR CREATION":"BEFORE YOU INSTALL",15,true);
  text(c,278,226,(remove?"Remove ":restore?"Restore ":update?"Update ":"Subscribe to ")+textfield(m,"name")+"?",34,false,940);
  wrap(c,278,276,925,remove?"This stops the creation and its subscription. Your saved data is kept.":restore?"This restores the previous version and its saved data from before the update. Your current saves are backed up. Automatic updates skip the version you replaced.":update?"Install this update now. If the creation is On, it will restart. Your saved data is kept. You can also cancel and let the update install when the creation is Off.":"MagicShelf will download and install it for you. Then use On / Off on its collection card. Future updates download automatically and install while the creation is Off.",20,3);
  if(!remove&&!restore){
   text(c,278,368,"What this creation can do",23);
   auto*details=field(target,"permission_details");
   for(size_t i=0;details&&i<json_object_array_length(details)&&i<4;i++){
    auto*p=json_object_array_get_idx(details,i);int y=405+int(i)*66;
    text(c,278,y,textfield(p,"title"),19);wrap(c,278,y+24,925,textfield(p,"description"),16,2);
   }
   wrap(c,278,690,925,"Creations run with access to your SteamOS account. If an update asks for more access, MagicShelf will ask you again.",16,2);
  }
  button(c,278,755,230,"Cancel","ui.cancel");button(c,533,755,500,remove?"Remove creation":restore?"Restore previous version":update?"Install update":"Subscribe & install","ui.confirm","{}",true);
 }
 // Navigation stays local. Only concrete user actions produce manager requests.
 bool local(const StoreButton&b,json_object*state,std::string&method,std::string&params){auto*arg=json_tokener_parse(b.params.c_str());std::string id=textfield(arg,"id");if(arg)json_object_put(arg);
  if(b.method=="ui.discover"||b.method=="ui.library"||b.method=="ui.preferences"){view=b.method=="ui.discover"?"discover":b.method=="ui.library"?"library":"settings";selected.clear();reviewId.clear();page=0;}
  else if(b.method.rfind("ui.pref.",0)==0)settingsTab=b.method.substr(8);
  else if(b.method=="ui.detail"){selected=id;auto*m=find(state,id);tab=boolfield(m,"installed")&&field(m,"setup")&&!boolfield(field(m,"setup"),"ready")?"settings":"about";gallery=0;creditPage=0;linkPage=0;aboutPage=0;}
  else if(b.method=="ui.about-next")aboutPage++;else if(b.method=="ui.about-prev")aboutPage--;
  else if(b.method=="ui.updates"){view="updates";selected.clear();reviewId.clear();noticePage=0;}
  else if(b.method=="ui.notices-next")noticePage++;else if(b.method=="ui.notices-prev")noticePage--;
  else if(b.method=="ui.back")selected.clear();else if(b.method=="ui.settings")tab="settings";
  else if(b.method=="ui.setup"){selected=id;tab="settings";reviewId.clear();}
  else if(b.method=="ui.appupdates"){selected.clear();reviewId.clear();view="settings";settingsTab="app";}
  else if(b.method.rfind("ui.tab.",0)==0)tab=b.method.substr(7);
  else if(b.method=="ui.next")page++;else if(b.method=="ui.prev")page--;
  else if(b.method=="ui.photo-next"||b.method=="ui.photo-prev"){auto*p=field(find(state,selected),"screenshots");int n=p?json_object_array_length(p):0;if(n)gallery=(gallery+n+(b.method=="ui.photo-next"?1:-1))%n;}
  else if(b.method=="ui.credit-next"||b.method=="ui.credit-prev"){auto*p=field(find(state,selected),"credits");int n=p?json_object_array_length(p):0;if(n)creditPage=(creditPage+n+(b.method=="ui.credit-next"?1:-1))%n;}
  else if(b.method=="ui.links-next")linkPage++;else if(b.method=="ui.links-prev")linkPage--;
  else if(b.method=="ui.cancel")reviewId.clear();
  else if(b.method=="ui.subscribe"||b.method=="ui.update"||b.method=="ui.remove"||b.method=="ui.rollback"){reviewId=id;reviewMethod=b.method=="ui.remove"?"module.remove":b.method=="ui.rollback"?"module.rollback":b.method=="ui.subscribe"||boolfield(find(state,id),"subscribed")?"module.subscribe":"module.install";}
  else if(b.method=="ui.confirm"){auto*m=find(state,reviewId);if(m){auto*target=field(m,"update");if(!target)target=m;auto*a=json_object_new_object();json_object_object_add(a,"id",json_object_new_string(reviewId.c_str()));json_object_object_add(a,"subscribed",json_object_new_boolean(true));json_object_object_add(a,"permissions",json_object_get(field(target,"permissions")));method=reviewMethod;params=json_object_to_json_string(a);json_object_put(a);}reviewId.clear();return !method.empty();}
  else {method=b.method;params=b.params;return true;}return false;
 }
};
