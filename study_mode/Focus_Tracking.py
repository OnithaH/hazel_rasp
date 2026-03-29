import os, cv2, mediapipe as mp, numpy as np, time, pygame

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True)
LEFT_EYE = [33, 160, 158, 133, 153, 144] 
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
EAR_THRESHOLD, YAW_LIMIT = 0.26, 35
drowsy_start_time = away_start_time = None
is_alerting = False

def calculate_ear(eye_landmarks):
    p1, p2, p3, p4, p5, p6 = eye_landmarks
    return (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * np.linalg.norm(p1 - p4))

def get_head_pose(lms, w, h):
    nose = np.array([lms[1].x * w, lms[1].y * h])
    center_eyes = np.array([(lms[33].x + lms[263].x)/2 * w, (lms[33].y + lms[263].y)/2 * h])
    return nose[0] - center_eyes[0], nose[1] - center_eyes[1]

def process_frame(image, music_loaded):
    global drowsy_start_time, away_start_time, is_alerting
    h, w, _ = image.shape
    results = face_mesh.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    if results.multi_face_landmarks:
        lms = results.multi_face_landmarks[0].landmark
        yaw, _ = get_head_pose(lms, w, h)
        left_coords = [np.array([int(lms[i].x * w), int(lms[i].y * h)]) for i in LEFT_EYE]
        right_coords = [np.array([int(lms[i].x * w), int(lms[i].y * h)]) for i in RIGHT_EYE]
        avg_ear = (calculate_ear(left_coords) + calculate_ear(right_coords)) / 2.0
        if avg_ear < EAR_THRESHOLD:
            if drowsy_start_time is None: drowsy_start_time = time.time()
            if time.time() - drowsy_start_time >= 3.0:
                cv2.putText(image, "DROWSY!", (50, 70), 0, 1.2, (0, 0, 255), 3)
                if not is_alerting and music_loaded:
                    pygame.mixer.music.play(-1); is_alerting = True
        else: 
            drowsy_start_time = None
            if is_alerting and music_loaded:
                pygame.mixer.music.stop()
                is_alerting = False
        cv2.putText(image, f"EAR: {avg_ear:.2f}", (10, 30), 0, 0.7, (255, 255, 255), 2)
    return image