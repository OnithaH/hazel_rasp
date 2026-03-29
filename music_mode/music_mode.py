import os
import sys
import threading
import time
import time
import json
import shlex

# Add parent directory to path so we can import from hazel_services
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hazel_services'))
from db_manager import DBManager

import speech_recognition as sr
import vlc
import yt_dlp
from ytmusicapi import YTMusic

def speak(text):
    """Uses espeak for Raspberry Pi voice feedback."""
    print(f"SPOKEN: {text}")
    os.system(f"espeak {shlex.quote(text)} 2>/dev/null")

class SpotifyClone:
    def __init__(self):
        self.db = DBManager()
        self.yt = YTMusic()
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.queue = []
        self.staging_queue = []
        self.history = []
        self.current_song = None
        self.is_playing = False

        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_song_end)

        threading.Thread(target=self._update_progress_bar, daemon=True).start()
        threading.Thread(target=self._poll_server_commands, daemon=True).start()

    def _poll_server_commands(self):
        """Polls the database MusicState directly instead of using a web API."""
        while True:
            try:
                # 1. Check for incoming Dashboard commands directly in DB
                state = self.db.get_music_state()
                if state and state.get("command"):
                    cmd = state["command"]
                    if cmd == "next": self.play_next()
                    elif cmd == "play_pause": self.toggle_pause()
                    elif cmd == "previous": self.play_previous()
                    elif cmd == "enqueue_song":
                        song = state.get("song") # This is already a dict from JSON field
                        if song:
                            yt_song = {
                                "title": song.get("title", "Unknown"),
                                "videoId": song.get("videoId"),
                                "artists": [{"name": song.get("artist", "")}],
                                "thumbnails": [{"url": song.get("thumbnail", "")}],
                            }
                            self.queue.append(yt_song)
                            if not self.is_playing: self.play_next()
                            else: speak(f"Added {song.get('title')} to the queue")

                    # 2. Clear command directly in DB
                    self.db.clear_music_command()

                # 3. Push current playback status directly to DB
                if self.current_song:
                    current_t = max(0, self.player.get_time() / 1000)
                    total_t = max(0, self.player.get_length() / 1000)
                    
                    nowPlaying = {
                        "title": self.current_song.get("title", "Unknown"),
                        "artist": self.current_song.get("artists", [{"name": "Unknown"}])[0]["name"],
                        "videoId": self.current_song.get("videoId"),
                        "thumbnail": self.current_song.get("thumbnails", [{"url": ""}])[0]["url"] if self.current_song.get("thumbnails") else "",
                        "currentTime": current_t,
                        "totalTime": total_t,
                        "isPlaying": self.is_playing,
                    }
                    queue_simple = [{"title": s["title"]} for s in self.queue]
                    self.db.update_music_state(nowPlaying, queue_simple)

            except Exception as e:
                print(f"📡 Sync Error: {e}")
            time.sleep(2)

    def _update_progress_bar(self):
        while True:
            try:
                if self.player and self.player.is_playing():
                    length = self.player.get_length() / 1000
                    current = self.player.get_time() / 1000
                    if length > 0:
                        filled = int(30 * current // length)
                        bar = "█" * filled + "-" * (30 - filled)
                        sys.stdout.write(f"\r|{bar}| {(current/length)*100:.1f}% ({int(current)}s/{int(length)}s)")
                        sys.stdout.flush()
            except Exception: pass
            time.sleep(1)

    def search_and_stage(self, query):
        """Search and add song to staging queue"""
        print(f"   Searching for: {query}")
        res = self.yt.search(query, filter="songs")
        if res:
            song = res[0]
            self.staging_queue.append(song)
            print(f"   Added: {song['title']} to staging queue")
            speak(f"Added {song['title']} to queue")
            return True
        else:
            print("   Song not found")
            speak("Song not found")
            return False

    def play_staging_queue(self):
        if not self.staging_queue: return
        self.queue.extend(self.staging_queue)
        self.staging_queue = []
        speak("Playing your queue now")
        if not self.is_playing: self.play_next()

    def search_and_play_now(self, query):
        """Search and play song immediately"""
        print(f"   Searching for: {query}")
        res = self.yt.search(query, filter="songs")
        if res:
            song = res[0]
            self.queue.insert(0, song)
            print(f"   Playing: {song['title']}")
            self.play_next()
            return True
        else:
            print("   Song not found")
            speak("Song not found")
            return False

    def get_stream_url(self, v_id):
        try:
            with yt_dlp.YoutubeDL({"format": "bestaudio/best", "quiet": True}) as ydl:
                return ydl.extract_info(f"https://www.youtube.com/watch?v={v_id}", download=False)["url"]
        except Exception: return None

    def _play_current_song(self):
        speak(f"Now playing {self.current_song['title']}")
        url = self.get_stream_url(self.current_song["videoId"])
        if url:
            self.player.set_media(self.instance.media_new(url))
            self.player.play()
            self.is_playing = True
        else: self.play_next()

    def play_next(self):
        if not self.queue:
            self.is_playing = False
            return
        if self.current_song: self.history.append(self.current_song)
        self.current_song = self.queue.pop(0)
        self._play_current_song()
        self.sync_state()

    def play_previous(self):
        if self.history:
            self.queue.insert(0, self.current_song)
            self.current_song = self.history.pop()
            self._play_current_song()
            self.sync_state()

    def toggle_pause(self):
        self.player.pause()
        time.sleep(0.2)
        self.is_playing = self.player.is_playing()
        self.sync_state()

    def sync_state(self):
        """Manually triggers a push of the current state to the database."""
        if self.current_song:
            try:
                current_t = max(0, self.player.get_time() / 1000)
                total_t = max(0, self.player.get_length() / 1000)
                
                nowPlaying = {
                    "title": self.current_song.get("title", "Unknown"),
                    "artist": self.current_song.get("artists", [{"name": "Unknown"}])[0]["name"],
                    "videoId": self.current_song.get("videoId"),
                    "thumbnail": self.current_song.get("thumbnails", [{"url": ""}])[0]["url"] if self.current_song.get("thumbnails") else "",
                    "currentTime": current_t,
                    "totalTime": total_t,
                    "isPlaying": self.is_playing,
                }
                queue_simple = [{"title": s["title"]} for s in self.queue]
                self.db.update_music_state(nowPlaying, queue_simple)
            except Exception: pass

    def _on_song_end(self, event):
        threading.Thread(target=self.play_next).start()

class VoiceController:
    def __init__(self, app):
        self.app, self.recognizer, self.microphone = app, sr.Recognizer(), sr.Microphone()
        with self.microphone as source: self.recognizer.adjust_for_ambient_noise(source, duration=1)
        #speak("Welcome to Hazel's music mode")

    def listen_and_process(self):
        with self.microphone as source:
            while True:
                try:
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=4)
                    cmd = self.recognizer.recognize_google(audio).lower()
                    if "exit" in cmd: break
                    elif "run queue" in cmd: self.app.play_staging_queue()
                    elif "add to queue" in cmd: self.app.search_and_stage(cmd.replace("add to queue", "").strip())
                    elif "next" in cmd: self.app.play_next()
                    elif "previous" in cmd: self.app.play_previous()
                    elif "pause" in cmd or "stop" in cmd: self.app.toggle_pause()
                    elif "play" in cmd:
                        q = cmd.replace("play", "").strip()
                        if q: self.app.search_and_play_now(q)
                        else: self.app.toggle_pause()
                except Exception: pass

if __name__ == "__main__":
    app = SpotifyClone()
    VoiceController(app).listen_and_process()
