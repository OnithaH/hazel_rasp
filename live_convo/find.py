import pyaudio
p = pyaudio.PyAudio()
mic_id = 1
# Check a huge range of frequencies
for rate in range(8000, 192001, 1000):
    try:
        if p.is_format_supported(rate, input_device_id=mic_id, input_channels=1, input_format=pyaudio.paInt16):
            print(f"✅ FOUND IT: {rate} Hz is supported!")
            break
    except:
        pass
else:
    print("❌ Absolute failure. No rates supported on ID 1.")
p.terminate()