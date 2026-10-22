#include "compat/object_dock.h"
#include <cassert>
#include <limits>

int main(){
 // A creation can land anywhere along the dock, including a rotated/scaled
 // shelf or curved rail, then return to its own slot without reordering.
 for(bool shelf:{false,true})for(float scale:{.5f,1.f,2.f})for(int count:{1,2,8,16}){
  DockLayout layout;layout.shelf=shelf;layout.count=count;
  layout.joinYaw=56;layout.joinRoll=8;layout.joinPitch=-5;
  if(!shelf){layout.curveRadius=2.8;layout.curvePitch=-40;}
  layout=layout.scaled(scale);M anchor=yawPose(.73f);anchor[12]=1;anchor[13]=1.2;anchor[14]=-.5;
  for(int i=0;i<count;i++)for(float size:{.6f,1.f,3.f}){
   M creation=dockObjectPose(layout.slot(anchor,i),size);
   assert(layout.acceptsDrop(anchor,creation,size));
   M high=creation;high[13]+=3;assert(!layout.acceptsDrop(anchor,high,size));
   M far=creation;far[14]+=5;assert(!layout.acceptsDrop(anchor,far,size));
  }
 }
 DockLayout layout;layout.shelf=true;
 M anchor=identity(),creation=dockObjectPose(layout.slot(anchor,0),1);
 M gap=identity();gap[14]=.13f;M edge=mm(layout.slot(anchor,0),gap);
 assert(!layout.acceptsDrop(anchor,edge,1));assert(layout.acceptsDrop(anchor,edge,1,true));
 M bad=creation;bad[12]=NAN;assert(!layout.acceptsDrop(anchor,bad,1));
 assert(!layout.acceptsDrop(anchor,creation,0));
 layout.count=0;assert(!layout.acceptsDrop(anchor,creation,1));

 // Four deliberate reversals work at different sampling rates and along
 // every axis. Slow adjustment, a single sweep and tracking noise do not.
 for(int hz:{30,45,90,120})for(int axis=0;axis<3;axis++){
  ShakeToDock shake;bool detected=false;
  for(int frame=0;frame<hz*2;frame++){
   double t=double(frame)/hz;V p{};
   if(t>.3)p[axis]=.075f*sinf((t-.3)*2*M_PI*3.2);
   if(shake.update(p,t)){detected=true;break;}
  }
  assert(detected);
 }
 for(int motion=0;motion<4;motion++){
  ShakeToDock shake;
  for(int frame=0;frame<450;frame++){
   double t=frame/90.;float x=motion==0?t*.8f:motion==1?.006f*sinf(t*100):motion==2?.1f*sinf(t*2*M_PI*.4):0;
   assert(!shake.update({x,0,0},t));
  }
 }
 ShakeToDock shake;assert(!shake.update({0,0,0},0));
 assert(!shake.update({1,0,0},.02)); // tracking jump cannot count as a stroke
 assert(!shake.update({NAN,0,0},.04));
 assert(!shake.update({0,0,0},1));assert(!shake.update({.1f,0,0},2));
 shake.reset();assert(!shake.sampled&&!shake.stroke&&shake.reversals==0);

 // Only actual spatial configuration changes request recovery. Invalid and
 // identical rewrites, appearance changes, and the initial load do not.
 auto dir=std::filesystem::temp_directory_path()/("magicshelf-recovery-"+std::to_string(getpid()));
 std::filesystem::create_directories(dir);int revision=0;
 auto write=[&](const char*data){std::ofstream(dir/"object-dock.json")<<data;std::filesystem::last_write_time(dir/"object-dock.json",std::filesystem::file_time_type::clock::now()+std::chrono::seconds(++revision));};
 const char*original=R"({"objects":["local.androidphone.device","local.digitalpartner.device"]})";
 write(original);ObjectDock dock(nullptr,dir.string());assert(!dock.takeHomeRequest());
 auto reload=[&](const char*data){write(data);dock.nextConfig={};dock.reload();};
 reload(original);assert(!dock.takeHomeRequest());
 reload(R"({"opacity":0.8,"objects":["local.androidphone.device","local.digitalpartner.device"]})");assert(!dock.takeHomeRequest());
 reload(R"({"slot_spacing_m":0.16,"objects":["local.androidphone.device","local.digitalpartner.device"]})");assert(dock.takeHomeRequest());assert(!dock.takeHomeRequest());
 reload("{broken");assert(!dock.takeHomeRequest());
 reload(R"({"slot_spacing_m":0.16,"objects":["local.digitalpartner.device","local.androidphone.device"]})");assert(dock.takeHomeRequest());
 assert(!dock.canSnap(creation,1)); // a hidden/unavailable dock cannot catch drops
 std::filesystem::remove_all(dir);
 for(uint32_t type:{vr::VREvent_ResetDashboard,vr::VREvent_SeatedZeroPoseReset,vr::VREvent_StandingZeroPoseReset,vr::VREvent_ChaperoneUniverseHasChanged,vr::VREvent_ChaperoneRoomSetupCommitted})assert(dockResetEvent(type));
 for(uint32_t type:{vr::VREvent_DashboardActivated,vr::VREvent_DashboardDeactivated,vr::VREvent_FocusLeave,vr::VREvent_TrackedDeviceUpdated})assert(!dockResetEvent(type));
 std::cout<<AppTitle<<": dock drop geometry, shake recognition, noise rejection and reset routing passed\n";
}
