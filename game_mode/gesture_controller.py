import cv2
import mediapipe as mp
import math

class GestureController:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.prev_x = None
        self.gesture_cooldown = 0
        self.cooldown_frames = 15
        
    def detect_gesture(self, frame):
        if self.gesture_cooldown > 0:
            self.gesture_cooldown -= 1
            return None
            
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb_frame)
        
        if not results.multi_hand_landmarks:
            self.prev_x = None
            return None
        
        hand_landmarks = results.multi_hand_landmarks[0]
        
        self.mp_draw.draw_landmarks(
            frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
        )
        
        landmarks = hand_landmarks.landmark
        gesture = self._classify_gesture(landmarks, frame.shape)
        
        if gesture:
            self.gesture_cooldown = self.cooldown_frames
        
        return gesture
    
    def _classify_gesture(self, landmarks, frame_shape):
        h, w, _ = frame_shape
        
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        fingers_up = self._get_fingers_up(landmarks)
        hand_x = int(index_tip.x * w)
        
        if self.prev_x is not None:
            movement = hand_x - self.prev_x
            if abs(movement) > 80:
                self.prev_x = None
                if movement > 0:
                    return "swipe_right"
                else:
                    return "swipe_left"
        
        self.prev_x = hand_x
        
        if fingers_up == [0, 0, 0, 0, 0]:
            return "fist"
        elif fingers_up == [1, 0, 0, 0, 0]:
            return "thumbs_up"
        elif fingers_up == [1, 1, 1, 1, 1]:
            return "open_palm"
        elif fingers_up == [0, 1, 1, 0, 0]:
            return "peace"
        
        return None
    
    def _get_fingers_up(self, landmarks):
        fingers = []
        
        if landmarks[4].x < landmarks[3].x:
            fingers.append(1)
        else:
            fingers.append(0)
        
        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]
        
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip].y < landmarks[pip].y:
                fingers.append(1)
            else:
                fingers.append(0)
        
        return fingers
    
    def release(self):
        """Properly close MediaPipe hand detection resources"""
        if self.hands:
            self.hands.close()