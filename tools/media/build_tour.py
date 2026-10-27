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
            signal=np.tanh(1.4*(np.sin(2*np.pi*hz*t)+.35*np.sin(4*np.pi*hz*t)+.15*np.sin(6*np.pi*hz*t)))
            env=np.minimum(t/.006,1)*np.exp(-t*4.3)*np.minimum((duration-t)/.08,1)
        return (signal*env).astype(np.float32)
    chords=[([52,55,59],40),([48,52,55],36),([57,60,64],45),([50,54,57],38)]
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
        for b in (0,2):
            t=np.arange(int(sr*.4))/sr;phase=2*np.pi*(46*t+100*.025*(1-np.exp(-t/.025)))
            kick=np.sin(phase)*np.exp(-t*12)+rng.normal(0,.1,len(t))*np.exp(-t*120)
            add(start+b*beat,kick.astype(np.float32),.24)
        for b in (.75,1.5,2.75,3.5):
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
 (0,6,'collection','Browse creations\nby josethevrtech','','MAGICSHELF'),
 (6,12,'android-phone','Explore before\nyou subscribe.','Screenshots, permissions and project links.','DISCOVER'),
 (12,18,'permissions-example','Choose what\nyou install.','Review permissions before subscribing.','INSTALL'),
 (18,24,'collection','Updates without\ninterruptions.','Keep playing. Updates install when Off.\nUpdate now asks before restarting.','STAY CURRENT'),
 (24,30,'shelf-settings','Make room\nfor your shelf.','Adjust size, spacing and placement.','CUSTOMIZE'),
 (30,48,'artist-credits','Credits and links\ninside every creation.','MagicShelf and all creations will always\nbe free. Visit the Credits section to\ndiscover the artists behind the assets\nand the original projects each creation\nis based on, follow their work, and\nfind ways to support them.','MAGICSHELF'),
]

def main():
    p=argparse.ArgumentParser();p.add_argument('screens',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    score(a.output/'neon-shelf.wav')
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
        start,end,name,title,body,kicker=SCENES[index]
        c.set_source_rgb(.018,.022,.042);c.paint()
        c.set_source_rgb(.25,.85,.95);c.rectangle(64,66,72,5);c.fill()
        text(64,119,'MAGICSHELF',25,WHITE,True)
        text(64,270,kicker,18,BLUE,True)
        text(64,350,title,40 if name=='artist-credits' else 48,WHITE,True)
        text(64,535,body,24,MUTED)
        picture(name,590,120,1260,886)
        if name=='permissions-example':text(64,690,'INSTALL PREVIEW',16,BLUE)
        text(64,950,'SteamOS + Steam Frame',22,MUTED)
        text(64,1036,'github.com/josethevrtech/magicshelf',24,BLUE,True)
        # One short dissolve at each cut. Screenshots stay still and readable.
        opacity=max(0,1-(t-start)/.18 if start else 0,1-(end-t)/.18)
        if opacity>0:c.set_source_rgba(.018,.022,.042,min(opacity,1));c.paint()
    output=a.output/'magicshelf-feature-tour.mp4'
    slides=[]
    for index,(start,end,*_) in enumerate(SCENES):
        scene(index,(start+end)/2)
        path=a.output/f'slide-{index+1}.png'
        surface.write_to_png(str(path))
        slides.append("file '"+path.resolve().as_posix()+"'\nduration "+str(end-start)+"\n")
        if index==0:surface.write_to_png(str(a.output/'poster.png'))
    slides.append("file '"+path.resolve().as_posix()+"'\n")
    playlist=a.output/'slides.txt';playlist.write_text(''.join(slides))
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(playlist),'-i',str(a.output/'neon-shelf.wav'),'-vf',f'fps={FPS},fade=t=in:st=0:d=0.18,fade=t=out:st={SECONDS-.3}:d=0.3','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(SECONDS),str(output)],check=True)
    print(output)

if __name__=='__main__':main()
