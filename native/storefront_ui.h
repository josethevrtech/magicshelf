#pragma once
#include "compat/render.h"
#include <json-c/json.h>
#include <sstream>
#include <filesystem>
#include <map>

inline json_object* field(json_object*j,const char*k){json_object*v=nullptr;if(j)json_object_object_get_ex(j,k,&v);return v;}
inline std::string textfield(json_object*j,const char*k){auto*v=field(j,k);return v?json_object_get_string(v):"";}
inline bool boolfield(json_object*j,const char*k){return json_object_get_boolean(field(j,k));}
inline std::string argsFor(const std::string&id,const char*key=nullptr,json_object*value=nullptr){auto*j=json_object_new_object();json_object_object_add(j,"id",json_object_new_string(id.c_str()));if(key)json_object_object_add(j,key,value);std::string s=json_object_to_json_string(j);json_object_put(j);return s;}
struct StoreButton{int x,y,w,h;std::string method,params;bool hit(float a,float b)const{return a>=x&&a<x+w&&b>=y&&b<y+h;}};
struct StoreUI{
 static constexpr int W=1280,H=900;
 std::string view="discover",selected,tab="about",reviewId,reviewMethod;
 int page=0,gallery=0,creditPage=0,linkPage=0;bool working=false;
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
  if(!available){cairo_save(c.c);cairo_set_source_rgba(c.c,.06,.075,.078,.42);cairo_rectangle(c.c,x,y,w,h);cairo_fill(c.c);cairo_restore(c.c);return;}
  if(hover!=id)return;
  cairo_save(c.c);cairo_set_source_rgba(c.c,.83,.94,.69,pressed==id?.19:.08);cairo_rectangle(c.c,x+2,y+2,w-4,h-4);cairo_fill(c.c);
  cairo_set_source_rgb(c.c,.72,.86,.61);cairo_set_line_width(c.c,pressed==id?3:2);cairo_rectangle(c.c,x+2,y+2,w-4,h-4);cairo_stroke(c.c);cairo_restore(c.c);
 }
 std::string key()const{return view+selected+tab+reviewId+reviewMethod+std::to_string(page)+":"+std::to_string(gallery)+":"+std::to_string(creditPage)+":"+std::to_string(linkPage);}
 json_object* find(json_object*state,const std::string&id){auto*a=field(state,"modules");for(size_t i=0;a&&i<json_object_array_length(a);i++){auto*m=json_object_array_get_idx(a,i);if(textfield(m,"id")==id)return m;}return nullptr;}
 void round(Canvas&c,double x,double y,double w,double h,double r,double red,double green,double blue){cairo_new_sub_path(c.c);cairo_arc(c.c,x+w-r,y+r,r,-M_PI/2,0);cairo_arc(c.c,x+w-r,y+h-r,r,0,M_PI/2);cairo_arc(c.c,x+r,y+h-r,r,M_PI/2,M_PI);cairo_arc(c.c,x+r,y+r,r,M_PI,3*M_PI/2);cairo_close_path(c.c);cairo_set_source_rgb(c.c,red,green,blue);cairo_fill(c.c);}
 void text(Canvas&c,int x,int y,const std::string&s,int size=20,bool muted=false,int width=1000){cairo_save(c.c);cairo_rectangle(c.c,x,y-size,width,size+9);cairo_clip(c.c);c.text(x,y,s,size,muted?.65:.94,muted?.71:.96,muted?.68:.92);cairo_restore(c.c);}
 void wrap(Canvas&c,int x,int y,int width,const std::string&s,int size,int lines=4,bool muted=true){std::istringstream words(s);std::string word,line;int n=0;cairo_set_font_size(c.c,size);while(words>>word){auto next=line.empty()?word:line+" "+word;cairo_text_extents_t e{};cairo_text_extents(c.c,next.c_str(),&e);if(e.x_advance>width&&!line.empty()){text(c,x,y+n*(size+9),line,size,muted,width);line=word;if(++n>=lines)return;}else line=next;}if(!line.empty()&&n<lines)text(c,x,y+n*(size+9),line,size,muted,width);}
 void button(Canvas&c,int x,int y,int w,const std::string&label,const std::string&method,const std::string&params="{}",bool primary=false,int h=48){round(c,x,y,w,h,9,primary?.83:.15,primary?.94:.19,primary?.69:.19);if(primary){cairo_save(c.c);cairo_rectangle(c.c,x+14,y+8,w-28,h-10);cairo_clip(c.c);c.text(x+16,y+h/2+7,label,19,.12,.17,.10);cairo_restore(c.c);}else text(c,x+16,y+h/2+7,label,19,false,w-28);buttons.push_back({x,y,w,h,method,params});feedback(c,x,y,w,h,method,params);}
 void art(Canvas&c,json_object*m,int x,int y,int w,int h,int index=0){bool pet=textfield(m,"category")=="Companions";round(c,x,y,w,h,14,pet?.20:.13,pet?.18:.19,pet?.14:.18);auto*pics=field(m,"screenshots");int n=pics?json_object_array_length(pics):0;if(!n){text(c,x+w/2-20,y+h/2+18,"M",56);return;}auto*p=json_object_array_get_idx(pics,index%n);auto path=textfield(p,"path");auto*s=image(path);if(cairo_surface_status(s)==CAIRO_STATUS_SUCCESS){int iw=cairo_image_surface_get_width(s),ih=cairo_image_surface_get_height(s);double scale=std::min(double(w)/iw,double(h-12)/ih);cairo_save(c.c);cairo_translate(c.c,x+(w-iw*scale)/2,y+(h-ih*scale)/2);cairo_scale(c.c,scale,scale);cairo_set_source_surface(c.c,s,0,0);cairo_paint(c.c);cairo_restore(c.c);}else text(c,x+30,y+70,"Preview unavailable",20,true,w-60);}
 void sidebar(Canvas&c,json_object*state){c.rect(0,0,222,H,.075,.09,.09);c.rect(221,0,1,H,.17,.20,.20);round(c,25,34,37,39,7,.83,.94,.69);c.text(31,63,"M",25,.12,.17,.10);text(c,76,55,"MagicShelf",25);text(c,77,77,"by josethevrtech",12,true);
  button(c,20,141,180,"Discover","ui.discover","{}",view=="discover");button(c,20,199,180,"My Shelf","ui.library","{}",view=="library");
  c.rect(26,614,169,1,.19,.23,.22);text(c,27,655,"Always free.",23);wrap(c,27,689,170,"Subscribe to favorites. Keep them up to date.",17,3);button(c,20,779,182,"Check updates","catalog.refresh");text(c,27,861,"MagicShelf "+textfield(state,"version"),13,true,175);
 }
 void draw(Canvas&c,json_object*state,bool busy,const std::string&message){working=busy;buttons.clear();c.fill(.062,.075,.078);sidebar(c,state);auto*m=find(state,selected);if(!selected.empty()&&!m)selected.clear();text(c,254,55,m?"Collection / "+textfield(m,"name"):"The creation collection",17,true,670);button(c,1010,25,238,"Return creations home","home");c.rect(254,94,994,1,.17,.20,.20);
  if(!reviewId.empty())review(c,state);else if(m)detail(c,m);else collection(c,state);
  c.rect(254,848,994,1,.17,.20,.20);text(c,254,869,busy?"Updating your shelf... You can keep browsing.":message,14,true,994);text(c,254,891,textfield(state,"update_message"),12,true,994);
 }
 void collection(Canvas&c,json_object*state){text(c,254,134,view=="discover"?"MADE FOR YOUR SPACE":"YOUR OWN LITTLE COLLECTION",13,true);text(c,254,180,view=="discover"?"A home for my VR creations.":"Make your shelf your own.",37);text(c,254,219,view=="discover"?"Subscribe to your favorites. Every creation is free.":"Open a creation to configure it and manage updates.",20,true);
  std::vector<json_object*>items;auto*list=field(state,"modules");for(size_t i=0;list&&i<json_object_array_length(list);i++){auto*m=json_object_array_get_idx(list,i);if(view=="discover"||boolfield(m,"installed")||boolfield(m,"subscribed"))items.push_back(m);}page=std::clamp(page,0,std::max(0,(int(items.size())-1)/4));text(c,254,270,view=="discover"?"Explore the collection":"On your shelf",23);text(c,1102,270,std::to_string(items.size())+" creations",16,true,145);
  int count=std::min(4,int(items.size())-page*4);bool big=count<=2;int cardH=big?448:235,artH=big?292:122;
  for(int n=0;n<count;n++){auto*m=items[page*4+n];int x=254+(n%2)*510,y=293+(n/2)*253;round(c,x,y,484,cardH,14,.10,.12,.13);art(c,m,x,y,484,artH);round(c,x+407,y+16,59,27,5,.83,.94,.69);c.text(x+418,y+35,"FREE",12,.12,.17,.10);text(c,x+21,y+artH+29,textfield(m,"category"),13,true,445);text(c,x+21,y+artH+61,textfield(m,"name"),25,false,445);
   if(big){wrap(c,x+21,y+artH+92,442,textfield(m,"description"),17,2);text(c,x+21,y+cardH-20,boolfield(m,"installed")?(boolfield(m,"enabled")?"On your shelf":"Installed · Off"):"Free download",15,true);text(c,x+337,y+cardH-20,"View creation >",16,false,130);}else text(c,x+21,y+cardH-17,boolfield(m,"installed")?"Installed   ·   View creation >":"Free   ·   View creation >",15,true,442);
   auto params=argsFor(textfield(m,"id"));buttons.push_back({x,y,484,cardH,"ui.detail",params});feedback(c,x,y,484,cardH,"ui.detail",params);
  }
  if(!count){text(c,280,375,"Your shelf starts here.",30);wrap(c,280,420,820,"Explore Discover and subscribe to a creation you like. New published creations appear when the collection is refreshed.",22,3);}
  if(page>0)button(c,254,792,150,"< Previous","ui.prev");if((page+1)*4<int(items.size()))button(c,1098,792,150,"Next >","ui.next");if(big&&count&&page==0)text(c,254,797,"Free to collect. Yours to arrange. Artist support is always optional.",17,true,820);
 }
 void detail(Canvas&c,json_object*m){auto id=textfield(m,"id");button(c,254,112,163,"< Collection","ui.back");
  art(c,m,254,183,450,534,gallery);auto*pics=field(m,"screenshots");int n=pics?json_object_array_length(pics):0;if(n){auto*p=json_object_array_get_idx(pics,gallery%n);wrap(c,266,749,428,textfield(p,"caption"),16,2);if(n>1){button(c,254,790,150,"< Previous","ui.photo-prev");button(c,554,790,150,"Next >","ui.photo-next");text(c,452,820,std::to_string(gallery%n+1)+" / "+std::to_string(n),17,true);}}
  text(c,738,200,textfield(m,"category"),14,true,510);text(c,738,247,textfield(m,"name"),37,false,510);text(c,738,277,"by "+textfield(m,"author"),17,true,510);wrap(c,738,316,504,textfield(m,"tagline").empty()?textfield(m,"description"):textfield(m,"tagline"),21,2,false);
  round(c,738,373,58,27,5,.83,.94,.69);c.text(748,392,"FREE",12,.12,.17,.10);text(c,812,392,boolfield(m,"adapter")?"Installed locally":boolfield(m,"subscribed")?"Subscribed · automatic updates":boolfield(m,"installed")?"Downloaded":"Ready to download",16,true,425);
  if(boolfield(m,"subscription_available")&&!boolfield(m,"subscribed"))button(c,738,416,510,boolfield(m,"installed")?"Subscribe for automatic updates":"Subscribe & download","ui.subscribe",argsFor(id),true);
  else if(boolfield(m,"installed"))button(c,738,416,510,"Configure creation","ui.settings","{}",true);
  std::string note=boolfield(m,"adapter")?"Local build. Downloadable releases are still being prepared.":boolfield(m,"subscribed")?"New updates download automatically, even while Off.":"No payment. Your subscription includes future updates.";wrap(c,738,488,508,note,16,2);
  int tx=738;for(auto t:{"about","settings","credits","links"}){std::string name=t;name[0]=toupper(name[0]);button(c,tx,541,120,name,std::string("ui.tab.")+t,"{}",false,42);if(tab==t)c.rect(tx+10,581,100,3,.83,.94,.69);tx+=130;}
  if(tab=="about"){wrap(c,738,616,508,textfield(m,"about"),18,5);auto*links=field(m,"links");for(size_t i=0;links&&i<std::min(size_t(2),json_object_array_length(links));i++){auto*l=json_object_array_get_idx(links,i);button(c,738+int(i)*260,773,248,textfield(l,"label"),"module.link",argsFor(id,"index",json_object_new_int(i)),false,48);}}
  else if(tab=="settings"){
   if(!boolfield(m,"installed")){wrap(c,738,625,508,"Subscribe and download this creation to configure it.",20,3);return;}
   text(c,738,621,"On your shelf",21);text(c,738,650,boolfield(m,"enabled")?"Running and ready to use.":"Off. Session and saved data are kept.",16,true,330);button(c,1104,604,144,boolfield(m,"enabled")?"Turn off":"Turn on","module.toggle",argsFor(id,"enabled",json_object_new_boolean(!boolfield(m,"enabled"))));
   if(boolfield(m,"can_configure")||boolfield(m,"adapter")){button(c,738,676,510,"Open device settings in VR","module.open",argsFor(id));if(!boolfield(m,"adapter")){if(boolfield(m,"subscribed"))button(c,738,738,245,"Unsubscribe","module.subscribe",argsFor(id,"subscribed",json_object_new_boolean(false)));button(c,1003,738,245,"Remove download","ui.remove",argsFor(id));}text(c,738,818,"Opening settings turns this creation on.",16,true,508);}else{int y=679;if(boolfield(m,"subscribed")){button(c,738,y,245,"Unsubscribe","module.subscribe",argsFor(id,"subscribed",json_object_new_boolean(false)));y+=58;}if(field(m,"update")){button(c,738,y,245,"Review update","ui.update",argsFor(id));y+=58;}button(c,1003,737,245,"Remove download","ui.remove",argsFor(id));if(!boolfield(m,"subscribed"))text(c,738,800,"Subscribe to receive automatic updates.",16,true,508);}
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
 void review(Canvas&c,json_object*state){auto*m=find(state,reviewId);if(!m){reviewId.clear();return;}bool remove=reviewMethod=="module.remove";auto*target=field(m,"update");if(!target)target=m;text(c,278,169,remove?"MANAGE YOUR DOWNLOAD":"FREE · NO PAYMENT REQUIRED",15,true);text(c,278,226,(remove?"Remove ":reviewMethod=="module.install"?"Update ":"Subscribe to ")+textfield(m,"name")+"?",34,false,940);wrap(c,278,285,875,remove?"This stops the creation and its subscription. Your saved data is kept.":"Download this creation for free. Subscriptions install future updates automatically; you choose when to turn the creation on.",24,4);
  if(!remove){auto*p=field(target,"permissions");std::string labels;for(size_t i=0;p&&i<json_object_array_length(p);i++){if(i)labels+="  /  ";labels+=json_object_get_string(json_object_array_get_idx(p,i));}text(c,278,446,"Permissions",19,true);wrap(c,278,483,870,labels,23,3);text(c,278,578,"Additional permissions will ask for a review.",20,true);}
  button(c,278,666,230,"Cancel","ui.cancel");button(c,533,666,500,remove?"Remove download":reviewMethod=="module.install"?"Download update":"Subscribe & download","ui.confirm","{}",true);
 }
 // Navigation stays local. Only concrete user actions produce manager requests.
 bool local(const StoreButton&b,json_object*state,std::string&method,std::string&params){auto*arg=json_tokener_parse(b.params.c_str());std::string id=textfield(arg,"id");if(arg)json_object_put(arg);
  if(b.method=="ui.discover"||b.method=="ui.library"){view=b.method=="ui.discover"?"discover":"library";selected.clear();reviewId.clear();page=0;}
  else if(b.method=="ui.detail"){selected=id;tab="about";gallery=0;creditPage=0;linkPage=0;}
  else if(b.method=="ui.back")selected.clear();else if(b.method=="ui.settings")tab="settings";
  else if(b.method.rfind("ui.tab.",0)==0)tab=b.method.substr(7);
  else if(b.method=="ui.next")page++;else if(b.method=="ui.prev")page--;
  else if(b.method=="ui.photo-next"||b.method=="ui.photo-prev"){auto*p=field(find(state,selected),"screenshots");int n=p?json_object_array_length(p):0;if(n)gallery=(gallery+n+(b.method=="ui.photo-next"?1:-1))%n;}
  else if(b.method=="ui.credit-next"||b.method=="ui.credit-prev"){auto*p=field(find(state,selected),"credits");int n=p?json_object_array_length(p):0;if(n)creditPage=(creditPage+n+(b.method=="ui.credit-next"?1:-1))%n;}
  else if(b.method=="ui.links-next")linkPage++;else if(b.method=="ui.links-prev")linkPage--;
  else if(b.method=="ui.cancel")reviewId.clear();
  else if(b.method=="ui.subscribe"||b.method=="ui.update"||b.method=="ui.remove"){reviewId=id;reviewMethod=b.method=="ui.remove"?"module.remove":b.method=="ui.subscribe"||boolfield(find(state,id),"subscribed")?"module.subscribe":"module.install";}
  else if(b.method=="ui.confirm"){auto*m=find(state,reviewId);if(m){auto*target=field(m,"update");if(!target)target=m;auto*a=json_object_new_object();json_object_object_add(a,"id",json_object_new_string(reviewId.c_str()));json_object_object_add(a,"subscribed",json_object_new_boolean(true));json_object_object_add(a,"permissions",json_object_get(field(target,"permissions")));method=reviewMethod;params=json_object_to_json_string(a);json_object_put(a);}reviewId.clear();return !method.empty();}
  else {method=b.method;params=b.params;return true;}return false;
 }
};
