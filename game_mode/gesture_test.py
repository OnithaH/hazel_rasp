import cv2
import mediapipe as mp
import math
import time
import numpy as np
from picamera2 import Picamera2
from collections import deque

class GestureController:
    """
    A robust gesture controller with enhanced swipe detection.
    """
    
    def __init__(self, show_feedback=True, camera_size=(640, 480)):
        """
        Initialize the gesture controller.
        
        Args:
            show_feedback: If True, shows camera feed with gesture overlay
            camera_size: Tuple of (width, height) for camera resolution
        """
        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Camera setup
        self.picam2 = None
        self.camera_size = camera_size
        
        # ENHANCED SWIPE DETECTION
        self.wrist_positions = deque(maxlen=15)
        self.swipe_velocity = 0
        self.swipe_direction = None
        self.swipe_confidence = 0
        
        # Swipe parameters
        self.SWIPE_MIN_DISTANCE = 0.18
        self.SWIPE_MIN_VELOCITY = 0.8
        self.SWIPE_TIME_WINDOW = 0.4
        self.SWIPE_COOLDOWN = 0.6
        self.last_swipe_time = 0
        
        # Velocity tracking
        self.prev_wrist_x = None
        self.prev_time = None
        self.velocity_history = deque(maxlen=5)
        
        # Pose hold detection
        self.pose_name = None
        self.pose_start_time = 0
        self.POSE_HOLD_TIME = 0.3
        self.POSE_COOLDOWN = 1.0
        
        # Tracking - Prevent repeated detections
        self.current_active_gesture = None
        self.last_reported_gesture = None
        self.last_report_time = 0
        self.gesture_active = False
        
        # Movement smoothing
        self.smoothed_x = None
        self.smoothing_factor = 0.3
        
        # Display settings
        self.show_feedback = show_feedback
        self.window_name = 'Gesture Control'
        
        # Current detection
        self.current_gesture = None
        self.current_fingers = 0
        self.current_landmarks = None
        self.swipe_debug_info = ""
        self.last_wrist_y = None
        
        # Statistics
        self.frame_count = 0
        self.detection_count = 0
        
    def start_camera(self):
        """Initialize and start the Raspberry Pi camera"""
        try:
            print("[CAMERA] Initializing Picamera2...")
            self.picam2 = Picamera2()
            
            # Configure camera
            config = self.picam2.create_preview_configuration(
                main={'size': self.camera_size, 'format': 'RGB888'}
            )
            self.picam2.configure(config)
            self.picam2.start()
            
            # Wait for camera to warm up
            time.sleep(2)
            print(f"[CAMERA] Camera started at {self.camera_size}")
            return True
            
        except Exception as e:
            print(f"[CAMERA] Error starting camera: {e}")
            return False
    
    def get_frame(self):
        """Capture a frame from the camera"""
        if self.picam2 is None:
            return None
        
        try:
            frame = self.picam2.capture_array()
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frame = cv2.flip(frame, 1)
            return frame
        except Exception as e:
            print(f"[CAMERA] Error capturing frame: {e}")
            return None
    
    def _count_fingers(self, landmarks):
        """Count number of extended fingers (for display only)"""
        fingers = 0
        
        # For counting, we include thumb for display
        if landmarks[4].x < landmarks[3].x:
            fingers += 1
        if landmarks[8].y < landmarks[6].y:
            fingers += 1
        if landmarks[12].y < landmarks[10].y:
            fingers += 1
        if landmarks[16].y < landmarks[14].y:
            fingers += 1
        if landmarks[20].y < landmarks[18].y:
            fingers += 1
            
        return fingers
    
    def _is_fist(self, landmarks):
        """Check if hand is making a fist"""
        # All finger tips should be below their respective PIP joints
        if landmarks[8].y < landmarks[6].y:  # Index extended
            return False
        if landmarks[12].y < landmarks[10].y:  # Middle extended
            return False
        if landmarks[16].y < landmarks[14].y:  # Ring extended
            return False
        if landmarks[20].y < landmarks[18].y:  # Pinky extended
            return False
            
        # Thumb should be close to index finger
        thumb_index_dist = math.sqrt((landmarks[4].x - landmarks[8].x)**2 + 
                                     (landmarks[4].y - landmarks[8].y)**2)
        if thumb_index_dist > 0.1:
            return False
            
        return True
    
    def _is_thumbs_up(self, landmarks):
        """Check if hand is making thumbs up gesture - HIGH PRIORITY"""
        # Thumb should be extended upward (tip above wrist)
        if landmarks[4].y > landmarks[0].y - 0.08:
            return False
        
        # Check thumb is extended (tip to the left of IP joint for right hand)
        if not (landmarks[4].x < landmarks[3].x):
            return False
        
        # CRITICAL: All other fingers MUST be curled (not extended)
        # Index finger should be curled (tip below PIP)
        if landmarks[8].y < landmarks[6].y:
            return False
        
        # Middle finger should be curled
        if landmarks[12].y < landmarks[10].y:
            return False
        
        # Ring finger should be curled
        if landmarks[16].y < landmarks[14].y:
            return False
        
        # Pinky should be curled
        if landmarks[20].y < landmarks[18].y:
            return False
        
        return True
    
    def _is_open_palm(self, landmarks):
        """Check if hand is open palm - LOWEST PRIORITY"""
        # Count extended fingers
        fingers_extended = 0
        
        # Check each finger
        if landmarks[4].x < landmarks[3].x:  # Thumb extended
            fingers_extended += 1
        if landmarks[8].y < landmarks[6].y:  # Index extended
            fingers_extended += 1
        if landmarks[12].y < landmarks[10].y:  # Middle extended
            fingers_extended += 1
        if landmarks[16].y < landmarks[14].y:  # Ring extended
            fingers_extended += 1
        if landmarks[20].y < landmarks[18].y:  # Pinky extended
            fingers_extended += 1
        
        # Open palm requires at least 4 fingers extended
        # But we need to ensure it's NOT a thumbs up
        if fingers_extended >= 4:
            # Double-check it's not a thumbs up
            if self._is_thumbs_up(landmarks):
                return False
            return True
        
        return False
    
    def _is_peace(self, landmarks):
        """Check for peace sign (index and middle finger up)"""
        # Index and middle fingers extended
        index_extended = landmarks[8].y < landmarks[6].y
        middle_extended = landmarks[12].y < landmarks[10].y
        
        # Ring and pinky curled
        ring_curled = landmarks[16].y > landmarks[14].y
        pinky_curled = landmarks[20].y > landmarks[18].y
        
        # Thumb can be either, but typically curled for peace sign
        return index_extended and middle_extended and ring_curled and pinky_curled
    
    def _is_pointing(self, landmarks):
        """Check for pointing gesture (index finger up)"""
        # Index finger extended
        index_extended = landmarks[8].y < landmarks[6].y
        
        # Other fingers curled
        middle_curled = landmarks[12].y > landmarks[10].y
        ring_curled = landmarks[16].y > landmarks[14].y
        pinky_curled = landmarks[20].y > landmarks[18].y
        thumb_curled = landmarks[4].x > landmarks[3].x
        
        return index_extended and middle_curled and ring_curled and pinky_curled and thumb_curled
    
    def _detect_swipe_enhanced(self, landmarks, current_time):
        """Enhanced swipe detection"""
        current_x = landmarks[0].x
        current_y = landmarks[0].y
        
        self.last_wrist_y = current_y
        
        # Apply smoothing
        if self.smoothed_x is None:
            self.smoothed_x = current_x
        else:
            self.smoothed_x = (self.smoothed_x * (1 - self.smoothing_factor) + 
                              current_x * self.smoothing_factor)
        
        # Add to position history
        self.wrist_positions.append((self.smoothed_x, current_time))
        
        # Calculate velocity
        if self.prev_wrist_x is not None and self.prev_time is not None:
            dt = current_time - self.prev_time
            if dt > 0:
                velocity = (self.smoothed_x - self.prev_wrist_x) / dt
                self.velocity_history.append(velocity)
        
        self.prev_wrist_x = self.smoothed_x
        self.prev_time = current_time
        
        if len(self.wrist_positions) < 8:
            return None
        
        recent_positions = [(x, t) for x, t in self.wrist_positions 
                           if current_time - t <= self.SWIPE_TIME_WINDOW]
        
        if len(recent_positions) < 5:
            return None
        
        start_x, start_time = recent_positions[0]
        end_x, end_time = recent_positions[-1]
        
        distance = abs(end_x - start_x)
        time_elapsed = end_time - start_time
        
        if len(self.velocity_history) > 0:
            avg_velocity = abs(sum(self.velocity_history) / len(self.velocity_history))
        else:
            avg_velocity = 0
        
        # Calculate consistency
        x_positions = [x for x, t in recent_positions]
        consistency = 0
        if len(x_positions) > 2:
            n = len(x_positions)
            indices = list(range(n))
            mean_x = sum(x_positions) / n
            mean_i = sum(indices) / n
            numerator = sum((x_positions[i] - mean_x) * (indices[i] - mean_i) for i in range(n))
            denominator = sum((indices[i] - mean_i) ** 2 for i in range(n))
            if denominator > 0:
                slope = numerator / denominator
                predicted = [mean_x + slope * (i - mean_i) for i in indices]
                ss_res = sum((x_positions[i] - predicted[i]) ** 2 for i in range(n))
                ss_tot = sum((x_positions[i] - mean_x) ** 2 for i in range(n))
                consistency = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Confidence scoring
        confidence = 0
        if distance >= self.SWIPE_MIN_DISTANCE:
            confidence += 0.4
        elif distance >= self.SWIPE_MIN_DISTANCE * 0.7:
            confidence += 0.2
        
        if avg_velocity >= self.SWIPE_MIN_VELOCITY:
            confidence += 0.4
        elif avg_velocity >= self.SWIPE_MIN_VELOCITY * 0.7:
            confidence += 0.2
        
        if consistency >= 0.7:
            confidence += 0.2
        elif consistency >= 0.5:
            confidence += 0.1
        
        if time_elapsed < 0.3:
            confidence += 0.1
        
        self.swipe_debug_info = f"Dist:{distance:.2f} Vel:{avg_velocity:.1f} Conf:{confidence:.2f}"
        
        if confidence >= 0.7 and current_time - self.last_swipe_time >= self.SWIPE_COOLDOWN:
            direction = "swipe_right" if end_x > start_x else "swipe_left"
            
            if len(self.velocity_history) > 0:
                avg_vel_dir = sum(self.velocity_history) / len(self.velocity_history)
                if (direction == "swipe_right" and avg_vel_dir > 0) or \
                   (direction == "swipe_left" and avg_vel_dir < 0):
                    self.last_swipe_time = current_time
                    self.wrist_positions.clear()
                    self.velocity_history.clear()
                    self.smoothed_x = None
                    self.prev_wrist_x = None
                    return direction
        
        return None
    
    def detect_gesture(self, frame):
        """
        Detect gestures from a single frame.
        Returns gesture only when it's first detected.
        """
        if frame is None:
            return None
        
        self.frame_count += 1
        
        # Process frame
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        gesture = None
        current_time = time.time()
        
        # Process hand landmarks
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            landmarks = hand_landmarks.landmark
            self.current_landmarks = landmarks
            
            # Draw landmarks
            if self.show_feedback:
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                )
            
            # Count fingers for display
            finger_count = self._count_fingers(landmarks)
            self.current_fingers = finger_count
            
            # Check for swipe first (highest priority)
            swipe_gesture = self._detect_swipe_enhanced(landmarks, current_time)
            
            if swipe_gesture:
                gesture = swipe_gesture
                self.detection_count += 1
                self.current_active_gesture = None
                self.gesture_active = False
                self.current_gesture = gesture
                self.last_reported_gesture = gesture
                self.last_report_time = current_time
            else:
                # Check static poses in PRIORITY ORDER
                static_gesture = None
                
                # 1. Fist (highest priority after swipe)
                if self._is_fist(landmarks):
                    static_gesture = "fist"
                
                # 2. Thumbs up (HIGH priority - before open palm)
                elif self._is_thumbs_up(landmarks):
                    static_gesture = "thumbs_up"
                
                # 3. Peace sign
                elif self._is_peace(landmarks):
                    static_gesture = "peace"
                
                # 4. Pointing
                elif self._is_pointing(landmarks):
                    static_gesture = "pointing"
                
                # 5. Open palm (lowest priority)
                elif self._is_open_palm(landmarks):
                    static_gesture = "open_palm"
                
                # Handle pose detection with hold and single reporting
                if static_gesture:
                    self.current_gesture = static_gesture
                    
                    if self.current_active_gesture != static_gesture:
                        self.current_active_gesture = static_gesture
                        self.pose_start_time = current_time
                        self.gesture_active = False
                    else:
                        hold_time = current_time - self.pose_start_time
                        if hold_time >= self.POSE_HOLD_TIME and not self.gesture_active:
                            if current_time - self.last_report_time >= self.POSE_COOLDOWN:
                                gesture = static_gesture
                                self.gesture_active = True
                                self.last_report_time = current_time
                                self.detection_count += 1
                                self.last_reported_gesture = gesture
                else:
                    self.current_active_gesture = None
                    self.gesture_active = False
                    self.current_gesture = None
        
        else:
            # No hand - reset
            self.wrist_positions.clear()
            self.velocity_history.clear()
            self.smoothed_x = None
            self.prev_wrist_x = None
            self.current_active_gesture = None
            self.gesture_active = False
            self.current_gesture = None
            self.current_fingers = 0
            self.current_landmarks = None
            self.last_wrist_y = None
        
        # Draw UI
        if self.show_feedback:
            self._draw_ui(frame, current_time)
        
        return gesture
    
    def _draw_ui(self, frame, current_time):
        """Draw UI overlay"""
        h, w, _ = frame.shape
        
        # Background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 35), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        
        # Title
        cv2.putText(frame, "GESTURE CONTROLLER", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
        
        # Info box
        if self.current_gesture or self.current_fingers > 0:
            box_h = 150 if self.swipe_debug_info else 120
            box_y = h - box_h - 10
            
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, box_y), (w - 10, h - 10), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            # Finger count circles
            if self.current_fingers > 0:
                y_offset = box_y + 35
                for i in range(5):
                    x_pos = 30 + i * 50
                    color = (0, 255, 0) if i < self.current_fingers else (100, 100, 100)
                    cv2.circle(frame, (x_pos, y_offset), 15, color, -1)
                    cv2.circle(frame, (x_pos, y_offset), 15, (255, 255, 255), 2)
            
            # Current gesture
            if self.current_gesture:
                gesture_text = f"Current: {self.current_gesture.upper()}"
                cv2.putText(frame, gesture_text, (20, box_y + 85),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # Swipe debug info
            if self.swipe_debug_info:
                cv2.putText(frame, f"Swipe: {self.swipe_debug_info}", (20, box_y + 115),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 200, 255), 1)
            
            # Last reported gesture
            if self.last_reported_gesture:
                time_since = current_time - self.last_report_time
                if time_since < self.POSE_COOLDOWN:
                    status = f"Last: {self.last_reported_gesture.upper()} (cooldown: {self.POSE_COOLDOWN - time_since:.1f}s)"
                else:
                    status = f"Last: {self.last_reported_gesture.upper()} (ready)"
                cv2.putText(frame, status, (20, box_y + 135),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            
            # Statistics
            stats_text = f"Total: {self.detection_count}"
            cv2.putText(frame, stats_text, (w - 100, box_y + 135),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            
            # Hold progress bar
            if self.current_active_gesture and not self.gesture_active:
                hold_progress = min(1.0, (current_time - self.pose_start_time) / self.POSE_HOLD_TIME)
                bar_width = int(200 * hold_progress)
                bar_x = w // 2 - 100
                bar_y = box_y + 10
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + 200, bar_y + 8), (50, 50, 50), -1)
                cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + 8), (0, 255, 0), -1)
                
                hold_text = f"Holding {self.current_active_gesture.upper()}..."
                cv2.putText(frame, hold_text, (w // 2 - 80, box_y + 28),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        
        # Draw wrist trail
        if len(self.wrist_positions) > 1 and self.last_wrist_y is not None:
            positions = list(self.wrist_positions)
            y_pos = int(self.last_wrist_y * h)
            
            for i in range(1, len(positions)):
                x1 = int(positions[i-1][0] * w)
                x2 = int(positions[i][0] * w)
                
                if len(self.velocity_history) > i-1 and i-1 < len(self.velocity_history):
                    vel = abs(self.velocity_history[min(i-1, len(self.velocity_history)-1)])
                    intensity = min(255, int(vel * 200))
                    color = (0, intensity, 255 - intensity)
                else:
                    color = (0, 255, 255)
                
                cv2.line(frame, (x1, y_pos), (x2, y_pos), color, 4)
        
        # Guide text
        guide_y = h - 10
        guide_text = "SWIPE L/R | Fist | THUMBS UP | Peace | Point | Open Palm"
        cv2.putText(frame, guide_text, (10, guide_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        
        # Finger tips
        if self.current_landmarks:
            tips = [4, 8, 12, 16, 20]
            for tip in tips:
                x = int(self.current_landmarks[tip].x * w)
                y = int(self.current_landmarks[tip].y * h)
                cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)
    
    def release(self):
        """Release resources"""
        if self.hands:
            self.hands.close()
        
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
        
        if self.show_feedback:
            cv2.destroyAllWindows()
        
        print(f"\n[STATS] Frames: {self.frame_count}, Detections: {self.detection_count}")


def test_gesture_controller():
    """Test the gesture controller"""
    print("\n" + "="*60)
    print("       GESTURE CONTROLLER TEST (Enhanced Swipe)")
    print("="*60)
    print("\nDetected gestures (in priority order):")
    print("  1. SWIPE LEFT/RIGHT")
    print("  2. FIST")
    print("  3. THUMBS UP  ← FIXED! Now properly detected")
    print("  4. PEACE")
    print("  5. POINTING")
    print("  6. OPEN PALM")
    print("\nTips:")
    print("  - Thumbs up: Only thumb extended, all other fingers CLOSED")
    print("  - Open palm: All fingers spread wide")
    print("  - Hold any pose for 0.3 seconds to register")
    print("\nPress 'q' to quit, 'r' to reset stats\n")
    print("-"*60)
    
    controller = GestureController(show_feedback=True, camera_size=(640, 480))
    
    if not controller.start_camera():
        print("Error: Could not start camera")
        return
    
    print("[INFO] Ready! Try making a thumbs up gesture (other fingers closed)...\n")
    
    try:
        cv2.namedWindow(controller.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(controller.window_name, 640, 480)
        
        while True:
            frame = controller.get_frame()
            if frame is None:
                print("Warning: No frame received")
                continue
            
            try:
                gesture = controller.detect_gesture(frame)
                
                if gesture:
                    if gesture == "thumbs_up":
                        print(f"[{controller.detection_count}] 👍 {gesture.upper()} 👍")
                    elif gesture.startswith("swipe"):
                        print(f"[{controller.detection_count}] 🖐️ {gesture.upper()} 🖐️")
                    else:
                        print(f"[{controller.detection_count}] {gesture.upper()}")
                
                cv2.imshow(controller.window_name, frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key == ord('r'):
                    controller.detection_count = 0
                    print("\nStats reset")
                    
            except Exception as e:
                print(f"Error in detection loop: {e}")
                continue
    
    except KeyboardInterrupt:
        pass
    finally:
        controller.release()
        print("\nTest complete.")


if __name__ == "__main__":
    test_gesture_controller()