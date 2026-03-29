"""
gesture_controller.py - Unified gesture controller for all games
"""

import cv2
import mediapipe as mp
import math
import time

class GestureController:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # Swipe detection
        self.prev_x = None
        self.prev_time = 0
        self.swipe_cooldown = 0.5  # seconds
        self.last_swipe_time = 0
        
        # Pose hold detection
        self.pose_name = None
        self.pose_start_time = 0
        self.pose_hold_time = 0.35  # seconds to hold for action
        self.last_pose_time = 0
        self.pose_cooldown = 0.5
        
        # Trail for visual feedback
        self.trail = []
        self.trail_positions = []
        
        # Camera reference
        self.picam2 = None
        
    def set_camera(self, camera):
        """Set the camera instance"""
        self.picam2 = camera
        
    def start(self):
        """Start gesture detection (placeholder for compatibility)"""
        return True
        
    def detect_gesture(self, frame=None):
        """
        Detect gestures from camera frame.
        If no frame provided, captures from camera.
        Returns: gesture string or None
        """
        if frame is None and self.picam2:
            frame_raw = self.picam2.capture_array()
            if frame_raw is None:
                return None
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            frame = cv2.flip(frame, 1)
        
        if frame is None:
            return None
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        now = time.time()
        h, w = frame.shape[:2]
        
        if not results.multi_hand_landmarks:
            self.prev_x = None
            self.pose_name = None
            self.trail = []
            self.trail_positions = []
            return None
        
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # Draw landmarks on frame
        self.mp_draw.draw_landmarks(
            frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
        )
        
        landmarks = hand_landmarks.landmark
        gesture = self._classify_gesture(landmarks, w, h, now, frame)
        
        return gesture
    
    def _classify_gesture(self, landmarks, w, h, now, frame):
        """
        Classify gesture using finger counting and pose detection.
        """
        # Get which fingers are up
        fingers_up = self._get_fingers_up(landmarks)
        fingers_count = sum(fingers_up)
        
        # Get index finger tip position for swipe
        index_tip = landmarks[8]
        hand_x = int(index_tip.x * w)
        hand_y = int(index_tip.y * h)
        
        # Add to trail
        self.trail_positions.append((hand_x, hand_y, now))
        self.trail_positions = [(x, y, t) for x, y, t in self.trail_positions if now - t < 0.5]
        
        # Draw trail
        for i in range(1, len(self.trail_positions)):
            age = now - self.trail_positions[i][2]
            alpha = max(0, 1 - age * 2)
            c = int(255 * alpha)
            cv2.line(frame,
                     (self.trail_positions[i-1][0], self.trail_positions[i-1][1]),
                     (self.trail_positions[i][0], self.trail_positions[i][1]),
                     (c, c, 0), 3)
        
        # SWIPE DETECTION (with cooldown)
        if now - self.last_swipe_time > self.swipe_cooldown:
            if self.prev_x is not None:
                movement = hand_x - self.prev_x
                if abs(movement) > 80:  # Swipe threshold
                    self.last_swipe_time = now
                    self.prev_x = None
                    if movement > 0:
                        return "swipe_right"
                    else:
                        return "swipe_left"
            self.prev_x = hand_x
        else:
            self.prev_x = hand_x
        
        # POSE DETECTION (hold gestures)
        # Determine current pose
        if fingers_count == 0:
            current_pose = "fist"
        elif fingers_count >= 5:
            current_pose = "open_palm"
        elif self._is_thumbs_up(landmarks):
            current_pose = "thumbs_up"
        elif fingers_count == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:
            current_pose = "peace"
        elif fingers_count == 3:
            current_pose = "three_fingers"
        elif fingers_count == 1 and fingers_up[1] == 1:
            current_pose = "point"
        else:
            current_pose = None
        
        # Handle pose hold detection
        if current_pose is None:
            self.pose_name = None
        elif self.pose_name != current_pose:
            self.pose_name = current_pose
            self.pose_start_time = now
        elif (now - self.pose_start_time >= self.pose_hold_time 
              and now - self.last_pose_time > self.pose_cooldown):
            self.last_pose_time = now
            self.pose_name = None
            
            # Convert pose to gesture name expected by games
            if current_pose == "fist":
                return "up"
            elif current_pose == "open_palm":
                return "down"
            elif current_pose == "thumbs_up":
                return "thumbs_up"
            elif current_pose == "peace":
                return "restart"
            elif current_pose == "three_fingers":
                return "quit"
            elif current_pose == "point":
                return "next"
        
        return None
    
    def _get_fingers_up(self, landmarks):
        """
        Returns list of which fingers are extended.
        Index 0 = thumb, 1 = index, 2 = middle, 3 = ring, 4 = pinky
        """
        fingers = []
        
        # Thumb detection (for right hand)
        if landmarks[4].x < landmarks[3].x:
            fingers.append(1)
        else:
            fingers.append(0)
        
        # Other fingers
        finger_tips = [8, 12, 16, 20]  # Index, Middle, Ring, Pinky
        finger_pips = [6, 10, 14, 18]   # PIP joints
        
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip].y < landmarks[pip].y:
                fingers.append(1)
            else:
                fingers.append(0)
        
        return fingers
    
    def _is_thumbs_up(self, landmarks):
        """
        Check if hand is showing thumbs up gesture.
        """
        # Thumb tip should be above wrist
        if landmarks[4].y > landmarks[0].y - 0.08:
            return False
        
        # Other fingers should be down
        for tip, mcp in zip([8, 12, 16, 20], [5, 9, 13, 17]):
            if landmarks[tip].y < landmarks[mcp].y:
                return False
        
        return True
    
    def get_fingers_count(self, frame=None):
        """Get current finger count"""
        if frame is None and self.picam2:
            frame_raw = self.picam2.capture_array()
            if frame_raw is None:
                return 0
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            frame = cv2.flip(frame, 1)
        
        if frame is None:
            return 0
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        if not results.multi_hand_landmarks:
            return 0
        
        landmarks = results.multi_hand_landmarks[0].landmark
        fingers_up = self._get_fingers_up(landmarks)
        return sum(fingers_up)
    
    def draw_ui(self, frame, gesture=None, fingers_count=None):
        """
        Draw UI elements on camera feed.
        """
        h, w = frame.shape[:2]
        
        # Instruction text
        cv2.putText(frame, 
            "SWIPE L/R=MOVE | FIST=UP | PALM=DOWN | THUMB=NEXT | PEACE=RESTART",
            (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 100), 1)
        
        # Show detected gesture
        if gesture:
            text_size = cv2.getTextSize(gesture.upper(), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)[0]
            cv2.rectangle(frame,
                         (w//2 - text_size[0]//2 - 10, h//2 - 40),
                         (w//2 + text_size[0]//2 + 10, h//2 + 20),
                         (0, 0, 0), -1)
            cv2.putText(frame, gesture.upper(),
                        (w//2 - text_size[0]//2, h//2 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 200), 3)
        
        # Show finger count if available
        if fingers_count is not None:
            cv2.putText(frame, f"Fingers: {fingers_count}",
                        (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
        
        return frame
    
    def stop(self):
        """Stop gesture detection and cleanup"""
        try:
            cv2.destroyAllWindows()
        except:
            pass
    
    def release(self):
        """Properly close MediaPipe hand detection resources"""
        if self.hands:
            self.hands.close()