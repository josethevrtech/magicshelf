#pragma once
// MagicShelf module API v1: environment, private state, shelf poses and readiness.
// Rendering belongs to the module; the host owns the shelf and module order.
#include "compat/object_dock.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <cstring>
#include <ctime>

inline std::string magicshelfEnv(const char*key){auto*p=getenv(key);if(!p||!*p)throw std::runtime_error(std::string("Missing MagicShelf environment: ")+key);return p;}
inline std::string magicshelfRpc(const std::string&request,int seconds=90){
 int fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);if(fd<0)throw std::runtime_error("MagicShelf socket failed");
 timeval timeout{seconds,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));setsockopt(fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
 sockaddr_un address{};address.sun_family=AF_UNIX;std::string path=magicshelfEnv("MAGICSHELF_RUNTIME_DIR")+"/manager.sock";
 if(path.size()>=sizeof(address.sun_path)){close(fd);throw std::runtime_error("MagicShelf socket path is too long");}strcpy(address.sun_path,path.c_str());
 if(connect(fd,(sockaddr*)&address,sizeof(address))){close(fd);throw std::runtime_error("MagicShelf is unavailable");}
 std::string data=request+"\n";size_t sent=0;while(sent<data.size()){auto n=send(fd,data.data()+sent,data.size()-sent,MSG_NOSIGNAL);if(n<=0){close(fd);throw std::runtime_error("MagicShelf send failed");}sent+=n;}
 data.clear();char buffer[4096];while(data.size()<1024*1024){auto n=read(fd,buffer,sizeof(buffer));if(n<=0)break;data.append(buffer,n);if(data.back()=='\n')break;}close(fd);return data;
}
inline void magicshelfReady(){
 auto*j=json_object_new_object();json_object_object_add(j,"api_version",json_object_new_int(1));json_object_object_add(j,"method",json_object_new_string("runtime.ready"));auto*p=json_object_new_object();json_object_object_add(p,"id",json_object_new_string(magicshelfEnv("MAGICSHELF_MODULE_ID").c_str()));json_object_object_add(p,"token",json_object_new_string(magicshelfEnv("MAGICSHELF_SESSION").c_str()));json_object_object_add(j,"params",p);
 auto result=magicshelfRpc(json_object_to_json_string(j),5);json_object_put(j);if(result.find("\"result\"")==std::string::npos)throw std::runtime_error("MagicShelf rejected module readiness");
}
inline vr::HmdMatrix34_t magicshelfTransform(M m){vr::HmdMatrix34_t t{};for(int r=0;r<3;r++)for(int c=0;c<4;c++)t.m[r][c]=m[r+c*4];return t;}
inline float magicshelfFit(const ObjectDock&dock,float width,float height,float userScale=1.f){
 if(!(width>0&&height>0&&userScale>0))throw std::runtime_error("Invalid toy dimensions");
 float sceneScale=dock.effective.objectHeight/dock.layout.objectHeight;
 return std::min({userScale*sceneScale,(dock.effective.spacing-.01f*sceneScale)/width,dock.effective.objectHeight/height});
}
