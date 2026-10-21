#include "pet_text_input.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <string>

std::vector<unsigned char> read(const char*path){
 std::ifstream f(path,std::ios::binary);std::string magic;int w,h,max;
 f>>magic>>w>>h>>max;f.get();assert(magic=="P6"&&w==480&&h==1046&&max==255);
 std::vector<unsigned char> rgb(w*h*3),rgba(w*h*4,255);
 f.read((char*)rgb.data(),rgb.size());assert(f.gcount()==(std::streamsize)rgb.size());
 for(int i=0;i<w*h;i++)for(int c=0;c<3;c++)rgba[i*4+c]=rgb[i*3+c];
 return rgba;
}
int main(int argc,char**argv){
 assert(argc>=3);auto name=read(argv[1]);
 // A real first-run frame, including every edge of the field and OK below it.
 for(int y:{477,485,503,520,524})for(int x:{50,80,240,410,429})
  assert(petTextFieldAt(name,480,1046,x,y));
 for(auto p:std::vector<std::pair<int,int>>{{49,503},{430,503},{240,476},{240,525},{240,610},{240,440}})
  assert(!petTextFieldAt(name,480,1046,p.first,p.second));
 // Typed contents and a blinking caret must not influence field recognition.
 auto filled=name;
 for(int y=485;y<517;y++)for(int x=60;x<420;x++)for(int c=0;c<3;c++)filled[(y*480+x)*4+c]=(x+y)%256;
 assert(petTextFieldAt(filled,480,1046,240,503));
 // The same widget in another dialog position must still work.
 std::vector<unsigned char> moved(480*1046*4,0);
 for(int y=477;y<=524;y++)for(int x=50;x<=429;x++)for(int c=0;c<4;c++)moved[((y-200)*480+x)*4+c]=filled[(y*480+x)*4+c];
 assert(petTextFieldAt(moved,480,1046,240,303));
 assert(!petTextFieldAt(moved,480,1046,240,503));
 // A blue rectangle lacking the inset is not an editable widget.
 for(int x=55;x<=424;x++)for(int c=0;c<3;c++)filled[(482*480+x)*4+c]=0;
 assert(!petTextFieldAt(filled,480,1046,240,503));
 assert(!petTextFieldAt(name,720,1600,240,503));
 assert(!petTextFieldAt({},480,1046,240,503));
 // Sample other actual game screens for accidental keyboard triggers.
 for(int a=2;a<argc;a++){
  auto other=read(argv[a]);
  for(int y=0;y<1046;y+=8)for(int x=0;x<480;x+=8)assert(!petTextFieldAt(other,480,1046,x,y));
 }
 PetKeyboardRequest request;auto now=PetKeyboardRequest::Clock::now();
 request.tap(true,240,503,now);assert(!request.take(now+std::chrono::milliseconds(65)));
 assert(request.take(now+std::chrono::milliseconds(140)));assert(!request.take(now+std::chrono::seconds(1)));
 request.tap(true,240,503,now);request.tap(false,240,610,now);assert(!request.take(now+std::chrono::seconds(1)));
 request.tap(true,240,503,now);request.cancel();assert(!request.take(now+std::chrono::seconds(1)));
 std::cout<<"Text field recognition and deferred keyboard tests passed\n";
}
