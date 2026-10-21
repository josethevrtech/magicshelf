#pragma once
#include "dock_layout.h"
#include "openvr.h"
#include <json-c/json.h>
#include <filesystem>
#include <chrono>
#include <memory>
#include <set>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

struct ObjectDock {
 vr::IVROverlay*overlay;vr::VROverlayHandle_t background=0;int owner=-1;
 std::string base,moduleKey=DeviceKey,anchorKey="valve.steam.gamepadui.bar";DockLayout layout,effective;
 bool shelfOwner=true;
 int slot=AndroidOnly?0:1;M anchor=identity(),slotPose=identity();bool available=false,anchorValid=false,repaint=true;
 struct RailSection {vr::VROverlayHandle_t handle=0;M pose{};float width=0;bool shown=false,placed=false;};
 std::vector<RailSection> sections;
 std::chrono::steady_clock::time_point nextConfig{},nextOwner{};
 std::filesystem::file_time_type configTime{};std::unique_ptr<Canvas> image;
 explicit ObjectDock(vr::IVROverlay*o,const std::string&b):overlay(o),base(b){
  if(auto*p=getenv("MAGICSHELF_LAYOUT_DIR"))if(*p)base=p;
  if(auto*p=getenv("MAGICSHELF_MODULE_KEY"))if(*p)moduleKey=p;
  if(auto*p=getenv("MAGICSHELF_SHELF_OWNER"))shelfOwner=std::string(p)!="0";
  reload();
 }
 void reload(){
  auto now=std::chrono::steady_clock::now();if(now<nextConfig)return;nextConfig=now+std::chrono::seconds(1);
  std::error_code ec;auto t=std::filesystem::last_write_time(base+"/object-dock.json",ec);if(ec||t==configTime)return;
  auto*j=json_object_from_file((base+"/object-dock.json").c_str());if(!j)return;
  DockLayout candidate;std::string key="valve.steam.gamepadui.bar";int index=-1;bool valid=true;json_object*v=nullptr;
  if(json_object_object_get_ex(j,"schema",&v)&&(!json_object_is_type(v,json_type_int)||(json_object_get_int(v)!=2&&json_object_get_int(v)!=3)))valid=false;
  auto number=[&](const char*k,float&dest,float lo,float hi){if(json_object_object_get_ex(j,k,&v)){if(!json_object_is_type(v,json_type_double)&&!json_object_is_type(v,json_type_int)){valid=false;return;}double n=json_object_get_double(v);if(!std::isfinite(n)||n<lo||n>hi)valid=false;else dest=n;}};
  number("slot_spacing_m",candidate.spacing,.12f,.5f);number("object_height_m",candidate.objectHeight,.12f,.20f);
  number("right_edge_m",candidate.rightEdge,-2.f,2.f);number("center_y_m",candidate.centerY,-1.f,1.f);number("depth_m",candidate.depth,-2.f,2.f);number("rail_height_m",candidate.railHeight,.03f,.10f);number("lean_degrees",candidate.leanDegrees,-25.f,25.f);
  number("join_yaw_degrees",candidate.joinYaw,-180.f,180.f);number("join_pitch_degrees",candidate.joinPitch,-45.f,45.f);number("join_roll_degrees",candidate.joinRoll,-45.f,45.f);
  number("curve_radius_m",candidate.curveRadius,0.f,10.f);number("curve_pitch_degrees",candidate.curvePitch,-75.f,75.f);
  number("foot_inset_m",candidate.footInset,-.03f,.05f);number("front_offset_m",candidate.frontOffset,0.f,.05f);
  number("opacity",candidate.opacity,.1f,1.f);
  if(json_object_object_get_ex(j,"style",&v)){if(!json_object_is_type(v,json_type_string))valid=false;else{std::string style=json_object_get_string(v);if(style=="shelf")candidate.shelf=true;else if(style!="rail")valid=false;}}
  if(json_object_object_get_ex(j,"launcher_only",&v)){if(!json_object_is_type(v,json_type_boolean))valid=false;else candidate.launcherOnly=json_object_get_boolean(v);}
  if(candidate.shelf&&candidate.curveRadius>0)valid=false;
  if(json_object_object_get_ex(j,"anchor_overlay",&v)){if(json_object_is_type(v,json_type_string))key=json_object_get_string(v);else valid=false;}
  if(json_object_object_get_ex(j,"objects",&v)&&json_object_is_type(v,json_type_array)){
   candidate.count=json_object_array_length(v);if(candidate.count>16)valid=false;std::set<std::string> keys;
   for(int i=0;valid&&i<candidate.count;i++){auto*entry=json_object_array_get_idx(v,i);if(!json_object_is_type(entry,json_type_string)){valid=false;break;}std::string k=json_object_get_string(entry);if(k.empty()||!keys.insert(k).second){valid=false;break;}if(k==moduleKey)index=i;}
  }else valid=false;
  json_object_put(j);configTime=t;
  if(!valid){std::cerr<<"Power Toys: invalid configuration; keeping previous layout\n";return;}
  layout=candidate;anchorKey=key;slot=index;repaint=true;
 }
 bool refresh(){
  reload();available=false;anchorValid=false;if(!overlay->IsDashboardVisible())return false;
  vr::VROverlayHandle_t bar=0;vr::HmdVector2_t scale{};
  if(overlay->FindOverlay(anchorKey.c_str(),&bar)||overlay->GetOverlayMouseScale(bar,&scale))return false;
  if(!dockVisible(true,overlay->IsOverlayVisible(bar),overlay->IsActiveDashboardOverlay(bar),layout.launcherOnly))return false;
  if(!(scale.v[0]>0&&scale.v[1]>0)||!std::isfinite(scale.v[0])||!std::isfinite(scale.v[1]))return false;
  vr::HmdMatrix34_t center{};
  if(overlay->GetTransformForOverlayCoordinates(bar,vr::TrackingUniverseStanding,{{scale.v[0]*.5f,scale.v[1]*.5f}},&center))return false;
  M matrix=identity();for(int r=0;r<3;r++)for(int c=0;c<4;c++)matrix[r+c*4]=center.m[r][c];
  if(!rigidDockAnchor(matrix,anchor))return false;
  float sceneScale=sqrtf(matrix[0]*matrix[0]+matrix[1]*matrix[1]+matrix[2]*matrix[2])/.369f;effective=layout.scaled(std::clamp(sceneScale,.2f,4.f));
  anchorValid=true;if(slot<0)return false;slotPose=effective.slot(anchor,slot);available=true;return true;
 }
 void claim(){
  if(!shelfOwner)return;
  if(background)return;auto now=std::chrono::steady_clock::now();if(now<nextOwner)return;nextOwner=now+std::chrono::seconds(1);
  int fd=open((base+"/power-toys-dock.lock").c_str(),O_CREAT|O_RDWR|O_CLOEXEC,0600);if(fd<0)return;
  if(flock(fd,LOCK_EX|LOCK_NB)){close(fd);return;}
  if(overlay->CreateOverlay("local.powertoys.dock","Power Toys",&background)){background=0;close(fd);return;}
  owner=fd;sections.push_back({background});overlay->SetOverlayInputMethod(background,vr::VROverlayInputMethod_None);
  overlay->SetOverlayFlag(background,vr::VROverlayFlags_VisibleInDashboard,true);repaint=true;
 }
 void show(bool tracking){
  claim();if(!background)return;
  auto hide=[&](RailSection&s){if(s.shown){overlay->HideOverlay(s.handle);s.shown=false;}};
  if(!tracking||!anchorValid||layout.count==0){for(auto&s:sections)hide(s);return;}
  int count=layout.shelf?2:effective.radius()>0?std::clamp((int)ceilf(effective.width()/effective.radius()/(M_PI/360.f)),1,32):1;
  while((int)sections.size()<count){
   vr::VROverlayHandle_t handle=0;std::string key="local.powertoys.dock.segment."+std::to_string(sections.size());
   if(overlay->CreateOverlay(key.c_str(),"Power Toys rail",&handle))return;
   overlay->SetOverlayInputMethod(handle,vr::VROverlayInputMethod_None);overlay->SetOverlayFlag(handle,vr::VROverlayFlags_VisibleInDashboard,true);
   sections.push_back({handle});repaint=true;
  }
  if(repaint&&layout.shelf){
   for(int i=0;i<2;i++){
    float height=i==0?layout.height():layout.lipHeight();int w=1280,h=std::max(8,(int)std::lround(w*height/layout.width()));
    image=std::make_unique<Canvas>(w,h);cairo_set_operator(image->c,CAIRO_OPERATOR_SOURCE);cairo_set_source_rgba(image->c,0,0,0,0);cairo_paint(image->c);cairo_set_operator(image->c,CAIRO_OPERATOR_OVER);
    float radius=std::min(h*.35f,w*.008f/layout.width());cairo_new_sub_path(image->c);
    cairo_arc(image->c,w-radius,radius,radius,-M_PI/2,0);cairo_arc(image->c,w-radius,h-radius,radius,0,M_PI/2);cairo_arc(image->c,radius,h-radius,radius,M_PI/2,M_PI);cairo_arc(image->c,radius,radius,radius,M_PI,3*M_PI/2);cairo_close_path(image->c);
    cairo_set_source_rgb(image->c,7/255.,10/255.,14/255.);cairo_fill_preserve(image->c);
    if(i==0){cairo_set_source_rgba(image->c,.35,.42,.48,.35);cairo_set_line_width(image->c,2);cairo_stroke(image->c);}else cairo_new_path(image->c);
    std::string path=base+"/power-toys-shelf-v1-"+std::to_string(w)+"x"+std::to_string(h)+"-"+std::to_string((int)lroundf(radius*100))+"-"+std::to_string(i)+".png",temporary=path+".next";
    if(cairo_surface_write_to_png(image->s,temporary.c_str())!=CAIRO_STATUS_SUCCESS)return;
    std::error_code ec;std::filesystem::rename(temporary,path,ec);if(ec)return;
    if(overlay->SetOverlayFromFile(sections[i].handle,path.c_str()))return;
    overlay->SetOverlayTexelAspect(sections[i].handle,layout.width()*h/(height*w));
    overlay->SetOverlayAlpha(sections[i].handle,layout.opacity);overlay->SetOverlaySortOrder(sections[i].handle,0);
    overlay->SetOverlayCurvature(sections[i].handle,0);overlay->SetOverlayPreCurvePitch(sections[i].handle,0);
   }
   repaint=false;
  }
  if(repaint){
   float part=layout.width()/count,overlap=count>1?.0003f:0.f;
   int h=std::clamp((int)floorf(1920*layout.height()/(part+overlap)),1,256),w=std::clamp((int)std::lround(h*(part+overlap)/layout.height()),8,1920);
   for(int i=0;i<count;i++){
    image=std::make_unique<Canvas>(w,h);cairo_set_operator(image->c,CAIRO_OPERATOR_SOURCE);cairo_set_source_rgba(image->c,0,0,0,0);cairo_paint(image->c);cairo_set_operator(image->c,CAIRO_OPERATOR_OVER);
    float radius=std::min(w*.45f,h*.006f/layout.height());cairo_new_sub_path(image->c);
    if(i==0){cairo_move_to(image->c,w,0);cairo_line_to(image->c,w,h);cairo_line_to(image->c,radius,h);cairo_arc(image->c,radius,h-radius,radius,M_PI/2,M_PI);cairo_arc(image->c,radius,radius,radius,M_PI,3*M_PI/2);cairo_close_path(image->c);}
    else cairo_rectangle(image->c,0,0,w,h);
    cairo_set_source_rgb(image->c,14/255.,20/255.,27/255.);cairo_fill(image->c);
    // Persistent PNG sections avoid the Frame's invisible curved-overlay path.
    // SteamVR caches file uploads by path, so a new raster shape needs a new path.
    std::string path=base+"/power-toys-backing-v2-"+std::to_string(count)+"-"+std::to_string(w)+"x"+std::to_string(h)+"-"+std::to_string((int)lroundf(radius*100))+"-"+std::to_string(i)+".png",temporary=path+".next";
    if(cairo_surface_write_to_png(image->s,temporary.c_str())!=CAIRO_STATUS_SUCCESS)return;
    std::error_code ec;std::filesystem::rename(temporary,path,ec);if(ec)return;
    if(overlay->SetOverlayFromFile(sections[i].handle,path.c_str()))return;
    overlay->SetOverlayTexelAspect(sections[i].handle,(part+overlap)*h/(layout.height()*w));
    overlay->SetOverlayAlpha(sections[i].handle,layout.opacity);
    overlay->SetOverlayCurvature(sections[i].handle,0);overlay->SetOverlayPreCurvePitch(sections[i].handle,0);
   }
   repaint=false;
  }
  float part=effective.width()/count,overlap=count>1?.0003f*effective.width()/layout.width():0.f;
  for(int i=0;i<(int)sections.size();i++){
   auto&s=sections[i];if(i>=count){hide(s);continue;}
   // Arc distance runs left-to-right, terminating at the calibrated Steam join.
   M m=layout.shelf?effective.shelfPart(anchor,i):effective.surface(anchor,-effective.width()+(i+.5f)*part);float width=layout.shelf?effective.width():part+overlap;
   bool moved=!s.placed;for(int j=0;j<16;j++)moved|=fabsf(m[j]-s.pose[j])>.00001f;
   if(moved){vr::HmdMatrix34_t tr{};for(int r=0;r<3;r++)for(int c=0;c<4;c++)tr.m[r][c]=m[r+c*4];overlay->SetOverlayTransformAbsolute(s.handle,vr::TrackingUniverseStanding,&tr);s.pose=m;s.placed=true;}
   if(width!=s.width){overlay->SetOverlayWidthInMeters(s.handle,width);s.width=width;}
   if(!s.shown){overlay->ShowOverlay(s.handle);s.shown=true;}
  }
 }
 float size(float userSize)const{return dockObjectSize(userSize,effective.objectHeight);}
 M model(float userSize)const{return dockObjectPose(slotPose,size(userSize));}
 void destroy(){for(auto&s:sections)overlay->DestroyOverlay(s.handle);sections.clear();background=0;if(owner>=0)close(owner);owner=-1;}
};
