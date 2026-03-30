import os
import asyncio
import subprocess
import time
import edge_tts  # New high-quality voice engine
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

load_dotenv()

# 1. CLIENTS & SYSTEM SETUP
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
dg_client = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))

# Use the powerful 70B versatile model
MODEL_NAME = "llama-3.3-70b-versatile" 
current_date = datetime.now().strftime("%B %d, %Y")

# Voice selection (English Female - Neural)
VOICE = "en-US-AvaNeural" 

messages = [{
    "role": "system", 
    "content": f"You are Hazel,  companion robot who loves to chat and help out. Today is {current_date}, year 2026. "
               "You are intelligent, and concise. keep conversations light and fun."
}]

# --- GLOBAL STATE ---
is_speaking = False 
sox_process = None
main_loop = None
SILENCE_CHUNK = b'\x00' * 2048 
# --------------------

def start_mic():
    global sox_process
    sox_cmd = ["rec", "-q", "-t", "raw", "-c", "1", "-r", "16000", "-b", "16", "-e", "signed-integer", "-"]
    sox_process = subprocess.Popen(sox_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return sox_process

async def get_groq_response(text):
    global messages
    messages.append({"role": "user", "content": text})
    try:
        completion = groq_client.chat.completions.create(model=MODEL_NAME, messages=messages)
        response = completion.choices[0].message.content
        messages.append({"role": "assistant", "content": response})
        return response
    except Exception:
        return "Brain glitch. Try again."

async def speak(text, dg_connection):
    """High-quality Female Neural TTS"""
    global is_speaking, sox_process
    is_speaking = True
    
    # 1. STOP MIC
    if sox_process:
        sox_process.terminate()
        sox_process.wait()
    
    print(f"\n🤖 Hazel: {text}")

    # 2. GENERATE NEURAL AUDIO
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save("speech.mp3")

    # 3. PLAY AUDIO (Non-blocking so we can send silence)
    p = subprocess.Popen(["mpv", "--no-video", "speech.mp3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4. KEEP-ALIVE: Send silence to Deepgram
    while p.poll() is None:
        dg_connection.send(SILENCE_CHUNK)
        await asyncio.sleep(0.1)
        
    # 5. COOL DOWN & RESTART
    await asyncio.sleep(0.4)
    start_mic()
    is_speaking = False

async def process_and_speak(text, dg_connection):
    reply = await get_groq_response(text)
    # Changed: Running speak directly as an async function
    await speak(reply, dg_connection)

def on_message(self, result, **kwargs):
    global is_speaking
    if is_speaking: return
    sentence = result.channel.alternatives[0].transcript
    if len(sentence) > 1 and result.is_final:
        print(f"👤 You: {sentence}")
        if main_loop:
            asyncio.run_coroutine_threadsafe(process_and_speak(sentence, self), main_loop)

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()

    dg_connection = dg_client.listen.websocket.v("1")
    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

    options = LiveOptions(
        model="nova-2", language="en-US", smart_format=True,
        encoding="linear16", channels=1, sample_rate=16000,
    )

    print(f"\n🚀 HAZEL CORE 2026: ONLINE (Neural Voice: {VOICE})")
    if not dg_connection.start(options): return

    start_mic()
    print("🎤 Hazel is listening. She sounds much better now!\n")

    try:
        while True:
            if not is_speaking and sox_process:
                data = sox_process.stdout.read(2048)
                if data:
                    dg_connection.send(data)
            await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        if sox_process: sox_process.terminate()
        dg_connection.finish()

if __name__ == "__main__":
    asyncio.run(main())