import os
import wave
import numpy as np

from kivy.app import App
from kivy.core.audio import SoundLoader
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.metrics import dp


def read_wav(path):
    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.getnframes()
        raw = wf.readframes(frames)

    if sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError("Only 8, 16, or 32-bit PCM WAV is supported.")

    if channels > 1:
        data = data.reshape(-1, channels)
    return rate, data


def write_wav(path, rate, data):
    x = np.clip(data, -1.0, 1.0)
    if x.ndim > 1:
        x = x.reshape(-1)

    pcm = (x * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1 if data.ndim == 1 else data.shape[1])
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())


def equalize_fft(audio, rate, bass_db, mid_db, treble_db):
    """3-band FFT equalizer matching the project bands."""
    original_shape = audio.shape
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)

    n = len(mono)
    spectrum = np.fft.rfft(mono)
    freqs = np.fft.rfftfreq(n, 1.0 / rate)

    gains = np.ones_like(freqs)
    gains[(freqs >= 20) & (freqs < 250)] = 10 ** (bass_db / 20.0)
    gains[(freqs >= 250) & (freqs < 4000)] = 10 ** (mid_db / 20.0)
    gains[(freqs >= 4000) & (freqs <= 20000)] = 10 ** (treble_db / 20.0)

    processed = np.fft.irfft(spectrum * gains, n=n)
    peak = np.max(np.abs(processed)) if len(processed) else 0
    if peak > 0.98:
        processed = processed * (0.98 / peak)

    # Keep stereo files stereo by applying the same EQ to each channel.
    if len(original_shape) == 2:
        channels = []
        for c in range(original_shape[1]):
            spec = np.fft.rfft(audio[:, c])
            y = np.fft.irfft(spec * gains, n=n)
            channels.append(y)
        processed = np.stack(channels, axis=1)
        peak = np.max(np.abs(processed)) if processed.size else 0
        if peak > 0.98:
            processed *= 0.98 / peak

    return processed


class EqualizerApp(App):
    title = "Audio Equalizer - DSP"

    def build(self):
        self.audio_path = None
        self.output_path = None
        self.sound = None

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        title = Label(
            text="[b]AUDIO EQUALIZER[/b]\nDigital Signal Processing",
            markup=True,
            font_size="22sp",
            size_hint_y=None,
            height=dp(70),
        )
        root.add_widget(title)

        self.status = Label(
            text="Load a WAV file to begin",
            size_hint_y=None,
            height=dp(42),
        )
        root.add_widget(self.status)

        load_btn = Button(text="🎵  Load WAV", size_hint_y=None, height=dp(52))
        load_btn.bind(on_release=self.choose_file)
        root.add_widget(load_btn)

        for name, low, high, attr in [
            ("Bass", "20–250 Hz", "12", "bass"),
            ("Mid", "250 Hz–4 kHz", "12", "mid"),
            ("Treble", "4–20 kHz", "12", "treble"),
        ]:
            row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(92))
            label = Label(
                text=f"{name}  ({low})   0 dB",
                size_hint_y=None,
                height=dp(30),
            )
            slider = Slider(min=-12, max=12, value=0, step=1)
            setattr(self, f"{attr}_slider", slider)
            setattr(self, f"{attr}_label", label)

            def update(slider_obj, value, lab=label, nm=name):
                lab.text = f"{nm}  ({low if nm == 'Bass' else ('250 Hz–4 kHz' if nm == 'Mid' else '4–20 kHz')})   {int(value):+d} dB"

            slider.bind(value=update)
            row.add_widget(label)
            row.add_widget(slider)
            root.add_widget(row)

        apply_btn = Button(
            text="⚡  APPLY EQUALIZER",
            size_hint_y=None,
            height=dp(56),
        )
        apply_btn.bind(on_release=self.apply_equalizer)
        root.add_widget(apply_btn)

        controls = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.play_original_btn = Button(text="▶ Original")
        self.play_original_btn.bind(on_release=lambda *_: self.play_file(self.audio_path))
        self.play_equalized_btn = Button(text="▶ Equalized")
        self.play_equalized_btn.bind(on_release=lambda *_: self.play_file(self.output_path))
        stop_btn = Button(text="■ Stop")
        stop_btn.bind(on_release=lambda *_: self.stop_audio())
        controls.add_widget(self.play_original_btn)
        controls.add_widget(self.play_equalized_btn)
        controls.add_widget(stop_btn)
        root.add_widget(controls)

        save_btn = Button(text="💾  Save Equalized WAV", size_hint_y=None, height=dp(52))
        save_btn.bind(on_release=self.save_equalized)
        root.add_widget(save_btn)

        root.add_widget(
            Label(
                text="Bass: 20–250 Hz   •   Mid: 250 Hz–4 kHz   •   Treble: 4–20 kHz",
                font_size="12sp",
                size_hint_y=None,
                height=dp(34),
            )
        )
        return root

    def choose_file(self, *_):
        chooser = FileChooserListView(
            filters=["*.wav", "*.WAV"],
            path="/storage/emulated/0/Download",
        )
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        box.add_widget(chooser)
        buttons = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        cancel = Button(text="Cancel")
        select = Button(text="Select")
        buttons.add_widget(cancel)
        buttons.add_widget(select)
        box.add_widget(buttons)

        popup = Popup(title="Select a WAV file", content=box, size_hint=(0.95, 0.9))

        def do_select(*_):
            if chooser.selection:
                self.audio_path = chooser.selection[0]
                self.output_path = None
                self.status.text = "Loaded: " + os.path.basename(self.audio_path)
                popup.dismiss()

        cancel.bind(on_release=popup.dismiss)
        select.bind(on_release=do_select)
        popup.open()

    def apply_equalizer(self, *_):
        if not self.audio_path:
            self.status.text = "Please load a WAV file first."
            return

        try:
            rate, data = read_wav(self.audio_path)
            result = equalize_fft(
                data,
                rate,
                self.bass_slider.value,
                self.mid_slider.value,
                self.treble_slider.value,
            )
            base = os.path.splitext(os.path.basename(self.audio_path))[0]
            self.output_path = os.path.join(
                App.get_running_app().user_data_dir, base + "_equalized.wav"
            )
            write_wav(self.output_path, rate, result)
            self.status.text = (
                f"Equalized: Bass {self.bass_slider.value:+.0f} dB | "
                f"Mid {self.mid_slider.value:+.0f} dB | "
                f"Treble {self.treble_slider.value:+.0f} dB"
            )
        except Exception as e:
            self.status.text = "Error: " + str(e)

    def play_file(self, path):
        if not path or not os.path.exists(path):
            self.status.text = "No audio available."
            return
        self.stop_audio()
        self.sound = SoundLoader.load(path)
        if self.sound:
            self.sound.play()
            self.status.text = "Playing: " + os.path.basename(path)
        else:
            self.status.text = "Could not play this WAV file."

    def stop_audio(self):
        if self.sound:
            self.sound.stop()

    def save_equalized(self, *_):
        if not self.output_path or not os.path.exists(self.output_path):
            self.status.text = "Apply the equalizer first."
            return

        # The processed file is already saved in the app's private storage.
        self.status.text = "Saved: " + os.path.basename(self.output_path)


if __name__ == "__main__":
    EqualizerApp().run()
