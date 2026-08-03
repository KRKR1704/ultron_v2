# record_samples.py — run this, say "Ultron" clearly each time it prompts
import sounddevice as sd
import soundfile as sf
import os

os.makedirs("wake_word_samples", exist_ok=True)
fs = 16000
duration = 1.5

for i in range(50):
    input(f"Press Enter, then say 'Ultron' (sample {i+1}/50)...")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    sf.write(f"wake_word_samples/ultron_{i:03d}.wav", recording, fs)
    print("saved")

print("Done! Now say it with different tones/speeds for variety in the next batch if you want more.")