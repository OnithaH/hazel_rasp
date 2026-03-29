"""
camera_manager.py - Shared camera management across all modules
"""

import threading
import time
from picamera2 import Picamera2

_global_camera = None
_camera_lock = threading.Lock()

def get_camera():
    """Get the global camera instance - creates if not exists"""
    global _global_camera
    with _camera_lock:
        if _global_camera is None:
            print("[CAMERA] Creating global camera instance...")
            try:
                _global_camera = Picamera2()
                config = _global_camera.create_preview_configuration(main={'size': (640, 480)})
                
                # FIX: Check if config exists before subscripting (avoids NoneType error)
                if config is not None:
                    _global_camera.configure(config)
                    _global_camera.start()
                    # FIX: Increased wait time for Pi hardware stability
                    time.sleep(2.5) 
                    print("[CAMERA] Global camera started")
                else:
                    print("[CAMERA] Failed to create configuration")
                    _global_camera = None
            except Exception as e:
                print(f"[CAMERA] Error during initialization: {e}")
                _global_camera = None
        return _global_camera

def release_camera():
    """Release the global camera instance"""
    global _global_camera
    with _camera_lock:
        if _global_camera is not None:
            print("[CAMERA] Releasing global camera...")
            try:
                _global_camera.stop()
                _global_camera.close()
            except:
                pass
            _global_camera = None
            time.sleep(1)
            print("[CAMERA] Camera released")

def camera_available():
    """Check if camera is available"""
    global _global_camera
    return _global_camera is not None