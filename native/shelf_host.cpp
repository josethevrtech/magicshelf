#include "magicshelf_sdk.h"
#include <atomic>
#include <csignal>
#include <thread>
static std::atomic<bool> running{true};
static void stop(int){running=false;}
int main(){
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 vr::EVRInitError error;vr::VR_Init(&error,vr::VRApplication_Background);
 if(error){std::cerr<<vr::VR_GetVRInitErrorAsEnglishDescription(error)<<"\n";return 1;}
 try{
  ObjectDock shelf(vr::VROverlay(),magicshelfEnv("MAGICSHELF_LAYOUT_DIR"));
  while(running){
   vr::VREvent_t event;while(vr::VRSystem()->PollNextEvent(&event,sizeof(event)))if(event.eventType==vr::VREvent_Quit){vr::VRSystem()->AcknowledgeQuit_Exiting();running=false;}
   vr::TrackedDevicePose_t poses[vr::k_unMaxTrackedDeviceCount];
   vr::VRSystem()->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding,.01f,poses,vr::k_unMaxTrackedDeviceCount);
   shelf.refresh();shelf.show(poses[0].bPoseIsValid);
   std::this_thread::sleep_for(std::chrono::milliseconds(vr::VROverlay()->IsDashboardVisible()?50:250));
  }
  shelf.destroy();vr::VR_Shutdown();return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";vr::VR_Shutdown();return 1;}
}
