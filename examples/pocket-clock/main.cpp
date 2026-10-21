#include "magicshelf_sdk.h"
#include <csignal>
#include <thread>
static bool running=true;void stop(int){running=false;}
int main(){try{
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);vr::EVRInitError error;vr::VR_Init(&error,vr::VRApplication_Overlay);if(error)throw std::runtime_error(vr::VR_GetVRInitErrorAsEnglishDescription(error));
 auto*o=vr::VROverlay();vr::VROverlayHandle_t clock;std::string key=magicshelfEnv("MAGICSHELF_MODULE_KEY");if(o->CreateOverlay(key.c_str(),"Pocket Clock",&clock))return 1;
 o->SetOverlayInputMethod(clock,vr::VROverlayInputMethod_None);o->SetOverlayFlag(clock,vr::VROverlayFlags_VisibleInDashboard,true);
 ObjectDock dock(o,magicshelfEnv("MAGICSHELF_LAYOUT_DIR"));Canvas face(560,320);std::string last,lastFile;magicshelfReady();
 while(running){time_t now=time(nullptr);tm local{};localtime_r(&now,&local);char stamp[20],date[64];strftime(stamp,sizeof(stamp),"%H:%M",&local);strftime(date,sizeof(date),"%a, %b %d",&local);
  if(last!=stamp){face.fill(.04,.075,.09);face.text(38,68,"POCKET CLOCK",24,.63,.77,.78);face.text(35,210,stamp,112,.83,.96,.92);face.text(39,274,date,28,.63,.77,.78);std::string path=magicshelfEnv("MAGICSHELF_DATA_DIR")+"/clock-"+std::to_string(now)+".png";face.png(path);if(o->SetOverlayFromFile(clock,path.c_str()))throw std::runtime_error("Clock texture failed");if(!lastFile.empty())std::filesystem::remove(lastFile);lastFile=path;last=stamp;}
  vr::TrackedDevicePose_t poses[vr::k_unMaxTrackedDeviceCount];vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding,0,poses,vr::k_unMaxTrackedDeviceCount);
  if(dock.refresh()&&poses[0].bPoseIsValid){float scale=magicshelfFit(dock,.14f,.08f);M lift=identity();lift[13]=.04f*scale;auto transform=magicshelfTransform(mm(dock.slotPose,lift));o->SetOverlayTransformAbsolute(clock,vr::TrackingUniverseStanding,&transform);o->SetOverlayWidthInMeters(clock,.14f*scale);o->ShowOverlay(clock);}else o->HideOverlay(clock);
  vr::VREvent_t event;while(vr::VRSystem()->PollNextEvent(&event,sizeof(event)))if(event.eventType==vr::VREvent_Quit){vr::VRSystem()->AcknowledgeQuit_Exiting();running=false;}
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
 }
 o->DestroyOverlay(clock);vr::VR_Shutdown();return 0;
}catch(std::exception&e){std::cerr<<"Pocket Clock: "<<e.what()<<"\n";return 1;}}
