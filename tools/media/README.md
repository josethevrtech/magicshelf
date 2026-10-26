# MagicShelf feature tour

The 36-second 1080p/30 fps tour presents MagicShelf 0.3.21. It uses the actual
native UI renderer and public creation metadata captured on October 26, 2026.
Six still screenshot scenes show Discover, creation details, permission review,
the update policy, shelf customization and artist credits. Short fades are the
only visual effect. The tour does not change the headset or install creations.

The permission review is an illustrative scene, labeled INSTALL PREVIEW.
No simulated download progress or network-speed claims appear in the video.
No headset input, subscriptions, creation state or user data changes are made by
the media tools.

## Music and credits

**Neon Shelf** is an original 100 BPM cyberpunk/reggaeton instrumental with a
dembow rhythm, dark synth chords, plucks and bass. It is composed and
synthesized by `build_tour.py` for this video. Pads, plucks, bass and percussion
are generated from oscillators and seeded noise; there are no external samples
or borrowed recordings. The source is covered by the repository's MIT license.
Audio fades in and out and is peak limited before encoding.

MagicShelf and the original phone model: josethevrtech. Smartphone Digivice's
Courage model: [Jojogape](https://x.com/jojogape). Digital Partner game:
[Aludeku](https://aludeku.itch.io/digital-partner-digimon). The third-party
artwork and game shown in the previews retain their original rights; the
repository's source license does not relicense them.

## Rebuild

Use a current `ui-state.json` snapshot whose screenshot paths exist on the build
machine. When exporting from Steam Frame, copy the referenced cached previews
and update only their `path` values to the corresponding local files. Do not
publish private snapshots or unrelated user content.

```sh
mkdir -p work/feature-tour
c++ -std=c++17 -O2 -Inative tools/media/render_storefront.cpp \
  -o work/feature-tour/render-storefront \
  $(pkg-config --cflags --libs egl glesv2 cairo json-c)
work/feature-tour/render-storefront /path/to/ui-state.json work/feature-tour/screens
python3 -m venv --system-site-packages work/feature-tour/venv
work/feature-tour/venv/bin/pip install numpy pycairo
work/feature-tour/venv/bin/python tools/media/build_tour.py \
  work/feature-tour/screens outputs/feature-tour
```

FFmpeg with libx264/AAC and DejaVu Sans must be installed. Outputs include an
H.264/AAC MP4 with fast-start metadata, a stereo WAV master, a poster and sample
frames for review. Large video/audio files stay out of Git; the README links to
GitHub-hosted attachments. The generated soundtrack is deterministic.
