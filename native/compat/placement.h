#pragma once
#include "render.h"
#include <cstdint>

// A distance grab preserves the controller-to-phone transform. It remains
// attached to that controller until release, even outside the overlay's bounds.
struct RoomGrab {
 bool active=false,watchTriggerRelease=false;
 uint32_t controller=0;
 M offset=identity();
 void begin(uint32_t index,M hand,M room,bool watchRelease=false){
  controller=index;offset=mm(inverse(hand),room);
  active=true;watchTriggerRelease=watchRelease;
 }
 M follow(M hand)const{return mm(hand,offset);}
 void end(){active=false;watchTriggerRelease=false;}
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
bool onHomeButton(V hit){return fabsf(hit[0])<HomeHalfX&&fabsf(hit[1]-HomeY)<HomeHalfY;}
std::array<int,2> screenPixel(V hit,int width=ScreenWidth,int height=ScreenHeight){
 float u=(hit[0]/ScreenX+1)*.5f,v=(1-(hit[1]-ScreenCY)/ScreenY)*.5f;
 return {std::clamp((int)(u*width),0,width-1),std::clamp((int)(v*height),0,height-1)};
}
