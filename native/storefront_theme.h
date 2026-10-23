#pragma once
#include "compat/render.h"
#include <filesystem>

namespace ShelfTheme {
struct Color { double r,g,b; };
// The Steam dashboard icon is the reference for the storefront palette.
inline constexpr Color background{0,0,0}, accent{.36,.66,1.0}, text{.9,.95,1.0};
inline constexpr Color muted{.57,.65,.76}, panel{.015,.022,.032}, artwork{.009,.014,.022};
inline constexpr Color secondary{.027,.043,.065}, border{.08,.13,.20}, track{.12,.18,.26};
inline void source(Canvas&c,Color color,double alpha=1){cairo_set_source_rgba(c.c,color.r,color.g,color.b,alpha);}
inline void rect(Canvas&c,double x,double y,double w,double h,Color color){c.rect(x,y,w,h,color.r,color.g,color.b);}
inline void logo(Canvas&c,double x,double y,double size){
 // The editable SVG is rendered to icon.png at build time. The dashboard,
 // desktop shortcuts and release launchers therefore share the same artwork.
 static cairo_surface_t* image=[](){
  std::error_code error;auto binary=std::filesystem::read_symlink("/proc/self/exe",error);
  if(error)return static_cast<cairo_surface_t*>(nullptr);
  auto*surface=cairo_image_surface_create_from_png((binary.parent_path().parent_path()/"icon.png").c_str());
  if(cairo_surface_status(surface)!=CAIRO_STATUS_SUCCESS){cairo_surface_destroy(surface);return static_cast<cairo_surface_t*>(nullptr);}
  return surface;
 }();
 if(image){cairo_save(c.c);cairo_translate(c.c,x,y);cairo_scale(c.c,size/cairo_image_surface_get_width(image),size/cairo_image_surface_get_height(image));cairo_set_source_surface(c.c,image,0,0);cairo_paint(c.c);cairo_restore(c.c);return;}
 cairo_save(c.c);cairo_translate(c.c,x,y);cairo_scale(c.c,size/128,size/128);
 rect(c,0,0,128,128,background);
 rect(c,23,37,82,65,accent);rect(c,30,44,68,51,background);rect(c,18,27,92,10,accent);
 c.text(35,82,"M",39,text.r,text.g,text.b);cairo_restore(c.c);
}
}
