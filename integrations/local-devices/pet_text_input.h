#pragma once
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <vector>

// PC 1.1.9 draws its own input widgets. Their keyboard_virtual_show calls do
// nothing on Windows, so X11 cannot report edit focus. Recognize the input
// sprite's double border, not a fixed screen coordinate or the entered text.
inline bool petTextFieldAt(const std::vector<unsigned char>& rgba,
                           int w,int h,int x,int y){
 if(w!=480||h!=1046||rgba.size()!=size_t(w)*h*4||x<0||x>=w||y<0||y>=h)return false;
 auto color=[&](int px,int py,int r,int g,int b){
  const auto*p=&rgba[(py*w+px)*4];
  return std::abs(int(p[0])-r)<=10&&std::abs(int(p[1])-g)<=10&&std::abs(int(p[2])-b)<=10;
 };
 auto edge=[&](int px,int py){return color(px,py,99,155,255);};
 for(int top=std::max(0,y-55);top<=y;top++){
  if(!edge(x,top))continue;
  int left=x,right=x;
  while(left>0&&edge(left-1,top))--left;
  while(right+1<w&&edge(right+1,top))++right;
  if(right-left<320||right-left>410)continue;
  for(int bottom=std::max(y,top+40);bottom<std::min(h,top+56);bottom++){
   if(!edge(x,bottom))continue;
   bool match=true;
   for(int px=left;px<=right&&match;px+=3)match=edge(px,top)&&edge(px,bottom);
   for(int py=top;py<=bottom&&match;py+=3)match=edge(left,py)&&edge(right,py);
   // The cyan inset distinguishes a text field from other blue game panels.
   for(int px=left+5;px<=right-5&&match;px+=3){
    match=color(px,top+5,95,205,228)&&color(px,bottom-5,95,205,228)
       &&color(px,top+3,192,212,246)&&color(px,bottom-3,192,212,246);
   }
   for(int py=top+5;py<=bottom-5&&match;py+=3)
    match=color(left+5,py,95,205,228)&&color(right-5,py,95,205,228);
   if(match)return true;
  }
 }
 return false;
}

struct PetKeyboardRequest{
 using Clock=std::chrono::steady_clock;
 bool pending=false;int x=0,y=0;Clock::time_point due{};
 void cancel(){pending=false;}
 void tap(bool field,int px,int py,Clock::time_point now){
  pending=field;x=px;y=py;due=now+std::chrono::milliseconds(140);
 }
 bool take(Clock::time_point now){
  if(!pending||now<due)return false;
  pending=false;return true;
 }
};
