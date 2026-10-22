#pragma once
#include "render.h"
#include <cstdint>

// Keep the selected point attached to the controller's laser. Thumbstick depth
// translates along that ray without changing the creation's size or rotation.
struct RoomGrab {
 bool active=false,watchTriggerRelease=false;
 uint32_t controller=0;
 M offset=identity();
 V ray{0,0,-1};
 float distance=0,pendingScrollDepth=0;
 static constexpr float MinDistance=.20f,MaxDistance=5.f,DepthSpeed=1.5f;
 static constexpr float ScrollMetresPerUnit=.075f;
 void begin(uint32_t index,M hand,M room,bool watchRelease=false){
  beginAt(index,hand,room,point(room,{0,0,0}),watchRelease);
 }
 void beginAt(uint32_t index,M hand,M room,V target,bool watchRelease=false){
  controller=index;offset=mm(inverse(hand),room);
  V local=point(inverse(hand),target);distance=std::sqrt(dot(local,local));
  ray=distance>.0001f?mul(local,1.f/distance):V{0,0,-1};
  pendingScrollDepth=0;active=true;watchTriggerRelease=watchRelease;
 }
 void moveDepth(float stick,float dt){
  if(!active||!std::isfinite(stick)||!std::isfinite(dt)||dt<=0)return;
  moveDepthBy(std::clamp(stick,-1.f,1.f)*DepthSpeed*std::min(dt,.05f));
 }
 // SteamVR's dashboard owns the stick on Frame and delivers integrated scroll
 // deltas instead of an active analog action. Forward produces positive scroll.
 // Do not dead-zone these deltas or multiply them by frame time a second time.
 bool queueScrollDepth(uint32_t source,float delta,float age){
  if(!active||source!=controller||!std::isfinite(delta)||!std::isfinite(age)||age<0||age>.1f)return false;
  pendingScrollDepth=std::clamp(pendingScrollDepth+delta*ScrollMetresPerUnit,-DepthSpeed*.05f,DepthSpeed*.05f);
  return true;
 }
 void updateDepth(float stick,float dt,bool axisAvailable){
  if(axisAvailable)moveDepth(stick,dt);
  else moveDepthBy(pendingScrollDepth);
  pendingScrollDepth=0;
 }
 void moveDepthBy(float step){
  if(!active||!std::isfinite(step))return;
  // An existing placement outside the range may move back gradually, without
  // jumping to a limit when the user first touches the stick.
  float next=std::clamp(distance+step,std::min(MinDistance,distance),std::max(MaxDistance,distance));
  for(int i=0;i<3;i++)offset[12+i]+=ray[i]*(next-distance);
  distance=next;
 }
 M follow(M hand)const{return mm(hand,offset);}
 void end(){active=false;watchTriggerRelease=false;pendingScrollDepth=0;}
};

// Detect deliberate controller shakes, independent of the creation's distance.
// Feed the controller's short forward tip relative to the head, only while held.
struct ShakeToDock {
 bool sampled=false,stroke=false;int reversals=0;
 V previous{},peak{},direction{};
 double last=0,began=0,window=0,turned=0;
 void reset(){sampled=stroke=false;reversals=0;}
 bool update(V p,double now){
  for(float value:p)if(!std::isfinite(value)){reset();return false;}
  if(!std::isfinite(now)){reset();return false;}
  if(!sampled){sampled=true;previous=peak=p;last=began=now;return false;}
  double dt=now-last;V movement=sub(p,previous);float travel=std::sqrt(dot(movement,movement));
  if(dt<=0||dt>.12||travel>.35f||travel/dt>6){reset();return false;}
  previous=p;last=now;
  if(now-began<.25){peak=p;return false;}
  if(stroke&&(now-turned>.5||now-window>1.6)){stroke=false;reversals=0;peak=p;}
  V excursion=sub(p,peak);float length=std::sqrt(dot(excursion,excursion));
  if(stroke&&dot(excursion,direction)>0){peak=p;return false;}
  if(length<.045f||travel/dt<.55f)return false;
  V next=mul(excursion,1/length);
  if(!stroke){stroke=true;direction=next;peak=p;window=turned=now;return false;}
  if(now-turned<.07||dot(next,direction)>-.65f)return false;
  direction=next;peak=p;turned=now;
  if(++reversals<4)return false;
  reset();return true;
 }
};

bool validRoomPose(const M&m){
 for(float x:m)if(!std::isfinite(x))return false;
 if(fabsf(m[12])>100||fabsf(m[13])>100||fabsf(m[14])>100)return false;
 V x{m[0],m[1],m[2]},y{m[4],m[5],m[6]},z{m[8],m[9],m[10]};
 return fabsf(dot(x,x)-1)<.01f&&fabsf(dot(y,y)-1)<.01f&&fabsf(dot(z,z)-1)<.01f
  &&fabsf(dot(x,y))<.01f&&fabsf(dot(x,z))<.01f&&fabsf(dot(y,z))<.01f
  &&dot(cross(x,y),z)>.99f&&fabsf(m[3])+fabsf(m[7])+fabsf(m[11])+fabsf(m[15]-1)<.001f;
}

bool onGameScreen(V hit){return fabsf(hit[0])<=ScreenX&&fabsf(hit[1]-ScreenCY)<=ScreenY;}
bool onPhoneBody(V hit){return fabsf(hit[0])<=BodyX+.002f&&fabsf(hit[1])<=BodyY+.002f;}
bool onGrabHandle(V hit){return fabsf(hit[0])<=GrabHalfWidth+.005f&&fabsf(hit[1]-GrabY)<=GrabHalfHeight+.004f;}
bool onHomeButton(V hit){return fabsf(hit[0])<HomeHalfX&&fabsf(hit[1]-HomeY)<HomeHalfY;}
std::array<int,2> screenPixel(V hit,int width=ScreenWidth,int height=ScreenHeight){
 float u=(hit[0]/ScreenX+1)*.5f,v=(1-(hit[1]-ScreenCY)/ScreenY)*.5f;
 return {std::clamp((int)(u*width),0,width-1),std::clamp((int)(v*height),0,height-1)};
}
