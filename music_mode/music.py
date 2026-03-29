import os
import sys
import threading

import speech_recognition as sr
import vlc
import yt_dlp
from ytmusicapi import YTMusic


def configure_vlc():
    if sys.platform.startswith("win"):
        vlc_path = r"/usr/bin/vlc"
        if os.path.exists(vlc_path):
            os.add_dll_directory(vlc_path)
            os.environ["PATH"] = vlc_path + ";" + os.environ.get("PATH", "")
        else:
            print("Error: VLC directory not found. Check the path.")


configure_vlc()


class SpotifyClone:
    def __init__(self):
        self.yt = YTMusic() 
        self.instance = vlc.Instance('--no-video')
        self.player = self.instance.media_player_new()
        
        # --- The "Spotify" State ---
        self.queue = []           # Songs coming up
        self.history = []         # Songs we already played
        self.current_song = None
        self.is_playing = False
        
        # Events to handle auto-play when a song finishes
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_song_end)

    def search_and_queue(self, query):
        """Behaves like clicking a song or playlist in search"""
        print(f"Searching for '{query}'...")
        results = self.yt.search(query, filter="songs")
        
        if not results:
            print("No results found.")
            return

        # Add top result to queue
        song = results[0]
        self.queue.append(song)
        print(f"Added to Queue: {song['title']} - {song['artists'][0]['name']}")
        
        # If nothing is playing, start immediately (Like Spotify)
        if not self.is_playing:
            self.play_next()

    def load_playlist(self, query):
        """Behaves like clicking a Playlist"""
        playlists = self.yt.search(query, filter="playlists")
        if not playlists: return
        
        pl_id = playlists[0]['browseId']
        print(f"Loading Playlist: {playlists[0]['title']}...")
        
        # Get all tracks
        pl_data = self.yt.get_playlist(pl_id)
        tracks = pl_data['tracks']
        
        # Add all to queue
        self.queue.extend(tracks)
        print(f"Queued {len(tracks)} songs.")
        
        if not self.is_playing:
            self.play_next()

    def get_stream_url(self, video_id):
        """Extracts audio with Android client to avoid 403 errors"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            # FORCE 'android' client. This is the magic fix for VLC 403 errors.
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return info['url']
        except Exception as e:
            print(f"Error extracting audio: {e}")
            return None

    def play_next(self):
        """The 'Next' Button logic"""
        if not self.queue:
            print("Queue is empty.")
            self.is_playing = False
            return

        # 1. Archive current song to history
        if self.current_song:
            self.history.append(self.current_song)

        # 2. Get next song
        self.current_song = self.queue.pop(0)
        
        print(f"\n>> NOW PLAYING: {self.current_song['title']}")
        
        url = self.get_stream_url(self.current_song['videoId'])
        
        if url: 
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.play()
            self.is_playing = True
        else:
            print("Could not load song URL. Skipping...")
            self.play_next() # Skip to next if this one fails

    def prev(self):
        """The 'Previous' Button logic"""
        if not self.history:
            print("No history.")
            return
            
        # Put current song back to start of queue
        if self.current_song:
            self.queue.insert(0, self.current_song)
            
        # Get last song from history
        self.current_song = self.history.pop() # Remove from history
        self.queue.insert(0, self.current_song) # make it next
        self.play_next() # Play it immediately

    def toggle_pause(self):
        self.player.pause()
        state = "Paused" if not self.player.is_playing() else "Playing"
        print(f"[{state}]")

    def show_queue(self):
        """Display the song queue"""
        if not self.queue:
            print("\n=== QUEUE IS EMPTY ===")
            return
        
        print("\n=== SONG QUEUE ===")
        for i, song in enumerate(self.queue, 1):
            artist = song['artists'][0]['name'] if 'artists' in song and song['artists'] else 'Unknown'
            print(f"{i}. {song['title']} - {artist}")
        print(f"\nTotal: {len(self.queue)} song(s) in queue\n")

    def show_history(self):
        """Display previously played songs"""
        if not self.history:
            print("\n=== NO PREVIOUS SONGS ===")
            return
        
        print("\n=== PREVIOUS SONGS ===")
        # Show most recent first (reverse order)
        for i, song in enumerate(reversed(self.history), 1):
            artist = song['artists'][0]['name'] if 'artists' in song and song['artists'] else 'Unknown'
            print(f"{i}. {song['title']} - {artist}")
        print(f"\nTotal: {len(self.history)} song(s) played\n")

    def _on_song_end(self, event):
        """Auto-play next song when one finishes"""
        # Note: VLC events run in a separate thread, so we need to be careful
        print("\nSong finished. Playing next...")
        # We start a new thread to avoid blocking the VLC event loop
        threading.Thread(target=self.play_next).start()


class VoiceController:
    """Voice command handler for the music player"""
    def __init__(self, app):
        self.app = app
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        
        # Adjust for ambient noise on startup
        print("Calibrating microphone...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Voice control ready!")
    
    def listen_for_command(self):
        """Listen for a single voice command"""
        with self.microphone as source:
            print("\n🎤 Listening...")
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                command = self.recognizer.recognize_google(audio).lower()
                print(f"🗣️  You said: '{command}'")
                return command
            except sr.WaitTimeoutError:
                print("⏱️  No speech detected")
                return None
            except sr.UnknownValueError:
                print("❌ Could not understand audio")
                return None
            except sr.RequestError as e:
                print(f"❌ Speech recognition error: {e}")
                return None
    
    def process_command(self, command):
        """Process the voice command and execute appropriate action"""
        if not command:
            return True
        
        # Stop listening commands
        if "stop listening" in command or "exit voice" in command or "disable voice" in command:
            print("👋 Voice control disabled")
            return False
        
        # Playback controls
        elif "next" in command or "skip" in command:
            print("⏭️  Playing next song")
            self.app.play_next()
        
        elif "previous" in command or "back" in command or "last song" in command:
            print("⏮️  Playing previous song")
            self.app.prev()
        
        elif "pause" in command or "stop" in command:
            print("⏸️  Pausing")
            self.app.toggle_pause()
        
        elif "play" in command and ("resume" in command or command.strip() == "play"):
            print("▶️  Resuming")
            self.app.toggle_pause()
        
        # Queue and history
        elif "show queue" in command or "what's in queue" in command or "queue" in command:
            self.app.show_queue()
        
        elif "show history" in command or "what played" in command or "history" in command:
            self.app.show_history()
        
        # Search commands
        elif "search" in command or "play" in command:
            # Extract song name after 'search' or 'play'
            if "search" in command:
                query = command.split("search", 1)[1].strip()
            elif "play" in command:
                query = command.split("play", 1)[1].strip()
            else:
                query = ""
            
            if query and "for" in query:
                query = query.split("for", 1)[1].strip()
            
            if query:
                print(f"🔍 Searching for: {query}")
                self.app.search_and_queue(query)
            else:
                print("❓ Please specify what to search for")
        
        # Playlist commands
        elif "playlist" in command:
            query = command.split("playlist", 1)[1].strip()
            if query and "for" in query:
                query = query.split("for", 1)[1].strip()
            
            if query:
                print(f"📋 Loading playlist: {query}")
                self.app.load_playlist(query)
            else:
                print("❓ Please specify playlist name")
        
        # Help
        elif "help" in command or "commands" in command:
            self.show_voice_commands()
        
        else:
            print("❓ Command not recognized. Say 'help' for available commands.")
        
        return True
    
    def show_voice_commands(self):
        """Display available voice commands"""
        print("""
