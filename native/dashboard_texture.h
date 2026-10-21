#pragma once
#include "compat/render.h"
#include "compat/openvr.h"

// One EGL context and texture live for the dashboard's lifetime. Replacing PNG
// resources on every interaction makes SteamVR drop/reload the entire surface.
struct DashboardTexture {
 EGLDisplay display=EGL_NO_DISPLAY;
 EGLContext context=EGL_NO_CONTEXT;
 EGLSurface surface=EGL_NO_SURFACE;
 GLuint texture=0;
 int width,height;
 std::vector<unsigned char> upload;
 DashboardTexture(int w,int h):width(w),height(h) {
  auto get=reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(eglGetProcAddress("eglGetPlatformDisplayEXT"));
  display=get?get(EGL_PLATFORM_SURFACELESS_MESA,EGL_DEFAULT_DISPLAY,nullptr):eglGetDisplay(EGL_DEFAULT_DISPLAY);
  if(!eglInitialize(display,nullptr,nullptr))throw std::runtime_error("Cannot initialize dashboard graphics");
  eglBindAPI(EGL_OPENGL_ES_API);
  EGLint attributes[]={EGL_SURFACE_TYPE,EGL_PBUFFER_BIT,EGL_RENDERABLE_TYPE,EGL_OPENGL_ES3_BIT,EGL_RED_SIZE,8,EGL_GREEN_SIZE,8,EGL_BLUE_SIZE,8,EGL_ALPHA_SIZE,8,EGL_NONE};
  EGLConfig config;EGLint count=0;eglChooseConfig(display,attributes,&config,1,&count);
  if(!count)throw std::runtime_error("No dashboard graphics configuration");
  EGLint version[]={EGL_CONTEXT_CLIENT_VERSION,3,EGL_NONE},size[]={EGL_WIDTH,1,EGL_HEIGHT,1,EGL_NONE};
  context=eglCreateContext(display,config,EGL_NO_CONTEXT,version);surface=eglCreatePbufferSurface(display,config,size);
  if(!eglMakeCurrent(display,surface,surface,context))throw std::runtime_error("Cannot activate dashboard graphics");
  glGenTextures(1,&texture);glBindTexture(GL_TEXTURE_2D,texture);
  glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
  glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
  glTexStorage2D(GL_TEXTURE_2D,1,GL_RGBA8,width,height);
  if(glGetError()!=GL_NO_ERROR)throw std::runtime_error("Cannot allocate dashboard texture");
 }
 DashboardTexture(const DashboardTexture&)=delete;
 ~DashboardTexture(){
  // The host releases/destroys its overlay before this texture or context dies.
  if(context!=EGL_NO_CONTEXT){eglMakeCurrent(display,surface,surface,context);glFinish();if(texture)glDeleteTextures(1,&texture);eglMakeCurrent(display,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT);eglDestroyContext(display,context);}
  if(surface!=EGL_NO_SURFACE)eglDestroySurface(display,surface);
  if(display!=EGL_NO_DISPLAY)eglTerminate(display);
 }
 void update(Canvas&canvas,int x,int y,int w,int h) {
  if(w<=0||h<=0)return;
  cairo_surface_flush(canvas.s);const auto*p=cairo_image_surface_get_data(canvas.s);int stride=cairo_image_surface_get_stride(canvas.s);
  upload.resize(size_t(w)*h*4);
  // Cairo rows start at the top, OpenGL rows at the bottom. Also convert BGRA
  // to RGBA without allocating a second whole-screen Canvas pixel buffer.
  for(int row=0;row<h;row++)for(int col=0;col<w;col++){
   const auto*src=p+(y+h-1-row)*stride+(x+col)*4;auto*dst=upload.data()+(size_t(row)*w+col)*4;
   dst[0]=src[2];dst[1]=src[1];dst[2]=src[0];dst[3]=src[3];
  }
  glBindTexture(GL_TEXTURE_2D,texture);glPixelStorei(GL_UNPACK_ALIGNMENT,4);
  glTexSubImage2D(GL_TEXTURE_2D,0,x,height-y-h,w,h,GL_RGBA,GL_UNSIGNED_BYTE,upload.data());
  glFinish(); // Finish before the compositor imports/reads this shared texture.
  if(glGetError()!=GL_NO_ERROR)throw std::runtime_error("Dashboard texture update failed");
 }
 void present(vr::IVROverlay*overlay,vr::VROverlayHandle_t panel){
  vr::Texture_t frame{reinterpret_cast<void*>(uintptr_t(texture)),vr::TextureType_OpenGL,vr::ColorSpace_Gamma};
  auto error=overlay->SetOverlayTexture(panel,&frame);
  if(error!=vr::VROverlayError_None)throw std::runtime_error(std::string("Dashboard presentation failed: ")+overlay->GetOverlayErrorNameFromEnum(error));
 }
};
