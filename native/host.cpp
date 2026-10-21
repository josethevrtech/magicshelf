#include "magicshelf_sdk.h"
#include <atomic>
#include <csignal>
#include <thread>
#include <mutex>

static std::atomic<bool> running{true},busy{false};
void stop(int){running=false;}
std::string getstr(json_object*j,const char*k){json_object*v=nullptr;return json_object_object_get_ex(j,k,&v)?json_object_get_string(v):"";}
bool getbool(json_object*j,const char*k){json_object*v=nullptr;return json_object_object_get_ex(j,k,&v)&&json_object_get_boolean(v);}
void clipped(Canvas&c,int x,int y,int w,const std::string&s,int size=22){cairo_save(c.c);cairo_rectangle(c.c,x,y-size,w,size+10);cairo_clip(c.c);c.text(x,y,s,size);cairo_restore(c.c);}
struct Button{int x,y,w,h;std::string method,params;bool hit(float px,float py)const{return px>=x&&px<x+w&&py>=y&&py<y+h;}};
int main(int argc,char**argv){try{
 if(argc==3&&std::string(argv[1])=="--icon"){Canvas icon(128,128);icon.fill(.045,.064,.091);icon.rect(23,37,82,65,.58,.79,.72);icon.rect(30,44,68,51,.045,.064,.091);icon.rect(18,27,92,10,.76,.91,.85);icon.text(35,82,"M",39);icon.png(argv[2]);return 0;}
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);std::signal(SIGPIPE,SIG_IGN);
 if(argc==2&&std::string(argv[1])=="--unregister"){vr::EVRInitError error;vr::VR_Init(&error,vr::VRApplication_Background);if(error)return 1;auto path=std::filesystem::path(getenv("HOME"))/".config/magicshelf/magicshelf.vrmanifest";vr::VRApplications()->RemoveApplicationManifest(path.c_str());vr::VR_Shutdown();return 0;}
 vr::EVRInitError error;vr::VR_Init(&error,vr::VRApplication_Overlay);if(error)throw std::runtime_error(vr::VR_GetVRInitErrorAsEnglishDescription(error));
 auto config=magicshelfEnv("MAGICSHELF_LAYOUT_DIR");auto*applications=vr::VRApplications();if(applications->AddApplicationManifest((config+"/magicshelf.vrmanifest").c_str(),false))throw std::runtime_error("Cannot register MagicShelf with SteamVR");applications->SetApplicationAutoLaunch("com.josethevrtech.magicshelf",false);applications->IdentifyApplication(getpid(),"com.josethevrtech.magicshelf");
 auto*o=vr::VROverlay();vr::VROverlayHandle_t panel=0,thumb=0;
 if(o->CreateDashboardOverlay("com.josethevrtech.magicshelf","MagicShelf",&panel,&thumb))throw std::runtime_error("MagicShelf dashboard already exists");
 auto dir=magicshelfEnv("MAGICSHELF_RUNTIME_DIR");
 o->SetOverlayFromFile(thumb,(std::filesystem::canonical("/proc/self/exe").parent_path().parent_path()/"icon.png").c_str());
 o->SetOverlayInputMethod(panel,vr::VROverlayInputMethod_Mouse);vr::HmdVector2_t mouse{{1024,760}};o->SetOverlayMouseScale(panel,&mouse);o->SetOverlayWidthInMeters(panel,1.1f);
 ObjectDock shelf(o,config);Canvas canvas(1024,760);std::string previous,lastImage;int page=0;std::vector<Button> buttons;std::thread worker;
 std::string reviewId,reviewPermissions;std::mutex stateMutex;std::string actionError;
 auto action=[&](std::string method,std::string params){if(busy.exchange(true))return;{std::lock_guard<std::mutex>lock(stateMutex);actionError.clear();}if(worker.joinable())worker.join();worker=std::thread([&,method,params](){
  try{std::string packet="{\"api_version\":1,\"method\":\""+method+"\",\"params\":"+params+"}";auto result=magicshelfRpc(packet);auto*j=json_tokener_parse(result.c_str());if(j){auto error=getstr(j,"error");if(!error.empty()){std::lock_guard<std::mutex>lock(stateMutex);actionError=error;}json_object_put(j);}}
  catch(std::exception&e){std::lock_guard<std::mutex>lock(stateMutex);actionError=e.what();}busy=false;
 });};
 auto button=[&](int x,int y,int w,const char*label,std::string method,std::string params="{}"){
  canvas.rect(x,y,w,48,.15,.21,.27);canvas.text(x+14,y+32,label,21);buttons.push_back({x,y,w,48,method,params});
 };
 while(running){
  vr::TrackedDevicePose_t poses[vr::k_unMaxTrackedDeviceCount];vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding,.01f,poses,vr::k_unMaxTrackedDeviceCount);
  shelf.refresh();shelf.show(poses[0].bPoseIsValid);
  std::ifstream f(dir+"/ui-state.json");std::string data((std::istreambuf_iterator<char>(f)),{});std::string key=data+std::to_string(page)+reviewId+std::to_string(busy.load());{std::lock_guard<std::mutex>lock(stateMutex);key+=actionError;}
  if(key!=previous){auto*j=json_tokener_parse(data.c_str());if(j){
   buttons.clear();canvas.fill(.045,.064,.091);canvas.text(32,53,"MagicShelf",35);canvas.text(32,88,"Your shelf. Your toys.",20,.65,.72,.79);
   button(660,32,330,"Return toys home","home");
   if(!reviewId.empty()){
    canvas.text(48,167,"Install this toy?",30);canvas.text(48,215,reviewId,23);canvas.text(48,266,"Permissions: "+reviewPermissions,21);canvas.text(48,325,"This module runs code as your Linux user.",23);canvas.text(48,367,"Only install toys from publishers you trust.",23);
    button(48,450,200,"Cancel","ui.cancel");button(277,450,200,"Install toy","ui.confirm");
   }else{
    json_object*modules=nullptr;json_object_object_get_ex(j,"modules",&modules);int count=modules?json_object_array_length(modules):0;page=std::clamp(page,0,std::max(0,(count-1)/6));
    for(int i=page*6;i<std::min(count,page*6+6);i++){
     auto*m=json_object_array_get_idx(modules,i);int n=i-page*6,x=32+(n%2)*496,y=119+(n/2)*172;canvas.rect(x,y,464,153,.078,.11,.15);
     clipped(canvas,x+17,y+35,425,getstr(m,"name"),25);clipped(canvas,x+17,y+68,425,getstr(m,"description"),17);
     std::string id=getstr(m,"id");json_object*params=json_object_new_object();json_object_object_add(params,"id",json_object_new_string(id.c_str()));
     if(getbool(m,"installed")){bool enabled=getbool(m,"enabled");json_object_object_add(params,"enabled",json_object_new_boolean(!enabled));button(x+16,y+89,150,enabled?"Turn off":"Turn on","module.toggle",json_object_to_json_string(params));if(getbool(m,"adapter"))button(x+185,y+89,110,"Open","module.open",json_object_to_json_string(params));json_object*update=nullptr;if(json_object_object_get_ex(m,"update",&update))button(x+310,y+89,130,"Update","ui.review",json_object_to_json_string(update));}
     else button(x+16,y+89,170,"Add toy","ui.review",json_object_to_json_string(m));json_object_put(params);
    }
    if(!count)canvas.text(40,190,"Follow the MagicShelf collection from the desktop library.",23);
    if(page>0)button(32,653,130,"Previous","ui.prev");if((page+1)*6<count)button(180,653,130,"Next","ui.next");button(664,653,328,"Check for updates","catalog.refresh");
   }
   std::string message=busy?"Working...":getstr(j,"message");{std::lock_guard<std::mutex>lock(stateMutex);if(!actionError.empty())message=actionError;}clipped(canvas,32,737,960,message,18);
   std::string path=dir+"/library-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+".png";canvas.png(path);if(o->SetOverlayFromFile(panel,path.c_str())==vr::VROverlayError_None){if(!lastImage.empty())std::filesystem::remove(lastImage);lastImage=path;}previous=key;json_object_put(j);
  }}
  vr::VREvent_t event;while(vr::VRSystem()->PollNextEvent(&event,sizeof(event))){if(event.eventType==vr::VREvent_Quit){vr::VRSystem()->AcknowledgeQuit_Exiting();running=false;}}
  while(o->PollNextOverlayEvent(panel,&event,sizeof(event))){if(event.eventType==vr::VREvent_Quit)running=false;if(event.eventType!=vr::VREvent_MouseButtonDown||busy)continue;float x=event.data.mouse.x,y=760-event.data.mouse.y;
   for(auto&b:buttons)if(b.hit(x,y)){if(b.method=="ui.next")page++;else if(b.method=="ui.prev")page--;else if(b.method=="ui.cancel")reviewId.clear();else if(b.method=="ui.review"){
     auto*m=json_tokener_parse(b.params.c_str());reviewId=getstr(m,"id");json_object*p=nullptr;json_object_object_get_ex(m,"permissions",&p);reviewPermissions.clear();for(int i=0;p&&i<(int)json_object_array_length(p);i++){if(i)reviewPermissions+=", ";reviewPermissions+=json_object_get_string(json_object_array_get_idx(p,i));}json_object_put(m);
    }else if(b.method=="ui.confirm"){
     auto*s=json_tokener_parse(data.c_str());json_object*list=nullptr;json_object_object_get_ex(s,"modules",&list);for(int i=0;list&&i<(int)json_object_array_length(list);i++){auto*m=json_object_array_get_idx(list,i);if(getstr(m,"id")==reviewId){json_object*update=nullptr;if(json_object_object_get_ex(m,"update",&update))m=update;json_object*p=nullptr;json_object_object_get_ex(m,"permissions",&p);json_object*args=json_object_new_object();json_object_object_add(args,"id",json_object_new_string(reviewId.c_str()));json_object_object_add(args,"permissions",json_object_get(p));action("module.install",json_object_to_json_string(args));json_object_put(args);break;}}json_object_put(s);reviewId.clear();
    }else action(b.method,b.params);previous.clear();break;}
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
 }
 if(worker.joinable())worker.join();shelf.destroy();o->DestroyOverlay(panel);if(!lastImage.empty())std::filesystem::remove(lastImage);vr::VR_Shutdown();return 0;
}catch(std::exception&e){std::cerr<<"MagicShelf: "<<e.what()<<"\n";return 1;}}
