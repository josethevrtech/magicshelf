#include "magicshelf_sdk.h"
#include "storefront_input.h"
#include "dashboard_texture.h"
#include <atomic>
#include <csignal>
#include <ctime>
#include <thread>
#include <mutex>
#include <memory>
#include <set>

static constexpr int RenderScale=2;
static constexpr float DashboardWidthMeters=1.8f;
static std::atomic<bool> running{true},busy{false};
void stop(int){running=false;}
struct ActionWorker {std::thread thread;~ActionWorker(){if(thread.joinable())thread.join();}};
struct OverlayLifetime {
 vr::IVROverlay*overlay;vr::VROverlayHandle_t panel=0;
 ~OverlayLifetime(){if(panel){overlay->ClearOverlayTexture(panel);overlay->DestroyOverlay(panel);}}
};
struct Damage {
 int x=StoreUI::W,y=StoreUI::H,right=0,bottom=0;
 void add(const StoreButton&b){x=std::min(x,b.x);y=std::min(y,b.y);right=std::max(right,b.x+b.w);bottom=std::max(bottom,b.y+b.h);}
 bool empty()const{return right<=x||bottom<=y;}
};

void dashboard(){
 auto config=magicshelfEnv("MAGICSHELF_LAYOUT_DIR"),dir=magicshelfEnv("MAGICSHELF_RUNTIME_DIR");
 auto*applications=vr::VRApplications();
 if(applications->AddApplicationManifest((config+"/magicshelf.vrmanifest").c_str(),false))throw std::runtime_error("Cannot register MagicShelf with SteamVR");
 applications->SetApplicationAutoLaunch("com.josethevrtech.magicshelf",true);applications->IdentifyApplication(getpid(),"com.josethevrtech.magicshelf");
 auto*o=vr::VROverlay();
 DashboardTexture gpu(StoreUI::W*RenderScale,StoreUI::H*RenderScale);
 OverlayLifetime overlay{o};vr::VROverlayHandle_t thumb=0;
 if(o->CreateDashboardOverlay("com.josethevrtech.magicshelf","MagicShelf",&overlay.panel,&thumb))throw std::runtime_error("MagicShelf dashboard already exists");
 auto panel=overlay.panel;
 o->SetOverlayFlag(panel,vr::VROverlayFlags_MinimalControlBar,true);
 o->SetOverlayFlag(panel,vr::VROverlayFlags_EnableControlBarClose,true);
 o->SetOverlayFlag(panel,vr::VROverlayFlags_SendVRDiscreteScrollEvents,true);
 o->SetOverlayFromFile(thumb,(std::filesystem::canonical("/proc/self/exe").parent_path().parent_path()/"icon.png").c_str());
 o->SetOverlayInputMethod(panel,vr::VROverlayInputMethod_Mouse);vr::HmdVector2_t mouse{{StoreUI::W,StoreUI::H}};
 o->SetOverlayMouseScale(panel,&mouse);o->SetOverlayWidthInMeters(panel,DashboardWidthMeters);
 vr::VRTextureBounds_t bounds{0,0,1,1};o->SetOverlayTextureBounds(panel,&bounds);
 ObjectDock shelf(o,config);Canvas canvas(StoreUI::W*RenderScale,StoreUI::H*RenderScale);cairo_scale(canvas.c,RenderScale,RenderScale);
 // The GPU uploader converts only dirty regions. Canvas's full RGBA copy is unused.
 canvas.rgba.clear();canvas.rgba.shrink_to_fit();
 StoreUI ui;StoreInput input;bool initialView=false;float appliedWidth=DashboardWidthMeters;
 std::string data,previous,previousHover,previousPressed,actionError;
 std::mutex stateMutex;ActionWorker worker;
 auto action=[&](const std::string&method,const std::string&params){
  if(busy.exchange(true))return;
  {std::lock_guard<std::mutex>lock(stateMutex);actionError.clear();}
  if(worker.thread.joinable())worker.thread.join();
  worker.thread=std::thread([&,method,params](){
   try{auto result=magicshelfRpc("{\"api_version\":1,\"method\":\""+method+"\",\"params\":"+params+"}");auto*j=json_tokener_parse(result.c_str());if(!j)throw std::runtime_error("MagicShelf returned an invalid response");auto message=textfield(j,"error");json_object_put(j);if(!message.empty())throw std::runtime_error(message);}
   catch(std::exception&e){std::lock_guard<std::mutex>lock(stateMutex);actionError=e.what();}
   busy=false;
  });
 };
 using State=std::unique_ptr<json_object,decltype(&json_object_put)>;
 State state(json_tokener_parse("{\"modules\":[],\"message\":\"Connecting to MagicShelf...\"}"),json_object_put);
 using Clock=std::chrono::steady_clock;auto poll=Clock::now(),dockTick=poll,activityTick=poll;
 auto nextNotice=poll;std::set<std::string> delivered;std::set<vr::VRNotificationId> noticeIds;
 uint64_t frames=0,fullFrames=0,partialFrames=0;double peakMs=0;
 while(running){
  auto now=Clock::now();
  if(now>=dockTick){vr::TrackedDevicePose_t poses[vr::k_unMaxTrackedDeviceCount];vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding,.01f,poses,vr::k_unMaxTrackedDeviceCount);shelf.refresh();shelf.show(poses[0].bPoseIsValid);dockTick=now+std::chrono::milliseconds(50);}
  if(now>=poll){std::ifstream f(dir+"/ui-state.json");std::string next((std::istreambuf_iterator<char>(f)),{});if(next!=data){auto*j=json_tokener_parse(next.c_str());if(j){state.reset(j);data=next;}}poll=now+std::chrono::milliseconds(100);}
  auto*j=state.get();auto*prefs=field(field(j,"preferences"),"values");
  if(prefs){
   if(!initialView){ui.view=textfield(prefs,"start_view")=="library"?"library":"discover";initialView=true;}
   float width=json_object_get_double(field(prefs,"dashboard_width_m"));
   if(std::isfinite(width)&&width>=1.2f&&width<=2.4f&&fabsf(width-appliedWidth)>.001f){o->SetOverlayWidthInMeters(panel,width);appliedWidth=width;}
  }
  bool working=busy||boolfield(j,"busy")||textfield(field(j,"framework_update"),"stage")=="installing";
  if(!working&&now>=nextNotice){
   nextNotice=now+std::chrono::seconds(30);auto*notices=field(j,"update_notices");
   for(size_t i=0;notices&&i<json_object_array_length(notices);i++){
    auto*n=json_object_array_get_idx(notices,i);auto identity=textfield(n,"id")+":"+textfield(n,"token");
    if(boolfield(n,"announced")||boolfield(n,"dismissed")||delivered.count(identity))continue;
    auto name=textfield(n,"name");if(name.size()>110){size_t end=110;while(end&&((unsigned char)name[end]&0xc0)==0x80)--end;name.resize(end);}
    auto message=name+" update ready\nKeep playing. It installs when Off. Open MagicShelf for options.";
    vr::VRNotificationId id=0;auto*notifications=vr::VRNotifications();
    auto result=notifications?notifications->CreateNotification(panel,0,vr::EVRNotificationType_Transient,message.c_str(),vr::EVRNotificationStyle_Application,nullptr,&id):vr::VRNotificationError_ServiceUnavailable;
    if(result==vr::VRNotificationError_OK){delivered.insert(identity);noticeIds.insert(id);action("notifications.ack",noticeArgs(n,"announced"));}
    else{nextNotice=now+std::chrono::seconds(60);std::cerr<<"MagicShelf update toast unavailable: "<<result<<" (notice remains in Updates ready)\n";}
    break;
   }
  }
  if(now>=activityTick){
   // Publish even while hidden. Atomic replacement prevents partial heartbeats.
   auto path=dir+"/dashboard-activity.json";
   std::ofstream activity(path+".next");
   activity<<"{\"pid\":"<<getpid()<<",\"time\":"<<std::time(nullptr)<<",\"visible\":"<<(o->IsOverlayVisible(panel)?"true":"false")<<",\"busy\":"<<(working?"true":"false")<<"}\n";
   activity.close();std::filesystem::rename(path+".next",path);activityTick=now+std::chrono::seconds(1);
  }
  vr::VREvent_t event;
  while(vr::VRSystem()->PollNextEvent(&event,sizeof(event))){
   if(event.eventType==vr::VREvent_Quit){vr::VRSystem()->AcknowledgeQuit_Exiting();running=false;}
   if(event.eventType==vr::VREvent_Notification_BeginInteraction&&noticeIds.count(event.data.notification.notificationId)){ui.view="updates";ui.selected.clear();ui.reviewId.clear();input.cancel();o->ShowDashboard("com.josethevrtech.magicshelf");}
  }
  while(o->PollNextOverlayEvent(panel,&event,sizeof(event))){
   if(event.eventType==vr::VREvent_Notification_BeginInteraction&&noticeIds.count(event.data.notification.notificationId)){ui.view="updates";ui.selected.clear();ui.reviewId.clear();input.cancel();o->ShowDashboard("com.josethevrtech.magicshelf");continue;}
   if(event.eventType==vr::VREvent_Notification_Destroyed){noticeIds.erase(event.data.notification.notificationId);continue;}
   if(event.eventType==vr::VREvent_OverlayClosed){o->HideOverlay(panel);input.cancel();continue;}
   if(event.eventType==vr::VREvent_ScrollDiscrete&&!ui.selected.empty()&&ui.tab=="about"&&event.data.scroll.ydelta!=0){ui.aboutPage+=event.data.scroll.ydelta<0?1:-1;input.cancel();continue;}
   if(event.eventType==vr::VREvent_OverlayShown){action("catalog.discover","{}");continue;}
   if(event.eventType==vr::VREvent_Quit){running=false;continue;}
   if(event.eventType==vr::VREvent_FocusLeave||event.eventType==vr::VREvent_OverlayHidden){input.cancel();continue;}
   if(event.eventType==vr::VREvent_MouseMove){input.move(ui,event.data.mouse.x,StoreUI::H-event.data.mouse.y,working);continue;}
   if(event.eventType!=vr::VREvent_MouseButtonDown&&event.eventType!=vr::VREvent_MouseButtonUp)continue;
   if(event.data.mouse.button!=vr::VRMouseButton_Left)continue;
   float x=event.data.mouse.x,y=StoreUI::H-event.data.mouse.y;
   if(event.eventType==vr::VREvent_MouseButtonDown)input.down(ui,x,y,working);
   else if(auto hit=input.up(ui,x,y,working)){
    if(hit->method=="ui.close"){o->HideOverlay(panel);input.cancel();continue;}
    std::string method,params;auto before=ui.key();if(ui.local(*hit,j,method,params))action(method,params);
    else if(hit->method=="ui.discover")action("catalog.discover","{}");
    if(ui.key()!=before)input.cancel();
    o->TriggerLaserMouseHapticVibration(panel,.012f,90.f,.16f);
    working=busy||boolfield(j,"busy")||textfield(field(j,"framework_update"),"stage")=="installing";
   }
  }
  std::string failure;{std::lock_guard<std::mutex>lock(stateMutex);failure=actionError;}
  auto key=data+ui.key()+std::to_string(working)+failure;
  bool full=key!=previous,feedback=input.hover!=previousHover||input.pressed!=previousPressed;
  bool capture=std::filesystem::exists(dir+"/capture-dashboard.request");
  if((full||feedback||capture)&&(frames==0||o->IsOverlayVisible(panel)||capture)){
   auto started=Clock::now();Damage damage;
   if(full||capture)damage={0,0,StoreUI::W,StoreUI::H};
   else for(const auto&b:ui.buttons){auto id=StoreInput::identity(b);if(id==input.hover||id==previousHover||id==input.pressed||id==previousPressed)damage.add(b);}
   ui.hover=input.hover;ui.pressed=input.pressed;
   if(!damage.empty()){
    cairo_save(canvas.c);cairo_rectangle(canvas.c,damage.x,damage.y,damage.right-damage.x,damage.bottom-damage.y);cairo_clip(canvas.c);
    ui.draw(canvas,j,working,failure.empty()?textfield(j,"message"):failure,!failure.empty());cairo_restore(canvas.c);
    gpu.update(canvas,damage.x*RenderScale,damage.y*RenderScale,(damage.right-damage.x)*RenderScale,(damage.bottom-damage.y)*RenderScale);gpu.present(o,panel);
    frames++;if(full)fullFrames++;else partialFrames++;
    double ms=std::chrono::duration<double,std::milli>(Clock::now()-started).count();peakMs=std::max(peakMs,ms);
    std::ofstream stats(dir+"/dashboard-render.json");stats<<"{\"pid\":"<<getpid()<<",\"frames\":"<<frames<<",\"full\":"<<fullFrames<<",\"partial\":"<<partialFrames<<",\"texture_allocations\":1,\"last_ms\":"<<ms<<",\"peak_ms\":"<<peakMs<<",\"width\":"<<canvas.w<<",\"height\":"<<canvas.h<<"}\n";
   }
   if(capture){canvas.png(dir+"/dashboard-capture.png");std::filesystem::remove(dir+"/capture-dashboard.request");}
   previous=key;previousHover=input.hover;previousPressed=input.pressed;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(o->IsOverlayVisible(panel)?8:50));
 }
 shelf.destroy();
 // worker joins, then the overlay releases its texture, then EGL is destroyed.
}

