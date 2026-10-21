#include "capture.h"
#include <chrono>
#include <thread>
#include <fstream>
int main(int argc,char**argv){
 if(argc<6)return 2;
 Capture c(std::stoul(argv[1]),std::stoul(argv[2]),std::stoul(argv[3]),std::stoull(argv[4]));
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(3);
 while(std::chrono::steady_clock::now()<deadline&&!c.failed&&c.frames<3){c.poll();std::this_thread::sleep_for(std::chrono::milliseconds(8));}
 std::cout<<"frames="<<c.frames<<" failed="<<c.failed<<" format="<<c.info.size.width<<"x"<<c.info.size.height<<"\n";
 bool reject=std::string(argv[5])=="reject";
 if(!reject&&c.frames&&argc>6){std::ofstream f(argv[6],std::ios::binary);f<<"P6\n"<<c.info.size.width<<" "<<c.info.size.height<<"\n255\n";for(size_t i=0;i<c.rgba.size();i+=4)f.write((char*)c.rgba.data()+i,3);}
 return reject?(c.frames==0?0:1):(c.frames>0&&!c.failed?0:1);
}
