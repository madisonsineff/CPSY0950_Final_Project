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
    title_font = pygame.font.SysFont("chalkboard", 48, bold=True)
    panel_title_font = pygame.font.SysFont("optima", 30, bold=True)
    hub = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"
    running = True
    app_phase = "INSTRUCTIONS"

    cx, cy = size[0] // 2, size[1] // 2
    instr_panel = pygame.Rect(cx - 320, 90, 640, 420)
    start_rect = pygame.Rect(cx - 140, instr_panel.bottom - 84, 280, 56)

    def return_to_hub() -> None:
        if hub.exists():
            subprocess.Popen([sys.executable, str(hub)])
        pygame.quit()
        sys.exit(0)

    def draw_instructions() -> None:
        screen.fill((235, 245, 255))
        pygame.draw.rect(screen, (248, 250, 255), instr_panel, border_radius=18)
        pygame.draw.rect(screen, (30, 44, 88), instr_panel, width=3, border_radius=18)

        title = panel_title_font.render("How to play", True, (20, 25, 45))
        screen.blit(title, (instr_panel.centerx - title.get_width() // 2, instr_panel.y + 22))

        lines = [
            "Filler is still under construction in this project.",
            "",
            "For now, this game launches a placeholder screen so the hub",
            "can open it (and you can return back to the hub).",
            "",
            "Controls:",
            "  - Enter / Space: start",
            "  - H: return to hub",
            "  - Esc: quit",
        ]
        y = instr_panel.y + 76
        for line in lines:
            if line == "":
                y += 16
                continue
            surf = small.render(line, True, (35, 40, 70))
            screen.blit(surf, (instr_panel.x + 44, y))
            y += 30

        mp = pygame.mouse.get_pos()
        hover = start_rect.collidepoint(mp)
        fill = (52, 168, 98) if hover else (42, 140, 78)
        pygame.draw.rect(screen, fill, start_rect, border_radius=12)
        pygame.draw.rect(screen, (18, 72, 44), start_rect, width=2, border_radius=12)
        st = panel_title_font.render("Start", True, (255, 255, 255))
        screen.blit(st, (start_rect.centerx - st.get_width() // 2, start_rect.centery - st.get_height() // 2))

        hint = small.render("Tip: press H anytime to go back to the hub", True, (95, 98, 120))
        screen.blit(hint, (cx - hint.get_width() // 2, instr_panel.bottom + 18))

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_h:
                return_to_hub()

            if app_phase == "INSTRUCTIONS":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    app_phase = "PLAY"
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and start_rect.collidepoint(event.pos):
                    app_phase = "PLAY"
                continue

        if app_phase == "INSTRUCTIONS":
            draw_instructions()
            pygame.display.flip()
            clock.tick(60)
            continue

        screen.fill((235, 245, 255))
        t = title_font.render("Filler", True, (25, 40, 80))
        screen.blit(t, (size[0] // 2 - t.get_width() // 2, 90))
        lines = [
            "This is a placeholder game screen.",
            "Press H to return to the hub.",
            "Esc — quit",
        ]
        y = 210
        for line in lines:
            s = font.render(line, True, (50, 55, 90))
            screen.blit(s, (size[0] // 2 - s.get_width() // 2, y))
            y += 46
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
