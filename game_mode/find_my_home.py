"""
FIND MY HOME - Maze navigation game with gesture controls
"""
import queue
import pygame
import sys
import math
import random
import time
import threading
import cv2
from camera_manager import get_camera as get_shared_camera
from gesture_controller import GestureController

# Global camera reference
_global_camera = None

def set_camera(camera):
    """Set the camera instance from main"""
    global _global_camera
    _global_camera = camera
    print(f"[FIND MY HOME] Camera set: {camera is not None}")

def get_camera():
    """Get the camera instance"""
    global _global_camera
    if _global_camera is None:
        print("[FIND MY HOME] No camera set, getting from camera_manager")
        _global_camera = get_shared_camera()
    return _global_camera

pygame.init()

SCREEN_W, SCREEN_H = 1100, 750
TILE = 64
FPS = 60

# Colors
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
    def draw(self, ox, oy, screen):
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

def run_find_my_home():
    real_screen = pygame.display.set_mode((640, 480))
    screen = pygame.Surface((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("✦ Find My Home ✦")
    clock = pygame.time.Clock()
    
    # Get camera from global and restart it if needed
    picam2 = get_camera()
    print(f"[FIND MY HOME] Camera obtained: {picam2 is not None}")
    
    # If camera exists but is stopped, restart it
    if picam2:
        try:
            # Check if camera is still running
            picam2.start()
            time.sleep(1)
            print("[FIND MY HOME] Camera restarted")
        except Exception as e:
            print(f"[FIND MY HOME] Camera restart error: {e}")
    
    # Gesture setup
    controller = None
    if picam2:
        try:
            controller = GestureController()
            controller.set_camera(picam2)
            #cv2.namedWindow('Gesture Control - Find My Home', cv2.WINDOW_NORMAL)
            #cv2.resizeWindow('Gesture Control - Find My Home', 640, 480)
            #cv2.moveWindow('Gesture Control - Find My Home', 100, 100)
            print("[FIND MY HOME] Gesture control ready")
        except Exception as e:
            print(f"[FIND MY HOME] Gesture setup error: {e}")
    
    def emit_particles(x, y, color, count=12):
        for _ in range(count):
            particles.append(Particle(x, y, color))
    
    def draw_stars(t):
        for sx, sy, sz, phase in stars:
            brightness = int(160 + 80 * math.sin(t * 1.5 + phase))
            col = (brightness, brightness, int(brightness * 0.85))
            pygame.draw.circle(screen, col, (sx, sy), max(1, int(sz * 0.6)))
    
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
    
    last_gesture = [""]
    last_gesture_time = [0.0]
    current_detected_gesture = [""]
    
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
    
    def draw_minimap(player, level_map):
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
    
    def draw_instruction_bar():
        bar_y = SCREEN_H - 80
        bar_h = 60
        bar_surf = pygame.Surface((SCREEN_W, bar_h), pygame.SRCALPHA)
        bar_surf.fill((0, 0, 0, 180))
        screen.blit(bar_surf, (0, bar_y))
        
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
    print("✓ Gesture control ready — SWIPE to move!")
    print("⌨  Arrow Keys  |  R = Restart  |  ESC = Back to Launcher\n")
    
    current_level = 0
    total_levels = len(LEVELS)
    level_map = LEVELS[current_level]
    px, py = find_start(level_map)
    player = Player(px, py, level_map)
    start_time = time.time()
    won = False
    win_time = 0
    btn1 = btn2 = None
    prev_time = time.time()
    
    particles = []
    stars = []
    for _ in range(100):
        stars.append((random.randint(0, SCREEN_W), random.randint(0, SCREEN_H), random.uniform(0.5, 2.0), random.uniform(0, 6.28)))
    running = True
    while running:
        now = time.time()
        dt = now - prev_time
        prev_time = now
        t_sec = now
        
        # Get raw mouse position on the 640x480 screen
        raw_mx, raw_my = pygame.mouse.get_pos()
        # Scale mouse position up to match the 1100x750 logical space
        mouse_pos = (int(raw_mx * (SCREEN_W / 640)), int(raw_my * (SCREEN_H / 480)))
        clock.tick(FPS)

        if picam2 and controller:
            try:
                frame_raw = picam2.capture_array()
                if frame_raw is not None:
                    # 1. Process Frame
                    frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                    frame = cv2.flip(frame, 1)
                    
                    # 2. Detect & Action (Directly, no queue)
                    gesture = controller.detect_gesture(frame)
                    fingers = controller.get_fingers_count(frame)
                    
                    if gesture:
                        last_gesture[0] = gesture
                        last_gesture_time[0] = time.time()
                        current_detected_gesture[0] = gesture

                        if gesture == "quit":
                            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_ESCAPE}))
                        # ------------------------------------
                        
                        if not won and not player.moving:
                            moved = False
                            if gesture == "swipe_left":   moved = player.move(-1, 0)
                            elif gesture == "swipe_right": moved = player.move(1, 0)
                            elif gesture == "up":          moved = player.move(0, -1)
                            elif gesture == "down":        moved = player.move(0, 1)
                            elif gesture == "restart":
                                px, py = find_start(level_map)
                                player = Player(px, py, level_map)
                                start_time = time.time()
                            
                            if moved:
                                ox_m = (SCREEN_W - len(level_map[0])*TILE)//2
                                oy_m = (SCREEN_H - len(level_map)*TILE)//2 + 10
                                emit_particles(player.tx + TILE//2 + ox_m, player.ty + TILE//2 + oy_m, C_UI_GOLD)
                                won = True
                                win_time = int(time.time() - start_time)

                    # 3. Draw Debug Window (Safe on Main Thread)
                    #frame = controller.draw_ui(frame, gesture, fingers)
                    #cv2.imshow("Gesture Control - Find My Home", frame)
                    #cv2.waitKey(1)
            except Exception as e:
                print(f"Camera Sync Error: {e}")
                
        # Pygame events
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                #gesture_thread_running[0] = False
                running = False
                break
            
            if e.type == pygame.MOUSEMOTION and won:
                if btn1:
                    btn1.check_hover(mouse_pos)
                if btn2:
                    btn2.check_hover(mouse_pos)
            
            if e.type == pygame.MOUSEBUTTONDOWN and won:
                if btn1 and btn1.is_clicked(mouse_pos):
                    if btn1.text == "Play Again":
                        current_level = 0
                    else:
                        current_level = (current_level + 1) % total_levels
                    level_map = LEVELS[current_level]
                    px, py = find_start(level_map)
                    player = Player(px, py, level_map)
                    start_time = time.time()
                    won = False
                if btn2 and btn2.is_clicked(mouse_pos):
                    #gesture_thread_running[0] = False
                    running = False
                    break
            
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    #gesture_thread_running[0] = False
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
                    if e.key == pygame.K_LEFT:
                        moved = player.move(-1, 0)
                    elif e.key == pygame.K_RIGHT:
                        moved = player.move(1, 0)
                    elif e.key == pygame.K_UP:
                        moved = player.move(0, -1)
                    elif e.key == pygame.K_DOWN:
                        moved = player.move(0, 1)
                    elif e.key == pygame.K_r:
                        px, py = find_start(level_map)
                        player = Player(px, py, level_map)
                        start_time = time.time()
                    if moved:
                        ox_m = (SCREEN_W - len(level_map[0])*TILE) // 2
                        oy_m = (SCREEN_H - len(level_map)*TILE) // 2 + 10
                        emit_particles(player.tx + TILE//2 + ox_m,
                                       player.ty + TILE//2 + oy_m, C_UI_GOLD)
                        won = True
                        win_time = int(time.time() - start_time)
        
        player.update(dt)
        particles[:] = [p for p in particles if p.update(dt)]
        
        draw_background()
        draw_stars(t_sec)
        ox, oy = draw_map(level_map)
        player.draw(ox, oy, screen)
        for p in particles:
            p.draw(screen)
        draw_top_hud(start_time, current_level, total_levels)
        draw_minimap(player, level_map)
        draw_gesture_panel()
        draw_instruction_bar()
        if won:
            btn1, btn2 = draw_win_screen(win_time, current_level, total_levels)
            btn1.draw(screen)
            btn2.draw(screen)
        
        scaled_surf = pygame.transform.scale(screen, (640, 480))
        real_screen.blit(scaled_surf, (0, 0))
        pygame.display.flip()
    
    #gesture_thread_running[0] = False
    if controller:
        controller.release()
    cv2.destroyAllWindows()
    time.sleep(1)

if __name__ == "__main__":
    run_find_my_home()