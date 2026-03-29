import cv2, time, pygame
from ultralytics import YOLO

model = YOLO("yolov8n.pt") 
detection_counter = 0
is_alerting = False

def detect_phone(frame):
    """Highly optimized phone detection for RPi5."""
    global detection_counter
    # Only detect class 67 (cell phone) to save processing time
    results = model.predict(frame, conf=0.3, classes=[67], verbose=False)[0]
    has_phone = len(results.boxes) > 0
    
    if has_phone: 
        detection_counter += 1
        if detection_counter >= 2: # Reduce from 3 to 2 for slightly faster response
            return True
    else: 
        detection_counter = 0
    return False

def process_frame(frame, alert_sound):
    global detection_counter, is_alerting
    results = model(frame, verbose=False)[0]
    has_phone = any(int(box.cls[0]) == 67 and float(box.conf[0]) > 0.2 for box in results.boxes)
    if has_phone: detection_counter += 1
    else: detection_counter = 0
    
    if detection_counter >= 3:
        cv2.putText(frame, "PHONE DETECTED!", (50, 150), 0, 1.2, (0, 0, 255), 3)
        if alert_sound and not is_alerting:
            alert_sound.play(-1)
            is_alerting = True
    else:
        if alert_sound and is_alerting:
            alert_sound.stop()
            is_alerting = False
            
    return frame