#!/usr/bin/env python3
"""Compose a native UI feature tour and an original, deterministic synth score.
Requires Python, numpy, pycairo and ffmpeg. Does not control the live app.
"""
import argparse, math, pathlib, subprocess, wave
import cairo
import numpy as np

W,H,FPS,SECONDS=1920,1080,30,48
BLUE=(.35,.65,1.0); WHITE=(.95,.97,1.0); MUTED=(.57,.66,.77)

def score(path):
    sr=48000; beat=.6; length=int(SECONDS*sr)
    mix=np.zeros((length,2),dtype=np.float32);rng=np.random.default_rng(2701)
    def add(start,sound,gain=1.,pan=0.):
        offset=int(start*sr);n=min(len(sound),length-offset)
        if n<=0:return
        mix[offset:offset+n,0]+=sound[:n]*gain*math.sqrt((1-pan)/2)
        mix[offset:offset+n,1]+=sound[:n]*gain*math.sqrt((1+pan)/2)
    def tone(note,duration,kind):
        t=np.arange(int(duration*sr))/sr;hz=440*2**((note-69)/12)
        if kind=='pad':
            signal=(np.sin(2*np.pi*hz*t)+.28*np.sin(2*np.pi*hz*1.003*t)+.16*np.sin(4*np.pi*hz*t))/1.44
            env=np.minimum(t/.32,1)*np.minimum((duration-t)/.7,1)*.6
        elif kind=='bass':
            signal=np.sin(2*np.pi*hz*t)+.18*np.sin(4*np.pi*hz*t)
            env=np.minimum(t/.012,1)*np.exp(-t*2.4)*np.minimum((duration-t)/.07,1)
        else:
            signal=np.sin(2*np.pi*hz*t)+.22*np.sin(4*np.pi*hz*t)+.08*np.sin(6*np.pi*hz*t)
            env=np.minimum(t/.006,1)*np.exp(-t*4.3)*np.minimum((duration-t)/.08,1)
        return (signal*env).astype(np.float32)
    chords=[([52,55,59,62,66],40),([48,52,55,59,62],36),([55,59,62,66,69],43),([50,57,62,64,69],38)]
    melody=[[76,79,83,78,74,79,78,71],[76,79,83,86,83,79,74,76],[79,83,86,81,78,83,81,79],[78,81,86,88,86,81,78,74]]
    for bar in range(20):
        start=bar*4*beat;notes,root=chords[bar%4]
        for i,note in enumerate(notes):add(start,tone(note,2.8,'pad'),.052,(-.6+i*.3))
        for b in (0,1.5,2,3.5):add(start+b*beat,tone(root+(12 if b==3.5 else 0),.42,'bass'),.19)
        for j in range(8):
            if bar<2 and j%2:continue
            n=melody[bar%4][j];s=tone(n,.7,'pluck');at=start+j*.5*beat
            add(at,s,.080 if bar>=2 else .045,(-.38 if j%2 else .38))
            add(at+beat*.75,s,.021,(-.65 if j%2 else .65))
        if bar<2 or bar>=19:continue
        for b in (0,2,3.5 if bar%2 else 2.75):
            t=np.arange(int(sr*.4))/sr;phase=2*np.pi*(46*t+100*.025*(1-np.exp(-t/.025)))
            kick=np.sin(phase)*np.exp(-t*12)+rng.normal(0,.1,len(t))*np.exp(-t*120)
            add(start+b*beat,kick.astype(np.float32),.24)
        for b in (1,3):
            t=np.arange(int(sr*.18))/sr;noise=rng.normal(0,1,len(t));noise=np.concatenate(([0],np.diff(noise)))
            clap=noise*np.exp(-t*30)*(.75+.25*np.cos(t*2*np.pi*75))
            add(start+b*beat,clap.astype(np.float32),.040,.12)
        for j in range(8):
            t=np.arange(int(sr*.08))/sr;noise=rng.normal(0,1,len(t));noise=np.concatenate(([0],np.diff(noise)))
            hat=noise*np.exp(-t*75)*np.minimum(t/.0015,1)
            add(start+j*.5*beat,hat.astype(np.float32),.016 if j%2 else .010,(-.4 if j%2 else .4))
    # Gentle saturation and a seamless opening/closing envelope; no external audio.
    mix=np.tanh(mix*1.15)
    timeline=np.arange(length)/sr
    fade=np.minimum(timeline/1.2,1)*np.clip((SECONDS-timeline)/2.5,0,1)
    mix*=fade[:,None];mix*=.76/max(float(np.max(np.abs(mix))),1e-6)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((mix*32767).astype('<i2').tobytes())

SCENES=[
 (0,4.8,'intro','MagicShelf','','SteamOS + Steam Frame'),
 (4.8,10.8,'collection','Explore the\nCollection','Browse the collection.\nTurn creations on or off\nright from their cards.','01 / DISCOVER'),
 (10.8,16.8,'android-phone','Creation\nDetails','Screenshots, settings,\nand project links\nfor each creation.','02 / EXPLORE'),
 (16.8,22.8,'artist-credits','Credits &\nLinks','Find artist credits,\nproject links and\ncreator support pages.','03 / CREDITS'),
 (22.8,28.8,'permissions-example','Know what\nyou install.','Permissions explained\nin everyday language\nbefore you subscribe.','04 / INSTALL'),
 (28.8,34.8,'download','Subscribe.\nStay current.','Downloads install\nautomatically. Follow\nprogress as it happens.','05 / UPDATES'),
 (34.8,40.8,'shelf-settings','Make it\nyour own.','Adjust the shelf’s size,\nspacing and placement\nto fit your space.','06 / CUSTOMIZE'),
 (40.8,48,'outro','MagicShelf','github.com/josethevrtech/magicshelf','MAGICSHELF'),
]

