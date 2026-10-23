MagicShelf logo

Edit magicshelf.svg in Inkscape or another SVG editor. The letter is outlined,
so the artwork does not depend on which fonts are installed.

Run ./build.sh to render a 512 x 512 PNG and rebuild the app. The app header,
SteamVR icon, desktop shortcuts and both downloadable launchers use that PNG.

The download icons register this public image in the user's icon directory on
first launch. It stays available after uninstall so saved installer shortcuts
keep their logo. No settings or saved data are stored with the image.

The latest SVG and PNG are also attached to each GitHub release.
