#include "magicshelf_sdk.h"
#include <cassert>
#include <thread>
#include <iostream>
int main(){
 auto dir=std::filesystem::temp_directory_path()/ ("magicshelf-rpc-test-"+std::to_string(getpid()));std::filesystem::create_directory(dir);
 setenv("MAGICSHELF_RUNTIME_DIR",dir.c_str(),1);int server=socket(AF_UNIX,SOCK_STREAM,0);sockaddr_un addr{};addr.sun_family=AF_UNIX;strcpy(addr.sun_path,(dir/"manager.sock").c_str());assert(bind(server,(sockaddr*)&addr,sizeof(addr))==0);assert(listen(server,1)==0);
 std::atomic<bool> received{false},completed{false},keepRunning{true};
 std::thread backend([&]{int client=accept(server,nullptr,nullptr);assert(client>=0);char b[200];assert(read(client,b,sizeof(b))>0);received=true;std::this_thread::sleep_for(std::chrono::seconds(1));completed=true;send(client,"{}\n",3,MSG_NOSIGNAL);close(client);});
 bool cancelled=false;std::thread frontend([&]{try{magicshelfRpc("{}",10,&keepRunning);}catch(const std::runtime_error&){cancelled=true;}});
 auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);while(!received&&std::chrono::steady_clock::now()<until)std::this_thread::sleep_for(std::chrono::milliseconds(5));assert(received);
 auto started=std::chrono::steady_clock::now();keepRunning=false;frontend.join();
 assert(cancelled&&std::chrono::steady_clock::now()-started<std::chrono::milliseconds(700));
 backend.join();assert(completed);close(server);std::filesystem::remove_all(dir);
 std::cout<<"Library request cancels promptly; manager operation continues independently\n";
}
