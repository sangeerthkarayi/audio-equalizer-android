# Audio Equalizer DSP — Android App

This is a mobile version of the 3-band Audio Equalizer project.

Bands:
- Bass: 20–250 Hz
- Mid: 250 Hz–4 kHz
- Treble: 4–20 kHz

Controls:
- Load WAV
- Bass/Mid/Treble gain sliders
- Apply Equalizer
- Play Original
- Play Equalized
- Save Equalized WAV

The DSP uses an FFT-based 3-band gain approach and normalizes the result to reduce digital clipping.

## Build locally

Install Buildozer on a Linux environment and run:

```bash
buildozer android debug
```

The APK will be placed in the `bin/` folder.

## Cloud build

A GitHub Actions workflow is included in `.github/workflows/build-apk.yml`.
Create a GitHub repository, upload this project, then run the workflow from the Actions tab.
