# Placeholder for the Filler game — launched from GamePython_MAINHUB.
# Replace this file with the real game logic when ready.

import pathlib
import subprocess
import sys

import pygame


def main() -> None:
    pygame.init()
    size = (900, 600)
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Filler")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("optima", 28, bold=True)
    small = pygame.font.SysFont("optima", 20)
    hub = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_h and hub.exists():
                    subprocess.Popen([sys.executable, str(hub)])
                    pygame.quit()
                    sys.exit(0)
        screen.fill((235, 245, 255))
        t = font.render("Filler", True, (25, 40, 80))
        screen.blit(t, (size[0] // 2 - t.get_width() // 2, 120))
        lines = [
            "This is a placeholder window.",
            "Esc — quit   |   H — open hub (new window)",
        ]
        y = 220
        for line in lines:
            s = small.render(line, True, (50, 55, 90))
            screen.blit(s, (size[0] // 2 - s.get_width() // 2, y))
            y += 36
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
