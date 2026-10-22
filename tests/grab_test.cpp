#include "compat/placement.h"
#include <cassert>
#include <limits>

static void close(float a,float b){assert(std::abs(a-b)<.0002f);}
static void same(M a,M b){for(int i=0;i<16;i++)close(a[i],b[i]);}
static M rotated(float a,V position){return pose({cosf(a),0,-sinf(a)},{0,1,0},{sinf(a),0,cosf(a)},position);}

int main(){
 // At different controller angles, depth follows the selected laser point,
 // preserves the off-centre grab, and leaves size and rotation unchanged.
 for(int n=0;n<100;n++){
  M hand=rotated(n*.061f,{.3f,1.2f,-.2f});
  V targetLocal{.1f,.05f,-1};
  M creation=mm(hand,rotated(.4f,{.08f,.06f,-1.01f}));
  RoomGrab grab;grab.beginAt(2,hand,creation,point(hand,targetLocal),true);
  same(grab.follow(hand),creation);
  grab.moveDepth(1,.04f);
  M moved=grab.follow(hand);
  V expected=point(hand,mul(norm(targetLocal),.06f));
  V delta=sub(expected,point(hand,{0,0,0}));
  for(int i=0;i<12;i++)close(moved[i],creation[i]);
  for(int i=0;i<3;i++)close(moved[12+i]-creation[12+i],delta[i]);
  grab.moveDepth(-1,.04f);same(grab.follow(hand),creation);
  M movedHand=rotated(n*.061f+.7f,{-1,.5f,1});
  same(mm(inverse(movedHand),grab.follow(movedHand)),mm(inverse(hand),creation));
  assert(validRoomPose(grab.follow(movedHand)));
 }
 RoomGrab g;M room=identity();room[14]=-1;g.begin(1,identity(),room);
 auto stable=g.follow(identity());
 g.moveDepth(0,1);g.moveDepth(1,0);g.moveDepth(1,-1);
 g.moveDepth(std::numeric_limits<float>::quiet_NaN(),.01f);
 g.moveDepth(1,std::numeric_limits<float>::infinity());same(g.follow(identity()),stable);
 g.moveDepth(1,10);close(g.distance,1+.05f*RoomGrab::DepthSpeed); // no wake-up leap
 for(int i=0;i<1000;i++)g.moveDepth(1,.02f);
 close(g.distance,RoomGrab::MaxDistance);
 for(int i=0;i<1000;i++)g.moveDepth(-1,.02f);
 close(g.distance,RoomGrab::MinDistance);
 stable=g.follow(identity());g.end();g.moveDepth(1,.05f);same(g.follow(identity()),stable);
 room[14]=-7;g.begin(1,identity(),room);g.moveDepth(0,.02f);same(g.follow(identity()),room);
 g.moveDepth(-1,.02f);close(g.distance,7-.02f*RoomGrab::DepthSpeed);
 // Same elapsed time at different frame rates produces the same distance.
 RoomGrab a,b;room[14]=-1;a.begin(1,identity(),room);b.begin(1,identity(),room);
 for(int i=0;i<100;i++)a.moveDepth(.5f,.01f);
 for(int i=0;i<50;i++)b.moveDepth(.5f,.02f);
 same(a.follow(identity()),b.follow(identity()));
 // Frame regression: the analog action is inactive while SteamVR supplies
 // smooth overlay scroll. Positive pushes away; negative pulls closer.
 // Replay the observed magnitudes for both hands.
 for(uint32_t hand:{1u,2u}){
  room[14]=-1;g.begin(hand,identity(),room);
  assert(g.queueScrollDepth(hand,.22f,.01f));
  assert(g.queueScrollDepth(hand,.22f,0));
  g.updateDepth(0,.022f,false);close(g.distance,1+.44f*RoomGrab::ScrollMetresPerUnit);
  stable=g.follow(identity());g.updateDepth(0,.022f,false);same(g.follow(identity()),stable);
  g.queueScrollDepth(hand,-.44f,.01f);g.updateDepth(0,.022f,false);same(g.follow(identity()),room);
  assert(!g.queueScrollDepth(3-hand,.22f,0));
  assert(!g.queueScrollDepth(hand,.22f,.2f));
  assert(!g.queueScrollDepth(hand,std::numeric_limits<float>::quiet_NaN(),0));
  assert(!g.queueScrollDepth(hand,.22f,std::numeric_limits<float>::infinity()));
  g.updateDepth(0,.022f,false);same(g.follow(identity()),room);
  // Actions take precedence if both paths deliver the same physical input.
  g.queueScrollDepth(hand,.44f,0);g.updateDepth(1,.022f,true);
  close(g.distance,1+.022f*RoomGrab::DepthSpeed);
  stable=g.follow(identity());g.updateDepth(0,.022f,false);same(g.follow(identity()),stable);
  g.queueScrollDepth(hand,.44f,0);g.end();g.updateDepth(0,.022f,false);same(g.follow(identity()),stable);
  assert(!g.queueScrollDepth(hand,.22f,0));
  g.begin(hand,identity(),room);g.updateDepth(0,.022f,false);same(g.follow(identity()),room);
  for(int i=0;i<100;i++)g.queueScrollDepth(hand,.22f,0);
  g.updateDepth(0,1,false);close(g.distance,1+.05f*RoomGrab::DepthSpeed);
 }
 // Integrated events produce the same travel whether batched per frame or
 // delivered individually; they must not be multiplied by frame time again.
 room[14]=-1;a.begin(1,identity(),room);b.begin(1,identity(),room);
 for(int i=0;i<90;i++){a.queueScrollDepth(1,.22f,0);a.updateDepth(0,1.f/90,false);}
 for(int i=0;i<45;i++){b.queueScrollDepth(1,.22f,0);b.queueScrollDepth(1,.22f,.011f);b.updateDepth(0,1.f/45,false);}
 same(a.follow(identity()),b.follow(identity()));
 assert(onGrabHandle({0,GrabY,ScreenZ}));
 assert(!onPhoneBody({0,GrabY,ScreenZ})&&!onGameScreen({0,GrabY,ScreenZ})&&!onHomeButton({0,GrabY,ScreenZ}));
 assert(!onGrabHandle({0,HomeY,ScreenZ}));
 assert(!onGrabHandle({0,ScreenCY,ScreenZ}));
 assert(InteractionPlaneWidth/2>std::abs(GrabY)+GrabHalfHeight+.004f);
 std::cout<<AppTitle<<": depth direction, rotation, bounds, timing, release, Frame scroll routing and handle hit tests passed\n";
}
