import pygame
import sys
import math
import random
import cv2
import threading
import queue as _queue
import time as _time
from picamera2 import Picamera2 # Specific for Pi 5

pygame.init()

# ─────────────────────────────────────────────────────────────────────────────
#  LAUNCHER
# ─────────────────────────────────────────────────────────────────────────────
LAUNCH_W, LAUNCH_H = 900, 600

def run_launcher():
    import threading
    import queue as _queue

    try:
        import cv2
        import mediapipe as mp
        _GESTURE_OK = True
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

    _gq           = _queue.Queue()   
    _frame_queue = _queue.Queue(maxsize=1) 
    _g_running    = [True]
    _last_gesture = [""]             

    def _gesture_thread():
        if not _GESTURE_OK:
            return
        try:
            mp_hands  = mp.solutions.hands
            hands_sol = mp_hands.Hands(
                static_image_mode=False, max_num_hands=1,
                min_detection_confidence=0.65, min_tracking_confidence=0.65)
            
            # Pi 5 Picamera2 setup
            picam2 = Picamera2()
            config = picam2.create_preview_configuration(main={'size': (640, 480)})
            picam2.configure(config)
            picam2.start()

            swipe_start      = None
            swipe_start_time = 0.0
            pose_name        = None
            pose_start_time  = 0.0
            last_fire_time   = 0.0
            COOLDOWN         = 0.9   
            POSE_HOLD        = 0.6   

            import time as _time

            def count_fingers(lm):
                f = 0
                if lm[4].x < lm[3].x: f += 1
                for tip, pip in zip([8,12,16,20],[6,10,14,18]):
                    if lm[tip].y < lm[pip].y: f += 1
                return f

            def is_thumbs_up(lm):
                if lm[4].y > lm[0].y - 0.08: return False
                for tip, mcp in zip([8,12,16,20],[5,9,13,17]):
                    if lm[tip].y < lm[mcp].y: return False
                return True

            while _g_running[0]:
                frame_raw = picam2.capture_array()
                if frame_raw is None: continue
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = hands_sol.process(rgb)
                now = _time.time()
                action = None

                if result.multi_hand_landmarks:
                    for hl in result.multi_hand_landmarks:
                        lm = hl.landmark
                        fingers = count_fingers(lm)
                        if fingers == 0:
                            if pose_name != "fist":
                                pose_name = "fist"; pose_start_time = now
                                _last_gesture[0] = "✊ FIST"
                            elif now - pose_start_time >= POSE_HOLD:
                                action = "launch"; pose_name = None
                        elif is_thumbs_up(lm):
                            if pose_name != "thumb":
                                pose_name = "thumb"; pose_start_time = now
                                _last_gesture[0] = "👍 THUMB UP"
                            elif now - pose_start_time >= POSE_HOLD:
                                action = "launch"; pose_name = None
                        else:
                            pose_name = None
                            _last_gesture[0] = ""
                            tip_idx = 8
                            hp = (lm[tip_idx].x, lm[tip_idx].y)
                            if swipe_start is None:
                                swipe_start = hp; swipe_start_time = now
                            else:
                                dx = hp[0] - swipe_start[0]
                                dy = hp[1] - swipe_start[1]
                                dist    = math.sqrt(dx*dx + dy*dy)
                                elapsed = now - swipe_start_time
                                if dist > 0.20 and elapsed < 0.8 and abs(dx) > abs(dy) * 1.4:
                                    action      = "right" if dx > 0 else "left"
                                    swipe_start = hp; swipe_start_time = now
                                    _last_gesture[0] = ("👉 SWIPE RIGHT"
                                                         if action == "right"
                                                         else "👈 SWIPE LEFT")
                                elif elapsed > 1.2:
                                    swipe_start = hp; swipe_start_time = now

                        if action and now - last_fire_time > COOLDOWN:
                            _gq.put(action)
                            last_fire_time = now
                else:
                    swipe_start = None
                    pose_name   = None
                    _last_gesture[0] = ""

                cv2.putText(frame, "SWIPE L/R = Switch Game | FIST / THUMBS UP = Launch",
                            (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 100), 1)
                if _last_gesture[0]:
                    cv2.putText(frame, f">> {_last_gesture[0]} <<",
                                (frame.shape[1]//2 - 120, frame.shape[0]//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 200), 3)
                if not _frame_queue.full():
                    _frame_queue.put(frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            picam2.stop()
            hands_sol.close()
        except Exception as e:
            print(f"[LAUNCHER GESTURE] {e}")

    _gthread = threading.Thread(target=_gesture_thread, daemon=True)
    _gthread.start()

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
        {"rect": pygame.Rect(60, 170, 360, 290), "title": "Find My Home", "lines": ["Navigate maze levels home","10 hand-crafted levels","Minimap + gesture control","Swipe gestures to move"], "accent": CUTE_PINK, "index": 0},
        {"rect": pygame.Rect(480, 170, 360, 290), "title": "Puzzle Escape", "lines": ["Collect keys & flip switches","10 levels, beat the clock","Score time-bonus points","Swipe gestures to play"], "accent": CYAN, "index": 1},
    ]

    selected     = 0
    t            = 0.0
    launching    = False
    launch_idx   = 0
    launch_timer = 0
    _gest_flash  = 0   

    while True:
        try:
            cam_frame = _frame_queue.get_nowait()
            cv2.imshow("Gesture Control Feed", cam_frame)
            cv2.waitKey(1)
        except _queue.Empty:
            pass
            
        t += 0.04
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _g_running[0] = False
                pygame.quit(); sys.exit()

        while not _gq.empty():
            g = _gq.get()
            _gest_flash = 90   
            if not launching:
                if g == "left": selected = 0
                elif g == "right": selected = 1
                elif g == "launch":
                    launching = True
                    launch_idx = selected
                    launch_timer = 90

        if _gest_flash > 0: _gest_flash -= 1
        if launching:
            launch_timer -= 1
            if launch_timer <= 0:
                _g_running[0] = False
                cv2.destroyAllWindows()
                return launch_idx

        for sp in sparks:
            sp.update()
            if sp.life <= 0: sp.reset()

        for y in range(LAUNCH_H):
            r2 = int(8  + 20  * y / LAUNCH_H)
            g2 = int(8  + 12  * y / LAUNCH_H)
            b2 = int(22 + 40  * y / LAUNCH_H)
            pygame.draw.line(screen, (r2, g2, b2), (0, y), (LAUNCH_W, y))

        for st in stars:
            br = int(120 + 80 * math.sin(t * 0.8 + st.phase))
            pygame.draw.circle(screen, (br, br, br), (int(st.x), int(st.y)), max(1, int(st.sz)))

        for sp in sparks: sp.draw(screen)

        ts = font_title.render("GAME MODE", True, WHITE)
        for gi in range(3):
            gs = font_title.render("GAME MODE", True, NEON_PINK)
            screen.blit(gs, (LAUNCH_W//2 - ts.get_width()//2 - gi, 28 - gi))
        screen.blit(ts, (LAUNCH_W//2 - ts.get_width()//2, 28))
        sub = font_sub.render("Choose a game to play", True, GOLD)
        screen.blit(sub, (LAUNCH_W//2 - sub.get_width()//2, 92))

        for i, card in enumerate(cards):
            rect, accent, is_sel = card["rect"], card["accent"], (i == selected)
            if is_sel:
                for gi in range(5, 0, -1):
                    gr = rect.inflate(gi * 6, gi * 6)
                    gs = pygame.Surface((gr.width, gr.height), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*accent, max(0, 60 - gi * 10)), gs.get_rect(), border_radius=18)
                    screen.blit(gs, gr.topleft)
            cs = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            for row in range(rect.height):
                ratio = row / rect.height
                pygame.draw.line(cs, (int(25+20*ratio), int(20+15*ratio), int(45+30*ratio), 230), (0, row), (rect.width, row))
            screen.blit(cs, rect.topleft)
            bc = accent if is_sel else tuple(c // 2 for c in accent)
            pygame.draw.rect(screen, bc, rect, 3 if is_sel else 1, border_radius=16)
            bob = int(math.sin(t * 3) * 5) if is_sel else 0
            ct = font_card.render(card["title"], True, WHITE)
            screen.blit(ct, (rect.x + 20, rect.y + 18 + bob))
            pygame.draw.line(screen, accent, (rect.x + 20,  rect.y + 52 + bob), (rect.x + 20 + ct.get_width(), rect.y + 52 + bob), 2)
            for j, line in enumerate(card["lines"]):
                col = accent if is_sel else LIGHT_GRAY
                ls  = font_desc.render(f"  •  {line}", True, col)
                screen.blit(ls, (rect.x + 18, rect.y + 68 + j * 26 + bob))
            if is_sel:
                badge_txt = "SELECTED  ▶  Hold  ✊  or  👍  to launch"
                badge = font_hint.render(badge_txt, True, BLACK)
                bw, bh = badge.get_width() + 20, badge.get_height() + 10
                bx, by = rect.x + rect.width  // 2 - bw // 2, rect.y + rect.height - bh - 10 + bob
                pygame.draw.rect(screen, accent, (bx, by, bw, bh), border_radius=8)
                screen.blit(badge, (bx + 10, by + 5))

        bar_y = LAUNCH_H - 52
        bar_surf = pygame.Surface((LAUNCH_W, 52), pygame.SRCALPHA)
        bar_surf.fill((0, 0, 0, 140))
        screen.blit(bar_surf, (0, bar_y))
        guide_items = [("👈 Swipe Left", CUTE_PINK, "Select Find My Home"), ("👉 Swipe Right", CYAN, "Select Puzzle Escape"), ("✊ Fist  /  👍 Thumbs Up", NEON_GREEN, "Hold to Launch")]
        col_w = LAUNCH_W // len(guide_items)
        for idx, (sym, col, desc) in enumerate(guide_items):
            cx = col_w * idx + col_w // 2
            sym_s, desc_s = font_gest.render(sym, True, col), font_hint.render(desc, True, DIM_GRAY)
            screen.blit(sym_s, (cx - sym_s.get_width() // 2, bar_y + 6))
            screen.blit(desc_s, (cx - desc_s.get_width() // 2, bar_y + 30))

        if _gest_flash > 0 and _last_gesture[0]:
            fade = _gest_flash / 90
            fg_col = tuple(int(c * fade) for c in NEON_GREEN)
            gf = font_sub.render(f"Detected:  {_last_gesture[0]}", True, fg_col)
            screen.blit(gf, (LAUNCH_W//2 - gf.get_width()//2, bar_y - 30))

        if launching:
            progress = 1 - launch_timer / 90
            ov = pygame.Surface((LAUNCH_W, LAUNCH_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, int(220 * progress)))
            screen.blit(ov, (0, 0))
            if progress > 0.35:
                lname = cards[launch_idx]["title"]
                lt = font_title.render(f"Loading {lname} ...", True, NEON_GREEN)
                screen.blit(lt, (LAUNCH_W//2 - lt.get_width()//2, LAUNCH_H//2 - lt.get_height()//2))

        pygame.display.flip()
        clock.tick(60)

# =============================================================================
#  FIND MY HOME
# =============================================================================
def run_find_my_home():
    import time
    import threading
    import queue

    try:
        import cv2
        import mediapipe as mp
        GESTURE_AVAILABLE = True
    except (ImportError, AttributeError) as e:
        GESTURE_AVAILABLE = False

    SCREEN_W, SCREEN_H = 1100, 750
    TILE = 64
    FPS  = 60
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("✦ Find My Home ✦")
    clock = pygame.time.Clock()

    C_BG_TOP, C_BG_BOT = (10, 8, 30), (30, 15, 60)
    C_GRASS, C_GRASS_DARK = (30, 180, 90), (20, 140, 65)
    C_PATH, C_PATH_EDGE = (220, 185, 110), (180, 140, 70)
    C_WATER, C_WATER_GLOW = (40, 160, 230), (80, 200, 255)
    C_TREE_TRUNK, C_TREE_CROWN, C_TREE_HIGH = (100, 60, 20), (50, 200, 80), (120, 255, 100)
    C_ROCK, C_ROCK_DARK = (140, 130, 150), (90, 85, 100)
    C_HOME_WALL, C_HOME_ROOF, C_HOME_DOOR = (255, 90, 80), (200, 40, 40), (120, 40, 30)
    C_HOME_WIN, C_HOME_GLOW = (255, 240, 120), (255, 150, 50)
    C_PLAYER_BODY, C_PLAYER_FACE, C_PLAYER_GLOW = (255, 200, 60), (255, 225, 140), (255, 240, 100)
    C_UI_BG, C_UI_PANEL, C_UI_BORDER = (12, 8, 35, 210), (20, 14, 55, 230), (120, 80, 255)
    C_UI_ACCENT, C_UI_GOLD, C_UI_GREEN, C_UI_PINK = (80, 230, 255), (255, 210, 50), (80, 255, 150), (255, 80, 180)
    C_UI_TEXT, C_UI_MUTED = (220, 215, 255), (140, 130, 180)
    C_G_LEFT, C_G_RIGHT, C_G_UP, C_G_DOWN, C_G_RESTART = (255, 80, 100), (80, 200, 255), (100, 255, 150), (255, 200, 50), (200, 100, 255)

    LEVELS = [
        [[1,1,1,1,1,1,1,1,1,1],[1,3,7,7,0,0,0,0,2,1],[1,0,1,7,1,0,1,0,0,1],[1,0,1,7,7,7,1,0,0,1],[1,0,5,1,1,1,1,4,4,1],[1,0,0,0,0,0,1,4,4,1],[1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,0,0,0,2,1],[1,0,0,7,1,4,4,1,1,0,0,1],[1,1,0,7,7,7,7,7,1,0,1,1],[1,5,0,1,1,5,1,7,1,0,0,1],[1,0,0,0,0,0,0,7,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,1,4,4,4,1,0,0,0,2,1],[1,0,7,1,4,4,4,1,1,1,0,0,1],[1,0,7,7,7,7,7,7,7,1,0,1,1],[1,1,1,1,5,1,5,1,7,0,0,0,1],[1,0,0,0,0,0,0,0,7,1,1,0,1],[1,5,1,1,1,1,1,1,7,7,7,7,1],[1,0,0,0,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,1,0,0,0,2,1],[1,0,0,7,1,4,4,4,1,1,1,0,0,1],[1,1,0,7,1,4,4,4,0,0,1,1,0,1],[1,5,0,7,7,7,7,7,7,0,0,7,0,1],[1,1,1,1,1,5,1,1,7,1,0,7,1,1],[1,0,0,0,0,0,0,0,7,1,0,7,0,1],[1,0,1,1,1,1,1,1,7,7,7,7,0,1],[1,0,0,0,5,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,4,1,0,0,0,2,1],[1,0,0,7,1,4,4,4,4,1,1,1,0,0,1],[1,1,0,7,1,4,4,4,4,0,0,1,1,0,1],[1,5,0,7,7,7,7,7,7,7,0,0,7,0,1],[1,1,1,1,1,5,1,1,1,7,1,0,7,1,1],[1,0,0,0,0,0,0,0,0,7,1,0,7,0,1],[1,0,1,1,5,1,1,1,1,7,7,7,7,0,1],[1,0,0,0,0,0,0,0,0,1,1,1,1,0,1],[1,1,1,5,1,1,1,1,0,0,0,0,0,0,1],[1,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,1,0,0,0,0,0,0,0,2,1],[1,0,7,1,1,1,1,1,1,1,0,0,1],[1,0,7,7,7,7,7,1,4,1,0,1,1],[1,0,1,5,1,0,7,1,4,1,0,0,1],[1,0,1,0,1,0,7,7,7,1,1,0,1],[1,0,0,0,1,0,1,5,1,0,0,0,1],[1,1,1,1,1,0,0,0,1,1,1,1,1],[1,5,0,0,0,0,1,0,0,0,5,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,0,4,4,4,0,4,4,4,0,0,2,1],[1,0,0,4,0,4,0,4,0,4,7,0,0,1],[1,1,0,7,0,7,0,7,0,7,1,1,0,1],[1,5,0,4,0,4,0,4,0,4,0,5,0,1],[1,0,7,4,4,4,0,4,4,4,0,0,0,1],[1,0,7,7,7,7,7,7,7,7,7,1,0,1],[1,0,1,5,1,1,1,5,1,1,7,1,0,1],[1,0,0,0,0,0,0,0,0,0,7,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,7,7,7,7,7,7,7,7,2,1,1],[1,0,1,1,1,1,1,1,1,1,1,7,0,1,1],[1,0,1,5,5,5,5,5,5,5,1,7,0,1,1],[1,0,1,5,1,1,1,1,1,5,1,7,0,1,1],[1,0,1,5,1,4,4,4,1,5,1,7,0,1,1],[1,0,1,5,1,4,4,4,1,5,1,7,0,1,1],[1,0,1,5,1,1,1,1,1,5,1,7,0,1,1],[1,0,1,5,5,5,5,5,5,5,1,7,0,1,1],[1,0,1,1,1,1,1,1,1,1,1,7,0,1,1],[1,0,7,7,7,7,7,7,7,7,7,7,0,1,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,1,4,4,4,1,0,0,0,0,2,1],[1,0,1,7,1,4,4,4,1,1,1,1,0,0,1],[1,0,1,7,7,7,7,7,7,7,7,1,0,1,1],[1,0,1,1,1,5,1,7,1,5,7,1,0,0,1],[1,0,0,0,0,0,0,7,0,0,7,0,0,0,1],[1,1,1,5,1,1,1,7,1,1,7,1,5,1,1],[1,0,0,0,0,0,0,7,0,0,7,0,0,0,1],[1,0,1,1,1,1,1,7,7,7,7,1,1,0,1],[1,0,0,0,5,0,0,0,0,0,0,0,0,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
        [[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],[1,3,7,7,7,1,4,4,4,4,1,0,0,0,2,1],[1,0,1,1,7,1,4,4,4,4,1,1,1,0,0,1],[1,0,1,5,7,1,4,4,4,4,0,5,1,0,1,1],[1,0,1,0,7,7,7,7,7,7,7,0,1,0,0,1],[1,0,1,0,1,5,1,7,1,5,1,0,1,1,0,1],[1,0,1,0,0,0,0,7,0,0,1,0,0,0,0,1],[1,0,1,1,1,1,1,7,1,1,1,1,5,1,0,1],[1,0,0,0,5,0,0,7,0,0,0,0,0,1,0,1],[1,1,5,1,1,1,1,7,7,7,7,7,7,7,0,1],[1,0,0,0,0,0,0,1,1,1,1,1,1,7,0,1],[1,0,1,1,1,1,0,0,0,5,0,0,0,7,0,1],[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]],
    ]

    LEVEL_NAMES = ["The First Step","Watery Paths","Rocky Road","The Maze","Grand Finale","Zigzag Trail","Island Hopping","The Spiral","Crossroads","Grand Labyrinth"]
    LEVEL_COLORS = [C_UI_GREEN, C_UI_ACCENT, C_UI_GOLD, C_UI_PINK, (255,140,80), (100,255,220), (255,180,80), (180,100,255), (80,220,180), (255,80,80)]

    class Particle:
        def __init__(self, x, y, color, vx=None, vy=None, life=None, size=None):
            self.x, self.y, self.color = x, y, color
            self.vx, self.vy = vx if vx else random.uniform(-2, 2), vy if vy else random.uniform(-3, -0.5)
            self.life = life if life else random.uniform(0.4, 1.2)
            self.max_life, self.size = self.life, size if size else random.uniform(3, 8)
        def update(self, dt):
            self.x += self.vx; self.y += self.vy; self.vy += 0.08; self.life -= dt
            return self.life > 0
        def draw(self, surf):
            alpha = max(0, self.life / self.max_life)
            s = max(1, int(self.size * alpha))
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), s)

    particles = []
    def emit_particles(x, y, color, count=12):
        for _ in range(count): particles.append(Particle(x, y, color))
    stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H), random.uniform(0.5, 2.5), random.random()*6.28) for _ in range(120)]
    def draw_stars(t):
        for sx, sy, sz, phase in stars:
            br = int(160 + 80 * math.sin(t * 1.5 + phase))
            pygame.draw.circle(screen, (br, br, int(br*0.85)), (sx, sy), max(1, int(sz*0.6)))

    gesture_queue, gesture_running = queue.Queue(), [True]
    last_gesture, last_gesture_time, current_detected_gesture = [""], [0.0], [""]

    class GestureDetector:
        def __init__(self):
            if not GESTURE_AVAILABLE: self.available = False; return
            try:
                self.mp_hands = mp.solutions.hands
                self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.6, min_tracking_confidence=0.6)
                self.mp_draw = mp.solutions.drawing_utils
                self.picam2 = None
                self.prev_pos, self.swipe_start, self.swipe_start_time = None, None, 0.0
                self.swipe_cooldown, self.last_action_time, self.trail = 0.8, 0.0, []
                self._pose_start_gesture, self._pose_start_time = None, 0.0
                self.available = True
            except Exception: self.available = False

        def start(self):
            if not self.available: return False
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(main={'size': (640, 480)})
                self.picam2.configure(config)
                self.picam2.start()
                threading.Thread(target=self._loop, daemon=True).start()
                return True
            except: return False

        def _loop(self):
            while gesture_running[0]:
                frame_raw = self.picam2.capture_array()
                if frame_raw is None: continue
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
                        px_x, px_y = int(tip.x * w), int(tip.y * h)
                        fingers = self._count_fingers(hl.landmark)
                        self.trail.append((px_x, px_y, now))
                        self.trail = [(x,y,t) for x,y,t in self.trail if now-t < 0.5]
                        self.mp_draw.draw_landmarks(frame, hl, self.mp_hands.HAND_CONNECTIONS)
                        action = None
                        if fingers == 0:
                            if self._pose_start_gesture != "fist": self._pose_start_gesture, self._pose_start_time = "fist", now
                            elif now - self._pose_start_time >= 0.3: action, self._pose_start_gesture = "up", None
                        elif fingers >= 5:
                            if self._pose_start_gesture != "palm": self._pose_start_gesture, self._pose_start_time = "palm", now
                            elif now - self._pose_start_time >= 0.3: action, self._pose_start_gesture = "down", None
                        elif fingers == 2:
                            if self._pose_start_gesture != "peace": self._pose_start_gesture, self._pose_start_time = "peace", now
                            elif now - self._pose_start_time >= 0.4: action, self._pose_start_gesture = "restart", None
                        elif self._is_thumbs_up(hl.landmark):
                            if self._pose_start_gesture != "thumbs_up": self._pose_start_gesture, self._pose_start_time = "thumbs_up", now
                            elif now - self._pose_start_time >= 0.5: action, self._pose_start_gesture = "next", None
                        else:
                            self._pose_start_gesture = None
                            if self.swipe_start is None: self.swipe_start, self.swipe_start_time = hand_pos, now
                            else:
                                dx, dy = hand_pos[0] - self.swipe_start[0], hand_pos[1] - self.swipe_start[1]
                                dist, elapsed = math.sqrt(dx*dx + dy*dy), now - self.swipe_start_time
                                if dist > 0.22 and elapsed < 0.8 and abs(dx) > abs(dy) * 1.5:
                                    action = "right" if dx > 0 else "left"
                                    self.swipe_start, self.swipe_start_time = hand_pos, now
                                elif elapsed > 1.2: self.swipe_start, self.swipe_start_time = hand_pos, now
                        if action and now - self.last_action_time > self.swipe_cooldown:
                            gesture_queue.put(action)
                            last_gesture[0], last_gesture_time[0] = action, now
                            self.last_action_time, current_detected_gesture[0] = now, action
                        elif action: current_detected_gesture[0] = action
                else:
                    self.swipe_start, self._pose_start_gesture, self.trail, current_detected_gesture[0] = None, None, [], ""
                cv2.imshow("Gesture Control", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
            self.picam2.stop()

        def _count_fingers(self, landmarks):
            f = 0
            if landmarks[4].x < landmarks[3].x: f += 1
            for tip, pip in zip([8,12,16,20], [6,10,14,18]):
                if landmarks[tip].y < landmarks[pip].y: f += 1
            return f

        def _is_thumbs_up(self, landmarks):
            if landmarks[4].y > landmarks[0].y - 0.08: return False
            for tip, mcp in zip([8,12,16,20], [5,9,13,17]):
                if landmarks[tip].y < landmarks[mcp].y: return False
            return True

        def stop(self):
            gesture_running[0] = False
            try: cv2.destroyAllWindows()
            except: pass

    class Player:
        def __init__(self, x, y, lm):
            self.x, self.y, self.tx, self.ty, self.moving, self.level_map, self.facing, self.step, self.trail_positions = x, y, x, y, False, lm, 1, 0.0, []
        def move(self, dx, dy):
            gx, gy = int((self.x + dx * TILE) // TILE), int((self.y + dy * TILE) // TILE)
            if self.level_map[gy][gx] not in [1, 4, 5]:
                self.trail_positions.append((self.x + TILE//2, self.y + TILE//2))
                if len(self.trail_positions) > 20: self.trail_positions.pop(0)
                self.tx += dx * TILE; self.ty += dy * TILE; self.moving = True
                if dx != 0: self.facing = dx
                return self.level_map[gy][gx] == 2
            return False
        def update(self, dt):
            if self.moving:
                self.step += dt * 8
                self.x += (self.tx - self.x) * 0.22; self.y += (self.ty - self.y) * 0.22
                if abs(self.x - self.tx) < 1 and abs(self.y - self.ty) < 1: self.x, self.y, self.moving = self.tx, self.ty, False
        def draw(self, ox, oy):
            t = pygame.time.get_ticks() / 1000
            bob = math.sin(t * 3.5) * 4 if not self.moving else math.sin(self.step * 4) * 5
            cx, cy = int(self.x + TILE//2 + ox), int(self.y + TILE//2 + oy + bob)
            for i, (px, py) in enumerate(self.trail_positions[-8:]):
                af = (i + 1) / 8; s = max(2, int(8 * af))
                tc = (int(C_PLAYER_GLOW[0]*af), int(C_PLAYER_GLOW[1]*af*0.5), int(50*af))
                pygame.draw.circle(screen, tc, (int(px + ox), int(py + oy)), s)
            gr = int(28 + 4 * math.sin(t * 4))
            for g in range(3, 0, -1): pygame.draw.circle(screen, C_PLAYER_GLOW, (cx, cy), gr + g * 4)
            pygame.draw.ellipse(screen, (0,0,0), (cx-18, cy+18, 36, 10))
            pygame.draw.circle(screen, C_PLAYER_BODY, (cx, cy), 22)
            pygame.draw.circle(screen, C_PLAYER_FACE, (cx, cy - 2), 15)
            ex = 5 * self.facing
            pygame.draw.circle(screen, (40,30,80), (cx+ex-3, cy-5), 4)
            pygame.draw.circle(screen, (40,30,80), (cx+ex+5, cy-5), 4)
            pygame.draw.circle(screen, (255,255,255), (cx+ex-2, cy-6), 1)
            pygame.draw.circle(screen, (255,255,255), (cx+ex+6, cy-6), 1)
            pygame.draw.arc(screen, (100,60,30), (cx-7, cy, 14, 9), 3.14, 6.28, 2)
            px_val = cx - self.facing * 20
            pygame.draw.rect(screen, (180,100,40), (px_val-6, cy-8, 12, 18), border_radius=3)
            pygame.draw.rect(screen, (220,140,60), (px_val-4, cy-6, 8, 6), border_radius=2)

    class FancyButton:
        def __init__(self, x, y, w, h, text, color=None, fs=30):
            self.rect, self.text, self.font, self.color, self.hovered, self._phase = pygame.Rect(x, y, w, h), text, pygame.font.Font(None, fs), color or C_UI_BORDER, False, random.random() * 6.28
        def draw(self, surf):
            t = pygame.time.get_ticks() / 1000
            pulse = 0.5 + 0.5 * math.sin(t * 3 + self._phase)
            if self.hovered:
                for g in range(4, 0, -1):
                    gr = self.rect.inflate(g*4, g*4)
                    s = pygame.Surface((gr.width, gr.height), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*self.color[:3], int(40*pulse)), s.get_rect(), border_radius=12)
                    surf.blit(s, gr.topleft)
            bg = tuple(min(255, int(c * (1.3 if self.hovered else 1.0))) for c in self.color[:3])
            inner = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            inner.fill((20, 15, 50, 220)); surf.blit(inner, self.rect.topleft)
            pygame.draw.rect(surf, bg, self.rect, 3, border_radius=10)
            txt = self.font.render(self.text, True, (230, 225, 255))
            surf.blit(txt, txt.get_rect(center=self.rect.center))
        def check_hover(self, pos): self.hovered = self.rect.collidepoint(pos)
        def is_clicked(self, pos): return self.rect.collidepoint(pos)

    def draw_tile(t, tx, ty, ox, oy):
        px, py = tx * TILE + ox, ty * TILE + oy
        r, tv = pygame.Rect(px, py, TILE, TILE), pygame.time.get_ticks() / 1000
        if t == 0:
            pygame.draw.rect(screen, C_GRASS, r)
            for i in range(3): pygame.draw.circle(screen, C_GRASS_DARK, (px + 10 + i*18 + int(math.sin(tx+ty+i)*3), py + 8 + int(math.cos(tx*2+i)*4)), 2)
        elif t == 7:
            pygame.draw.rect(screen, C_PATH, r); pygame.draw.rect(screen, C_PATH_EDGE, r, 2)
        elif t == 1:
            pygame.draw.rect(screen, C_GRASS_DARK, r); pygame.draw.rect(screen, C_TREE_TRUNK, (px+28, py+40, 8, 20), border_radius=3)
            pygame.draw.circle(screen, C_TREE_CROWN, (px+32, py+28), 22); pygame.draw.circle(screen, C_TREE_HIGH, (px+32, py+22), 14)
        elif t == 4:
            pygame.draw.rect(screen, C_WATER, r)
            for wi in range(3):
                wy = py + 10 + wi * 18 + int(math.sin(tv * 2 + tx * 0.8) * 3)
                if py <= wy <= py + TILE: pygame.draw.line(screen, C_WATER_GLOW, (px+4, wy), (px+TILE-4, wy), 2)
        elif t == 5:
            pygame.draw.rect(screen, C_GRASS, r); pygame.draw.ellipse(screen, C_ROCK, (px+12, py+22, 40, 28)); pygame.draw.ellipse(screen, C_ROCK_DARK, (px+14, py+24, 36, 24))
        elif t == 2:
            pygame.draw.rect(screen, C_GRASS, r); pygame.draw.rect(screen, C_HOME_WALL, (px+10, py+26, 44, 34), border_radius=3)
            pygame.draw.polygon(screen, C_HOME_ROOF, [(px+32, py+6),(px+6, py+30),(px+58, py+30)])
            pygame.draw.rect(screen, C_HOME_DOOR, (px+26, py+40, 12, 20), border_radius=2)
        elif t == 3:
            pygame.draw.rect(screen, C_GRASS, r)
            for i in range(4):
                ang = tv * 2 + i * math.pi / 2
                pygame.draw.circle(screen, C_UI_GOLD, (px + 32 + int(math.cos(ang) * 6), py + 32 + int(math.sin(ang) * 6)), 3)

    def draw_map(lm):
        rows, cols = len(lm), len(lm[0])
        ox, oy = (SCREEN_W - cols * TILE) // 2, (SCREEN_H - rows * TILE) // 2 + 10
        for y, row in enumerate(lm):
            for x, t in enumerate(row): draw_tile(t, x, y, ox, oy)
        return ox, oy

    _bg_surf = [None]
    def draw_background():
        if _bg_surf[0] is None:
            _bg_surf[0] = pygame.Surface((SCREEN_W, SCREEN_H))
            for y in range(SCREEN_H):
                t2 = y / SCREEN_H
                pygame.draw.line(_bg_surf[0], (int(C_BG_TOP[0]*(1-t2)+C_BG_BOT[0]*t2), int(C_BG_TOP[1]*(1-t2)+C_BG_BOT[1]*t2), int(C_BG_TOP[2]*(1-t2)+C_BG_BOT[2]*t2)), (0, y), (SCREEN_W, y))
        screen.blit(_bg_surf[0], (0, 0))

    def draw_top_hud(st, cl, tl):
        el, t = int(time.time() - st), pygame.time.get_ticks() / 1000
        hud = pygame.Surface((SCREEN_W, 68), pygame.SRCALPHA); hud.fill((8, 5, 25, 200))
        pygame.draw.line(hud, (*C_UI_BORDER, 160), (0, 67), (SCREEN_W, 67), 1)
        screen.blit(hud, (0, 0))
        fl, fs, fxs = pygame.font.Font(None, 38), pygame.font.Font(None, 22), pygame.font.Font(None, 18)
        screen.blit(fl.render(f"{el//60:02}:{el%60:02}", True, C_UI_ACCENT), (30, 28))
        screen.blit(fl.render(f"{cl + 1}", True, LEVEL_COLORS[cl % len(LEVEL_COLORS)]), (180, 28))
        screen.blit(fs.render(LEVEL_NAMES[cl % len(LEVEL_NAMES)], True, C_UI_GOLD), (340, 30))

    def draw_minimap(pl, lm, oxm, oym):
        sc, rows, cols = 9, len(lm), len(lm[0])
        mmw, mmh = cols * sc, rows * sc
        mmx, mmy = SCREEN_W - mmw - 18, 80
        pygame.draw.rect(screen, (8, 5, 25, 210), (mmx - 6, mmy - 20, mmw + 12, mmh + 28), border_radius=8)
        for y, row in enumerate(lm):
            for x, t in enumerate(row):
                col = {0: C_GRASS_DARK, 1: (30,90,30), 4: C_WATER, 7: C_PATH, 2: C_HOME_GLOW, 5: C_ROCK, 3: C_UI_GOLD}.get(t, (60,60,60))
                pygame.draw.rect(screen, col, (mmx + x*sc, mmy + y*sc, sc-1, sc-1))
        pygame.draw.circle(screen, (255,255,255), (mmx + int(pl.x // TILE) * sc + sc//2, mmy + int(pl.y // TILE) * sc + sc//2), 2)

    def draw_win_screen(et, cl, tl):
        t, is_final = pygame.time.get_ticks() / 1000, (cl >= tl - 1)
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); ov.fill((0, 0, 0, 130)); screen.blit(ov, (0, 0))
        pw, ph = 640, 380; px, py = (SCREEN_W - pw) // 2, (SCREEN_H - ph) // 2
        pygame.draw.rect(screen, (10, 7, 32, 245), (px, py, pw, ph), border_radius=16)
        fxl = pygame.font.Font(None, 72); fm = pygame.font.Font(None, 30)
        title = fxl.render("YOU MADE IT HOME!" if is_final else "LEVEL CLEAR!", True, C_UI_GOLD)
        screen.blit(title, title.get_rect(center=(SCREEN_W//2, py + 65)))
        if is_final: b1, b2 = FancyButton(SCREEN_W//2 - 200, py+270, 180, 52, "Play Again", C_UI_GREEN), FancyButton(SCREEN_W//2 + 20, py+270, 180, 52, "Quit", C_G_LEFT)
        else: b1, b2 = FancyButton(SCREEN_W//2 - 210, py+270, 200, 52, "Next Level ▶", LEVEL_COLORS[(cl+1)%len(LEVEL_COLORS)]), FancyButton(SCREEN_W//2 + 30, py+270, 180, 52, "Quit", C_G_LEFT)
        return b1, b2

    def find_start(lm):
        for y, row in enumerate(lm):
            for x, t in enumerate(row):
                if t == 3: return float(x * TILE), float(y * TILE)
        return 0.0, 0.0

    gd = GestureDetector()
    if GESTURE_AVAILABLE and gd.available: gd.start()
    current_level, total_levels = 0, len(LEVELS)
    level_map = LEVELS[current_level]
    px, py = find_start(level_map)
    player = Player(px, py, level_map)
    start_time, won, prev_time = time.time(), False, time.time()

    running = True
    while running:
        now, dt = time.time(), time.time() - prev_time; prev_time = now
        mouse_pos = pygame.mouse.get_pos(); clock.tick(FPS)
        for e in pygame.event.get():
            if e.type == pygame.QUIT: gesture_running[0], running = False, False; break
            if e.type == pygame.MOUSEBUTTONDOWN and won:
                if btn1.is_clicked(mouse_pos): current_level, won = (current_level + 1) % total_levels, False; level_map = LEVELS[current_level]; px, py = find_start(level_map); player = Player(px, py, level_map); start_time = time.time()
                if btn2.is_clicked(mouse_pos): gesture_running[0], running = False, False; break
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: gesture_running[0], running = False, False; break
                if not won and not player.moving:
                    m = False
                    if e.key == pygame.K_LEFT: m = player.move(-1, 0)
                    elif e.key == pygame.K_RIGHT: m = player.move(1, 0)
                    elif e.key == pygame.K_UP: m = player.move(0, -1)
                    elif e.key == pygame.K_DOWN: m = player.move(0, 1)
                    if m: won, win_time = True, int(time.time() - start_time)

        while not gesture_queue.empty():
            g = gesture_queue.get()
            if g == "next" and won: current_level, won = (current_level + 1) % total_levels, False; level_map = LEVELS[current_level]; px, py = find_start(level_map); player = Player(px, py, level_map); start_time = time.time(); continue
            if not won and not player.moving:
                m = False
                if g == "left": m = player.move(-1, 0)
                elif g == "right": m = player.move(1, 0)
                elif g == "up": m = player.move(0, -1)
                elif g == "down": m = player.move(0, 1)
                if m: won, win_time = True, int(time.time() - start_time)

        player.update(dt)
        draw_background(); draw_stars(now); ox, oy = draw_map(level_map); player.draw(ox, oy); draw_top_hud(start_time, current_level, total_levels); draw_minimap(player, level_map, ox, oy)
        if won: btn1, btn2 = draw_win_screen(win_time, current_level, total_levels); btn1.check_hover(mouse_pos); btn2.check_hover(mouse_pos); btn1.draw(screen); btn2.draw(screen)
        pygame.display.flip()
    gd.stop()

# =============================================================================
#  PUZZLE ESCAPE
# =============================================================================
def run_puzzle_escape():
    import cv2
    WIDTH, HEIGHT = 900, 650
    FPS = 60
    WHITE, BLACK, GOLD, CYAN = (255, 255, 255), (0, 0, 0), (255, 215, 0), (100, 200, 255)
    CUTE_PINK, CUTE_BLUE, CUTE_GREEN, CUTE_YELLOW, CUTE_PURPLE, CUTE_ORANGE = (255, 182, 193), (173, 216, 230), (144, 238, 144), (255, 255, 153), (216, 191, 216), (255, 200, 150)
    DARK_GRAY, LIGHT_GRAY, RED, ORANGE = (70, 70, 70), (200, 200, 200), (255, 100, 100), (255, 165, 0)
    PLAYING, WON, LOST, LEVEL_COMPLETE = 0, 1, 2, 3

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("🧩 Puzzle Escape")
    clock = pygame.time.Clock()

    class Particle:
        def __init__(self, x, y, color):
            self.x, self.y, self.color, self.life = x, y, color, 60
            self.vx, self.vy = random.uniform(-2, 2), random.uniform(-3, -1)
        def update(self): self.x += self.vx; self.y += self.vy; self.vy += 0.1; self.life -= 1
        def draw(self, s):
            if self.life > 0: pygame.draw.circle(s, self.color, (int(self.x), int(self.y)), int(5 * (self.life/60)))

    class Player:
        def __init__(self, x, y):
            self.x, self.y, self.tx, self.ty, self.color, self.bo = x, y, x, y, CUTE_PINK, 0.0
        def move_to(self, x, y): self.tx, self.ty = x, y
        def update(self):
            self.x += (self.tx - self.x) * 0.15; self.y += (self.ty - self.y) * 0.15; self.bo += 0.1
        def draw(self, s):
            b = math.sin(self.bo) * 4
            pygame.draw.circle(s, BLACK, (int(self.x), int(self.y+b)), 47); pygame.draw.circle(s, self.color, (int(self.x), int(self.y+b)), 45)

    class Item:
        def __init__(self, x, y, it, name): self.x, self.y, self.type, self.name, self.collected, self.fo = x, y, it, name, False, random.uniform(0, 6.28)
        def update(self): self.fo += 0.08
        def draw(self, s, f):
            if not self.collected:
                fy = self.y + math.sin(self.fo) * 6
                pygame.draw.circle(s, GOLD, (self.x, int(fy)), 12)

    class Switch:
        def __init__(self, x, y, name): self.x, self.y, self.name, self.activated, self.p = x, y, name, False, 0.0
        def update(self): self.p += 0.1
        def draw(self, s, f):
            col = CUTE_GREEN if self.activated else RED
            pygame.draw.circle(s, col, (self.x, self.y+22), 14)

    class Door:
        def __init__(self, x, y): self.x, self.y, self.locked, self.op = x, y, True, 0.0
        def unlock(self): self.locked = False
        def update(self):
            if not self.locked and self.op < 1: self.op += 0.04
        def draw(self, s, f):
            pygame.draw.rect(s, CYAN if not self.locked else DARK_GRAY, (self.x, self.y, 90 * (1-self.op), 140))

    class Game:
        def __init__(self):
            self.font, self.big_font = pygame.font.Font(None, 22), pygame.font.Font(None, 56)
            self.particles, self.current_level, self.total_score = [], 1, 0
            self.picam2 = Picamera2()
            config = self.picam2.create_preview_configuration(main={'size': (640, 480)})
            self.picam2.configure(config)
            self.picam2.start()
            self._mp_sol = mp.solutions.hands.Hands(min_detection_confidence=0.7)
            self.reset_game()

        def reset_game(self):
            self.state = PLAYING
            cfg = {1:{'time':60,'kp':[0],'sp':[],'dp':1}, 2:{'time':55,'kp':[0,1],'sp':[],'dp':2}, 3:{'time':50,'kp':[0],'sp':[1],'dp':2}, 4:{'time':50,'kp':[0,2],'sp':[1],'dp':3}, 5:{'time':45,'kp':[0,2],'sp':[1,3],'dp':4}, 6:{'time':45,'kp':[0,2,3],'sp':[1],'dp':4}, 7:{'time':40,'kp':[0,2,4],'sp':[1,3],'dp':5}, 8:{'time':40,'kp':[0,1,3,4],'sp':[2,5],'dp':6}, 9:{'time':35,'kp':[0,2,4],'sp':[1,3,5],'dp':6}, 10:{'time':30,'kp':[0,2,4,5],'sp':[1,3,6],'dp':7}}[self.current_level]
            self.time_left, self.pos = cfg['time'], [(450,400),(700,400),(200,380),(450,380),(700,380),(200,350),(450,350),(700,400),(180,320),(350,320),(520,320),(700,420),(200,280),(350,350),(500,280),(650,350),(750,450),(180,300),(320,380),(450,300),(580,380),(720,450)]
            self.player = Player(450, 400); self.items = [Item(self.pos[i][0], self.pos[i][1], "key", "K") for i in cfg['kp']]
            self.switches = [Switch(self.pos[i][0], self.pos[i][1], "S") for i in cfg['sp']]; self.door = Door(600, 300); self.cp = 0

        def handle_gestures(self):
            fr = self.picam2.capture_array()
            if fr is None: return
            frame = cv2.flip(cv2.cvtColor(fr, cv2.COLOR_BGRA2BGR), 1)
            res = self._mp_sol.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0].landmark
                f = 0
                if lm[4].x < lm[3].x: f += 1
                for t, p in zip([8,12,16,20],[6,10,14,18]):
                    if lm[t].y < lm[p].y: f += 1
                if f == 0: self.try_pick_up()
                elif f == 1: self.try_activate()
                elif f >= 5: self.try_open_door()
            cv2.imshow('Gestures', frame); cv2.waitKey(1)

        def try_pick_up(self):
            for i in self.items:
                if not i.collected and abs(i.x - self.player.x) < 50: i.collected = True
        def try_activate(self):
            for s in self.switches:
                if not s.activated and abs(s.x - self.player.x) < 50: s.activated = True
        def try_open_door(self):
            if all(i.collected for i in self.items) and all(s.activated for s in self.switches): self.door.unlock()

        def update(self):
            if self.state != PLAYING: return
            self.time_left -= 1/60
            if self.time_left <= 0: self.state = LOST
            self.player.update(); self.door.update()
            if not self.door.locked and abs(self.door.x - self.player.x) < 50: self.state = LEVEL_COMPLETE

        def draw(self):
            screen.fill((135, 206, 235)); self.player.draw(screen); self.door.draw(screen, self.font)
            for i in self.items: i.draw(screen, self.font)
            for s in self.switches: s.draw(screen, self.font)
            pygame.display.flip()

        def run(self):
            r = True
            while r:
                for e in pygame.event.get():
                    if e.type == pygame.QUIT: r = False
                    if e.type == pygame.KEYDOWN and e.key == pygame.K_RIGHT: self.player.tx += 50
                    if e.type == pygame.KEYDOWN and e.key == pygame.K_LEFT: self.player.tx -= 50
                self.handle_gestures(); self.update(); self.draw(); clock.tick(FPS)
            self.picam2.stop()

    Game().run()

def main():
    while True:
        c = run_launcher()
        if c == 0: run_find_my_home()
        else: run_puzzle_escape()

if __name__ == "__main__":
    main()