int main(int argc,char**argv){try{
 if(argc==3&&std::string(argv[1])=="--icon"){Canvas icon(128,128);ShelfTheme::logo(icon,0,0,128);icon.png(argv[2]);return 0;}
 if(argc>=4&&std::string(argv[1])=="--preview"){auto*j=json_object_from_file(argv[2]);if(!j)throw std::runtime_error("Cannot read preview state");Canvas c(StoreUI::W*RenderScale,StoreUI::H*RenderScale);cairo_scale(c.c,RenderScale,RenderScale);StoreUI ui;if(argc>4)ui.selected=argv[4];if(argc>5)ui.tab=argv[5];ui.draw(c,j,false,"Ready");c.png(argv[3]);json_object_put(j);return 0;}
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);std::signal(SIGPIPE,SIG_IGN);
 bool command=argc==2;vr::EVRInitError error;vr::VR_Init(&error,command?vr::VRApplication_Background:vr::VRApplication_Overlay);
 if(error)throw std::runtime_error(vr::VR_GetVRInitErrorAsEnglishDescription(error));
 if(command&&std::string(argv[1])=="--unregister"){auto path=std::filesystem::path(getenv("HOME"))/".config/magicshelf/magicshelf.vrmanifest";vr::VRApplications()->RemoveApplicationManifest(path.c_str());if(vr::VRApplications()->IsApplicationInstalled("com.josethevrtech.magicshelf"))throw std::runtime_error("MagicShelf is still registered with SteamVR");}
 else if(command&&std::string(argv[1])=="--show"){
  vr::VROverlayHandle_t handle=0;auto until=std::chrono::steady_clock::now()+std::chrono::seconds(10);
  while(vr::VROverlay()->FindOverlay("com.josethevrtech.magicshelf",&handle)!=vr::VROverlayError_None){if(std::chrono::steady_clock::now()>until)throw std::runtime_error("MagicShelf dashboard did not start");std::this_thread::sleep_for(std::chrono::milliseconds(100));}
  vr::VROverlay()->ShowDashboard("com.josethevrtech.magicshelf");
 }else if(command)throw std::runtime_error("Unknown MagicShelf dashboard option");
 else dashboard();
 vr::VR_Shutdown();return 0;
}catch(std::exception&e){std::cerr<<"MagicShelf: "<<e.what()<<"\n";vr::VR_Shutdown();return 1;}}
