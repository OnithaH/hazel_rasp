"""
Gesture-Music Bridge
Connects gesture controller with SpotifyClone music player
"""

import threading
import time
import signal
import sys
import os
import cv2
from gesture_test import GestureController
from music_mode import SpotifyClone, speak

class GestureMusicBridge:
    """
    Bridges gesture detection with music control
    """
    
    def __init__(self):
        # Initialize components
        self.gesture_controller = None
        self.music_player = None
        
        # State tracking
        self.running = True
        self.gesture_thread = None
        
        # Cooldown for repeated gestures (seconds)
        self.last_gesture_time = {
            'thumbs_up': 0,
            'fist': 0,
            'swipe_left': 0,
            'swipe_right': 0,
            'pointing': 0,
            'open_palm': 0
        }
        self.GESTURE_COOLDOWN = 0.5  # 500ms cooldown
        
        # Music state
        self.current_music_state = "idle"  # idle, playing, paused
        
        # Voice recognition flag to prevent multiple simultaneous voice sessions
        self.voice_active = False
    def start(self):
        """Initialize and start all components"""
        print("\n" + "="*60)
        print("     GESTURE-MUSIC BRIDGE - Starting System")
        print("="*60)
        
        # Initialize music player
        print("\n[1/3] Initializing Music Player...")
        self.music_player = SpotifyClone()
        speak("Music mode initialized")
        
        # Initialize gesture controller (Hidden GUI)
        print("\n[2/3] Initializing Gesture Controller...")
        self.gesture_controller = GestureController(show_feedback=False, camera_size=(640, 480))
        
        if not self.gesture_controller.start_camera():
            print("Error: Could not start camera")
            return False
        
        # Start gesture detection in separate thread
        print("\n[3/3] Starting gesture detection...")
        self.gesture_thread = threading.Thread(target=self._gesture_loop, daemon=True)
        self.gesture_thread.start()
        
        print("\n" + "="*60)
        print("SYSTEM READY! Website Queue Active.")
        print("Gesture controls active (Hidden):")
        print("  👍  THUMBS UP  →  Play music")
        print("  ✊  FIST       →  Pause music")
        print("  ➡️  SWIPE RIGHT →  Next track")
        print("  ⬅️  SWIPE LEFT  →  Previous track")
        print("  👆  POINTING   →  Voice Search (Play Now)")
        print("  🖐️  OPEN PALM   →  Neutral (no action)")
        print("="*60 + "\n")
        
        return True
    
    def _gesture_loop(self):
        """Main gesture detection loop"""
        while self.running:
            try:
                # Get frame from camera
                frame = self.gesture_controller.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                # Detect gesture
                gesture = self.gesture_controller.detect_gesture(frame)
                
                # Process gesture
                if gesture:
                    self._process_gesture(gesture)
                
                # Show feedback
                if self.gesture_controller.show_feedback:
                    cv2.imshow(self.gesture_controller.window_name, frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:
                        self.running = False
                        break
                
            except Exception as e:
                print(f"Error in gesture loop: {e}")
                time.sleep(0.1)
    
    def _process_gesture(self, gesture):
        """Process detected gesture and trigger music actions"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_gesture_time.get(gesture, 0) < self.GESTURE_COOLDOWN:
            return
        
        # Map gestures to actions
        if gesture == "thumbs_up":
            self._handle_play()
            self.last_gesture_time['thumbs_up'] = current_time
            
        elif gesture == "fist":
            self._handle_pause()
            self.last_gesture_time['fist'] = current_time
            
        elif gesture == "swipe_right":
            self._handle_next()
            self.last_gesture_time['swipe_right'] = current_time
            
        elif gesture == "swipe_left":
            self._handle_previous()
            self.last_gesture_time['swipe_left'] = current_time
            
        elif gesture == "pointing":
            self._handle_pointing()
            self.last_gesture_time['pointing'] = current_time
            
        elif gesture == "open_palm":
            # Neutral gesture - do nothing
            pass
    
    def _handle_play(self):
        """Handle play gesture"""
        print(f"\n🎵 Gesture: THUMBS UP → PLAY")
        
        if self.music_player.is_playing:
            print("   Music is already playing")
            speak("Music is already playing")
        else:
            # Toggle play/pause (resume if paused)
            self.music_player.toggle_pause()
            time.sleep(0.2)  # Wait for state to update
            
            if self.music_player.player.is_playing():
                self.current_music_state = "playing"
                print("   ▶️ Music resumed")
                speak("Playing")
            else:
                # If nothing is playing, try to play next
                if not self.music_player.current_song:
                    print("   Queue is empty. Please use voice commands to add songs")
                    speak("Queue is empty. Please use voice commands to add songs")
                else:
                    print("   ▶️ Play command sent")
                    speak("Playing")
    
    def _handle_pause(self):
        """Handle pause gesture"""
        print(f"\n🎵 Gesture: FIST → PAUSE")
        
        if not self.music_player.is_playing:
            print("   Music is already paused")
            speak("Music is already paused")
        else:
            self.music_player.toggle_pause()
            time.sleep(0.2)
            self.current_music_state = "paused"
            print("   ⏸️ Music paused")
            speak("Paused")
    
    def _handle_next(self):
        """Handle next track gesture"""
        print(f"\n🎵 Gesture: SWIPE RIGHT → NEXT TRACK")
        
        if self.music_player.queue or self.music_player.current_song:
            self.music_player.play_next()
            print("   ⏭️ Skipping to next track")
            time.sleep(0.5)  # Allow time for track to start
            if self.music_player.current_song:
                print(f"   Now playing: {self.music_player.current_song.get('title', 'Unknown')}")
        else:
            print("   Queue is empty")
            speak("No more songs in queue")
    
    def _handle_previous(self):
        """Handle previous track gesture"""
        print(f"\n🎵 Gesture: SWIPE LEFT → PREVIOUS TRACK")
        
        if self.music_player.history:
            self.music_player.play_previous()
            print("   ⏮️ Going to previous track")
            time.sleep(0.5)
            if self.music_player.current_song:
                print(f"   Now playing: {self.music_player.current_song.get('title', 'Unknown')}")
        else:
            print("   No previous track")
            speak("No previous track available")

    def _handle_pointing(self):
        """Handle pointing gesture - activates voice command for playing now"""
        if self.voice_active:
            print("   Voice recognition already active")
            return
            
        print(f"\n🎵 Gesture: POINTING → VOICE COMMAND (Play now)")
        speak("What song would you like to play?")
        
        # Start voice recognition in separate thread
        voice_thread = threading.Thread(target=self._voice_play_now, daemon=True)
        voice_thread.start()
    
    def _voice_play_now(self):
        """Voice recognition for playing song immediately"""
        self.voice_active = True
        
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            
            # Use default microphone
            with sr.Microphone() as source:
                print("   🎤 Listening for song name...")
                
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                try:
                    # Listen with timeout
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    print("   Processing speech...")
                    
                    # Recognize speech
                    query = recognizer.recognize_google(audio).lower()
                    print(f"   ✅ Recognized: '{query}'")
                    
                    if query and len(query) > 0:
                        # Search and play now
                        result = self.music_player.search_and_play_now(query)
                        if not result:
                            speak("Sorry, I couldn't find that song")
                    else:
                        speak("I didn't catch that")
                        
                except sr.WaitTimeoutError:
                    print("   ⏰ No voice detected")
                    speak("I didn't hear anything")
                except sr.UnknownValueError:
                    print("   🤔 Could not understand audio")
                    speak("Sorry, I didn't understand that")
                except sr.RequestError as e:
                    print(f"   🌐 Speech recognition service error: {e}")
                    speak("Speech recognition service error")
                except Exception as e:
                    print(f"   ❌ Voice recognition error: {e}")
                    speak("An error occurred")
                    
        except Exception as e:
            print(f"   ❌ Microphone initialization error: {e}")
            speak("Microphone not available")
        finally:
            self.voice_active = False
    
    def stop(self):
        """Stop all components gracefully"""
        print("\n" + "="*60)
        print("Shutting down Gesture-Music Bridge...")
        
        self.running = False
        
        if self.gesture_controller:
            print("  Stopping gesture controller...")
            self.gesture_controller.release()
        
        if self.music_player:
            print("  Stopping music player...")
            if self.music_player.player:
                self.music_player.player.stop()
        
        print("  System shutdown complete")
        print("="*60 + "\n")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nInterrupt received, shutting down...")
    sys.exit(0)

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and start bridge
    bridge = GestureMusicBridge()
    
    try:
        if bridge.start():
            # Keep main thread alive
            while bridge.running:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        bridge.stop()

if __name__ == "__main__":
    main()