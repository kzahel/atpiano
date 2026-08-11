# Third-party notices

Atpiano's macOS desktop package contains the following separately linked,
unmodified third-party media components:

## FFmpeg 8.1.2

- Project: <https://ffmpeg.org/>
- Source: <https://ffmpeg.org/releases/ffmpeg-8.1.2.tar.xz>
- License: GNU Lesser General Public License, version 2.1 or later

Atpiano builds FFmpeg as shared libraries without `--enable-gpl` or
`--enable-nonfree`. The exact enabled component list is recorded in
`desktop-media/manifest.json` and in the packaged media build manifest.

## LAME 4.0

- Project: <https://lame.sourceforge.io/>
- Source: <https://downloads.sourceforge.net/project/lame/lame/4.0/lame-4.0.tar.gz>
- License: GNU Library General Public License, version 2 or later

LAME is built as the separate shared `libmp3lame` library. Its command-line
frontend and decoder are disabled; Atpiano uses it only through FFmpeg's MP3
encoder.

## Source and replacement

Every desktop release includes an
`Atpiano_<version>_media-sources.tar.gz` asset beside the binary downloads.
It contains the exact verified FFmpeg and LAME source archives plus Atpiano's
complete media build script and configuration. Copies of the applicable
license texts and this notice are also installed inside the application.

The shared libraries use relative dynamic load paths. You may replace or
relink these LGPL components and re-sign the application for local execution.
Atpiano does not impose an end-user agreement that prohibits reverse
engineering these components for debugging your modifications.

Atpiano itself currently has no repository license. That default-copyright
status does not change the rights granted for FFmpeg or LAME under the
licenses above.
