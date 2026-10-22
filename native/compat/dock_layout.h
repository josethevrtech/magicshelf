#pragma once
#include "placement.h"

bool rigidDockAnchor(M transform,M&out){
 V x{transform[0],transform[1],transform[2]},y{transform[4],transform[5],transform[6]},z{transform[8],transform[9],transform[10]};
 for(float v:transform)if(!std::isfinite(v))return false;
 if(dot(x,x)<.000001f||dot(y,y)<.000001f||dot(z,z)<.000001f)return false;
 x=norm(x);y=norm(y);z=norm(z);out=pose(x,y,z,{transform[12],transform[13],transform[14]});return validRoomPose(out);
}
struct DockLayout {
 float spacing=.13f,objectHeight=.18f,rightEdge=-.35f,centerY=0.f,depth=0.f,railHeight=.0678f,leanDegrees=10.f,footInset=.010f,frontOffset=.012f,edgePadding=.010f;
 float joinYaw=0.f,joinPitch=0.f,joinRoll=0.f,curveRadius=0.f,curvePitch=-40.f;
 bool shelf=false,launcherOnly=false;float opacity=.72f;
 int count=2;
 DockLayout scaled(float s)const{DockLayout d=*this;d.spacing*=s;d.objectHeight*=s;d.rightEdge*=s;d.centerY*=s;d.depth*=s;d.railHeight*=s;d.footInset*=s;d.frontOffset*=s;d.edgePadding*=s;d.curveRadius*=s;return d;}
 float width()const{return count*spacing+2*edgePadding;}
 float height()const{return railHeight;}
 float x(int index)const{return rightEdge-edgePadding-(count-index-.5f)*spacing;}
 // Rotate about the seam so adjustments keep the extension attached at its right edge.
 M seam(M anchor)const{
  float y=joinYaw*M_PI/180.f,p=joinPitch*M_PI/180.f,r=joinRoll*M_PI/180.f;
  M ry=identity(),rx=identity(),rz=identity(),t=identity();
  ry[0]=cosf(y);ry[2]=-sinf(y);ry[8]=sinf(y);ry[10]=cosf(y);
  rx[5]=cosf(p);rx[6]=sinf(p);rx[9]=-sinf(p);rx[10]=cosf(p);
  rz[0]=cosf(r);rz[1]=sinf(r);rz[4]=-sinf(r);rz[5]=cosf(r);
  t[12]=rightEdge;t[13]=centerY;t[14]=depth;
  return mm(anchor,mm(t,mm(rz,mm(ry,rx))));
 }
 float radius()const{return curveRadius>0?std::max(curveRadius,width()/float(M_PI)):0.f;}
 float curvature()const{return radius()>0?width()/(2*M_PI*radius()):0.f;}
 M pitch(float degrees)const{M r=identity();float a=degrees*M_PI/180.f;r[5]=cosf(a);r[6]=sinf(a);r[9]=-sinf(a);r[10]=cosf(a);return r;}
 // Surface frame at arc distance s from the fixed right-hand join.
 M surface(M anchor,float s)const{
  M t=identity();float r=radius();if(r<=0){t[12]=s;return mm(seam(anchor),t);}
  float a=s/r;M turn=identity();turn[0]=cosf(a);turn[2]=sinf(a);turn[8]=-sinf(a);turn[10]=cosf(a);
  t[12]=r*sinf(a);t[14]=r*(1-cosf(a));
  return mm(seam(anchor),mm(pitch(-curvePitch),mm(t,mm(turn,pitch(curvePitch)))));
 }
 M backing(M anchor)const{
  M center=surface(anchor,-width()*.5f);
  // SteamVR applies the pre-curve pitch itself when drawing the PNG.
  return radius()>0?mm(center,pitch(-curvePitch)):center;
 }
 M slot(M anchor,int index)const{M p=identity();p[13]=shelf?0.f:-railHeight*.5f+footInset;p[14]=shelf?0.f:frontOffset;return mm(surface(anchor,x(index)-rightEdge),mm(p,pitch(leanDegrees)));}
 // A shallow horizontal tray and its thin front edge share the device foot plane.
 float lipHeight()const{return height()*.08f;}
 M shelfPart(M anchor,int part)const{M t=identity();t[12]=-width()/2;if(part==0)return mm(seam(anchor),mm(t,pitch(-90)));t[13]=-lipHeight()/2;t[14]=height()/2;return mm(seam(anchor),t);}

 bool samePlacement(const DockLayout&d)const{
  return spacing==d.spacing&&objectHeight==d.objectHeight&&rightEdge==d.rightEdge&&centerY==d.centerY&&depth==d.depth&&railHeight==d.railHeight&&leanDegrees==d.leanDegrees&&footInset==d.footInset&&frontOffset==d.frontOffset&&edgePadding==d.edgePadding&&joinYaw==d.joinYaw&&joinPitch==d.joinPitch&&joinRoll==d.joinRoll&&curveRadius==d.curveRadius&&curvePitch==d.curvePitch&&shelf==d.shelf&&count==d.count;
 }
 // Accept a drop anywhere over the dock; ordering and the home slot stay fixed.
 bool acceptsDrop(M anchor,M creation,float size,bool expanded=false)const{
  if(count<=0||!validRoomPose(anchor)||!validRoomPose(creation)||!std::isfinite(size)||size<=0)return false;
  float scale=objectHeight/.18f,margin=(expanded?.065f:.04f)*scale;
  V center=point(creation,{0,0,0}),foot=point(creation,{0,-BodyY*size,0});
  for(int i=0;i<count;i++){
   M inv=inverse(slot(anchor,i));V c=point(inv,center),f=point(inv,foot);
   auto inside=[&](V p,float top){return std::abs(p[0])<=spacing*.5f+margin&&p[1]>=-.06f*scale&&p[1]<=top&&std::abs(p[2])<=(expanded?.15f:.12f)*scale;};
   if(inside(c,objectHeight+.08f*scale)||inside(f,.08f*scale))return true;
  }
  return false;
 }

};
bool dockVisible(bool dashboard,bool anchorVisible,bool active,bool launcherOnly){return dashboard&&(!launcherOnly||(anchorVisible&&active));}
float dockObjectSize(float userSize,float height){return std::min(userSize,height/(2*BodyY));}
M dockObjectPose(M slot,float effective){M p=identity();p[13]=BodyY*effective;return mm(slot,p);}
M yawPose(float yaw){M r=identity();r[0]=cosf(yaw);r[2]=-sinf(yaw);r[8]=sinf(yaw);r[10]=cosf(yaw);return r;}
M undockedRoomPose(M displayed,float savedYaw){return mm(displayed,inverse(yawPose(savedYaw)));}

