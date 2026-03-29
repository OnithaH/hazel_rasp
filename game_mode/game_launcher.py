"""
GAME LAUNCHER - Gesture-controlled game selection menu
"""

import pygame
import sys
import math
import random
import cv2
import threading
import queue
import time
from camera_manager import get_camera, release_camera
from gesture_controller import GestureController


# Global camera instance - SHARED ACROSS ALL MODES
_global_camera = None
_camera_lock = threading.Lock()


pygame.init()

LAUNCH_W, LAUNCH_H = 900, 600

def run_launcher():
    """
    Gesture-controlled launcher with fixed camera handling.
    Returns 0 = Find My Home, 1 = Puzzle Escape
    """
    # The physical LCD display size
    real_screen = pygame.display.set_mode((640, 480))
    # The virtual surface where everything is actually drawn
    screen = pygame.Surface((LAUNCH_W, LAUNCH_H))
    pygame.display.set_caption("Game Launcher - Select a Game")
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

    # background gesture thread
    _gq           = queue.Queue()
    _g_running    = [True]
    _last_gesture = [""]

    # Initialize Camera directly in main thread
    controller = GestureController()
    picam2 = get_camera()
    if picam2:
        controller.set_camera(picam2)
        #cv2.namedWindow('Gesture Control', cv2.WINDOW_NORMAL)
        #cv2.resizeWindow('Gesture Control', 640, 480)
        #cv2.moveWindow('Gesture Control', 100, 100)
    last_action_time = 0
    COOLDOWN = 0.6



    # UI data
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

        if picam2 and controller:
            try:
                frame_raw = picam2.capture_array()
                if frame_raw is not None:
                    frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                    frame = cv2.flip(frame, 1)
                    
                    gesture = controller.detect_gesture(frame)
                    fingers = controller.get_fingers_count(frame)
                    now = time.time()
                    
                    if gesture and now - last_action_time > COOLDOWN:
                        _gest_flash = 90
                        if not launching:
                            if gesture == "swipe_left":
                                selected = 0
                                _last_gesture[0] = "SELECTED: Find My Home"
                                last_action_time = now
                            elif gesture == "swipe_right":
                                selected = 1
                                _last_gesture[0] = "SELECTED: Puzzle Escape"
                                last_action_time = now
                            elif gesture in ("up", "next", "fist", "thumbs_up", "thumbs-up"):
                                launching = True
                                launch_idx = selected
                                launch_timer = 90
                                _last_gesture[0] = "LAUNCHING!"
                                last_action_time = now

                    #frame = controller.draw_ui(frame, gesture, fingers)
                    #cv2.imshow("Gesture Control", frame)
                    #cv2.waitKey(1)
            except Exception as e:
                pass

        # pygame events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                _g_running[0] = False
                pygame.quit()
                sys.exit()

        if _gest_flash > 0:
            _gest_flash -= 1

        # launch countdown
        if launching:
            print(f"[LAUNCHER] Launch countdown: {launch_timer}")
            launch_timer -= 1
            if launch_timer <= 0:
                print(f"[LAUNCHER] Returning game index: {launch_idx}")
                cv2.destroyAllWindows()
                time.sleep(1)
                return launch_idx

        # update sparks
        for sp in sparks:
            sp.update()
            if sp.life <= 0:
                sp.reset()

        # draw background
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

        # title
        ts = font_title.render("GAME MODE", True, WHITE)
        for gi in range(3):
            gs = font_title.render("GAME MODE", True, NEON_PINK)
            screen.blit(gs, (LAUNCH_W//2 - ts.get_width()//2 - gi, 28 - gi))
        screen.blit(ts, (LAUNCH_W//2 - ts.get_width()//2, 28))
        sub = font_sub.render("Choose a game to play", True, GOLD)
        screen.blit(sub, (LAUNCH_W//2 - sub.get_width()//2, 92))

        # cards
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

        # gesture guide bar at the bottom
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

        # live gesture feedback flash
        if _gest_flash > 0 and _last_gesture[0]:
            fade  = _gest_flash / 90
            fg_col = tuple(int(c * fade) for c in NEON_GREEN)
            gf = font_sub.render(f"Detected:  {_last_gesture[0]}", True, fg_col)
            screen.blit(gf, (LAUNCH_W//2 - gf.get_width()//2, bar_y - 30))

        # launch fade overlay
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
                cv2.destroyAllWindows()
                time.sleep(1)
                return launch_idx
                
        # Scale the virtual screen to physical LCD size
        scaled_surf = pygame.transform.scale(screen, (640, 480))
        real_screen.blit(scaled_surf, (0, 0))
        
        pygame.display.flip()
        clock.tick(60)


def main():
    """Entry point for launcher - returns selected game index"""
    return run_launcher()


if __name__ == "__main__":
    choice = main()
    print(f"[LAUNCHER] Exited with choice: {choice}")