#include "dashboard_texture.h"
#include <cassert>
#include <iostream>
int main(){
 Canvas c(64,48);DashboardTexture gpu(c.w,c.h);auto texture=gpu.texture;
 c.fill(0,0,0);c.rect(0,0,32,12,1,0,0);c.rect(0,36,32,12,0,1,0);gpu.update(c,0,0,c.w,c.h);
 GLuint framebuffer;glGenFramebuffers(1,&framebuffer);glBindFramebuffer(GL_FRAMEBUFFER,framebuffer);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,gpu.texture,0);assert(glCheckFramebufferStatus(GL_FRAMEBUFFER)==GL_FRAMEBUFFER_COMPLETE);
 auto verify=[&](){std::vector<unsigned char> actual(c.w*c.h*4);glReadPixels(0,0,c.w,c.h,GL_RGBA,GL_UNSIGNED_BYTE,actual.data());auto*expected=c.pixels();for(int y=0;y<c.h;y++)for(int x=0;x<c.w*4;x++)assert(actual[y*c.w*4+x]==expected[(c.h-1-y)*c.w*4+x]);assert(gpu.texture==texture);assert(glGetError()==GL_NO_ERROR);};
 verify();
 for(int n=0;n<100;n++){int x=n%48,y=n%32;c.rect(x,y,16,16,n%2,0,(n+1)%2);gpu.update(c,x,y,16,16);verify();}
 glBindFramebuffer(GL_FRAMEBUFFER,0);glDeleteFramebuffers(1,&framebuffer);
 std::cout<<"Persistent texture: full/partial uploads, orientation, colors and 100 updates passed\n";
}
