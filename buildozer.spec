[app]
title = Audio Equalizer DSP
package.name = audioequalizer
package.domain = org.dsp
source.dir = .
source.include_exts = py,wav,png,jpg,kv
version = 1.0
requirements = python3,kivy,numpy,plyer
orientation = portrait
fullscreen = 0

# Android permissions
android.permissions = READ_MEDIA_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# Android build settings
android.api = 35
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
