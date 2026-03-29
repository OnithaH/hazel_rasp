"""
MAIN ENTRY POINT - Launches the game launcher and handles game switching
"""

import os
import sys
import time
import pygame
from camera_manager import get_camera, release_camera
from game_launcher import run_launcher
import find_my_home
import puzzle_escape

# Add parent directory to path to allow importing hazel_services
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from hazel_services.db_manager import DBManager

def set_camera_for_games(camera):
    """Set camera for all games"""
    find_my_home.set_camera(camera)
    puzzle_escape.set_camera(camera)

def main():
    """Main entry point for the game suite"""
    pygame.init()
    
    print("\n" + "="*60)
    print("         🎮 GESTURE-CONTROLLED GAMES 🎮")
    print("="*60)
    print("Launching Game Launcher...")
    print("Use gestures to select and launch games")
    print("Press ESC in any game to return to launcher")
    print("="*60 + "\n")
    
    try:
        # Get camera ONCE at the start
        camera = get_camera()
        set_camera_for_games(camera)
        db = DBManager()

        while True:
            # Run launcher (Camera stays active in background)
            choice = run_launcher()
            
            # REMOVED: release_camera() call here was causing the crash
            
            if choice == 0:
                print("🎮 LAUNCHING: FIND MY HOME")
                results = find_my_home.run_find_my_home()
                if results:
                    db.log_game_session("GAME", "Find My Home", results['duration'], results['score'], results['result'])
            else:
                print("🎮 LAUNCHING: PUZZLE ESCAPE")
                results = puzzle_escape.run_puzzle_escape()
                if results:
                    db.log_game_session("GAME", "Puzzle Escape", results['duration'], results['score'], results['result'])
            
            print("\nReturning to launcher...")
            time.sleep(1) # Short buffer
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # ONLY release here when the whole app exits
        release_camera()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()