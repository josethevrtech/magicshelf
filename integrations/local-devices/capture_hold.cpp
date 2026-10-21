// Keep a live gamescope source connected while its visual shell is replaced.
#include "capture.h"
#include <chrono>
#include <thread>
#include <fstream>
#include <csignal>
static volatile sig_atomic_t running=1;
static void stop(int){running=0;}
int main(int argc,char**argv){try{
 if(argc!=5)return 2;
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 Capture capture(std::stoul(argv[1]),std::stoul(argv[2]),std::stoul(argv[3]));
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(90);bool ready=false;
 while(running&&std::chrono::steady_clock::now()<deadline&&!capture.failed){
  capture.poll();
  // A sleeping/static gamescope session may emit no new frames. A negotiated
  // STREAMING connection still keeps the source alive across shell replacement.
  if(!ready&&capture.info.size.width&&pw_stream_get_state(capture.stream,nullptr)==PW_STREAM_STATE_STREAMING){std::ofstream(argv[4])<<"streaming\n";ready=true;std::cerr<<"Capture holder streaming\n";}
  std::this_thread::sleep_for(std::chrono::milliseconds(8));
 }
 std::cerr<<"Capture holder received "<<capture.frames<<" frames\n";
 return ready&&!capture.failed?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
