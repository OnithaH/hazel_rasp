import pygame
import sys
import math
import random
import cv2
import mediapipe as mp
import threading
import queue
import time
from picamera2 import Picamera2

# Global camera instance - SHARED ACROSS ALL MODES
_global_camera = None
_camera_lock = threading.Lock()

def get_camera():
    global _global_camera
    with _camera_lock:
        if _global_camera is None:
            print("[CAMERA] Creating global camera instance...")
            _global_camera = Picamera2()
            config = _global_camera.create_preview_configuration(main={'size': (640, 480)})
            _global_camera.configure(config)
            _global_camera.start()
            time.sleep(2)
            print("[CAMERA] Global camera started")
        return _global_camera

def release_camera():
    global _global_camera
    with _camera_lock:
        if _global_camera is not None:
            print("[CAMERA] Releasing global camera...")
            _global_camera.stop()
            _global_camera.close()
            _global_camera = None
            print("[CAMERA] Camera released")


pygame.init()

# ─────────────────────────────────────────────────────────────────────────────
#  LAUNCHER  –  shown at startup / after each game exits
#  Returns 0 = Find My Home,  1 = Puzzle Escape
# ─────────────────────────────────────────────────────────────────────────────

LAUNCH_W, LAUNCH_H = 900, 600

def run_launcher():
    """
    Gesture-controlled launcher with fixed camera handling.
    """
    import threading
    import queue as _queue

    # ── gesture imports ────────────────────────────────────────────────
    _GESTURE_OK = True
    try:
        import cv2
        import mediapipe as mp
    except Exception:
        _GESTURE_OK = False

    screen = pygame.display.set_mode((LAUNCH_W, LAUNCH_H))
    pygame.display.set_caption("Game Launcher – Select a Game")
    clock = pygame.time.Clock()

    try:
        font_title = pygame.font.SysFont("segoeuisymbol", 52, bold=True)
        font_sub   = pygame.font.SysFont("segoeuisymbol", 22)
        font_card  = pygame.font.SysFont("segoeuisymbol", 26, bold=True)
        font_desc  = pygame.font.SysFont("segoeuisymbol", 17)
        font_hint  = pygame.font.SysFont("segoeuisymbol", 16)
        font_gest  = pygame.font.SysFont("segoeuisymbol", 18)
    except Exception:
        font_title = pygame.font.Font(None, 52)
        font_sub   = pygame.font.Font(None, 22)
        font_card  = pygame.font.Font(None, 26)
        font_desc  = pygame.font.Font(None, 17)
        font_hint  = pygame.font.Font(None, 16)
        font_gest  = pygame.font.Font(None, 18)

    WHITE      = (255, 255, 255)
    BLACK      = (0,   0,   0)
    GOLD       = (255, 215, 0)
    CYAN       = (100, 200, 255)
    NEON_GREEN = (57,  255, 20)
    NEON_PINK  = (255, 16,  240)
    LIGHT_GRAY = (200, 200, 200)
    CUTE_PINK  = (255, 182, 193)
    CUTE_BLUE  = (173, 216, 230)
    DIM_GRAY   = (120, 120, 140)

    # ── background gesture thread with FIXED camera handling ───────────
    _gq           = _queue.Queue()
    _g_running    = [True]
    _last_gesture = [""]
    _gesture_window_created = [False]

    def _gesture_thread():
        if not _GESTURE_OK:
            return
        try:
            # Initialize MediaPipe Hands
            mp_hands  = mp.solutions.hands
            hands_sol = mp_hands.Hands(
                static_image_mode=False, 
                max_num_hands=1,
                min_detection_confidence=0.65, 
                min_tracking_confidence=0.65)

            print("[LAUNCHER] Getting camera instance...")
            picam2 = get_camera()  # Get the global shared camera
            print("[LAUNCHER] Camera ready")

            swipe_start      = None
            swipe_start_time = 0.0
            pose_name        = None
            pose_start_time  = 0.0
            last_fire_time   = 0.0
            COOLDOWN         = 0.6   # seconds between any two gestures
            POSE_HOLD        = 0.5   # seconds to hold fist / thumbs-up to launch
            SWIPE_THRESHOLD  = 0.22  # Normalized distance for swipe

            def count_fingers(lm):
                f = 0
                # Thumb (check if thumb tip is to the left of thumb IP for right hand)
                if lm[4].x < lm[3].x:
                    f += 1
                # Other fingers
                for tip, pip in zip([8,12,16,20],[6,10,14,18]):
                    if lm[tip].y < lm[pip].y:
                        f += 1
                return f

            def is_thumbs_up(lm):
                # Thumb tip above wrist
                if lm[4].y > lm[0].y - 0.08:
                    return False
                # Other fingers should be down
                for tip, mcp in zip([8,12,16,20],[5,9,13,17]):
                    if lm[tip].y < lm[mcp].y:
                        return False
                return True

            # Create OpenCV window once
            cv2.namedWindow('Gesture Control', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Gesture Control', 640, 480)
            cv2.moveWindow('Gesture Control', 100, 100)
            _gesture_window_created[0] = True

            while _g_running[0]:
                # ── capture frame from Picamera2 ──
                frame_raw = picam2.capture_array()
                if frame_raw is None:
                    continue
                
                # Convert from BGRA to BGR
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                # Flip horizontally for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Process for hand detection
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands_sol.process(rgb)
                now = time.time()

                action = None

                if result.multi_hand_landmarks:
                    for hl in result.multi_hand_landmarks:
                        lm = hl.landmark
                        fingers = count_fingers(lm)
                        
                        # Draw landmarks for visual feedback
                        mp.solutions.drawing_utils.draw_landmarks(
                            frame, hl, mp_hands.HAND_CONNECTIONS)

                        # ── FIST held → LAUNCH ──────────────────────────────
                        if fingers == 0:
                            if pose_name != "fist":
                                pose_name = "fist"
                                pose_start_time = now
                                _last_gesture[0] = "✊ FIST"
                            elif now - pose_start_time >= POSE_HOLD:
                                action = "launch"
                                pose_name = None
                                _last_gesture[0] = "✊ LAUNCHING!"
                        # ── THUMBS-UP held → LAUNCH ─────────────────────────
                        elif is_thumbs_up(lm):
                            if pose_name != "thumb":
                                pose_name = "thumb"
                                pose_start_time = now
                                _last_gesture[0] = "👍 THUMBS UP"
                            elif now - pose_start_time >= POSE_HOLD:
                                action = "launch"
                                pose_name = None
                                _last_gesture[0] = "👍 LAUNCHING!"
                        # ── SWIPE LEFT / RIGHT (using index finger tip) ──────
                        else:
                            pose_name = None
                            tip = lm[8]  # Index finger tip
                            hp = (tip.x, tip.y)
                            
                            if swipe_start is None:
                                swipe_start = hp
                                swipe_start_time = now
                            else:
                                dx = hp[0] - swipe_start[0]
                                dy = hp[1] - swipe_start[1]
                                dist = math.sqrt(dx*dx + dy*dy)
                                elapsed = now - swipe_start_time
                                
                                # Swipe detection: fast horizontal movement
                                if dist > SWIPE_THRESHOLD and elapsed < 0.8 and abs(dx) > abs(dy) * 1.5:
                                    if dx > 0:
                                        action = "right"
                                        _last_gesture[0] = "👉 SWIPE RIGHT"
                                    else:
                                        action = "left"
                                        _last_gesture[0] = "👈 SWIPE LEFT"
                                    swipe_start = hp
                                    swipe_start_time = now
                                elif elapsed > 1.2:
                                    swipe_start = hp
                                    swipe_start_time = now

                        if action and now - last_fire_time > COOLDOWN:
                            _gq.put(action)
                            last_fire_time = now
                else:
                    swipe_start = None
                    pose_name = None
                    if _last_gesture[0]:
                        _last_gesture[0] = ""

                # ── Draw UI on camera feed ─────────────────────────────────────────
                cv2.putText(frame, "GAME LAUNCHER | SWIPE = Select | FIST/THUMB = Launch",
                            (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 100), 1)
                
                # Show current gesture
                if _last_gesture[0]:
                    # Background for text
                    text_size = cv2.getTextSize(_last_gesture[0], cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)[0]
                    cv2.rectangle(frame, 
                                 (frame.shape[1]//2 - text_size[0]//2 - 10, frame.shape[0]//2 - 30),
                                 (frame.shape[1]//2 + text_size[0]//2 + 10, frame.shape[0]//2 + 30),
                                 (0, 0, 0), -1)
                    cv2.putText(frame, _last_gesture[0],
                                (frame.shape[1]//2 - text_size[0]//2, frame.shape[0]//2 + 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 200), 3)
                
                # Show finger count
                if result.multi_hand_landmarks:
                    cv2.putText(frame, f"Fingers: {fingers}", (10, frame.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
                
                # Show the frame
                cv2.imshow("Gesture Control", frame)
                cv2.waitKey(1)

            # Cleanup
            hands_sol.close()
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            print("[LAUNCHER] Gesture thread stopped")
            
        except Exception as e:
            print(f"[LAUNCHER GESTURE ERROR] {e}")
            import traceback
            traceback.print_exc()

    # Start gesture thread
    _gthread = threading.Thread(target=_gesture_thread, daemon=False)
    _gthread.start()
    
    # Wait for camera to initialize
    time.sleep(2)

    # ── UI data ──────────────────────────────────────────────────────────────
    class Star:
        def __init__(self):
            self.x     = random.randint(0, LAUNCH_W)
            self.y     = random.randint(0, LAUNCH_H)
            self.sz    = random.uniform(0.5, 2.0)
            self.phase = random.uniform(0, 6.28)

    class Spark:
        def __init__(self):
            self.reset()
        def reset(self):
            self.x     = random.randint(0, LAUNCH_W)
            self.y     = random.randint(0, LAUNCH_H)
            self.vx    = random.uniform(-0.6, 0.6)
            self.vy    = random.uniform(-1.2, -0.3)
            self.color = random.choice([GOLD, CYAN, NEON_GREEN, NEON_PINK, CUTE_PINK, CUTE_BLUE])
            self.life  = random.randint(40, 100)
            self.max_l = self.life
        def update(self):
            self.x   += self.vx
            self.y   += self.vy
            self.life -= 1
        def draw(self, surf):
            if self.life > 0:
                s = max(1, int(5 * self.life / self.max_l))
                pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), s)

    stars  = [Star()  for _ in range(100)]
    sparks = [Spark() for _ in range(60)]

    cards = [
        {
            "rect":   pygame.Rect(60,  170, 360, 290),
            "title":  "Find My Home",
            "lines":  ["Navigate maze levels home",
                       "10 hand-crafted levels",
                       "Minimap + gesture control",
                       "Swipe gestures to move"],
            "accent": CUTE_PINK,
            "index":  0,
        },
        {
            "rect":   pygame.Rect(480, 170, 360, 290),
            "title":  "Puzzle Escape",
            "lines":  ["Collect keys & flip switches",
                       "10 levels, beat the clock",
                       "Score time-bonus points",
                       "Swipe gestures to play"],
            "accent": CYAN,
            "index":  1,
        },
    ]

    selected     = 0
    t            = 0.0
    launching    = False
    launch_idx   = 0
    launch_timer = 0
    _gest_flash  = 0

    while True:
        t += 0.04

        # ── pygame events ───────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _g_running[0] = False
                pygame.quit()
                sys.exit()

        # ── consume gesture queue ────────────────────────────────────────────
        while not _gq.empty():
            g = _gq.get()
            _gest_flash = 90
            if not launching:
                if g == "left":
                    selected = 0
                    _last_gesture[0] = "SELECTED: Find My Home"
                elif g == "right":
                    selected = 1
                    _last_gesture[0] = "SELECTED: Puzzle Escape"
                elif g == "launch":
                    launching = True
                    launch_idx = selected
                    launch_timer = 90

        if _gest_flash > 0:
            _gest_flash -= 1

        # ── launch countdown ─────────────────────────────────────────────────
        if launching:
            launch_timer -= 1
            if launch_timer <= 0:
                _g_running[0] = False
                # Small delay to allow thread to cleanup
                cv2.destroyAllWindows()
                _gthread.join(timeout=3)
                time.sleep(2)
                return launch_idx

        # ── update sparks ─────────────────────────────────────────────────────
        for sp in sparks:
            sp.update()
            if sp.life <= 0:
                sp.reset()

        # ── draw background ───────────────────────────────────────────────────
        for y in range(LAUNCH_H):
            r2 = int(8  + 20  * y / LAUNCH_H)
            g2 = int(8  + 12  * y / LAUNCH_H)
            b2 = int(22 + 40  * y / LAUNCH_H)
            pygame.draw.line(screen, (r2, g2, b2), (0, y), (LAUNCH_W, y))

        for st in stars:
            br = int(120 + 80 * math.sin(t * 0.8 + st.phase))
            pygame.draw.circle(screen, (br, br, br), (int(st.x), int(st.y)), max(1, int(st.sz)))

        for sp in sparks:
            sp.draw(screen)

        # ── title ─────────────────────────────────────────────────────────────
        ts = font_title.render("GAME MODE", True, WHITE)
        for gi in range(3):
            gs = font_title.render("GAME MODE", True, NEON_PINK)
            screen.blit(gs, (LAUNCH_W//2 - ts.get_width()//2 - gi, 28 - gi))
        screen.blit(ts, (LAUNCH_W//2 - ts.get_width()//2, 28))
        sub = font_sub.render("Choose a game to play", True, GOLD)
        screen.blit(sub, (LAUNCH_W//2 - sub.get_width()//2, 92))

        # ── cards ─────────────────────────────────────────────────────────────
        for i, card in enumerate(cards):
            rect   = card["rect"]
            accent = card["accent"]
            is_sel = (i == selected)

            if is_sel:
                for gi in range(5, 0, -1):
                    gr = rect.inflate(gi * 6, gi * 6)
                    gs = pygame.Surface((gr.width, gr.height), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*accent, max(0, 60 - gi * 10)),
                                     gs.get_rect(), border_radius=18)
                    screen.blit(gs, gr.topleft)

            cs = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            for row in range(rect.height):
                ratio = row / rect.height
                pygame.draw.line(cs,
                    (int(25+20*ratio), int(20+15*ratio), int(45+30*ratio), 230),
                    (0, row), (rect.width, row))
            screen.blit(cs, rect.topleft)

            bc = accent if is_sel else tuple(c // 2 for c in accent)
            pygame.draw.rect(screen, bc, rect, 3 if is_sel else 1, border_radius=16)

            bob = int(math.sin(t * 3) * 5) if is_sel else 0

            ct = font_card.render(card["title"], True, WHITE)
            screen.blit(ct, (rect.x + 20, rect.y + 18 + bob))
            pygame.draw.line(screen, accent,
                             (rect.x + 20,  rect.y + 52 + bob),
                             (rect.x + 20 + ct.get_width(), rect.y + 52 + bob), 2)

            for j, line in enumerate(card["lines"]):
                col = accent if is_sel else LIGHT_GRAY
                ls  = font_desc.render(f"  •  {line}", True, col)
                screen.blit(ls, (rect.x + 18, rect.y + 68 + j * 26 + bob))

            # badge: show gesture hint
            if is_sel:
                badge_txt = "SELECTED  ▶  Hold  ✊  or  👍  to launch"
                badge = font_hint.render(badge_txt, True, BLACK)
                bw = badge.get_width() + 20
                bh = badge.get_height() + 10
                bx = rect.x + rect.width  // 2 - bw // 2
                by = rect.y + rect.height - bh - 10 + bob
                pygame.draw.rect(screen, accent, (bx, by, bw, bh), border_radius=8)
                screen.blit(badge, (bx + 10, by + 5))

        # ── gesture guide bar at the bottom ───────────────────────────────────
        bar_y = LAUNCH_H - 52
        bar_surf = pygame.Surface((LAUNCH_W, 52), pygame.SRCALPHA)
        bar_surf.fill((0, 0, 0, 140))
        screen.blit(bar_surf, (0, bar_y))

        guide_items = [
            ("👈 Swipe Left",  CUTE_PINK,  "Select Find My Home"),
            ("👉 Swipe Right", CYAN,        "Select Puzzle Escape"),
            ("✊ Fist  /  👍 Thumbs Up", NEON_GREEN, "Hold to Launch"),
        ]
        col_w = LAUNCH_W // len(guide_items)
        for idx, (sym, col, desc) in enumerate(guide_items):
            cx = col_w * idx + col_w // 2
            sym_s  = font_gest.render(sym,  True, col)
            desc_s = font_hint.render(desc, True, DIM_GRAY)
            screen.blit(sym_s,  (cx - sym_s.get_width()  // 2, bar_y + 6))
            screen.blit(desc_s, (cx - desc_s.get_width() // 2, bar_y + 30))

        # ── live gesture feedback flash ───────────────────────────────────────
        if _gest_flash > 0 and _last_gesture[0]:
            alpha = min(255, _gest_flash * 5)
            fade  = _gest_flash / 90
            fg_col = tuple(int(c * fade) for c in NEON_GREEN)
            gf = font_sub.render(f"Detected:  {_last_gesture[0]}", True, fg_col)
            screen.blit(gf, (LAUNCH_W//2 - gf.get_width()//2, bar_y - 30))

        # ── launch fade overlay ───────────────────────────────────────────────
        if launching:
            progress = 1 - launch_timer / 90
            ov = pygame.Surface((LAUNCH_W, LAUNCH_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, int(220 * progress)))
            screen.blit(ov, (0, 0))
            if progress > 0.35:
                lname = cards[launch_idx]["title"]
                lt = font_title.render(f"Loading  {lname} ...", True, NEON_GREEN)
                screen.blit(lt, (LAUNCH_W//2 - lt.get_width()//2,
                                 LAUNCH_H//2 - lt.get_height()//2))
            if launch_timer <= 0:
                _g_running[0] = False
                cv2.destroyAllWindows()
                _gthread.join(timeout=3)  # Wait for thread to exit
                time.sleep(2)
                return launch_idx
        pygame.display.flip()
        clock.tick(60)


# =============================================================================
#  FIND MY HOME  –  with FIXED camera handling
# =============================================================================
def run_find_my_home():
    import time
    import threading
    import queue
    import cv2
    import mediapipe as mp
    from picamera2 import Picamera2

    GESTURE_AVAILABLE = True

    SCREEN_W, SCREEN_H = 1100, 750
    TILE = 64
    FPS  = 60
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("✦ Find My Home ✦")
    clock = pygame.time.Clock()

    # Colors (same as before, keep them)
    C_BG_TOP      = (10, 8, 30)
    C_BG_BOT      = (30, 15, 60)
    C_GRASS       = (30, 180, 90)
    C_GRASS_DARK  = (20, 140, 65)
    C_PATH        = (220, 185, 110)
    C_PATH_EDGE   = (180, 140, 70)
    C_WATER       = (40, 160, 230)
    C_WATER_GLOW  = (80, 200, 255)
    C_TREE_TRUNK  = (100, 60, 20)
    C_TREE_CROWN  = (50, 200, 80)
    C_TREE_HIGH   = (120, 255, 100)
    C_ROCK        = (140, 130, 150)
    C_ROCK_DARK   = (90, 85, 100)
    C_HOME_WALL   = (255, 90, 80)
    C_HOME_ROOF   = (200, 40, 40)
    C_HOME_DOOR   = (120, 40, 30)
    C_HOME_WIN    = (255, 240, 120)
    C_HOME_GLOW   = (255, 150, 50)
    C_PLAYER_BODY = (255, 200, 60)
    C_PLAYER_FACE = (255, 225, 140)
    C_PLAYER_GLOW = (255, 240, 100)
    C_UI_BG       = (12, 8, 35, 210)
    C_UI_PANEL    = (20, 14, 55, 230)
    C_UI_BORDER   = (120, 80, 255)
    C_UI_ACCENT   = (80, 230, 255)
    C_UI_GOLD     = (255, 210, 50)
    C_UI_GREEN    = (80, 255, 150)
    C_UI_PINK     = (255, 80, 180)
    C_UI_TEXT     = (220, 215, 255)
    C_UI_MUTED    = (140, 130, 180)
    C_WIN_BG      = (15, 10, 45, 245)
    C_G_LEFT      = (255, 80, 100)
    C_G_RIGHT     = (80, 200, 255)
    C_G_UP        = (100, 255, 150)
    C_G_DOWN      = (255, 200, 50)
    C_G_RESTART   = (200, 100, 255)
    C_G_NONE      = (80, 75, 120)

    LEVELS = [
        [[1,1,1,1,1,1,1,1,1,1],[1,3,7,7,0,0,0,0,2,1],[1,0,1,7,1,0,1,0,0,1],[1,0,1,7,7,7,1,0,0,1],[1,0,5,1,1,1,1,4,4,1],[1,0,0,0,0,0,1,4,4,1],[1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,0,0,0,2,1],[1,0,0,7,1,4,4,1,1,0,0,1],[1,1,0,7,7,7,7,7,1,0,1,1],[1,5,0,1,1,5,1,7,1,0,0,1],[1,0,0,0,0,0,0,7,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,1,4,4,4,1,0,0,0,2,1],[1,0,7,1,4,4,4,1,1,1,0,0,1],[1,0,7,7,7,7,7,7,7,1,0,1,1],[1,1,1,1,5,1,5,1,7,0,0,0,1],[1,0,0,0,0,0,0,0,7,1,1,0,1],[1,5,1,1,1,1,1,1,7,7,7,7,1],[1,0,0,0,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,1,0,0,0,2,1],[1,0,0,7,1,4,4,4,1,1,1,0,0,1],[1,1,0,7,1,4,4,4,0,0,1,1,0,1],[1,5,0,7,7,7,7,7,7,0,0,7,0,1],[1,1,1,1,1,5,1,1,7,1,0,7,1,1],[1,0,0,0,0,0,0,0,7,1,0,7,0,1],[1,0,1,1,1,1,1,1,7,7,7,7,0,1],[1,0,0,0,5,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,4,1,0,0,0,2,1],[1,0,0,7,1,4,4,4,4,1,1,1,0,0,1],[1,1,0,7,1,4,4,4,4,0,0,1,1,0,1],[1,5,0,7,7,7,7,7,7,7,0,0,7,0,1],[1,1,1,1,1,5,1,1,1,7,1,0,7,1,1],[1,0,0,0,0,0,0,0,0,7,1,0,7,0,1],[1,0,1,1,5,1,1,1,1,7,7,7,7,0,1],[1,0,0,0,0,0,0,0,0,1,1,1,1,0,1],[1,1,1,5,1,1,1,1,0,0,0,0,0,0,1],[1,0,0,0,0,0,0,1,1,1,1,1,1,1,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,1,0,0,0,0,0,0,0,2,1],[1,0,7,1,1,1,1,1,1,1,0,0,1],[1,0,7,7,7,7,7,1,4,1,0,1,1],[1,0,1,5,1,0,7,1,4,1,0,0,1],[1,0,1,0,1,0,7,7,7,1,1,0,1],[1,0,0,0,1,0,1,5,1,0,0,0,1],[1,1,1,1,1,0,0,0,1,1,1,1,1],[1,5,0,0,0,0,1,0,0,0,5,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,0,4,4,4,0,4,4,4,0,0,2,1],[1,0,0,4,0,4,0,4,0,4,7,0,0,1],[1,1,0,7,0,7,0,7,0,7,1,1,0,1],[1,5,0,4,0,4,0,4,0,4,0,5,0,1],[1,0,7,4,4,4,0,4,4,4,0,0,0,1],[1,0,7,7,7,7,7,7,7,7,7,1,0,1],[1,0,1,5,1,1,1,5,1,1,7,1,0,1],[1,0,0,0,0,0,0,0,0,0,7,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,7,7,7,7,7,7,7,7,2,1,1],[1,0,1,1,1,1,1,1,1,1,1,7,0,1,1],[1,0,1,5,5,5,5,5,5,5,1,7,0,1,1],[1,0,1,5,1,1,1,1,1,5,1,7,0,1,1],[1,0,1,5,1,4,4,4,1,5,1,7,0,1,1],[1,0,1,5,1,4,4,4,1,5,1,7,0,1,1],[1,0,1,5,1,1,1,1,1,5,1,7,0,1,1],[1,0,1,5,5,5,5,5,5,5,1,7,0,1,1],[1,0,1,1,1,1,1,1,1,1,1,7,0,1,1],[1,0,7,7,7,7,7,7,7,7,7,7,0,1,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,1,0,0,0,0,2,1],[1,0,1,7,1,4,4,4,1,1,1,1,0,0,1],[1,0,1,7,7,7,7,7,7,7,7,1,0,1,1],[1,0,1,1,1,5,1,7,1,5,7,1,0,0,1],[1,0,0,0,0,0,0,7,0,0,7,0,0,0,1],[1,1,1,5,1,1,1,7,1,1,7,1,5,1,1],[1,0,0,0,0,0,0,7,0,0,7,0,0,0,1],[1,0,1,1,1,1,1,7,7,7,7,1,1,0,1],[1,0,0,0,5,0,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,7,1,4,4,4,4,1,0,0,0,2,1],[1,0,1,1,7,1,4,4,4,4,1,1,1,0,0,1],[1,0,1,5,7,1,4,4,4,4,0,5,1,0,1,1],[1,0,1,0,7,7,7,7,7,7,7,0,1,0,0,1],[1,0,1,0,1,5,1,7,1,5,1,0,1,1,0,1],[1,0,1,0,0,0,0,7,0,0,1,0,0,0,0,1],[1,0,1,1,1,1,1,7,1,1,1,1,5,1,0,1],[1,0,0,0,5,0,0,7,0,0,0,0,0,1,0,1],[1,1,5,1,1,1,1,7,7,7,7,7,7,7,0,1],[1,0,0,0,0,0,0,1,1,1,1,1,1,7,0,1],[1,0,1,1,1,1,0,0,0,5,0,0,0,7,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
    ]

    LEVEL_NAMES = [
        "The First Step","Watery Paths","Rocky Road","The Maze","Grand Finale",
        "Zigzag Trail","Island Hopping","The Spiral","Crossroads","Grand Labyrinth"
    ]
    LEVEL_COLORS = [
        C_UI_GREEN, C_UI_ACCENT, C_UI_GOLD, C_UI_PINK, (255,140,80),
        (100,255,220), (255,180,80), (180,100,255), (80,220,180), (255,80,80)
    ]

    # Particle class (same as before)
    class Particle:
        def __init__(self, x, y, color, vx=None, vy=None, life=None, size=None):
            self.x = x; self.y = y; self.color = color
            self.vx   = vx   if vx   is not None else random.uniform(-2, 2)
            self.vy   = vy   if vy   is not None else random.uniform(-3, -0.5)
            self.life = life if life is not None else random.uniform(0.4, 1.2)
            self.max_life = self.life
            self.size = size if size is not None else random.uniform(3, 8)
        def update(self, dt):
            self.x += self.vx; self.y += self.vy; self.vy += 0.08; self.life -= dt
            return self.life > 0
        def draw(self, surf):
            alpha = max(0, self.life / self.max_life)
            s = max(1, int(self.size * alpha))
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), s)

    particles = []

    def emit_particles(x, y, color, count=12):
        for _ in range(count):
            particles.append(Particle(x, y, color))

    stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H),
              random.uniform(0.5, 2.5), random.random()*6.28) for _ in range(120)]

    def draw_stars(t):
        for sx, sy, sz, phase in stars:
            brightness = int(160 + 80 * math.sin(t * 1.5 + phase))
            col = (brightness, brightness, int(brightness * 0.85))
            pygame.draw.circle(screen, col, (sx, sy), max(1, int(sz * 0.6)))

    gesture_queue   = queue.Queue()
    gesture_running = [True]
    last_gesture          = [""]
    last_gesture_time     = [0.0]
    current_detected_gesture = [""]

    class GestureDetector:
        def __init__(self):
            if not GESTURE_AVAILABLE:
                self.available = False
                return
            try:
                self.mp_hands = mp.solutions.hands
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False, max_num_hands=1,
                    min_detection_confidence=0.6, min_tracking_confidence=0.6)
                self.mp_draw = mp.solutions.drawing_utils
                self.picam2 = None
                self.prev_pos = None
                self.swipe_start = None
                self.swipe_start_time = 0.0
                self.swipe_cooldown = 0.8
                self.last_action_time = 0.0
                self.trail = []
                self._pose_start_gesture = None
                self._pose_start_time = 0.0
                self.available = True
            except Exception as e:
                print(f"[GESTURE] Init failed: {e}")
                self.available = False

        def start(self):
            if not self.available:
                return False
            try:
                from picamera2 import Picamera2
                print("[GAME] Waiting for camera to be available...")
                time.sleep(3)
                print("[GAME] Getting camera instance...")
                self.picam2 = get_camera()  # Get shared camera
                print("[GAME] Camera ready")
                print("[GAME] Camera started successfully")
                
                # Create OpenCV window
                cv2.namedWindow('Gesture Control - Find My Home', cv2.WINDOW_NORMAL)
                cv2.resizeWindow('Gesture Control - Find My Home', 640, 480)
                cv2.moveWindow('Gesture Control - Find My Home', 100, 100)
                
                thr = threading.Thread(target=self._loop, daemon=True)
                thr.start()
                print("[GESTURE] Camera started")
                return True
            except Exception as e:
                print(f"[GESTURE] Camera error: {e}")
                return False

        def _loop(self):
            while gesture_running[0] and self.picam2:
                frame_raw = self.picam2.capture_array()
                if frame_raw is None:
                    continue
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb)
                now = time.time()
                
                if results.multi_hand_landmarks:
                    for hl in results.multi_hand_landmarks:
                        tip = hl.landmark[8]
                        hand_pos = (tip.x, tip.y)
                        px_x = int(tip.x * w)
                        px_y = int(tip.y * h)
                        fingers = self._count_fingers(hl.landmark)
                        
                        # Draw trail
                        self.trail.append((px_x, px_y, now))
                        self.trail = [(x,y,t) for x,y,t in self.trail if now-t < 0.5]
                        for i in range(1, len(self.trail)):
                            age = now - self.trail[i][2]
                            alpha = max(0, 1 - age * 2)
                            c = int(255 * alpha)
                            cv2.line(frame,
                                     (self.trail[i-1][0], self.trail[i-1][1]),
                                     (self.trail[i][0],   self.trail[i][1]),
                                     (c, c, 0), 3)
                        
                        self.mp_draw.draw_landmarks(frame, hl, self.mp_hands.HAND_CONNECTIONS)
                        action = None
                        
                        # Gesture detection
                        if fingers == 0:  # Fist
                            if self._pose_start_gesture != "fist":
                                self._pose_start_gesture = "fist"
                                self._pose_start_time = now
                            elif now - self._pose_start_time >= 0.3:
                                action = "up"
                                self._pose_start_gesture = None
                        elif fingers >= 5:  # Open palm
                            if self._pose_start_gesture != "palm":
                                self._pose_start_gesture = "palm"
                                self._pose_start_time = now
                            elif now - self._pose_start_time >= 0.3:
                                action = "down"
                                self._pose_start_gesture = None
                        elif fingers == 2:  # Peace sign
                            if self._pose_start_gesture != "peace":
                                self._pose_start_gesture = "peace"
                                self._pose_start_time = now
                            elif now - self._pose_start_time >= 0.4:
                                action = "restart"
                                self._pose_start_gesture = None
                        elif self._is_thumbs_up(hl.landmark):
                            if self._pose_start_gesture != "thumbs_up":
                                self._pose_start_gesture = "thumbs_up"
                                self._pose_start_time = now
                            elif now - self._pose_start_time >= 0.5:
                                action = "next"
                                self._pose_start_gesture = None
                        else:
                            self._pose_start_gesture = None
                            # Swipe detection
                            if self.swipe_start is None:
                                self.swipe_start = hand_pos
                                self.swipe_start_time = now
                            else:
                                dx = hand_pos[0] - self.swipe_start[0]
                                dy = hand_pos[1] - self.swipe_start[1]
                                dist = math.sqrt(dx*dx + dy*dy)
                                elapsed = now - self.swipe_start_time
                                if dist > 0.22 and elapsed < 0.8 and abs(dx) > abs(dy) * 1.5:
                                    action = "right" if dx > 0 else "left"
                                    self.swipe_start = hand_pos
                                    self.swipe_start_time = now
                                elif elapsed > 1.2:
                                    self.swipe_start = hand_pos
                                    self.swipe_start_time = now
                        
                        if action and now - self.last_action_time > self.swipe_cooldown:
                            gesture_queue.put(action)
                            last_gesture[0] = action
                            last_gesture_time[0] = now
                            self.last_action_time = now
                            current_detected_gesture[0] = action
                            print(f"[GESTURE] Action: {action}")
                        elif action:
                            current_detected_gesture[0] = action
                else:
                    self.swipe_start = None
                    self._pose_start_gesture = None
                    self.trail = []
                    current_detected_gesture[0] = ""
                
                # Draw UI on camera feed
                cv2.putText(frame,
                    "SWIPE L/R | FIST=UP | PALM=DOWN | THUMB=NEXT | PEACE=RESTART",
                    (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 100), 1)
                
                if results.multi_hand_landmarks:
                    for hl in results.multi_hand_landmarks:
                        fc = self._count_fingers(hl.landmark)
                        is_thumb = self._is_thumbs_up(hl.landmark)
                        label = f"Fingers: {fc}"
                        if fc == 0:
                            label += "  >> FIST (UP)"
                        elif is_thumb:
                            label += "  >> THUMBS UP (NEXT)"
                        elif fc == 2:
                            label += "  >> PEACE (RESTART)"
                        elif fc >= 5:
                            label += "  >> PALM (DOWN)"
                        cv2.putText(frame, label, (10, frame.shape[0]-15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 200), 2)
                
                if current_detected_gesture[0]:
                    cv2.putText(frame, f">> {current_detected_gesture[0].upper()} <<",
                                (frame.shape[1]//2-80, frame.shape[0]//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 200), 3)
                
                cv2.imshow("Gesture Control - Find My Home", frame)
                cv2.waitKey(1)
            
            cv2.destroyAllWindows()

        def _count_fingers(self, landmarks):
            fingers = 0
            if landmarks[4].x < landmarks[3].x:
                fingers += 1
            for tip, pip in zip([8,12,16,20], [6,10,14,18]):
                if landmarks[tip].y < landmarks[pip].y:
                    fingers += 1
            return fingers

        def _is_thumbs_up(self, landmarks):
            wrist_y = landmarks[0].y
            thumb_tip_y = landmarks[4].y
            if thumb_tip_y > wrist_y - 0.08:
                return False
            for tip_idx, mcp_idx in zip([8,12,16,20], [5,9,13,17]):
                if landmarks[tip_idx].y < landmarks[mcp_idx].y:
                    return False
            return True

        def stop(self):
            gesture_running[0] = False
            try:
                cv2.destroyAllWindows()
            except:
                pass

    class Player:
        def __init__(self, x, y, level_map):
            self.x = x
            self.y = y
            self.tx = x
            self.ty = y
            self.moving = False
            self.level_map = level_map
            self.facing = 1
            self.step = 0.0
            self.trail_positions = []
        def move(self, dx, dy):
            gx = int((self.x + dx * TILE) // TILE)
            gy = int((self.y + dy * TILE) // TILE)
            if self.level_map[gy][gx] not in [1, 4, 5]:
                self.trail_positions.append((self.x + TILE//2, self.y + TILE//2))
                if len(self.trail_positions) > 20:
                    self.trail_positions.pop(0)
                self.tx += dx * TILE
                self.ty += dy * TILE
                self.moving = True
                if dx != 0:
                    self.facing = dx
                return self.level_map[gy][gx] == 2
            return False
        def update(self, dt):
            if self.moving:
                self.step += dt * 8
                self.x += (self.tx - self.x) * 0.22
                self.y += (self.ty - self.y) * 0.22
                if abs(self.x - self.tx) < 1 and abs(self.y - self.ty) < 1:
                    self.x, self.y = self.tx, self.ty
                    self.moving = False
        def draw(self, ox, oy):
            t = pygame.time.get_ticks() / 1000
            bob = math.sin(t * 3.5) * 4 if not self.moving else math.sin(self.step * 4) * 5
            cx = int(self.x + TILE//2 + ox)
            cy = int(self.y + TILE//2 + oy + bob)
            for i, (px, py) in enumerate(self.trail_positions[-8:]):
                alpha_f = (i + 1) / 8
                s = max(2, int(8 * alpha_f))
                trail_col = (int(C_PLAYER_GLOW[0]*alpha_f), int(C_PLAYER_GLOW[1]*alpha_f*0.5), int(50*alpha_f))
                pygame.draw.circle(screen, trail_col, (int(px + ox), int(py + oy)), s)
            glow_r = int(28 + 4 * math.sin(t * 4))
            for g in range(3, 0, -1):
                pygame.draw.circle(screen, C_PLAYER_GLOW, (cx, cy), glow_r + g * 4)
            pygame.draw.ellipse(screen, (0,0,0), (cx-18, cy+18, 36, 10))
            pygame.draw.circle(screen, C_PLAYER_BODY, (cx, cy), 22)
            pygame.draw.circle(screen, C_PLAYER_FACE, (cx, cy - 2), 15)
            ex = 5 * self.facing
            pygame.draw.circle(screen, (40,30,80), (cx+ex-3, cy-5), 4)
            pygame.draw.circle(screen, (40,30,80), (cx+ex+5, cy-5), 4)
            pygame.draw.circle(screen, (255,255,255), (cx+ex-2, cy-6), 1)
            pygame.draw.circle(screen, (255,255,255), (cx+ex+6, cy-6), 1)
            pygame.draw.arc(screen, (100,60,30), (cx-7, cy, 14, 9), 3.14, 6.28, 2)
            pack_x = cx - self.facing * 20
            pygame.draw.rect(screen, (180,100,40), (pack_x-6, cy-8, 12, 18), border_radius=3)
            pygame.draw.rect(screen, (220,140,60), (pack_x-4, cy-6, 8,  6),  border_radius=2)

    class FancyButton:
        def __init__(self, x, y, w, h, text, color=None, font_size=30):
            self.rect = pygame.Rect(x, y, w, h)
            self.text = text
            self.font = pygame.font.Font(None, font_size)
            self.color = color or C_UI_BORDER
            self.hovered = False
        def check_hover(self, pos):
            self.hovered = self.rect.collidepoint(pos)
        def is_clicked(self, pos):
            return self.rect.collidepoint(pos)
        def draw(self, surf):
            col = tuple(min(255, c + 40) for c in self.color) if self.hovered else self.color
            pygame.draw.rect(surf, col, self.rect, border_radius=10)
            pygame.draw.rect(surf, (255,255,255), self.rect, 2, border_radius=10)
            txt = self.font.render(self.text, True, (255,255,255))
            surf.blit(txt, txt.get_rect(center=self.rect.center))

    def draw_tile(t, tx, ty, ox, oy):
        px = ox + tx * TILE
        py = oy + ty * TILE
        r  = pygame.Rect(px, py, TILE, TILE)
        time_val = pygame.time.get_ticks() / 1000
        if t == 0:
            pygame.draw.rect(screen, C_GRASS, r)
            for _ in range(2):
                gx = px + random.randint(4, TILE-4)
                gy = py + random.randint(4, TILE-4)
                pygame.draw.circle(screen, C_GRASS_DARK, (gx, gy), 2)
        elif t == 7:
            pygame.draw.rect(screen, C_PATH, r)
            pygame.draw.rect(screen, C_PATH_EDGE, r, 2)
            for i in range(2):
                pygame.draw.ellipse(screen, C_PATH_EDGE, (px+15+i*30, py+30, 8, 5))
        elif t == 1:
            pygame.draw.rect(screen, C_GRASS_DARK, r)
            pygame.draw.rect(screen, C_TREE_TRUNK, (px+28, py+40, 8, 20), border_radius=3)
            pygame.draw.circle(screen, C_TREE_CROWN, (px+32, py+28), 22)
            pygame.draw.circle(screen, C_TREE_HIGH,  (px+32, py+22), 14)
            sp = math.sin(time_val * 2 + tx * 0.5 + ty * 0.7)
            if sp > 0.8:
                pygame.draw.circle(screen, (200,255,180), (px+32, py+15), 3)
        elif t == 4:
            wave = int(math.sin(time_val * 2 + tx * 0.8) * 3)
            pygame.draw.rect(screen, C_WATER, r)
            for wi in range(3):
                wy = py + 10 + wi * 18 + wave
                if py <= wy <= py + TILE:
                    pygame.draw.line(screen, C_WATER_GLOW, (px+4, wy), (px+TILE-4, wy), 2)
            gd = int(abs(math.sin(time_val*3 + tx + ty)) * 5)
            pygame.draw.circle(screen, C_WATER_GLOW, (px+32, py+32), 4+gd)
        elif t == 5:
            pygame.draw.rect(screen, C_GRASS, r)
            pygame.draw.ellipse(screen, C_ROCK,      (px+12, py+22, 40, 28))
            pygame.draw.ellipse(screen, C_ROCK_DARK, (px+14, py+24, 36, 24))
            pygame.draw.ellipse(screen, (180,175,200), (px+18, py+26, 14, 8))
        elif t == 2:
            pygame.draw.rect(screen, C_GRASS, r)
            glow_size = int(4 + 2 * math.sin(time_val * 3))
            for g in range(3, 0, -1):
                ga_surf = pygame.Surface((TILE + g*8, TILE + g*8), pygame.SRCALPHA)
                pygame.draw.rect(ga_surf, (*C_HOME_GLOW, 20), ga_surf.get_rect(), border_radius=8)
                screen.blit(ga_surf, (px - g*4, py - g*4))
            pygame.draw.rect(screen, C_HOME_WALL, (px+10, py+26, 44, 34), border_radius=3)
            pygame.draw.polygon(screen, C_HOME_ROOF, [(px+32, py+6),(px+6, py+30),(px+58, py+30)])
            pygame.draw.line(screen, (240,80,80), (px+32, py+8), (px+10, py+29), 2)
            pygame.draw.rect(screen, C_HOME_DOOR, (px+26, py+40, 12, 20), border_radius=2)
            pygame.draw.circle(screen, C_UI_GOLD, (px+35, py+51), 2)
            for wx in [px+14, px+40]:
                pygame.draw.rect(screen, C_HOME_WIN, (wx, py+30, 8, 8))
                pygame.draw.line(screen, C_HOME_WALL, (wx+4, py+30), (wx+4, py+38), 1)
                pygame.draw.line(screen, C_HOME_WALL, (wx,   py+34), (wx+8, py+34), 1)
            pygame.draw.rect(screen, (160,50,50), (px+44, py+10, 7, 16), border_radius=2)
            smoke_y = py + 6 + int(math.sin(time_val * 2) * 3)
            pygame.draw.circle(screen, (200,200,210), (px+47, smoke_y),   4)
            pygame.draw.circle(screen, (220,220,230), (px+50, smoke_y-8), 3)
        elif t == 3:
            pygame.draw.rect(screen, C_GRASS, r)
            for i in range(4):
                angle = time_val * 2 + i * math.pi / 2
                sx = px + 32 + int(math.cos(angle) * 6)
                sy = py + 32 + int(math.sin(angle) * 6)
                pygame.draw.circle(screen, C_UI_GOLD, (sx, sy), 3)

    def draw_map(level_map):
        rows = len(level_map)
        cols = len(level_map[0])
        ox = (SCREEN_W - cols * TILE) // 2
        oy = (SCREEN_H - rows * TILE) // 2 + 10
        for y, row in enumerate(level_map):
            for x, t in enumerate(row):
                draw_tile(t, x, y, ox, oy)
        return ox, oy

    _bg_surf = [None]
    def draw_background():
        if _bg_surf[0] is None:
            _bg_surf[0] = pygame.Surface((SCREEN_W, SCREEN_H))
            for y in range(SCREEN_H):
                t2 = y / SCREEN_H
                col = (int(C_BG_TOP[0]*(1-t2)+C_BG_BOT[0]*t2),
                       int(C_BG_TOP[1]*(1-t2)+C_BG_BOT[1]*t2),
                       int(C_BG_TOP[2]*(1-t2)+C_BG_BOT[2]*t2))
                pygame.draw.line(_bg_surf[0], col, (0, y), (SCREEN_W, y))
        screen.blit(_bg_surf[0], (0, 0))

    def draw_top_hud(start_time, current_level, total_levels):
        elapsed = int(time.time() - start_time)
        t = pygame.time.get_ticks() / 1000
        hud = pygame.Surface((SCREEN_W, 68), pygame.SRCALPHA)
        hud.fill((8, 5, 25, 200))
        for x in range(SCREEN_W):
            shimmer = int(128 + 80 * math.sin(x * 0.02 + t * 2))
            pygame.draw.line(hud, (*C_UI_BORDER, shimmer), (x, 0), (x, 1))
        pygame.draw.line(hud, (*C_UI_BORDER, 160), (0, 67), (SCREEN_W, 67), 1)
        screen.blit(hud, (0, 0))
        font_l  = pygame.font.Font(None, 38)
        font_s  = pygame.font.Font(None, 22)
        font_xs = pygame.font.Font(None, 18)
        tx = 30
        screen.blit(font_xs.render("ELAPSED", True, C_UI_MUTED), (tx, 10))
        timer_str = f"{elapsed//60:02}:{elapsed%60:02}"
        pulse = 0.8 + 0.2 * math.sin(t * 2)
        tc = tuple(min(255, int(c * pulse)) for c in C_UI_ACCENT)
        screen.blit(font_l.render(timer_str, True, tc), (tx, 28))
        lx = 180
        lvl_col = LEVEL_COLORS[current_level % len(LEVEL_COLORS)]
        screen.blit(font_xs.render("LEVEL", True, C_UI_MUTED), (lx, 10))
        screen.blit(font_l.render(f"{current_level + 1}", True, lvl_col), (lx, 28))
        for i in range(total_levels):
            pip_col = LEVEL_COLORS[i] if i <= current_level else C_UI_MUTED
            pip_x = lx + 42 + i * 16
            pygame.draw.circle(screen, pip_col, (pip_x, 42), 5 if i == current_level else 3)
            if i == current_level:
                pygame.draw.circle(screen, pip_col, (pip_x, 42), 7, 1)
        nx = 340
        screen.blit(font_xs.render("MISSION", True, C_UI_MUTED), (nx, 10))
        screen.blit(font_s.render(LEVEL_NAMES[current_level % len(LEVEL_NAMES)], True, C_UI_GOLD), (nx, 30))
        screen.blit(font_xs.render("Find your way home!", True, (160,155,210)), (nx, 52))
        cx2 = SCREEN_W - 320
        screen.blit(font_xs.render("CONTROLS", True, C_UI_MUTED), (cx2, 10))
        controls_lines = ["Arrow Keys  |  R: Restart  |  ESC: Quit"]
        if GESTURE_AVAILABLE:
            controls_lines.append("Swipe L/R  |  Fist=UP  |  Palm=DN  |  ThumbUp=NEXT  |  Peace=Restart")
        for i, ln in enumerate(controls_lines):
            screen.blit(font_xs.render(ln, True, C_UI_TEXT), (cx2, 28 + i*18))
        if last_gesture[0] and time.time() - last_gesture_time[0] < 2.0:
            age = time.time() - last_gesture_time[0]
            fade = max(0, 1 - age / 2.0)
            g_col = {"left": C_G_LEFT, "right": C_G_RIGHT,
                     "up": C_G_UP, "down": C_G_DOWN,
                     "restart": C_G_RESTART}.get(last_gesture[0], C_UI_ACCENT)
            gsurf = font_s.render(f">> {last_gesture[0].upper()}", True,
                                  tuple(int(c*fade) for c in g_col))
            screen.blit(gsurf, (cx2, 52))

    def draw_minimap(player, level_map, ox_map, oy_map):
        scale = 9
        rows = len(level_map)
        cols = len(level_map[0])
        mm_w = cols * scale
        mm_h = rows * scale
        mm_x = SCREEN_W - mm_w - 18
        mm_y = 80
        panel = pygame.Surface((mm_w + 12, mm_h + 28), pygame.SRCALPHA)
        panel.fill((8, 5, 25, 210))
        pygame.draw.rect(panel, (*C_UI_BORDER, 180), panel.get_rect(), 2, border_radius=8)
        screen.blit(panel, (mm_x - 6, mm_y - 20))
        font = pygame.font.Font(None, 18)
        lbl = font.render("MAP", True, C_UI_MUTED)
        screen.blit(lbl, (mm_x + mm_w//2 - lbl.get_width()//2, mm_y - 16))
        tile_colors = {0: C_GRASS_DARK, 1: (30,90,30), 4: C_WATER,
                       7: C_PATH, 2: C_HOME_GLOW, 5: C_ROCK, 3: C_UI_GOLD}
        for y, row in enumerate(level_map):
            for x, t in enumerate(row):
                col = tile_colors.get(t, (60,60,60))
                pygame.draw.rect(screen, col, (mm_x + x*scale, mm_y + y*scale, scale-1, scale-1))
        t = pygame.time.get_ticks() / 1000
        pulse = int(3 + 2 * math.sin(t * 4))
        px = int(player.x // TILE) * scale
        py = int(player.y // TILE) * scale
        pygame.draw.circle(screen, C_PLAYER_GLOW,
                           (mm_x + px + scale//2, mm_y + py + scale//2), pulse + 2)
        pygame.draw.circle(screen, (255,255,255),
                           (mm_x + px + scale//2, mm_y + py + scale//2), 2)

    def draw_gesture_panel():
        if not GESTURE_AVAILABLE:
            return
        t = pygame.time.get_ticks() / 1000
        panel_w, panel_h = 600, 72
        panel_x = 16
        panel_y = SCREEN_H - panel_h - 12
        ps = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        ps.fill((8, 5, 28, 215))
        pygame.draw.rect(ps, (*C_UI_BORDER, 160), ps.get_rect(), 2, border_radius=10)
        screen.blit(ps, (panel_x, panel_y))
        font_s  = pygame.font.Font(None, 20)
        font_xs = pygame.font.Font(None, 16)
        title = font_s.render("GESTURE CONTROL", True, C_UI_GREEN)
        screen.blit(title, (panel_x + 10, panel_y + 8))
        arrows = [("L","SWIPE",C_G_LEFT,"left"),("R","SWIPE",C_G_RIGHT,"right"),
                  ("UP","FIST",C_G_UP,"up"),("DN","PALM",C_G_DOWN,"down"),
                  ("NEXT","THUMB UP",C_UI_GOLD,"next")]
        for i, (sym, method, col, name) in enumerate(arrows):
            ax = panel_x + 10 + i * 112
            ay = panel_y + 28
            is_active = (current_detected_gesture[0] == name and
                         time.time() - last_gesture_time[0] < 1.5)
            if is_active:
                glow = pygame.Surface((100, 34), pygame.SRCALPHA)
                glow.fill((*col, 60))
                screen.blit(glow, (ax-4, ay-2))
            color = col if is_active else tuple(int(c * 0.6) for c in col)
            screen.blit(pygame.font.Font(None, 30 if is_active else 24).render(sym, True, color), (ax, ay))
            screen.blit(pygame.font.Font(None, 16).render(method, True, color), (ax, ay+20))
        pc_col = C_G_RESTART if current_detected_gesture[0] == "restart" else C_UI_MUTED
        screen.blit(font_xs.render("PEACE = Restart", True, pc_col), (panel_x+565, panel_y+32))

    def draw_instruction_bar(self):
        config = self.level_config[self.current_level]
        bar_y = HEIGHT - 100
        bar_h = 100
        
        # Background bar
        pygame.draw.rect(screen, (18, 18, 30), (0, bar_y, WIDTH, bar_h))
        pygame.draw.line(screen, GOLD, (0, bar_y), (WIDTH, bar_y), 2)
        
        # Level instruction text
        obj_font = pygame.font.Font(None, 21)
        instruction = obj_font.render(config['instruction'], True, CUTE_YELLOW)
        screen.blit(instruction, (WIDTH//2 - instruction.get_width()//2, bar_y + 7))
        
        # Gesture list
        gestures = [
            ("👈 👉", "Swipe Move", CUTE_BLUE),
            ("✊", "Fist Pick Up", GOLD),
            ("👍", "Thumbs Switch", CUTE_GREEN),
            ("✋", "Palm Open Door", CYAN),
            ("☝️", "Point Next Lvl", CUTE_PURPLE),
            ("🤟", "3-Finger Restart", RED),
        ]
        
        icon_font = pygame.font.Font(None, 26)
        label_font = pygame.font.Font(None, 18)
        
        n = len(gestures)
        col_w = WIDTH // n
        
        for idx, (icon, label, col) in enumerate(gestures):
            cx = col_w * idx + col_w // 2
            
            if idx > 0:
                pygame.draw.line(screen, (60, 60, 80),
                                (col_w * idx, bar_y + 26),
                                (col_w * idx, bar_y + bar_h - 4), 1)
            
            icon_surf = icon_font.render(icon, True, col)
            screen.blit(icon_surf, (cx - icon_surf.get_width()//2, bar_y + 28))
            
            lbl_surf = label_font.render(label, True, col)
            screen.blit(lbl_surf, (cx - lbl_surf.get_width()//2, bar_y + 56))

    def draw_win_screen(elapsed_time, current_level, total_levels):
        t = pygame.time.get_ticks() / 1000
        is_final = (current_level >= total_levels - 1)
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 130))
        screen.blit(ov, (0, 0))
        for i in range(20):
            angle = t * 1.5 + i * 0.31
            rx = SCREEN_W//2 + int(math.cos(angle) * (100 + i*15))
            ry = SCREEN_H//2 + int(math.sin(angle * 0.7) * (80 + i*8))
            pygame.draw.circle(screen, LEVEL_COLORS[i % len(LEVEL_COLORS)], (rx, ry), 4)
        pw, ph = 640, 380
        px = (SCREEN_W - pw) // 2
        py = (SCREEN_H - ph) // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 7, 32, 245))
        bhr = int(128 + 100 * math.sin(t * 2))
        bhg = int(100 + 80  * math.sin(t * 2 + 2))
        bhb = int(200 + 55  * math.sin(t * 2 + 4))
        pygame.draw.rect(panel, (bhr, bhg, bhb), panel.get_rect(), 4, border_radius=16)
        screen.blit(panel, (px, py))
        font_xl = pygame.font.Font(None, 72)
        font_l  = pygame.font.Font(None, 42)
        font_m  = pygame.font.Font(None, 30)
        font_s  = pygame.font.Font(None, 24)
        if is_final:
            title_col = tuple(int(128 + 100 * math.sin(t*3 + i*0.5)) for i in range(3))
            title = font_xl.render("YOU MADE IT HOME!", True, title_col)
        else:
            lvl_col = LEVEL_COLORS[current_level % len(LEVEL_COLORS)]
            title = font_xl.render("LEVEL CLEAR!", True, lvl_col)
        screen.blit(title, title.get_rect(center=(SCREEN_W//2, py + 65)))
        for i in range(3):
            star_x = SCREEN_W//2 - 60 + i * 60
            star_y = py + 118
            for sp in range(5):
                angle = sp * 1.257 + t * (0.5 + i * 0.3)
                spx = star_x + int(math.cos(angle) * 14)
                spy = star_y + int(math.sin(angle) * 14)
                pygame.draw.line(screen, C_UI_GOLD, (star_x, star_y), (spx, spy), 2)
            pygame.draw.circle(screen, C_UI_GOLD, (star_x, star_y), 5)
        timer_str = f"{elapsed_time//60:02}:{elapsed_time%60:02}"
        screen.blit(font_l.render("TIME",     True, C_UI_MUTED),  (SCREEN_W//2 - 120, py + 145))
        screen.blit(font_l.render(timer_str,  True, C_UI_ACCENT), (SCREEN_W//2 - 40,  py + 145))
        if not is_final:
            msg_col = LEVEL_COLORS[(current_level + 1) % len(LEVEL_COLORS)]
            msg = f"Next: {LEVEL_NAMES[(current_level + 1) % len(LEVEL_NAMES)]}"
            screen.blit(font_m.render(msg, True, msg_col),
                        font_m.render(msg, True, msg_col).get_rect(center=(SCREEN_W//2, py+210)))
        else:
            screen.blit(font_m.render("All levels conquered!", True, C_UI_GOLD),
                        font_m.render("All levels conquered!", True, C_UI_GOLD).get_rect(center=(SCREEN_W//2, py+210)))
        hint = font_s.render("ENTER / click Next Level  |  Gesture: hold THUMBS UP", True, C_UI_MUTED)
        screen.blit(hint, hint.get_rect(center=(SCREEN_W//2, py + 248)))
        btn_y = py + 270
        if is_final:
            btn1 = FancyButton(SCREEN_W//2 - 200, btn_y, 180, 52, "Play Again", C_UI_GREEN)
            btn2 = FancyButton(SCREEN_W//2 + 20,  btn_y, 180, 52, "Quit",       C_G_LEFT)
        else:
            btn1 = FancyButton(SCREEN_W//2 - 210, btn_y, 200, 52, "Next Level ▶",
                               LEVEL_COLORS[(current_level+1) % len(LEVEL_COLORS)])
            btn2 = FancyButton(SCREEN_W//2 + 30,  btn_y, 180, 52, "Quit", C_G_LEFT)
        return btn1, btn2

    def find_start(level_map):
        for y, row in enumerate(level_map):
            for x, t in enumerate(row):
                if t == 3:
                    return float(x * TILE), float(y * TILE)
        return 0.0, 0.0

    print("\n" + "="*55)
    print("          ✦  FIND MY HOME  ✦  Gesture Adventure")
    print("="*55)
    gd = GestureDetector()
    if GESTURE_AVAILABLE and getattr(gd, 'available', False):
        print("✓ Gesture control ready — SWIPE to move!")
        gd.start()
    else:
        print("⚠  Gesture not available (pip install opencv-python mediapipe)")
    print("⌨  Arrow Keys  |  R = Restart  |  ESC = Back to Launcher\n")

    current_level = 0
    total_levels  = len(LEVELS)
    level_map     = LEVELS[current_level]
    px, py = find_start(level_map)
    player = Player(px, py, level_map)
    start_time = time.time()
    won = False
    win_time = 0
    btn1 = btn2 = None
    prev_time = time.time()

    running = True
    while running:
        now = time.time()
        dt = now - prev_time
        prev_time = now
        t_sec = now
        mouse_pos = pygame.mouse.get_pos()
        clock.tick(FPS)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                gesture_running[0] = False
                gd.stop()
                running = False
                time.sleep(1)
                break

            if e.type == pygame.MOUSEMOTION and won:
                if btn1:
                    btn1.check_hover(mouse_pos)
                if btn2:
                    btn2.check_hover(mouse_pos)

            if e.type == pygame.MOUSEBUTTONDOWN and won:
                if btn1 and btn1.is_clicked(mouse_pos):
                    current_level = (current_level + 1) % total_levels
                    level_map = LEVELS[current_level]
                    px, py = find_start(level_map)
                    player = Player(px, py, level_map)
                    start_time = time.time()
                    won = False
                if btn2 and btn2.is_clicked(mouse_pos):
                    gesture_running[0] = False
                    gd.stop()
                    running = False
                    break

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    gesture_running[0] = False
                    gd.stop()
                    running = False
                    break
                if won and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    current_level = (current_level + 1) % total_levels
                    level_map = LEVELS[current_level]
                    px, py = find_start(level_map)
                    player = Player(px, py, level_map)
                    start_time = time.time()
                    won = False
                if not won and not player.moving:
                    moved = False
                    if   e.key == pygame.K_LEFT:
                        moved = player.move(-1, 0)
                    elif e.key == pygame.K_RIGHT:
                        moved = player.move( 1, 0)
                    elif e.key == pygame.K_UP:
                        moved = player.move( 0,-1)
                    elif e.key == pygame.K_DOWN:
                        moved = player.move( 0, 1)
                    elif e.key == pygame.K_r:
                        px, py = find_start(level_map)
                        player = Player(px, py, level_map)
                        start_time = time.time()
                    if moved:
                        ox_m = (SCREEN_W - len(level_map[0])*TILE) // 2
                        oy_m = (SCREEN_H - len(level_map)*TILE)    // 2 + 10
                        emit_particles(player.tx + TILE//2 + ox_m,
                                       player.ty + TILE//2 + oy_m, C_UI_GOLD)
                        won = True
                        win_time = int(time.time() - start_time)

        if GESTURE_AVAILABLE:
            while not gesture_queue.empty():
                g = gesture_queue.get()
                if g == "next" and won:
                    current_level = (current_level + 1) % total_levels
                    level_map = LEVELS[current_level]
                    px, py = find_start(level_map)
                    player = Player(px, py, level_map)
                    start_time = time.time()
                    won = False
                    continue
                if won or player.moving:
                    continue
                moved = False
                if   g == "left":
                    moved = player.move(-1, 0)
                elif g == "right":
                    moved = player.move( 1, 0)
                elif g == "up":
                    moved = player.move( 0,-1)
                elif g == "down":
                    moved = player.move( 0, 1)
                elif g == "restart":
                    px2, py2 = find_start(level_map)
                    player = Player(px2, py2, level_map)
                    start_time = time.time()
                if moved:
                    ox_m = (SCREEN_W - len(level_map[0])*TILE) // 2
                    oy_m = (SCREEN_H - len(level_map)*TILE)    // 2 + 10
                    emit_particles(player.tx + TILE//2 + ox_m,
                                   player.ty + TILE//2 + oy_m, C_HOME_GLOW, 20)
                    won = True
                    win_time = int(time.time() - start_time)

        player.update(dt)
        particles[:] = [p for p in particles if p.update(dt)]

        try:
            draw_background()
            draw_stars(t_sec)
            ox, oy = draw_map(level_map)
            player.draw(ox, oy)
            for p in particles:
                p.draw(screen)
            draw_top_hud(start_time, current_level, total_levels)
            draw_minimap(player, level_map, ox, oy)
            draw_gesture_panel()
            draw_instruction_bar()
            if won:
                btn1, btn2 = draw_win_screen(win_time, current_level, total_levels)
                btn1.draw(screen)
                btn2.draw(screen)
        except Exception as e:
            print(f"[DRAW ERROR] {e}")
            import traceback
            traceback.print_exc()
        pygame.display.flip()
    gesture_running[0] = False
    gd.stop()
    time.sleep(1)


# =============================================================================
#  PUZZLE ESCAPE  –  with FIXED camera handling (same fixes applied)
# =============================================================================
def run_puzzle_escape():
    import cv2
    import mediapipe as mp
    from picamera2 import Picamera2

    WIDTH, HEIGHT = 900, 650
    FPS = 60

    WHITE  = (255, 255, 255)
    BLACK       = (0, 0, 0)
    CUTE_PINK   = (255, 182, 193)
    CUTE_BLUE   = (173, 216, 230)
    CUTE_GREEN  = (144, 238, 144)
    CUTE_YELLOW = (255, 255, 153)
    CUTE_PURPLE = (216, 191, 216)
    CUTE_ORANGE = (255, 200, 150)
    DARK_GRAY   = (70, 70, 70)
    LIGHT_GRAY  = (200, 200, 200)
    RED  = (255, 100, 100)
    GOLD   = (255, 215, 0)
    ORANGE = (255, 165, 0)
    CYAN   = (100, 200, 255)

    PLAYING = 0
    WON = 1
    LOST = 2
    LEVEL_COMPLETE = 3

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("🧩 Puzzle Escape - 10 Levels! (Gesture Control)")
    clock = pygame.time.Clock()

    class Particle:
        def __init__(self, x, y, color):
            self.x = x
            self.y = y
            self.vx = random.uniform(-2, 2)
            self.vy = random.uniform(-3, -1)
            self.color = color
            self.life = 60
            self.max_life = 60
        def update(self):
            self.x += self.vx
            self.y += self.vy
            self.vy += 0.1
            self.life -= 1
        def draw(self, screen):
            size = int(5 * (self.life / self.max_life))
            if size > 0:
                pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), size)

    class Player:
        def __init__(self, x, y):
            self.x = x
            self.y = y
            self.target_x = x
            self.target_y = y
            self.size = 45
            self.color = CUTE_PINK
            self.speed = 5
            self.bob_offset = 0
            self.bob_speed = 0.1
            self.blink_timer = 0
            self.is_blinking = False
        def move_to(self, x, y):
            self.target_x = x
            self.target_y = y
        def update(self):
            if abs(self.x - self.target_x) > 1:
                self.x += (self.target_x - self.x) * 0.15
            else:
                self.x = self.target_x
            if abs(self.y - self.target_y) > 1:
                self.y += (self.target_y - self.y) * 0.15
            else:
                self.y = self.target_y
            self.bob_offset += self.bob_speed
            self.blink_timer += 1
            if self.blink_timer > 120:
                self.is_blinking = True
            if self.blink_timer > 130:
                self.is_blinking = False
                self.blink_timer = 0
        def draw(self, screen):
            bob = math.sin(self.bob_offset) * 4
            pygame.draw.ellipse(screen, (150,150,150),
                                (int(self.x-35), int(self.y+bob+40), 70, 15))
            pygame.draw.circle(screen, BLACK, (int(self.x), int(self.y+bob)), self.size+2)
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y+bob)), self.size)
            pygame.draw.circle(screen, (255,150,150), (int(self.x-20), int(self.y+5+bob)), 8)
            pygame.draw.circle(screen, (255,150,150), (int(self.x+20), int(self.y+5+bob)), 8)
            if not self.is_blinking:
                eye_offset = 12
                pygame.draw.circle(screen, WHITE, (int(self.x-eye_offset), int(self.y-5+bob)), 7)
                pygame.draw.circle(screen, WHITE, (int(self.x+eye_offset), int(self.y-5+bob)), 7)
                pygame.draw.circle(screen, BLACK, (int(self.x-eye_offset), int(self.y-5+bob)), 4)
                pygame.draw.circle(screen, BLACK, (int(self.x+eye_offset), int(self.y-5+bob)), 4)
                pygame.draw.circle(screen, WHITE, (int(self.x-eye_offset+2), int(self.y-7+bob)), 2)
                pygame.draw.circle(screen, WHITE, (int(self.x+eye_offset+2), int(self.y-7+bob)), 2)
            else:
                pygame.draw.line(screen, BLACK, (int(self.x-18), int(self.y-5+bob)),
                                               (int(self.x- 6), int(self.y-5+bob)), 3)
                pygame.draw.line(screen, BLACK, (int(self.x+ 6), int(self.y-5+bob)),
                                               (int(self.x+18), int(self.y-5+bob)), 3)
            pygame.draw.arc(screen, BLACK, (self.x-18, self.y+bob+5, 36, 25), 3.14, 6.28, 4)

    class Item:
        def __init__(self, x, y, item_type, name):
            self.x = x
            self.y = y
            self.type = item_type
            self.name = name
            self.collected = False
            self.float_offset = random.uniform(0, 6.28)
            self.float_speed = 0.08
            self.sparkle_timer = 0
            self.rotate_angle = 0
        def update(self):
            if not self.collected:
                self.float_offset += self.float_speed
                self.sparkle_timer += 1
                self.rotate_angle += 2
        def draw(self, screen, font):
            if self.collected:
                return
            float_y = self.y + math.sin(self.float_offset) * 6
            if self.type == "key":
                for i in range(3):
                    angle = (self.rotate_angle + i * 120) % 360
                    rad = math.radians(angle)
                    pygame.draw.circle(screen, GOLD,
                                       (int(self.x + math.cos(rad)*25), int(float_y + math.sin(rad)*25)), 3)
                pygame.draw.circle(screen, ORANGE, (self.x+2, int(float_y)+2), 12)
                pygame.draw.circle(screen, GOLD,   (self.x,   int(float_y)),   12)
                pygame.draw.rect(screen, ORANGE, (self.x+10, int(float_y)-4, 22, 8))
                pygame.draw.rect(screen, GOLD,   (self.x+ 8, int(float_y)-3, 22, 8))
                for i in range(3):
                    pygame.draw.rect(screen, GOLD, (self.x+22+i*6, int(float_y)+2, 3, 5))
                pygame.draw.circle(screen, ORANGE, (self.x, int(float_y)), 5)
            label = font.render(self.name, True, WHITE)
            label_bg = pygame.Surface((label.get_width()+10, label.get_height()+6))
            label_bg.fill(BLACK)
            label_bg.set_alpha(150)
            screen.blit(label_bg, (self.x - label.get_width()//2 - 5, float_y + 25))
            screen.blit(label,    (self.x - label.get_width()//2,     float_y + 28))

    class Switch:
        def __init__(self, x, y, name):
            self.x = x
            self.y = y
            self.name = name
            self.activated = False
            self.glow_offset = 0
            self.pulse = 0
        def update(self):
            if self.activated:
                self.glow_offset += 0.15
            self.pulse += 0.1
        def draw(self, screen, font):
            color = CUTE_GREEN if self.activated else LIGHT_GRAY
            pygame.draw.rect(screen, (50,50,50),  (self.x-32, self.y+12, 64, 24), border_radius=8)
            pygame.draw.rect(screen, DARK_GRAY,   (self.x-30, self.y+10, 60, 24), border_radius=8)
            switch_x = self.x + 12 if self.activated else self.x - 12
            pygame.draw.circle(screen, (50,50,50), (switch_x+2, self.y+24), 14)
            pygame.draw.circle(screen, color,       (switch_x,   self.y+22), 14)
            pygame.draw.circle(screen, WHITE,       (switch_x-3, self.y+19), 4)
            if self.activated:
                glow_size = 18 + math.sin(self.glow_offset) * 4
                for i in range(3):
                    pygame.draw.circle(screen, CUTE_GREEN, (switch_x, self.y+22), int(glow_size - i*3), 2)
            light_color = CUTE_GREEN if self.activated else RED
            pulse_size = 4 + math.sin(self.pulse) * 1 if self.activated else 4
            pygame.draw.circle(screen, light_color, (self.x, self.y+22), int(pulse_size))
            label = font.render(self.name, True, WHITE)
            label_bg = pygame.Surface((label.get_width()+10, label.get_height()+6))
            label_bg.fill(BLACK)
            label_bg.set_alpha(150)
            screen.blit(label_bg, (self.x - label.get_width()//2 - 5, self.y - 38))
            screen.blit(label,    (self.x - label.get_width()//2,     self.y - 35))

    class Door:
        def __init__(self, x, y):
            self.x = x
            self.y = y
            self.width = 90
            self.height = 140
            self.locked = True
            self.open_progress = 0
            self.lock_shake = 0
        def unlock(self):
            self.locked = False
        def shake(self):
            self.lock_shake = 10
        def update(self):
            if not self.locked and self.open_progress < 1:
                self.open_progress += 0.04
            if self.lock_shake > 0:
                self.lock_shake -= 1
        def draw(self, screen, font):
            shake_x = random.randint(-2, 2) if self.lock_shake > 0 else 0
            pygame.draw.rect(screen, (40,40,40),
                             (self.x-8, self.y-8, self.width+16, self.height+16), border_radius=15)
            pygame.draw.rect(screen, DARK_GRAY,
                             (self.x-5, self.y-5, self.width+10, self.height+10), border_radius=12)
            door_color = CYAN if not self.locked else (100,100,120)
            door_width = self.width * (1 - self.open_progress * 0.85)
            pygame.draw.rect(screen, (50,50,50),
                             (self.x+3+shake_x, self.y+3, door_width, self.height), border_radius=10)
            pygame.draw.rect(screen, door_color,
                             (self.x+shake_x,   self.y,   door_width, self.height), border_radius=10)
            if self.open_progress < 0.7:
                panel_width = door_width * 0.4
                pygame.draw.rect(screen, (door_color[0]-20, door_color[1]-20, door_color[2]-20),
                                 (self.x+shake_x+10, self.y+15, panel_width, 40), border_radius=5)
                pygame.draw.rect(screen, (door_color[0]-20, door_color[1]-20, door_color[2]-20),
                                 (self.x+shake_x+10, self.y+70, panel_width, 50), border_radius=5)
            if self.open_progress < 0.5:
                knob_x = self.x + shake_x + door_width - 18
                pygame.draw.circle(screen, ORANGE, (int(knob_x+1), self.y+72), 9)
                pygame.draw.circle(screen, GOLD,   (int(knob_x),   self.y+70), 9)
                pygame.draw.circle(screen, GOLD,   (int(knob_x-2), self.y+68), 3)
            if self.locked:
                lock_x = self.x + shake_x + self.width // 2
                lock_y = self.y + self.height // 2
                pygame.draw.rect(screen, (200,0,0), (lock_x-18, lock_y+2, 36, 32), border_radius=6)
                pygame.draw.rect(screen, RED,       (lock_x-16, lock_y,   32, 30), border_radius=5)
                pygame.draw.arc(screen, RED, (lock_x-12, lock_y-20, 24, 26), 0, 3.14159, 5)
                pygame.draw.circle(screen, (150,0,0), (lock_x, lock_y+10), 4)
                pygame.draw.rect(screen,   (150,0,0), (lock_x-2, lock_y+10, 4, 8))
            status = "OPEN!" if not self.locked else "LOCKED"
            status_color = CUTE_GREEN if not self.locked else RED
            label = font.render(status, True, status_color)
            label_bg = pygame.Surface((label.get_width()+14, label.get_height()+8))
            label_bg.fill(BLACK)
            label_bg.set_alpha(180)
            screen.blit(label_bg, (self.x + self.width//2 - label.get_width()//2 - 7,
                                   self.y + self.height + 15))
            screen.blit(label,    (self.x + self.width//2 - label.get_width()//2,
                                   self.y + self.height + 18))

    class Game:
        def __init__(self):
            self.font       = pygame.font.Font(None, 22)
            self.big_font   = pygame.font.Font(None, 56)
            self.title_font = pygame.font.Font(None, 40)
            self.particles  = []
            self.current_level = 1
            self.max_level  = 10
            self.total_score = 0
            self.level_config = self.get_level_config()

            # Gesture detection setup with FIXED camera
            self.use_gestures = False
            self.picam2       = None
            try:
                self._mp_sol = mp.solutions.hands.Hands(
                    static_image_mode=False, max_num_hands=1,
                    min_detection_confidence=0.7, min_tracking_confidence=0.6)
                self._mp_draw = mp.solutions.drawing_utils
                time.sleep(3)
                self.picam2 = get_camera()  # Get shared camera
                self.use_gestures = True
                # Create OpenCV window
                cv2.namedWindow('Gesture Control - Puzzle Escape', cv2.WINDOW_NORMAL)
                cv2.resizeWindow('Gesture Control - Puzzle Escape', 640, 480)
                cv2.moveWindow('Gesture Control - Puzzle Escape', 100, 100)
                print("[PUZZLE ESCAPE] Gesture control ready")
            except Exception as e:
                print(f"[PUZZLE ESCAPE] Gesture not available: {e}")

            # Swipe detection
            self._wrist_history   = []
            self._HISTORY_SEC     = 0.4
            self._SWIPE_THRESHOLD = 0.18
            self._SWIPE_COOLDOWN  = 0.6
            self._last_swipe_time = 0.0

            # Pose hold state
            self._pose_name       = None
            self._pose_start_time = 0.0
            self._POSE_HOLD       = 0.35
            self._last_pose_time  = 0.0
            self._POSE_COOLDOWN   = 0.5

            self.reset_game()

        def get_level_config(self):
            return {
                1:  {'time':60,'keys':1,'switches':0,'positions':[(450,400),(700,400)],'key_positions':[0],'switch_positions':[],'door_position':1,'theme_color':CUTE_PINK,'instruction':"Collect the key and open the door!"},
                2:  {'time':55,'keys':2,'switches':0,'positions':[(200,380),(450,380),(700,380)],'key_positions':[0,1],'switch_positions':[],'door_position':2,'theme_color':CUTE_BLUE,'instruction':"Collect both keys to unlock the door!"},
                3:  {'time':50,'keys':1,'switches':1,'positions':[(200,350),(450,350),(700,400)],'key_positions':[0],'switch_positions':[1],'door_position':2,'theme_color':CUTE_GREEN,'instruction':"Get the key AND activate the switch!"},
                4:  {'time':50,'keys':2,'switches':1,'positions':[(180,320),(350,320),(520,320),(700,420)],'key_positions':[0,2],'switch_positions':[1],'door_position':3,'theme_color':CUTE_YELLOW,'instruction':"Collect 2 keys and flip the switch!"},
                5:  {'time':45,'keys':2,'switches':2,'positions':[(200,280),(350,350),(500,280),(650,350),(750,450)],'key_positions':[0,2],'switch_positions':[1,3],'door_position':4,'theme_color':CUTE_PURPLE,'instruction':"2 keys + 2 switches = freedom!"},
                6:  {'time':45,'keys':3,'switches':1,'positions':[(180,300),(320,380),(450,300),(580,380),(720,450)],'key_positions':[0,2,3],'switch_positions':[1],'door_position':4,'theme_color':CUTE_ORANGE,'instruction':"Find all 3 keys and activate switch!"},
                7:  {'time':40,'keys':3,'switches':2,'positions':[(150,280),(280,350),(410,280),(540,350),(670,280),(780,430)],'key_positions':[0,2,4],'switch_positions':[1,3],'door_position':5,'theme_color':CYAN,'instruction':"3 keys + 2 switches - hurry up!"},
                8:  {'time':40,'keys':4,'switches':2,'positions':[(160,260),(280,330),(400,260),(520,330),(640,260),(760,330),(800,430)],'key_positions':[0,1,3,4],'switch_positions':[2,5],'door_position':6,'theme_color':(255,150,200),'instruction':"4 keys scattered! Find them all + switches!"},
                9:  {'time':35,'keys':3,'switches':3,'positions':[(140,250),(260,320),(380,250),(500,320),(620,250),(740,320),(800,420)],'key_positions':[0,2,4],'switch_positions':[1,3,5],'door_position':6,'theme_color':(180,255,180),'instruction':"3 keys + 3 switches! Navigate carefully!"},
                10: {'time':30,'keys':4,'switches':3,'positions':[(130,240),(240,310),(350,240),(460,310),(570,240),(680,310),(790,240),(800,420)],'key_positions':[0,2,4,5],'switch_positions':[1,3,6],'door_position':7,'theme_color':(255,180,255),'instruction':"FINAL LEVEL! 4 keys + 3 switches - GO GO GO!"},
            }

        def reset_game(self):
            self.state = PLAYING
            config = self.level_config[self.current_level]
            self.time_left = config['time']
            self.timer = 0
            self.positions = config['positions']
            self.player = Player(self.positions[0][0], self.positions[0][1])
            self.items = []
            for i, pos_idx in enumerate(config['key_positions']):
                pos = self.positions[pos_idx]
                self.items.append(Item(pos[0], pos[1], "key", f"Key {chr(65+i)}"))
            self.switches = []
            for i, pos_idx in enumerate(config['switch_positions']):
                pos = self.positions[pos_idx]
                self.switches.append(Switch(pos[0], pos[1], f"Switch {i+1}"))
            door_pos = self.positions[config['door_position']]
            self.door = Door(door_pos[0]-45, door_pos[1]-70)
            self.current_position = 0
            self.player_near_object = None
            self.message = config['instruction']
            self.message_timer = 240
            self.particles = []
            self.check_proximity()

        def next_level(self):
            if self.current_level < self.max_level:
                self.current_level += 1
                self.reset_game()
            else:
                self.state = WON

        def show_message(self, text):
            self.message = text
            self.message_timer = 180

        def add_particles(self, x, y, color):
            for _ in range(20):
                self.particles.append(Particle(x, y, color))

        def handle_input(self, key):
            if key in (pygame.K_LEFT, pygame.K_a):
                self.move_player(-1)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.move_player(1)
            elif key in (pygame.K_SPACE, pygame.K_p):
                self.try_pick_up()
            elif key in (pygame.K_e, pygame.K_RETURN):
                self.try_activate()
            elif key == pygame.K_o:
                self.try_open_door()
            elif key == pygame.K_r:
                self.current_level = 1
                self.total_score = 0
                self.reset_game()

        def handle_gestures(self):
            if not self.use_gestures or not self.picam2:
                return
            # Capture frame
            frame_raw = self.picam2.capture_array()
            if frame_raw is None:
                return
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            frame = cv2.flip(frame, 1)
            h_px, w_px = frame.shape[:2]

            now = time.time()

            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self._mp_sol.process(rgb)

            gesture = None

            if result.multi_hand_landmarks:
                hl = result.multi_hand_landmarks[0]
                lm = hl.landmark
                self._mp_draw.draw_landmarks(frame, hl,
                    mp.solutions.hands.HAND_CONNECTIONS)

                # Finger count
                fingers = 0
                if lm[4].x < lm[3].x:
                    fingers += 1
                for tip, pip in zip([8,12,16,20],[6,10,14,18]):
                    if lm[tip].y < lm[pip].y:
                        fingers += 1

                # Wrist X history for swipe
                wx = lm[0].x
                self._wrist_history.append((now, wx))
                self._wrist_history = [(t, x) for t, x in self._wrist_history
                                       if now - t <= self._HISTORY_SEC]

                # SWIPE detection
                if (len(self._wrist_history) >= 4
                        and fingers >= 2
                        and now - self._last_swipe_time > self._SWIPE_COOLDOWN):
                    oldest_x = self._wrist_history[0][1]
                    newest_x = self._wrist_history[-1][1]
                    delta    = newest_x - oldest_x
                    if abs(delta) >= self._SWIPE_THRESHOLD:
                        gesture = "swipe_right" if delta > 0 else "swipe_left"
                        self._wrist_history.clear()
                        self._last_swipe_time = now

                # POSE detection
                if gesture is None:
                    if fingers == 0:
                        pose = "fist"
                    elif fingers >= 5:
                        pose = "open_palm"
                    elif fingers == 1 and lm[4].y < lm[0].y - 0.06:
                        pose = "thumbs_up"
                    elif fingers == 2:
                        pose = "peace"
                    elif fingers == 3:
                        pose = "three_fingers"
                    elif fingers == 1:
                        pose = "point"
                    else:
                        pose = None

                    if pose is None:
                        self._pose_name = None
                    elif self._pose_name != pose:
                        self._pose_name       = pose
                        self._pose_start_time = now
                    elif (now - self._pose_start_time >= self._POSE_HOLD
                          and now - self._last_pose_time  > self._POSE_COOLDOWN):
                        gesture = pose
                        self._pose_name     = None
                        self._last_pose_time = now

            else:
                self._wrist_history.clear()
                self._pose_name = None

            # Apply gesture
            if self.state == PLAYING:
                if gesture == "swipe_left":
                    self.move_player(-1)
                    self.show_message("👈 Moved Left!")
                elif gesture == "swipe_right":
                    self.move_player(1)
                    self.show_message("👉 Moved Right!")
                elif gesture == "fist":
                    self.try_pick_up()
                elif gesture == "thumbs_up":
                    self.try_activate()
                elif gesture == "open_palm":
                    self.try_open_door()
                elif gesture == "three_fingers":
                    self.current_level = 1
                    self.total_score = 0
                    self.reset_game()
                    self.show_message("🔄 Game Restarted!")
            elif self.state == LEVEL_COMPLETE:
                if gesture in ("point", "thumbs_up"):
                    self.next_level()
                    self.show_message("☝️ Next Level!")
            elif self.state in (LOST, WON):
                if gesture == "three_fingers":
                    self.current_level = 1
                    self.total_score = 0
                    self.reset_game()
                    self.show_message("🔄 Game Restarted!")

            # Draw camera overlay
            hint = "Swipe L/R=Move  Fist=Pick  Thumb=Switch  Palm=Door"
            cv2.putText(frame, hint, (6, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 100), 1)
            if result.multi_hand_landmarks:
                fingers_lbl = f"Fingers: {fingers}"
                cv2.putText(frame, fingers_lbl, (6, h_px - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 255, 200), 2)
            if gesture:
                cv2.putText(frame, f">> {gesture.upper()} <<",
                            (w_px // 2 - 100, h_px // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 100), 3)

            cv2.imshow('Gesture Control - Puzzle Escape', frame)
            cv2.waitKey(1)

        def move_player(self, direction):
            new_pos = self.current_position + direction
            if 0 <= new_pos < len(self.positions):
                self.current_position = new_pos
                self.player.move_to(self.positions[self.current_position][0],
                                    self.positions[self.current_position][1])
                self.check_proximity()

        def check_proximity(self):
            px, py = self.positions[self.current_position]
            for item in self.items:
                if not item.collected and abs(item.x-px) < 50 and abs(item.y-py) < 50:
                    self.player_near_object = ("item", item)
                    return
            for switch in self.switches:
                if abs(switch.x-px) < 50 and abs(switch.y-py) < 50:
                    self.player_near_object = ("switch", switch)
                    return
            if (abs(self.door.x + self.door.width//2 - px) < 80 and
                    abs(self.door.y + self.door.height//2 - py) < 100):
                self.player_near_object = ("door", self.door)
                return
            self.player_near_object = None

        def try_pick_up(self):
            if self.player_near_object and self.player_near_object[0] == "item":
                item = self.player_near_object[1]
                if not item.collected:
                    item.collected = True
                    self.show_message(f"✨ Got {item.name}!")
                    self.add_particles(item.x, item.y, GOLD)
                else:
                    self.show_message("Already collected!")
            else:
                self.show_message("❌ Nothing here!")

        def try_activate(self):
            if self.player_near_object and self.player_near_object[0] == "switch":
                switch = self.player_near_object[1]
                if not switch.activated:
                    switch.activated = True
                    self.show_message("⚡ Switch ON!")
                    self.add_particles(switch.x, switch.y, CUTE_GREEN)
                else:
                    self.show_message("Already on!")
            else:
                self.show_message("❌ No switch here!")

        def try_open_door(self):
            if self.player_near_object and self.player_near_object[0] == "door":
                keys_collected   = all(item.collected   for item   in self.items)
                switches_activated = all(switch.activated for switch in self.switches)
                if keys_collected and switches_activated:
                    if self.door.locked:
                        self.door.unlock()
                        self.show_message("🎉 Door unlocked!")
                        self.add_particles(self.door.x + self.door.width//2,
                                           self.door.y, CUTE_GREEN)
                        bonus = self.time_left * 10
                        self.total_score += bonus
                        self.state = LEVEL_COMPLETE
                    else:
                        self.show_message("Door is open!")
                elif not keys_collected:
                    self.door.shake()
                    self.show_message("❌ Need all keys!")
                else:
                    self.door.shake()
                    self.show_message("❌ Activate all switches!")
            else:
                self.show_message("❌ Not at door!")

        def check_win_condition(self):
            if self.state == LEVEL_COMPLETE and self.door.open_progress >= 1.0:
                pass

        def update(self):
            for particle in self.particles[:]:
                particle.update()
                if particle.life <= 0:
                    self.particles.remove(particle)
            if self.state != PLAYING:
                return
            self.timer += 1
            if self.timer >= FPS:
                self.timer = 0
                self.time_left -= 1
                if self.time_left <= 0:
                    self.state = LOST
            self.player.update()
            for item in self.items:
                item.update()
            for switch in self.switches:
                switch.update()
            self.door.update()
            self.check_win_condition()
            if self.message_timer > 0:
                self.message_timer -= 1

        def draw_background(self):
            config = self.level_config[self.current_level]
            theme = config['theme_color']
            for y in range(HEIGHT - 100):
                ratio = y / (HEIGHT - 100)
                r = int(135 + (theme[0]-135) * ratio * 0.3)
                g = int(206 + (theme[1]-206) * ratio * 0.3)
                b = int(235 + (theme[2]-235) * ratio * 0.3)
                pygame.draw.line(screen, (r, g, b), (0, y), (WIDTH, y))
            cloud_offset = (pygame.time.get_ticks() / 50) % WIDTH
            for i in range(3):
                cx = (cloud_offset + i * 300) % (WIDTH + 200) - 100
                cy = 80 + i * 60
                pygame.draw.ellipse(screen, (200,200,220), (cx, cy+2, 120, 40))
                pygame.draw.ellipse(screen, (200,200,220), (cx+30, cy+2, 100, 35))
                pygame.draw.ellipse(screen, (240,240,255), (cx, cy, 120, 40))
                pygame.draw.ellipse(screen, (240,240,255), (cx+30, cy-5, 100, 35))
                pygame.draw.ellipse(screen, (240,240,255), (cx+60, cy, 90, 38))
            wall_color = (180,140,100)
            wall_shadow = (140,110,80)
            wall_highlight = (200,160,120)
            pygame.draw.polygon(screen, wall_shadow,    [(0,0),(180,120),(180,HEIGHT-100),(0,HEIGHT-100)])
            pygame.draw.polygon(screen, wall_color,     [(0,0),(170,120),(170,HEIGHT-100),(0,HEIGHT-100)])
            for i in range(2):
                panel_y = 200 + i * 150
                pygame.draw.rect(screen, wall_shadow,    (20, panel_y, 120, 100), border_radius=8)
                pygame.draw.rect(screen, wall_highlight, (25, panel_y+5, 110, 90), border_radius=6)
            pygame.draw.polygon(screen, wall_shadow, [(WIDTH,0),(WIDTH-180,120),(WIDTH-180,HEIGHT-100),(WIDTH,HEIGHT-100)])
            pygame.draw.polygon(screen, wall_color,  [(WIDTH,0),(WIDTH-170,120),(WIDTH-170,HEIGHT-100),(WIDTH,HEIGHT-100)])
            for i in range(2):
                panel_y = 200 + i * 150
                pygame.draw.rect(screen, wall_shadow,    (WIDTH-140, panel_y, 120, 100), border_radius=8)
                pygame.draw.rect(screen, wall_highlight, (WIDTH-135, panel_y+5, 110, 90), border_radius=6)
            back_wall_color = (160,130,90)
            pygame.draw.rect(screen, (140,110,80),      (170, 120, WIDTH-340, HEIGHT-220))
            pygame.draw.rect(screen, back_wall_color,   (170, 120, WIDTH-340, HEIGHT-220))
            window_x = WIDTH//2 - 100
            window_y = 140
            window_width = 200
            window_height = 150
            pygame.draw.rect(screen, (80,60,40),  (window_x-10, window_y-10, window_width+20, window_height+20), border_radius=8)
            pygame.draw.rect(screen, (150,200,250), (window_x, window_y, window_width, window_height))
            pane_w = window_width//2 - 5
            pane_h = window_height//2 - 5
            pygame.draw.rect(screen, (135,206,250), (window_x+5, window_y+5, pane_w, pane_h))
            pygame.draw.rect(screen, (135,206,250), (window_x+window_width//2+5, window_y+5, pane_w, pane_h))
            pygame.draw.rect(screen, (135,206,250), (window_x+5, window_y+window_height//2+5, pane_w, pane_h))
            pygame.draw.rect(screen, (135,206,250), (window_x+window_width//2+5, window_y+window_height//2+5, pane_w, pane_h))
            pygame.draw.rect(screen, (80,60,40), (window_x+window_width//2-5, window_y, 10, window_height))
            pygame.draw.rect(screen, (80,60,40), (window_x, window_y+window_height//2-5, window_width, 10))
            ceiling_points = [(0,0),(WIDTH,0),(WIDTH-170,120),(170,120)]
            pygame.draw.polygon(screen, (100,100,120), ceiling_points)
            light_x = WIDTH//2
            light_y = 60
            pygame.draw.ellipse(screen, (200,200,200), (light_x-40, light_y-5, 80, 15))
            pygame.draw.ellipse(screen, (255,255,220), (light_x-35, light_y-3, 70, 11))
            glow_radius = 60 + math.sin(pygame.time.get_ticks() / 200) * 5
            for i in range(3):
                pygame.draw.circle(screen, (255,255,200), (light_x, light_y), int(glow_radius - i*15), 2)
            floor_color = (120,80,60)
            floor_light = (140,100,80)
            floor_dark = (100,70,50)
            pygame.draw.rect(screen, floor_color, (0, HEIGHT-100, WIDTH, 100))
            tile_size = 80
            for x in range(0, WIDTH, tile_size):
                for y_idx, y in enumerate(range(HEIGHT-100, HEIGHT, tile_size)):
                    depth_factor = 1 - (y_idx * 0.15)
                    tile_h = int(tile_size * depth_factor)
                    if ((x // tile_size) + y_idx) % 2 == 0:
                        pygame.draw.rect(screen, floor_light, (x, y, tile_size, tile_h))
                    else:
                        pygame.draw.rect(screen, floor_dark,  (x, y, tile_size, tile_h))
                    pygame.draw.rect(screen, (80,60,40), (x, y, tile_size, tile_h), 1)
            frame_colors = [(139,69,19),(160,82,45)]
            for i in range(2):
                frame_y = 160 + i * 120
                frame_points = [(60,frame_y),(130,frame_y+20),(130,frame_y+80),(60,frame_y+60)]
                pygame.draw.polygon(screen, frame_colors[i%2], frame_points, 4)
                inner_points = [(68,frame_y+8),(122,frame_y+24),(122,frame_y+74),(68,frame_y+54)]
                pygame.draw.polygon(screen, theme, inner_points)
            shelf_x = WIDTH - 150
            shelf_y = 180
            pygame.draw.rect(screen, (80,60,40),  (shelf_x, shelf_y, 100, 180))
            pygame.draw.rect(screen, (100,80,60), (shelf_x+5, shelf_y+5, 90, 170))
            book_colors = [(200,50,50),(50,150,200),(100,200,100),(200,200,50)]
            for i in range(4):
                shelf_level_y = shelf_y + 20 + i * 40
                pygame.draw.rect(screen, (80,60,40), (shelf_x, shelf_level_y, 100, 3))
                for j in range(3):
                    book_x = shelf_x + 10 + j * 28
                    book_color = book_colors[(i + j) % len(book_colors)]
                    pygame.draw.rect(screen, book_color, (book_x, shelf_level_y-30, 20, 30))
                    pygame.draw.rect(screen, BLACK,      (book_x, shelf_level_y-30, 20, 30), 1)
            clock_x = WIDTH - 250
            clock_y = 200
            pygame.draw.circle(screen, (100,80,60),  (clock_x, clock_y), 35)
            pygame.draw.circle(screen, (200,180,140),(clock_x, clock_y), 32)
            pygame.draw.circle(screen, WHITE,         (clock_x, clock_y), 28)
            for i in range(12):
                angle = math.radians(i * 30 - 90)
                pygame.draw.circle(screen, BLACK,
                                   (int(clock_x + math.cos(angle)*20), int(clock_y + math.sin(angle)*20)), 2)
            time_angle   = (pygame.time.get_ticks() / 50)  % 360
            minute_angle = (pygame.time.get_ticks() / 500) % 360
            hour_x = clock_x + math.cos(math.radians(minute_angle - 90)) * 12
            hour_y = clock_y + math.sin(math.radians(minute_angle - 90)) * 12
            pygame.draw.line(screen, BLACK, (clock_x, clock_y), (int(hour_x), int(hour_y)), 3)
            hand_x = clock_x + math.cos(math.radians(time_angle - 90)) * 20
            hand_y = clock_y + math.sin(math.radians(time_angle - 90)) * 20
            pygame.draw.line(screen, BLACK, (clock_x, clock_y), (int(hand_x), int(hand_y)), 2)
            pygame.draw.circle(screen, BLACK, (clock_x, clock_y), 4)
            pygame.draw.circle(screen, GOLD,  (clock_x, clock_y), 3)
            plant_x = 200
            plant_y = HEIGHT - 100
            pygame.draw.polygon(screen, (180,100,80),
                                [(plant_x-20,plant_y),(plant_x-15,plant_y-30),
                                 (plant_x+15,plant_y-30),(plant_x+20,plant_y)])
            for i in range(5):
                leaf_angle = i * 72 + pygame.time.get_ticks() / 100
                leaf_x = plant_x + math.cos(math.radians(leaf_angle)) * 15
                leaf_y = plant_y - 35 + math.sin(math.radians(leaf_angle)) * 10
                pygame.draw.ellipse(screen, (50,150,50),  (int(leaf_x)-8, int(leaf_y)-12, 16, 24))
                pygame.draw.ellipse(screen, (80,180,80),  (int(leaf_x)-6, int(leaf_y)-10, 12, 20))

        
        def draw_instruction_bar():
            # Draw instruction bar at bottom
            bar_y = SCREEN_H - 80
            bar_h = 60
            bar_surf = pygame.Surface((SCREEN_W, bar_h), pygame.SRCALPHA)
            bar_surf.fill((0, 0, 0, 180))
            screen.blit(bar_surf, (0, bar_y))
            
            # Gesture instructions
            gestures = [
                ("👈 👉", "Swipe Move", C_G_LEFT),
                ("✊", "Fist Up", C_G_UP),
                ("✋", "Palm Down", C_G_DOWN),
                ("👍", "Thumb Next", C_UI_GOLD),
                ("✌️", "Peace Restart", C_G_RESTART),
            ]
            
            font = pygame.font.Font(None, 20)
            small_font = pygame.font.Font(None, 16)
            
            for i, (icon, label, color) in enumerate(gestures):
                x = 20 + i * 150
                icon_surf = font.render(icon, True, color)
                screen.blit(icon_surf, (x, bar_y + 15))
                label_surf = small_font.render(label, True, color)
                screen.blit(label_surf, (x, bar_y + 40))
        def draw(self):
            self.draw_background()
            if self.state == PLAYING:
                try:
                    for particle in self.particles:
                        particle.draw(screen)
                    for item in self.items:
                        item.draw(screen, self.font)
                    for switch in self.switches:
                        switch.draw(screen, self.font)
                    self.door.draw(screen, self.font)
                    self.player.draw(screen)
                except Exception as e:
                    print(f"[PUZZLE DRAW ERROR] {e}")
                    import traceback
                    traceback.print_exc()
                
                # These are safe to draw outside try-except
                level_text = self.big_font.render(f"LEVEL {self.current_level}", True, WHITE)
                level_bg = pygame.Surface((level_text.get_width()+30, level_text.get_height()+20))
                level_bg.fill(BLACK)
                level_bg.set_alpha(180)
                screen.blit(level_bg, (20, 15))
                screen.blit(level_text, (35, 20))
                
                timer_color = RED if self.time_left <= 10 else WHITE
                timer_bg_color = (100,0,0) if self.time_left <= 10 else (50,50,50)
                timer_text = self.big_font.render(f"⏱️ {self.time_left}s", True, timer_color)
                timer_bg = pygame.Surface((timer_text.get_width()+30, timer_text.get_height()+20))
                timer_bg.fill(timer_bg_color)
                timer_bg.set_alpha(200)
                screen.blit(timer_bg, (WIDTH - timer_text.get_width() - 45, 15))
                screen.blit(timer_text, (WIDTH - timer_text.get_width() - 30, 20))
                
                score_text = self.title_font.render(f"Score: {self.total_score}", True, GOLD)
                screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, 25))
                
                if self.message_timer > 0:
                    msg_surf = self.font.render(self.message, True, BLACK)
                    msg_width = msg_surf.get_width() + 30
                    msg_height = 50
                    msg_x = WIDTH//2 - msg_width//2
                    msg_y = 100
                    pygame.draw.rect(screen, WHITE, (msg_x, msg_y, msg_width, msg_height), border_radius=15)
                    pygame.draw.rect(screen, CUTE_YELLOW, (msg_x+3, msg_y+3, msg_width-6, msg_height-6), border_radius=12)
                    screen.blit(msg_surf, (WIDTH//2 - msg_surf.get_width()//2, msg_y + 15))
                
                draw_instruction_bar()
                
            elif self.state == LEVEL_COMPLETE:
                for particle in self.particles:
                    particle.draw(screen)
                complete_text = self.big_font.render(f"LEVEL {self.current_level} COMPLETE! 🎉", True, CUTE_GREEN)
                complete_bg = pygame.Surface((complete_text.get_width()+40, complete_text.get_height()+30))
                complete_bg.fill(BLACK)
                complete_bg.set_alpha(200)
                screen.blit(complete_bg, (WIDTH//2 - complete_text.get_width()//2 - 20, HEIGHT//2 - 80))
                screen.blit(complete_text, (WIDTH//2 - complete_text.get_width()//2, HEIGHT//2 - 70))
                bonus = self.time_left * 10
                bonus_text = self.title_font.render(f"Time Bonus: +{bonus} points", True, GOLD)
                screen.blit(bonus_text, (WIDTH//2 - bonus_text.get_width()//2, HEIGHT//2 - 10))
                total_text = self.title_font.render(f"Total Score: {self.total_score}", True, WHITE)
                screen.blit(total_text, (WIDTH//2 - total_text.get_width()//2, HEIGHT//2 + 30))
                if self.current_level < self.max_level:
                    next_text = self.font.render("Press SPACE or show ☝️ POINT gesture for next level", True, CYAN)
                    screen.blit(next_text, (WIDTH//2 - next_text.get_width()//2, HEIGHT//2 + 80))
                    
            elif self.state == WON:
                for particle in self.particles:
                    particle.draw(screen)
                win_text = self.big_font.render("🏆 YOU WON ALL LEVELS! 🏆", True, GOLD)
                win_bg = pygame.Surface((win_text.get_width()+40, win_text.get_height()+30))
                win_bg.fill(BLACK)
                win_bg.set_alpha(200)
                screen.blit(win_bg, (WIDTH//2 - win_text.get_width()//2 - 20, HEIGHT//2 - 80))
                screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 70))
                final_score = self.title_font.render(f"Final Score: {self.total_score}", True, CUTE_GREEN)
                screen.blit(final_score, (WIDTH//2 - final_score.get_width()//2, HEIGHT//2 + 10))
                restart_text = self.font.render("Press R or show ✌️ PEACE gesture to play again", True, CUTE_YELLOW)
                screen.blit(restart_text, (WIDTH//2 - restart_text.get_width()//2, HEIGHT//2 + 70))
                
            elif self.state == LOST:
                lose_text = self.big_font.render("⏰ TIME'S UP! ⏰", True, RED)
                lose_bg = pygame.Surface((lose_text.get_width()+40, lose_text.get_height()+30))
                lose_bg.fill(BLACK)
                lose_bg.set_alpha(200)
                screen.blit(lose_bg, (WIDTH//2 - lose_text.get_width()//2 - 20, HEIGHT//2 - 60))
                screen.blit(lose_text, (WIDTH//2 - lose_text.get_width()//2, HEIGHT//2 - 50))
                fail_text = self.title_font.render(f"You reached Level {self.current_level}", True, WHITE)
                screen.blit(fail_text, (WIDTH//2 - fail_text.get_width()//2, HEIGHT//2 + 20))
                restart_text = self.font.render("Press R or show ✌️ PEACE gesture to try again", True, CUTE_YELLOW)
                screen.blit(restart_text, (WIDTH//2 - restart_text.get_width()//2, HEIGHT//2 + 70))
            
            pygame.display.flip()

        def run(self):
            print("\n" + "="*70)
            print("🧩 PUZZLE ESCAPE GAME - 10 AMAZING LEVELS! 🧩")
            print("     🤚 NOW WITH GESTURE CONTROL! 🤚")
            print("="*70)
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif self.state == LEVEL_COMPLETE and event.key == pygame.K_SPACE:
                            self.next_level()
                        else:
                            self.handle_input(event.key)
                self.handle_gestures()
                self.update()
                self.draw()
                clock.tick(FPS)
            self._mp_sol.close()
            cv2.destroyAllWindows()

    game = Game()
    game.run()


# =============================================================================
#  ENTRY POINT
# =============================================================================
def main():
    try:
        while True:
            choice = run_launcher()
            if choice == 0:
                run_find_my_home()
            else:
                run_puzzle_escape()
    finally:
        release_camera()  # Clean up camera when program exits


if __name__ == "__main__":
    main()