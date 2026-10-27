#!/usr/bin/env python3
"""Compose a native UI feature tour and an original, deterministic synth score.
Requires Python, numpy, Pillow and ffmpeg. Does not control the live app.
"""
import argparse, math, pathlib, subprocess, wave
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
    from PIL import Image,ImageDraw,ImageFont
    # Reuse the real native header: the shelf/M mark and mixed-case wordmark.
    # Its source coordinates follow StoreUI::draw at the 2x capture scale.
    header=Image.open(a.screens/'collection.png').convert('RGB').crop((20,36,442,148))
    header=header.resize((295,78),Image.Resampling.LANCZOS)
    def scene(index,t):
        start,end,name,title,body,kicker=SCENES[index]
        frame=Image.new('RGB',(W,H),(0,0,0));draw=ImageDraw.Draw(frame)
        def label(x,y,value,size,color=WHITE,bold=False):
            font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',size)
            draw.multiline_text((x,y),value,font=font,fill=tuple(int(v*255) for v in color),spacing=int(size*.23),anchor='la')
        frame.paste(header,(64,60))
        if kicker!='MAGICSHELF':label(64,252,kicker,18,BLUE,True)
        label(64,307,title,40 if name=='artist-credits' else 48,WHITE,True)
        label(64,510,body,24,MUTED)
        picture=Image.open(a.screens/(name+'.png')).convert('RGB').resize((1260,886),Image.Resampling.LANCZOS)
        frame.paste(picture,(590,120))
        if name=='permissions-example':label(64,674,'INSTALL PREVIEW',16,BLUE)
        label(64,928,'SteamOS + Steam Frame',22,MUTED)
        label(64,1012,'github.com/josethevrtech/magicshelf',24,BLUE,True)
        return frame
    output=a.output/'magicshelf-feature-tour.mp4'
    slides=[]
    for index,(start,end,*_) in enumerate(SCENES):
        frame=scene(index,(start+end)/2)
        path=a.output/f'slide-{index+1}.png'
        frame.save(path)
        slides.append("file '"+path.resolve().as_posix()+"'\nduration "+str(end-start)+"\n")
        if index==0:frame.save(a.output/'poster.png')
    slides.append("file '"+path.resolve().as_posix()+"'\n")
    playlist=a.output/'slides.txt';playlist.write_text(''.join(slides))
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','concat','-safe','0','-i',str(playlist),'-i',str(a.output/'neon-shelf.wav'),'-vf',f'fps={FPS},fade=t=in:st=0:d=0.18,fade=t=out:st={SECONDS-.3}:d=0.3','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(SECONDS),str(output)],check=True)
    print(output)

if __name__=='__main__':main()