╔══════════════════════════════════════════╗
║      🎤 AVAILABLE VOICE COMMANDS         ║
╠══════════════════════════════════════════╣
║ Playback Controls:                       ║
║  • "next" / "skip"                       ║
║  • "previous" / "back"                   ║
║  • "pause" / "stop"                      ║
║  • "play" / "resume"                     ║
║                                          ║
║ Search & Queue:                          ║
║  • "search [song name]"                  ║
║  • "play [song name]"                    ║
║  • "playlist [playlist name]"            ║
║  • "show queue"                          ║
║  • "show history"                        ║
║                                          ║
║ Other:                                   ║
║  • "help" - show this menu               ║
║  • "stop listening" - exit voice control ║
╚══════════════════════════════════════════╝
        """)
    
    def start_voice_control(self):
        """Main voice control loop"""
        self.is_listening = True
        self.show_voice_commands()
        
        print("\n✨ Voice control is now active! Say 'stop listening' to exit.\n")
        
        while self.is_listening:
            command = self.listen_for_command()
            if not self.process_command(command):
                self.is_listening = False
                break

# --- The Interface (Controller) ---
def run_console(app):
    print("""
    === SPOTIFY CLI MODE ===
    [s] Search Song   [p] Play Playlist
    [n] Next          [b] Back
    [SPACE] Pause     [h] History
    [i] Queue     [v] Voice Control
    [q] Quit
    """)
    
    while True:
        cmd = input(">> ").strip().lower()
        
        if cmd == 'q':
            app.player.stop()
            break
        elif cmd == 'n':
            app.play_next()
        elif cmd == 'b':
            app.prev()
        elif cmd == ' ': # Spacebar representation
            app.toggle_pause()
        elif cmd == 's':
            query = input("Search Song: ")
            app.search_and_queue(query)
        elif cmd == 'p':
            query = input("Search Playlist: ")
            app.load_playlist(query)
        elif cmd == 'i':
            app.show_queue()
        elif cmd == 'h':
            app.show_history()
        elif cmd == 'v':
            voice = VoiceController(app)
            voice.start_voice_control()

if __name__ == "__main__":
    app = SpotifyClone()
    run_console(app)