def main():
    p=argparse.ArgumentParser();p.add_argument('screens',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    score(a.output/'shelf-lights.wav')
    cache={};surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,W,H);c=cairo.Context(surface)
    def text(x,y,label,size=24,color=WHITE,bold=False):
        c.set_source_rgb(*color);c.select_font_face('DejaVu Sans',cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL);c.set_font_size(size)
        for line in label.split('\n'):c.move_to(x,y);c.show_text(line);y+=size*1.23
    def rounded(x,y,w,h,r):
        c.new_sub_path()
        for cx,cy,start in [(x+w-r,y+r,-math.pi/2),(x+w-r,y+h-r,0),(x+r,y+h-r,math.pi/2),(x+r,y+r,math.pi)]:c.arc(cx,cy,r,start,start+math.pi/2)
        c.close_path()
    def picture(name,x,y,w,h,alpha=1):
        if name not in cache:cache[name]=cairo.ImageSurface.create_from_png(str(a.screens/(name+'.png')))
        pic=cache[name];c.save();c.translate(x,y);c.scale(w/pic.get_width(),h/pic.get_height());c.set_source_surface(pic);c.paint_with_alpha(alpha);c.restore()
    def scene(index,t):
        start,end,name,title,body,kicker=SCENES[index];u=(t-start)/(end-start);ease=1-(1-min(1,max(0,u)*4))**3
        c.set_source_rgb(.004,.008,.015);c.paint()
        grad=cairo.RadialGradient(1500,500,40,1500,500,1100);grad.add_color_stop_rgb(0,.025,.095,.18);grad.add_color_stop_rgb(1,.004,.008,.015);c.set_source(grad);c.paint()
        c.set_source_rgba(.35,.65,1,.045);c.set_line_width(1)
        for y in range(120,1080,120):c.move_to(0,y);c.line_to(1920,y)
        for x in range(0,1920,120):c.move_to(x,0);c.line_to(x,1080)
        c.stroke()
        text(72,66,'M / MAGIC SHELF',20,BLUE,True);text(1460,66,'STEAMOS + STEAM FRAME',18,MUTED)
        if name in ('intro','outro'):
            px=(850 if name=='intro' else 980)+12*math.sin(t*.2)
            py=(225 if name=='intro' else 180)+8*math.cos(t*.25)
            pw=1000 if name=='intro' else 860;ph=pw*1800/2560
            c.set_source_rgba(*BLUE,.2);rounded(px-2,py-2,pw+4,ph+4,18);c.fill();c.save();rounded(px,py,pw,ph,16);c.clip();picture('collection',px,py,pw,ph);c.restore()
            text(68,435,title,99,WHITE,True)
            if name=='outro':
                c.set_source_rgba(*BLUE,.09);rounded(72,850,1776,112,18);c.fill_preserve()
                c.set_source_rgba(*BLUE,.45);c.set_line_width(2);c.stroke()
                text(108,923,body,54,BLUE,True)
        else:
            text(72,265,kicker,18,BLUE,True);text(68,366,title,56,WHITE,True);text(72,560,body,26,MUTED)
            # Small lateral entrance plus a subtle float, with no artificial UI chrome.
            px=594+28*(1-ease);py=100+3*math.sin(t*.7)
            c.set_source_rgba(*BLUE,.23);rounded(px-2,py-2,1256,884,16);c.fill()
            c.save();rounded(px,py,1252,880,14);c.clip()
            if name=='download':name='download-%03d'%min(100,int(max(0,u-.08)/.72*100))
            if name=='shelf-settings' and u>.53:name='placement'
            picture(name,px,py,1252,880);c.restore()
            if SCENES[index][2] in ('download','permissions-example'):text(72,760,'ILLUSTRATIVE INSTALL FLOW',15,BLUE,True)
        text(72,1026,'MAGICSHELF 0.3.6  /  DEVELOPMENT PREVIEW',16,MUTED)
        text(1635,1026,f'{index+1:02d} / {len(SCENES):02d}',16,MUTED)
        c.set_source_rgba(*BLUE,.18);c.rectangle(72,1050,1776,3);c.fill();c.set_source_rgb(*BLUE);c.rectangle(72,1050,1776*t/SECONDS,3);c.fill()
        # Fade at cuts and the end; keep the first frame visible for video previews.
        opacity=max(0,1-(t-start)/.22 if start>0 else 0,1-(end-t)/.22)
        if opacity>0:c.set_source_rgba(.004,.008,.015,min(opacity,1));c.paint()
    output=a.output/'magicshelf-feature-tour.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-pixel_format','bgra','-video_size',f'{W}x{H}','-framerate',str(FPS),'-i','pipe:0','-i',str(a.output/'shelf-lights.wav'),'-c:v','libx264','-preset','fast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(SECONDS),str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for frame in range(FPS*SECONDS):
        t=frame/FPS;index=next(i for i,s in enumerate(SCENES) if s[0]<=t<s[1]);scene(index,t);surface.flush();proc.stdin.write(surface.get_data())
        if frame in (75,225,405,585,765,945,1125,1350):surface.write_to_png(str(a.output/f'frame-{frame:04d}.png'))
        if frame==225:surface.write_to_png(str(a.output/'poster.png'))
    proc.stdin.close()
    if proc.wait():raise RuntimeError('ffmpeg encoding failed')
    print(output)

if __name__=='__main__':main()
