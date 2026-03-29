import cv2, mediapipe as mp, numpy as np
from collections import deque

mp_pose = mp.solutions.pose
pose = mp_pose.Pose()

# Store the last 5 shoulder positions to smooth out the movement
history = deque(maxlen=5)

def process_frame(frame, esp_serial=None):
    h, w, _ = frame.shape
    results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    if results.pose_landmarks:
        lms = results.pose_landmarks.landmark
        current_x = (lms[11].x + lms[12].x) / 2
        history.append(current_x)
        
        # Calculate the moving average
        smoothed_x = sum(history) / len(history)
        
        # Determine status based on the smoothed value
        if smoothed_x < 0.40:
            status = "BODY LEFT"
            if esp_serial: esp_serial.write(b'L')
        elif smoothed_x > 0.60:
            status = "BODY RIGHT"
            if esp_serial: esp_serial.write(b'R')
        else:
            status = "Centered"
            # Optional: send 'S' to stop if you want it to wait when centered
            # if esp_serial: esp_serial.write(b'S')
            
        cv2.putText(frame, f"{status} (Avg: {smoothed_x:.2f})", (10, 60), 0, 0.6, (0, 255, 0), 2)
    else:
        # If tracking is lost, we stop the motor for safety
        if esp_serial: esp_serial.write(b'S')
        
    return frame