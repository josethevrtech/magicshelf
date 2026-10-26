#pragma once
#include "profile.h"
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <cairo/cairo.h>
#include <array>
#include <vector>
#include <string>
#include <fstream>
#include <cmath>
#include <stdexcept>
#include <iostream>
#include <algorithm>
using V=std::array<float,3>;using M=std::array<float,16>;
V add(V a,V b){return {a[0]+b[0],a[1]+b[1],a[2]+b[2]};}V sub(V a,V b){return {a[0]-b[0],a[1]-b[1],a[2]-b[2]};}V mul(V a,float t){return {a[0]*t,a[1]*t,a[2]*t};}float dot(V a,V b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}V cross(V a,V b){return {a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};}V norm(V a){return mul(a,1/std::max(.00001f,sqrtf(dot(a,a))));}
M identity(){return {1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1};}
M mm(M a,M b){M c{};for(int i=0;i<4;i++)for(int j=0;j<4;j++)for(int k=0;k<4;k++)c[i+j*4]+=a[i+k*4]*b[k+j*4];return c;}
M pose(V x,V y,V z,V p){return {x[0],x[1],x[2],0,y[0],y[1],y[2],0,z[0],z[1],z[2],0,p[0],p[1],p[2],1};}
M inverse(M a){M r=identity();for(int i=0;i<3;i++)for(int j=0;j<3;j++)r[i+j*4]=a[j+i*4];for(int i=0;i<3;i++)r[i+12]=-r[i]*a[12]-r[i+4]*a[13]-r[i+8]*a[14];return r;}
V point(M a,V p){return {a[0]*p[0]+a[4]*p[1]+a[8]*p[2]+a[12],a[1]*p[0]+a[5]*p[1]+a[9]*p[2]+a[13],a[2]*p[0]+a[6]*p[1]+a[10]*p[2]+a[14]};}
M projection(float l,float r,float b,float t,float n=.05f,float f=10){return {2*n/(r-l),0,0,0,0,2*n/(t-b),0,0,(r+l)/(r-l),(t+b)/(t-b),-(f+n)/(f-n),-1,0,0,-2*f*n/(f-n),0};}
struct Canvas{int w,h; cairo_surface_t*s; cairo_t*c;std::vector<unsigned char>rgba;
 Canvas(int W,int H):w(W),h(H),rgba(w*h*4){s=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,w,h);c=cairo_create(s);}~Canvas(){cairo_destroy(c);cairo_surface_destroy(s);}
 void fill(double r,double g,double b){cairo_set_source_rgb(c,r,g,b);cairo_paint(c);}
 void rect(double x,double y,double W,double H,double r,double g,double b){cairo_set_source_rgb(c,r,g,b);cairo_rectangle(c,x,y,W,H);cairo_fill(c);}
 void text(double x,double y,const std::string&t,double size=24,double r=.9,double g=.95,double b=1){cairo_set_source_rgb(c,r,g,b);cairo_select_font_face(c,"sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_NORMAL);cairo_set_font_size(c,size);cairo_move_to(c,x,y);cairo_show_text(c,t.c_str());}
 unsigned char* pixels(){cairo_surface_flush(s);auto*p=cairo_image_surface_get_data(s);int stride=cairo_image_surface_get_stride(s);for(int y=0;y<h;y++)for(int x=0;x<w;x++){auto a=p+y*stride+x*4;auto b=&rgba[(y*w+x)*4];b[0]=a[2];b[1]=a[1];b[2]=a[0];b[3]=a[3];}return rgba.data();}
 void png(std::string p){cairo_surface_write_to_png(s,p.c_str());}
};
struct Vertex{float x,y,z,nx,ny,nz,u,v;};
struct Material{uint32_t first,count;float roughness,metallic;GLuint texture=0;};
struct Renderer{
 EGLDisplay display;EGLContext context;EGLSurface surface;GLuint program,vbo,fbo,tex,depth,lcd;
 int count=0,mode=-1,W=RenderWidth,H=RenderHeight,lcdWidth=0,lcdHeight=0;std::vector<unsigned char>raw;std::vector<Material> materials;
 float brightness=1.f;
 bool showGrabHandle=false,highlightGrabHandle=false,dockGrabHandle=false;
 Renderer(std::string base):raw(W*H*4){
 auto get=(PFNEGLGETPLATFORMDISPLAYEXTPROC)eglGetProcAddress("eglGetPlatformDisplayEXT");display=get?get(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,nullptr):eglGetDisplay(EGL_DEFAULT_DISPLAY);
 if(!eglInitialize(display,nullptr,nullptr))throw std::runtime_error("EGL init failed");eglBindAPI(EGL_OPENGL_ES_API);
 EGLint attr[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};EGLConfig cfg;EGLint n;eglChooseConfig(display,attr,&cfg,1,&n);if(!n)throw std::runtime_error("No EGL config");EGLint ca[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE};context=eglCreateContext(display,cfg,EGL_NO_CONTEXT,ca);EGLint pa[]={EGL_WIDTH,1,EGL_HEIGHT,1,EGL_NONE};surface=eglCreatePbufferSurface(display,cfg,pa);if(!eglMakeCurrent(display,surface,surface,context))throw std::runtime_error("EGL context failed");
 std::cerr<<"Renderer: "<<glGetString(GL_RENDERER)<<"\n";
 const char*vs=R"(#version 300 es
 layout(location=0)in vec3 position;layout(location=1)in vec3 normal;layout(location=2)in vec2 uv;
 uniform mat4 mvp;out vec3 N;out vec3 P;out vec2 UV;
 void main(){gl_Position=mvp*vec4(position,1);N=normal;P=position;UV=uv;})";
 const char*fs=R"(#version 300 es
 precision highp float;in vec3 N;in vec3 P;in vec2 UV;
 uniform sampler2D lcd;uniform sampler2D housing;uniform bool screen;uniform bool handle;uniform bool handleHighlight;uniform bool handleDock;
 uniform vec3 eye;uniform float roughness;uniform float metallic;uniform float brightness;out vec4 frag;
 vec3 srgb(vec3 c){return mix(12.92*c,1.055*pow(max(c,vec3(0)),vec3(1.0/2.4))-.055,step(vec3(.0031308),c));}
 vec3 linearRGB(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
 void main(){
  if(handle){
   vec2 p=vec2((UV.x-.5)*8.333333,(UV.y-.5)*2.0);
   float d=length(vec2(max(abs(p.x)-3.166667,0.0),p.y));
   float a=1.0-smoothstep(.88,1.0,d);if(a<=0.0)discard;
   frag=vec4(handleDock?vec3(.40,1.0,.65):(handleHighlight?vec3(.55,.83,1.0):vec3(.8,.84,.89)),a*.95);return;
  }
  if(screen){frag=texture(lcd,UV);frag.rgb=srgb(linearRGB(frag.rgb)*brightness);return;}
  vec4 surface=texture(housing,UV);vec3 color=surface.rgb;
  vec3 normal=normalize(N),view=normalize(eye-P),light=normalize(view+vec3(-.4,.6,.35));
  float diffuse=max(0.0,dot(normal,light));
  float power=mix(130.0,10.0,roughness*roughness);
  float highlight=pow(max(0.0,dot(normal,normalize(view+light))),power);
  vec3 f0=mix(vec3(.04),color,metallic);
  float rim=pow(1.0-max(0.0,dot(normal,view)),4.0);
  vec3 lit=color*(.32+.68*diffuse)*(1.0-.45*metallic)+f0*highlight*(1.7-roughness)+f0*rim*.22;
  lit=mix(lit,color*1.25,surface.a);
  frag=vec4(srgb(clamp(lit,0.0,1.0)),1);
 })";
 auto shader=[](GLenum type,const char*src){GLuint s=glCreateShader(type);glShaderSource(s,1,&src,nullptr);glCompileShader(s);GLint ok;glGetShaderiv(s,GL_COMPILE_STATUS,&ok);if(!ok){char log[4096];glGetShaderInfoLog(s,4096,nullptr,log);throw std::runtime_error(log);}return s;};program=glCreateProgram();glAttachShader(program,shader(GL_VERTEX_SHADER,vs));glAttachShader(program,shader(GL_FRAGMENT_SHADER,fs));glLinkProgram(program);GLint ok;glGetProgramiv(program,GL_LINK_STATUS,&ok);if(!ok)throw std::runtime_error("GL link failed");
 std::string assets=base+"/"+AssetDirectory;
 std::ifstream f(assets+"/device.mesh",std::ios::binary);char magic[4];uint32_t numMaterials=0,num=0;
 f.read(magic,4);f.read((char*)&numMaterials,4);f.read((char*)&num,4);
 if(!f||std::string(magic,4)!="DPH2"||numMaterials>32||!numMaterials||num>1000000||num%3)throw std::runtime_error("Invalid Courage mesh");
 for(uint32_t i=0;i<numMaterials;i++){
  Material m{};f.read((char*)&m.first,4);f.read((char*)&m.count,4);f.read((char*)&m.roughness,4);f.read((char*)&m.metallic,4);
  if(!f||m.first+m.count>num||m.count%3)throw std::runtime_error("Invalid material batch");
  std::ifstream image(assets+"/body-"+std::to_string(i)+".rgba",std::ios::binary);uint32_t w=0,h=0;image.read((char*)&w,4);image.read((char*)&h,4);
  if(!image||!w||!h||w>2048||h>2048)throw std::runtime_error("Invalid material texture");
  std::vector<unsigned char> pixels(w*h*4);image.read((char*)pixels.data(),pixels.size());if(!image)throw std::runtime_error("Truncated material texture");
  glGenTextures(1,&m.texture);glBindTexture(GL_TEXTURE_2D,m.texture);glTexImage2D(GL_TEXTURE_2D,0,GL_SRGB8_ALPHA8,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
  glGenerateMipmap(GL_TEXTURE_2D);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR_MIPMAP_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_REPEAT);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_REPEAT);materials.push_back(m);
 }
 std::vector<Vertex> v(num);f.read((char*)v.data(),num*sizeof(Vertex));if(!f)throw std::runtime_error("Truncated mesh");count=num;
 float x=ScreenX,y=ScreenY,cy=ScreenCY,z=ScreenZ;
 Vertex q[]={ {-x,cy-y,z,0,0,1,0,1},{x,cy-y,z,0,0,1,1,1},{x,cy+y,z,0,0,1,1,0},{-x,cy-y,z,0,0,1,0,1},{x,cy+y,z,0,0,1,1,0},{-x,cy+y,z,0,0,1,0,0}};v.insert(v.end(),q,q+6);
 x=GrabHalfWidth;y=GrabHalfHeight;cy=GrabY;
 Vertex bar[]={ {-x,cy-y,z,0,0,1,0,1},{x,cy-y,z,0,0,1,1,1},{x,cy+y,z,0,0,1,1,0},{-x,cy-y,z,0,0,1,0,1},{x,cy+y,z,0,0,1,1,0},{-x,cy+y,z,0,0,1,0,0}};v.insert(v.end(),bar,bar+6);
 glGenBuffers(1,&vbo);glBindBuffer(GL_ARRAY_BUFFER,vbo);glBufferData(GL_ARRAY_BUFFER,v.size()*sizeof(Vertex),v.data(),GL_STATIC_DRAW);
 glGenTextures(1,&tex);glBindTexture(GL_TEXTURE_2D,tex);glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,W,H,0,GL_RGBA,GL_UNSIGNED_BYTE,nullptr);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
 glGenFramebuffers(1,&fbo);glBindFramebuffer(GL_FRAMEBUFFER,fbo);glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,tex,0);glGenRenderbuffers(1,&depth);glBindRenderbuffer(GL_RENDERBUFFER,depth);glRenderbufferStorage(GL_RENDERBUFFER,GL_DEPTH_COMPONENT24,W,H);glFramebufferRenderbuffer(GL_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_RENDERBUFFER,depth);if(glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE)throw std::runtime_error("FBO failed");
 glGenTextures(1,&lcd);glBindTexture(GL_TEXTURE_2D,lcd);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,AndroidOnly?GL_LINEAR:GL_LINEAR_MIPMAP_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,AndroidOnly?GL_LINEAR:GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
 }
 void screenPixels(int w,int h,const unsigned char*p){
  glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,lcd);
  if(w!=lcdWidth||h!=lcdHeight){glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,p);lcdWidth=w;lcdHeight=h;}
  else glTexSubImage2D(GL_TEXTURE_2D,0,0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,p);
  // Average subpixel game detail when viewed at a distance or angle. Keep
  // nearest magnification so large pixel-art displays retain their hard edges.
  if(!AndroidOnly)glGenerateMipmap(GL_TEXTURE_2D);
  // No swap/present happens while hidden or tracking is unavailable. Complete
  // uploads here so the driver cannot retain an unbounded queue of pixel data.
  glFinish();
 }
 void screen(Canvas& c){screenPixels(c.w,c.h,c.pixels());}
 unsigned char* draw(M plane,M model,V eye0,V eye1,float width,float size,bool readback=true){
 glBindFramebuffer(GL_FRAMEBUFFER,fbo);glViewport(0,0,W,H);glClearColor(0,0,0,0);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);glEnable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);glUseProgram(program);
 glBindBuffer(GL_ARRAY_BUFFER,vbo);for(int i=0;i<3;i++){glEnableVertexAttribArray(i);glVertexAttribPointer(i,i==2?2:3,GL_FLOAT,GL_FALSE,sizeof(Vertex),(void*)(uintptr_t)(i*12));}
 glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,lcd);glUniform1i(glGetUniformLocation(program,"lcd"),0);glUniform1i(glGetUniformLocation(program,"housing"),1);
 glUniform1f(glGetUniformLocation(program,"brightness"),std::clamp(brightness,.25f,1.f));
 M inv=inverse(plane),local=mm(inv,model);for(int i=0;i<3;i++)for(int j=0;j<3;j++)local[i+j*4]*=size;
 for(int index=0;index<2;index++){
  V worldEye=index?eye1:eye0,e=point(inv,worldEye),objectEye=mul(point(inverse(model),worldEye),1/size);
  glUniform3f(glGetUniformLocation(program,"eye"),objectEye[0],objectEye[1],objectEye[2]);
  float ez=std::max(.08f,e[2]);M view=identity();view[12]=-e[0];view[13]=-e[1];view[14]=-ez;float n=.02f;
  M pr=projection((-width/2-e[0])*n/ez,(width/2-e[0])*n/ez,(-width/2-e[1])*n/ez,(width/2-e[1])*n/ez,n);M mvp=mm(pr,mm(view,local));
  glViewport(index*W/2,0,W/2,H);glUniformMatrix4fv(glGetUniformLocation(program,"mvp"),1,GL_FALSE,mvp.data());glUniform1i(glGetUniformLocation(program,"screen"),0);glUniform1i(glGetUniformLocation(program,"handle"),0);
  glActiveTexture(GL_TEXTURE1);
  for(auto&m:materials){glBindTexture(GL_TEXTURE_2D,m.texture);glUniform1f(glGetUniformLocation(program,"roughness"),m.roughness);glUniform1f(glGetUniformLocation(program,"metallic"),m.metallic);glDrawArrays(GL_TRIANGLES,m.first,m.count);}
  glUniform1i(glGetUniformLocation(program,"screen"),1);glDrawArrays(GL_TRIANGLES,count,6);
  if(showGrabHandle){glUniform1i(glGetUniformLocation(program,"handle"),1);glUniform1i(glGetUniformLocation(program,"handleHighlight"),highlightGrabHandle);glUniform1i(glGetUniformLocation(program,"handleDock"),dockGrabHandle);glDrawArrays(GL_TRIANGLES,count+6,6);}
 }
 glActiveTexture(GL_TEXTURE0);
 if(readback){glReadPixels(0,0,W,H,GL_RGBA,GL_UNSIGNED_BYTE,raw.data());for(int y=0;y<H/2;y++)for(int x=0;x<W*4;x++)std::swap(raw[y*W*4+x],raw[(H-1-y)*W*4+x]);}return raw.data();
 }
 void save(std::string path){Canvas c(W/2,H);auto*p=cairo_image_surface_get_data(c.s);for(int y=0;y<H;y++)for(int x=0;x<W/2;x++){int i=y*(W/2)+x,j=y*W+x;p[i*4]=raw[j*4+2];p[i*4+1]=raw[j*4+1];p[i*4+2]=raw[j*4];p[i*4+3]=raw[j*4+3];}cairo_surface_mark_dirty(c.s);c.png(path);}
};
