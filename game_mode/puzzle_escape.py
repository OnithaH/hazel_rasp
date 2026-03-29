"""
PUZZLE ESCAPE - Collect keys & flip switches game with gesture controls
"""

import pygame
import sys
import math
import random
import time
import threading
import queue
import cv2
from camera_manager import get_camera
from gesture_controller import GestureController

# Global camera reference
_global_camera = None

def set_camera(camera):
    global _global_camera
    _global_camera = camera

def get_camera():
    global _global_camera
    if _global_camera is None:
        return __import__('camera_manager').get_camera()
    return _global_camera

pygame.init()

WIDTH, HEIGHT = 900, 650
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
CUTE_PINK = (255, 182, 193)
CUTE_BLUE = (173, 216, 230)
CUTE_GREEN = (144, 238, 144)
CUTE_YELLOW = (255, 255, 153)
CUTE_PURPLE = (216, 191, 216)
CUTE_ORANGE = (255, 200, 150)
DARK_GRAY = (70, 70, 70)
LIGHT_GRAY = (200, 200, 200)
RED = (255, 100, 100)
GOLD = (255, 215, 0)
ORANGE = (255, 165, 0)
CYAN = (100, 200, 255)

PLAYING = 0
WON = 1
LOST = 2
LEVEL_COMPLETE = 3

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
        return self.life > 0
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
            self.x += (self.target_x - self.x) * 0.4  # Sped up from 0.15
        else:
            self.x = self.target_x
        if abs(self.y - self.target_y) > 1:
            self.y += (self.target_y - self.y) * 0.4  # Sped up from 0.15
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
            self.open_progress += 0.15  # Sped up from 0.04
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
        self.real_screen = pygame.display.set_mode((640, 480))
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        pygame.display.set_caption(" Puzzle Escape - 10 Levels! (Gesture Control)")
        self.clock = pygame.time.Clock()
        
        self.font = pygame.font.Font(None, 22)
        self.big_font = pygame.font.Font(None, 56)
        self.title_font = pygame.font.Font(None, 40)
        self.particles = []
        self.current_level = 1
        self.max_level = 10
        self.total_score = 0
        self.level_config = self.get_level_config()
        
        # Gesture setup
        self.controller = None
        self.gesture_queue = queue.Queue()
        self.last_gesture = [""]
        self.last_gesture_time = [0.0]
        self.gesture_running = [True]
        
        self.picam2 = get_camera()
        if self.picam2:
            try:
                # Restart camera if needed
                self.picam2.start()
                time.sleep(1)
                
                self.controller = GestureController()
                self.controller.set_camera(self.picam2)
                #cv2.namedWindow('Gesture Control - Puzzle Escape', cv2.WINDOW_NORMAL)
                #cv2.resizeWindow('Gesture Control - Puzzle Escape', 640, 480)
                #cv2.moveWindow('Gesture Control - Puzzle Escape', 100, 100)
                print("[PUZZLE ESCAPE] Gesture control ready")
                
            except Exception as e:
                print(f"[PUZZLE ESCAPE] Gesture error: {e}")
                self.controller = None
    
        self.reset_game()

    def _gesture_loop(self):
        while self.gesture_running[0] and self.picam2:
            try:
                frame_raw = self.picam2.capture_array()
                if frame_raw is None:
                    continue
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                frame = cv2.flip(frame, 1)
                
                gesture = self.controller.detect_gesture(frame) if self.controller else None
                fingers = self.controller.get_fingers_count(frame) if self.controller else 0
                
                if gesture:
                    self.gesture_queue.put(gesture)
                    self.last_gesture[0] = gesture
                    self.last_gesture_time[0] = time.time()
                
                #if self.controller:
                    #frame = self.controller.draw_ui(frame, gesture, fingers)
                    #cv2.putText(frame, "PUZZLE ESCAPE: SWIPE=MOVE | FIST=PICK | THUMB=SWITCH | PALM=DOOR | PEACE=RESTART",
                                #(8, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 255, 200), 1)
                    #cv2.imshow("Gesture Control - Puzzle Escape", frame)
                    #cv2.waitKey(1)
            except Exception as e:
                pass
        
        cv2.destroyAllWindows()

    def get_level_config(self):
        return {
            1: {'time':60,'keys':1,'switches':0,'positions':[(450,400),(700,400)],'key_positions':[0],'switch_positions':[],'door_position':1,'theme_color':CUTE_PINK,'instruction':"Collect the key and open the door!"},
            2: {'time':55,'keys':2,'switches':0,'positions':[(200,380),(450,380),(700,380)],'key_positions':[0,1],'switch_positions':[],'door_position':2,'theme_color':CUTE_BLUE,'instruction':"Collect both keys to unlock the door!"},
            3: {'time':50,'keys':1,'switches':1,'positions':[(200,350),(450,350),(700,400)],'key_positions':[0],'switch_positions':[1],'door_position':2,'theme_color':CUTE_GREEN,'instruction':"Get the key AND activate the switch!"},
            4: {'time':50,'keys':2,'switches':1,'positions':[(180,320),(350,320),(520,320),(700,420)],'key_positions':[0,2],'switch_positions':[1],'door_position':3,'theme_color':CUTE_YELLOW,'instruction':"Collect 2 keys and flip the switch!"},
            5: {'time':45,'keys':2,'switches':2,'positions':[(200,280),(350,350),(500,280),(650,350),(750,450)],'key_positions':[0,2],'switch_positions':[1,3],'door_position':4,'theme_color':CUTE_PURPLE,'instruction':"2 keys + 2 switches = freedom!"},
            6: {'time':45,'keys':3,'switches':1,'positions':[(180,300),(320,380),(450,300),(580,380),(720,450)],'key_positions':[0,2,3],'switch_positions':[1],'door_position':4,'theme_color':CUTE_ORANGE,'instruction':"Find all 3 keys and activate switch!"},
            7: {'time':40,'keys':3,'switches':2,'positions':[(150,280),(280,350),(410,280),(540,350),(670,280),(780,430)],'key_positions':[0,2,4],'switch_positions':[1,3],'door_position':5,'theme_color':CYAN,'instruction':"3 keys + 2 switches - hurry up!"},
            8: {'time':40,'keys':4,'switches':2,'positions':[(160,260),(280,330),(400,260),(520,330),(640,260),(760,330),(800,430)],'key_positions':[0,1,3,4],'switch_positions':[2,5],'door_position':6,'theme_color':(255,150,200),'instruction':"4 keys scattered! Find them all + switches!"},
            9: {'time':35,'keys':3,'switches':3,'positions':[(140,250),(260,320),(380,250),(500,320),(620,250),(740,320),(800,420)],'key_positions':[0,2,4],'switch_positions':[1,3,5],'door_position':6,'theme_color':(180,255,180),'instruction':"3 keys + 3 switches! Navigate carefully!"},
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
        return True

    def handle_gestures(self):
        if not self.controller:
            return
        
        while not self.gesture_queue.empty():
            gesture = self.gesture_queue.get()
            
            if gesture == "quit":
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_ESCAPE}))
                continue 
            # ------------------------------------
            
            if self.state == PLAYING:
                if gesture == "swipe_left":
                    self.move_player(-1)
                    self.show_message("👈 Moved Left!")
                elif gesture == "swipe_right":
                    self.move_player(1)
                    self.show_message("👉 Moved Right!")
                elif gesture == "up" or gesture == "fist":
                    self.try_pick_up()
                    self.show_message("✊ Picking up...")
                elif gesture == "thumbs_up":
                    self.try_activate()
                    self.show_message("👍 Activating switch...")
                elif gesture == "down" or gesture == "open_palm":
                    self.try_open_door()
                    self.show_message("✋ Opening door...")
                elif gesture == "restart":
                    self.current_level = 1
                    self.total_score = 0
                    self.reset_game()
                    self.show_message("🔄 Game Restarted!")
            elif self.state == LEVEL_COMPLETE:
                if gesture in ("next", "point", "thumbs_up"):
                    self.next_level()
                    self.show_message("☝️ Next Level!")
            elif self.state in (LOST, WON):
                if gesture == "restart":
                    self.current_level = 1
                    self.total_score = 0
                    self.reset_game()
                    self.show_message("🔄 Game Restarted!")

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
            keys_collected = all(item.collected for item in self.items)
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

    def update(self):
        self.particles = [p for p in self.particles if p.update()]
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
            pygame.draw.line(self.screen, (r, g, b), (0, y), (WIDTH, y))
        
        cloud_offset = (pygame.time.get_ticks() / 50) % WIDTH
        for i in range(3):
            cx = (cloud_offset + i * 300) % (WIDTH + 200) - 100
            cy = 80 + i * 60
            pygame.draw.ellipse(self.screen, (200,200,220), (cx, cy+2, 120, 40))
            pygame.draw.ellipse(self.screen, (200,200,220), (cx+30, cy+2, 100, 35))
            pygame.draw.ellipse(self.screen, (240,240,255), (cx, cy, 120, 40))
            pygame.draw.ellipse(self.screen, (240,240,255), (cx+30, cy-5, 100, 35))
            pygame.draw.ellipse(self.screen, (240,240,255), (cx+60, cy, 90, 38))
        
        wall_color = (180,140,100)
        wall_shadow = (140,110,80)
        wall_highlight = (200,160,120)
        pygame.draw.polygon(self.screen, wall_shadow, [(0,0),(180,120),(180,HEIGHT-100),(0,HEIGHT-100)])
        pygame.draw.polygon(self.screen, wall_color, [(0,0),(170,120),(170,HEIGHT-100),(0,HEIGHT-100)])
        
        for i in range(2):
            panel_y = 200 + i * 150
            pygame.draw.rect(self.screen, wall_shadow, (20, panel_y, 120, 100), border_radius=8)
            pygame.draw.rect(self.screen, wall_highlight, (25, panel_y+5, 110, 90), border_radius=6)
        
        pygame.draw.polygon(self.screen, wall_shadow, [(WIDTH,0),(WIDTH-180,120),(WIDTH-180,HEIGHT-100),(WIDTH,HEIGHT-100)])
        pygame.draw.polygon(self.screen, wall_color, [(WIDTH,0),(WIDTH-170,120),(WIDTH-170,HEIGHT-100),(WIDTH,HEIGHT-100)])
        
        for i in range(2):
            panel_y = 200 + i * 150
            pygame.draw.rect(self.screen, wall_shadow, (WIDTH-140, panel_y, 120, 100), border_radius=8)
            pygame.draw.rect(self.screen, wall_highlight, (WIDTH-135, panel_y+5, 110, 90), border_radius=6)
        
        back_wall_color = (160,130,90)
        pygame.draw.rect(self.screen, (140,110,80), (170, 120, WIDTH-340, HEIGHT-220))
        pygame.draw.rect(self.screen, back_wall_color, (170, 120, WIDTH-340, HEIGHT-220))
        
        window_x = WIDTH//2 - 100
        window_y = 140
        window_width = 200
        window_height = 150
        pygame.draw.rect(self.screen, (80,60,40), (window_x-10, window_y-10, window_width+20, window_height+20), border_radius=8)
        pygame.draw.rect(self.screen, (150,200,250), (window_x, window_y, window_width, window_height))
        pane_w = window_width//2 - 5
        pane_h = window_height//2 - 5
        pygame.draw.rect(self.screen, (135,206,250), (window_x+5, window_y+5, pane_w, pane_h))
        pygame.draw.rect(self.screen, (135,206,250), (window_x+window_width//2+5, window_y+5, pane_w, pane_h))
        pygame.draw.rect(self.screen, (135,206,250), (window_x+5, window_y+window_height//2+5, pane_w, pane_h))
        pygame.draw.rect(self.screen, (135,206,250), (window_x+window_width//2+5, window_y+window_height//2+5, pane_w, pane_h))
        pygame.draw.rect(self.screen, (80,60,40), (window_x+window_width//2-5, window_y, 10, window_height))
        pygame.draw.rect(self.screen, (80,60,40), (window_x, window_y+window_height//2-5, window_width, 10))
        
        ceiling_points = [(0,0),(WIDTH,0),(WIDTH-170,120),(170,120)]
        pygame.draw.polygon(self.screen, (100,100,120), ceiling_points)
        light_x = WIDTH//2
        light_y = 60
        pygame.draw.ellipse(self.screen, (200,200,200), (light_x-40, light_y-5, 80, 15))
        pygame.draw.ellipse(self.screen, (255,255,220), (light_x-35, light_y-3, 70, 11))
        glow_radius = 60 + math.sin(pygame.time.get_ticks() / 200) * 5
        for i in range(3):
            pygame.draw.circle(self.screen, (255,255,200), (light_x, light_y), int(glow_radius - i*15), 2)
        
        floor_color = (120,80,60)
        floor_light = (140,100,80)
        floor_dark = (100,70,50)
        pygame.draw.rect(self.screen, floor_color, (0, HEIGHT-100, WIDTH, 100))
        tile_size = 80
        for x in range(0, WIDTH, tile_size):
            for y_idx, y in enumerate(range(HEIGHT-100, HEIGHT, tile_size)):
                depth_factor = 1 - (y_idx * 0.15)
                tile_h = int(tile_size * depth_factor)
                if ((x // tile_size) + y_idx) % 2 == 0:
                    pygame.draw.rect(self.screen, floor_light, (x, y, tile_size, tile_h))
                else:
                    pygame.draw.rect(self.screen, floor_dark, (x, y, tile_size, tile_h))
                pygame.draw.rect(self.screen, (80,60,40), (x, y, tile_size, tile_h), 1)
        
        frame_colors = [(139,69,19),(160,82,45)]
        for i in range(2):
            frame_y = 160 + i * 120
            frame_points = [(60,frame_y),(130,frame_y+20),(130,frame_y+80),(60,frame_y+60)]
            pygame.draw.polygon(self.screen, frame_colors[i%2], frame_points, 4)
            inner_points = [(68,frame_y+8),(122,frame_y+24),(122,frame_y+74),(68,frame_y+54)]
            pygame.draw.polygon(self.screen, theme, inner_points)
        
        shelf_x = WIDTH - 150
        shelf_y = 180
        pygame.draw.rect(self.screen, (80,60,40), (shelf_x, shelf_y, 100, 180))
        pygame.draw.rect(self.screen, (100,80,60), (shelf_x+5, shelf_y+5, 90, 170))
        book_colors = [(200,50,50),(50,150,200),(100,200,100),(200,200,50)]
        for i in range(4):
            shelf_level_y = shelf_y + 20 + i * 40
            pygame.draw.rect(self.screen, (80,60,40), (shelf_x, shelf_level_y, 100, 3))
            for j in range(3):
                book_x = shelf_x + 10 + j * 28
                book_color = book_colors[(i + j) % len(book_colors)]
                pygame.draw.rect(self.screen, book_color, (book_x, shelf_level_y-30, 20, 30))
                pygame.draw.rect(self.screen, BLACK, (book_x, shelf_level_y-30, 20, 30), 1)
        
        clock_x = WIDTH - 250
        clock_y = 200
        pygame.draw.circle(self.screen, (100,80,60), (clock_x, clock_y), 35)
        pygame.draw.circle(self.screen, (200,180,140), (clock_x, clock_y), 32)
        pygame.draw.circle(self.screen, WHITE, (clock_x, clock_y), 28)
        for i in range(12):
            angle = math.radians(i * 30 - 90)
            pygame.draw.circle(self.screen, BLACK,
                               (int(clock_x + math.cos(angle)*20), int(clock_y + math.sin(angle)*20)), 2)
        time_angle = (pygame.time.get_ticks() / 50) % 360
        minute_angle = (pygame.time.get_ticks() / 500) % 360
        hour_x = clock_x + math.cos(math.radians(minute_angle - 90)) * 12
        hour_y = clock_y + math.sin(math.radians(minute_angle - 90)) * 12
        pygame.draw.line(self.screen, BLACK, (clock_x, clock_y), (int(hour_x), int(hour_y)), 3)
        hand_x = clock_x + math.cos(math.radians(time_angle - 90)) * 20
        hand_y = clock_y + math.sin(math.radians(time_angle - 90)) * 20
        pygame.draw.line(self.screen, BLACK, (clock_x, clock_y), (int(hand_x), int(hand_y)), 2)
        pygame.draw.circle(self.screen, BLACK, (clock_x, clock_y), 4)
        pygame.draw.circle(self.screen, GOLD, (clock_x, clock_y), 3)
        
        plant_x = 200
        plant_y = HEIGHT - 100
        pygame.draw.polygon(self.screen, (180,100,80),
                            [(plant_x-20,plant_y),(plant_x-15,plant_y-30),
                             (plant_x+15,plant_y-30),(plant_x+20,plant_y)])
        for i in range(5):
            leaf_angle = i * 72 + pygame.time.get_ticks() / 100
            leaf_x = plant_x + math.cos(math.radians(leaf_angle)) * 15
            leaf_y = plant_y - 35 + math.sin(math.radians(leaf_angle)) * 10
            pygame.draw.ellipse(self.screen, (50,150,50), (int(leaf_x)-8, int(leaf_y)-12, 16, 24))
            pygame.draw.ellipse(self.screen, (80,180,80), (int(leaf_x)-6, int(leaf_y)-10, 12, 20))

    def draw_instruction_bar(self):
        bar_y = HEIGHT - 80
        bar_h = 60
        bar_surf = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        bar_surf.fill((0, 0, 0, 180))
        self.screen.blit(bar_surf, (0, bar_y))
        
        gestures = [
            ("👈 👉", "Swipe Move", CUTE_PINK),
            ("✊", "Fist Pick", CUTE_GREEN),
            ("👍", "Thumb Switch", GOLD),
            ("✋", "Palm Door", CYAN),
            ("✌️", "Peace Restart", RED),
        ]
        
        font = pygame.font.Font(None, 20)
        small_font = pygame.font.Font(None, 16)
        
        for i, (icon, label, color) in enumerate(gestures):
            x = 20 + i * 150
            icon_surf = font.render(icon, True, color)
            self.screen.blit(icon_surf, (x, bar_y + 15))
            label_surf = small_font.render(label, True, color)
            self.screen.blit(label_surf, (x, bar_y + 40))

    def draw(self):
        self.draw_background()
        
        if self.state == PLAYING:
            for particle in self.particles:
                particle.draw(self.screen)
            for item in self.items:
                item.draw(self.screen, self.font)
            for switch in self.switches:
                switch.draw(self.screen, self.font)
            self.door.draw(self.screen, self.font)
            self.player.draw(self.screen)
            
            level_text = self.big_font.render(f"LEVEL {self.current_level}", True, WHITE)
            level_bg = pygame.Surface((level_text.get_width()+30, level_text.get_height()+20))
            level_bg.fill(BLACK)
            level_bg.set_alpha(180)
            self.screen.blit(level_bg, (20, 15))
            self.screen.blit(level_text, (35, 20))
            
            timer_color = RED if self.time_left <= 10 else WHITE
            timer_bg_color = (100,0,0) if self.time_left <= 10 else (50,50,50)
            timer_text = self.big_font.render(f"⏱️ {self.time_left}s", True, timer_color)
            timer_bg = pygame.Surface((timer_text.get_width()+30, timer_text.get_height()+20))
            timer_bg.fill(timer_bg_color)
            timer_bg.set_alpha(200)
            self.screen.blit(timer_bg, (WIDTH - timer_text.get_width() - 45, 15))
            self.screen.blit(timer_text, (WIDTH - timer_text.get_width() - 30, 20))
            
            score_text = self.title_font.render(f"Score: {self.total_score}", True, GOLD)
            self.screen.blit(score_text, (WIDTH//2 - score_text.get_width()//2, 25))
            
            if self.message_timer > 0:
                msg_surf = self.font.render(self.message, True, BLACK)
                msg_width = msg_surf.get_width() + 30
                msg_height = 50
                msg_x = WIDTH//2 - msg_width//2
                msg_y = 100
                pygame.draw.rect(self.screen, WHITE, (msg_x, msg_y, msg_width, msg_height), border_radius=15)
                pygame.draw.rect(self.screen, CUTE_YELLOW, (msg_x+3, msg_y+3, msg_width-6, msg_height-6), border_radius=12)
                self.screen.blit(msg_surf, (WIDTH//2 - msg_surf.get_width()//2, msg_y + 15))
            
            self.draw_instruction_bar()
            
            if self.last_gesture[0] and time.time() - self.last_gesture_time[0] < 1.5:
                gesture_font = pygame.font.Font(None, 28)
                g_col = {"swipe_left": CUTE_PINK, "swipe_right": CUTE_PINK,
                         "fist": CUTE_GREEN, "thumbs_up": GOLD,
                         "open_palm": CYAN, "restart": RED}.get(self.last_gesture[0], WHITE)
                gsurf = gesture_font.render(f">> {self.last_gesture[0].upper()} <<", True, g_col)
                self.screen.blit(gsurf, (WIDTH//2 - gsurf.get_width()//2, HEIGHT - 110))
        
        elif self.state == LEVEL_COMPLETE:
            for particle in self.particles:
                particle.draw(self.screen)
            complete_text = self.big_font.render(f"LEVEL {self.current_level} COMPLETE! 🎉", True, CUTE_GREEN)
            complete_bg = pygame.Surface((complete_text.get_width()+40, complete_text.get_height()+30))
            complete_bg.fill(BLACK)
            complete_bg.set_alpha(200)
            self.screen.blit(complete_bg, (WIDTH//2 - complete_text.get_width()//2 - 20, HEIGHT//2 - 80))
            self.screen.blit(complete_text, (WIDTH//2 - complete_text.get_width()//2, HEIGHT//2 - 70))
            bonus = self.time_left * 10
            bonus_text = self.title_font.render(f"Time Bonus: +{bonus} points", True, GOLD)
            self.screen.blit(bonus_text, (WIDTH//2 - bonus_text.get_width()//2, HEIGHT//2 - 10))
            total_text = self.title_font.render(f"Total Score: {self.total_score}", True, WHITE)
            self.screen.blit(total_text, (WIDTH//2 - total_text.get_width()//2, HEIGHT//2 + 30))
            if self.current_level < self.max_level:
                next_text = self.font.render("Press SPACE or show 👍 THUMBS UP gesture for next level", True, CYAN)
                self.screen.blit(next_text, (WIDTH//2 - next_text.get_width()//2, HEIGHT//2 + 80))
        
        elif self.state == WON:
            for particle in self.particles:
                particle.draw(self.screen)
            win_text = self.big_font.render("🏆 YOU WON ALL LEVELS! 🏆", True, GOLD)
            win_bg = pygame.Surface((win_text.get_width()+40, win_text.get_height()+30))
            win_bg.fill(BLACK)
            win_bg.set_alpha(200)
            self.screen.blit(win_bg, (WIDTH//2 - win_text.get_width()//2 - 20, HEIGHT//2 - 80))
            self.screen.blit(win_text, (WIDTH//2 - win_text.get_width()//2, HEIGHT//2 - 70))
            final_score = self.title_font.render(f"Final Score: {self.total_score}", True, CUTE_GREEN)
            self.screen.blit(final_score, (WIDTH//2 - final_score.get_width()//2, HEIGHT//2 + 10))
            restart_text = self.font.render("Press R or show ✌️ PEACE gesture to play again", True, CUTE_YELLOW)
            self.screen.blit(restart_text, (WIDTH//2 - restart_text.get_width()//2, HEIGHT//2 + 70))
        
        elif self.state == LOST:
            lose_text = self.big_font.render("⏰ TIME'S UP! ⏰", True, RED)
            lose_bg = pygame.Surface((lose_text.get_width()+40, lose_text.get_height()+30))
            lose_bg.fill(BLACK)
            lose_bg.set_alpha(200)
            self.screen.blit(lose_bg, (WIDTH//2 - lose_text.get_width()//2 - 20, HEIGHT//2 - 60))
            self.screen.blit(lose_text, (WIDTH//2 - lose_text.get_width()//2, HEIGHT//2 - 50))
            fail_text = self.title_font.render(f"You reached Level {self.current_level}", True, WHITE)
            self.screen.blit(fail_text, (WIDTH//2 - fail_text.get_width()//2, HEIGHT//2 + 20))
            restart_text = self.font.render("Press R or show ✌️ PEACE gesture to try again", True, CUTE_YELLOW)
            self.screen.blit(restart_text, (WIDTH//2 - restart_text.get_width()//2, HEIGHT//2 + 70))
        
        # Scale down before displaying
        scaled_surf = pygame.transform.scale(self.screen, (640, 480))
        self.real_screen.blit(scaled_surf, (0, 0))
        
        pygame.display.flip()

    def run(self):
        print("\n" + "="*70)
        print("🧩 PUZZLE ESCAPE GAME - 10 AMAZING LEVELS! 🧩")
        print("     🤚 NOW WITH GESTURE CONTROL! 🤚")
        print("="*70)
        
        running = True
        frame_skip = 0
        while running:
            frame_skip += 1
            # Only run the heavy AI every 3 frames to stop Pygame from lagging
            if self.picam2 and self.controller and frame_skip % 3 == 0:
                try:
                    frame_raw = self.picam2.capture_array()
                    if frame_raw is not None:
                        frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                        frame = cv2.flip(frame, 1)
                        
                        gesture = self.controller.detect_gesture(frame)
                        fingers = self.controller.get_fingers_count(frame)
                        # Push to the queue so handle_gestures() can process it
                        if gesture:
                            self.gesture_queue.put(gesture)
                            self.last_gesture[0] = gesture
                            self.last_gesture_time[0] = time.time()                        
                    
                        # Draw UI
                        #frame = self.controller.draw_ui(frame, gesture, fingers)
                        #cv2.imshow("Gesture Control - Puzzle Escape", frame)
                        #cv2.waitKey(1)
                except Exception as e:
                    print(f"Camera Sync Error: {e}")

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
            self.clock.tick(FPS)
        
        self.gesture_running[0] = False
        if self.controller:
            self.controller.release()
        cv2.destroyAllWindows()

def run_puzzle_escape():
    game = Game()
    game.run()

if __name__ == "__main__":
    run_puzzle_escape()