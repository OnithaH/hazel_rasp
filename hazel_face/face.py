import pygame
import sys  # <--- Needed for clean exit codes

# Initialize Pygame
pygame.init()

# New requested resolution
WIDTH, HEIGHT = 640, 480 
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
FPS = 60 

# Fullscreen mode with scaling
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
pygame.display.set_caption("Robot 640x480")
clock = pygame.time.Clock()

def draw_filled_rect_eye(surface, x, y, base_w, base_h, blink_factor, radius=50):
    temp_surface = pygame.Surface((base_w, base_h), pygame.SRCALPHA)
    current_h = int(base_h * blink_factor)
    if current_h < 4: current_h = 4
    outer_rect = (0, (base_h - current_h) // 2, base_w, current_h)
    current_radius = min(radius, current_h // 2)
    pygame.draw.rect(temp_surface, WHITE, outer_rect, border_radius=current_radius)
    surface.blit(temp_surface, (x - base_w // 2, y - base_h // 2))

def draw_subtle_mouth(surface, x, y, w, h, thickness=28):
    temp_surface = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(temp_surface, WHITE, (0, 0, w, h))
    inner_rect = (thickness, thickness, w - (thickness * 2), h - (thickness * 2))
    pygame.draw.ellipse(temp_surface, (0, 0, 0, 0), inner_rect)
    pygame.draw.rect(temp_surface, (0, 0, 0, 0), (0, 0, w, h // 2 + 15))
    surface.blit(temp_surface, (x - w // 2, y - h // 4))

def main():
    blink_val = 1.0  
    target_blink = 1.0
    timer = 0

    while True: # Changed to True; we will exit via sys.exit
        screen.fill(BLACK)
        timer += 1
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0) # Standard clean exit
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    print("User requested quit. Shutting down face...")
                    pygame.quit()
                    sys.exit(0) # <--- THIS tells PM2 "I am done"

        # Blinking Logic
        if timer % 650 == 0: target_blink = 0.0
        if blink_val < 0.05: target_blink = 1.0
        blink_val += (target_blink - blink_val) * 0.2

        cx = (WIDTH // 2) - 25 
        top_offset_cy = 180 
        eye_y = top_offset_cy - 50    
        mouth_y = top_offset_cy + 120 
        
        eye_w, eye_h = 120, 180
        draw_filled_rect_eye(screen, cx - 130, eye_y, eye_w, eye_h, blink_val, radius=55)
        draw_filled_rect_eye(screen, cx + 130, eye_y, eye_w, eye_h, blink_val, radius=55)
        
        draw_subtle_mouth(screen, cx, mouth_y, 420, 130, thickness=28)

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass # Catch the exit to close gracefully