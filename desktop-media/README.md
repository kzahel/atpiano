# Atpiano desktop media runtime

Atpiano builds its macOS arm64 copies of FFmpeg and LAME from the exact
upstream source archives and checksums in `manifest.json`. The build enables
only the audio operations used by the desktop application and deliberately
excludes FFmpeg's GPL and nonfree configurations.

Run from the repository root:

```sh
scripts/build-atpiano-media-runtime ensure
scripts/build-atpiano-media-runtime validate
```

`ensure` reuses a valid ignored runtime or builds it under
`results/desktop-media/macos-arm64/runtime`. `rebuild` forces a clean build.
Both require macOS arm64, Xcode command-line build tools, `make`, and `uv`.

Create the exact corresponding-source release asset with:

```sh
scripts/build-atpiano-media-runtime source-archive \
  --version 0.1.0 \
  --output results/desktop-media/Atpiano_0.1.0_media-sources.tar.gz
```

The source archive contains the verified upstream archives, this contract,
the complete build implementation, and the third-party notices. The packaged
FFmpeg and LAME libraries use relative dynamic load paths so a recipient can
inspect, replace, relink, and re-sign them. Atpiano's application source has
no project license yet; the third-party licenses apply only to their named
components.
