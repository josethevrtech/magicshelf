# MagicShelf feature tour

The 48-second 1080p/30 fps tour presents the native MagicShelf 0.3.6 development
build. It uses actual native UI rendering with the creation metadata captured
on October 21, 2026: Android Phone (Virtual) 0.2.5 and Smartphone Digivice 0.2.4.
The Discover screenshot in the project README is a live Steam Frame capture.
The other pages are offline renders of the same native UI.

The install review and animated 32 MB download are illustrative scenes, labeled
in the video. They are not a recording of network speed or a package-size claim.
No headset input, subscriptions, creation state or user data changes are made by
the media tools.

## Music and credits

**Shelf Lights** is an original 100 BPM electronic instrumental composed and
synthesized by `build_tour.py` for this video. Pads, plucks, bass and percussion
are generated from oscillators and seeded noise; there are no external samples
or borrowed recordings. The source is covered by the repository's MIT license.
The exported master measures -16.7 LUFS integrated and -2.4 dBFS true peak.

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
