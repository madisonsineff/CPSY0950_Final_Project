"""Filler — GamePigeon-style color flood game for 2 players on the same keyboard.

Player 1 starts at the BOTTOM-LEFT corner.
Player 2 starts at the TOP-RIGHT corner.
Each turn, pick a color; your territory flood-fills to every adjacent cell of that color.
Most cells when the board is fully claimed wins!

Controls
--------
Player 1 (bottom-left): keys  1-6  (mapped to the 6 colors)
Player 2 (top-right):   keys  Q W E R T Y  (same 6 colors, same order)
H — return to hub at any time
Esc — quit
R — restart after game over
"""

from __future__ import annotations

import pathlib
import random
import subprocess
import sys
from typing import Optional

import pygame

# ── palette ──────────────────────────────────────────────────────────────────
COLORS = [
    (231,  76,  60),   # 0 red
    (241, 196,  15),   # 1 yellow
    ( 46, 204, 113),   # 2 green
    ( 52, 152, 219),   # 3 blue
    (155,  89, 182),   # 4 purple
    ( 52,  73,  94),   # 5 dark
]
COLOR_NAMES = ["Red", "Yellow", "Green", "Blue", "Purple", "Dark"]

ROWS, COLS = 8, 8          # board size (GamePigeon uses 8×8 visually)
CELL = 72                  # pixel size of each cell
MARGIN = 4                 # gap between cells

P1, P2 = 1, 2

# ── helpers ──────────────────────────────────────────────────────────────────

def make_board() -> list[list[int]]:
    """Random board; corners guaranteed to be different colors."""
    board = [[random.randrange(len(COLORS)) for _ in range(COLS)] for _ in range(ROWS)]
    # make sure starting corners differ
    board[ROWS - 1][0] = 0
    board[0][COLS - 1] = 1
    # make sure they don't accidentally match a neighbor in a way that gives free territory
    return board


def flood_fill(board: list[list[int]], owned: list[list[Optional[int]]], player: int, new_color: int) -> None:
    """Expand player's territory to any adjacent cell that matches new_color, then recolor owned cells."""
    # first: recolor all owned cells to new_color
    for r in range(ROWS):
        for c in range(COLS):
            if owned[r][c] == player:
                board[r][c] = new_color

    # BFS from all currently owned cells to adjacent cells of new_color
    frontier = [(r, c) for r in range(ROWS) for c in range(COLS) if owned[r][c] == player]
    visited = set(frontier)
    queue = list(frontier)

    while queue:
        r, c = queue.pop()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr, nc) not in visited:
                if board[nr][nc] == new_color and owned[nr][nc] is None:
                    visited.add((nr, nc))
                    owned[nr][nc] = player
                    board[nr][nc] = new_color
                    queue.append((nr, nc))


def count_owned(owned: list[list[Optional[int]]], player: int) -> int:
    return sum(owned[r][c] == player for r in range(ROWS) for c in range(COLS))


def is_board_full(owned: list[list[Optional[int]]]) -> bool:
    return all(owned[r][c] is not None for r in range(ROWS) for c in range(COLS))


def current_color(board: list[list[int]], owned: list[list[Optional[int]]], player: int) -> int:
    """Return the color the player currently occupies (all owned cells share a color)."""
    for r in range(ROWS):
        for c in range(COLS):
            if owned[r][c] == player:
                return board[r][c]
    return 0


# ── main ─────────────────────────────────────────────────────────────────────

def run_game() -> None:
    pygame.init()

    hub = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"

    board_px = COLS * (CELL + MARGIN) + MARGIN
    board_py = ROWS * (CELL + MARGIN) + MARGIN

    WIN_W = board_px + 320          # board + side panel
    WIN_H = board_py + 160          # board + top/bottom bars
    BOARD_X = 160                   # left offset of board inside window
    BOARD_Y = 100

    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Filler")
    clock = pygame.time.Clock()

    title_font  = pygame.font.SysFont("chalkboard", 44, bold=True)
    label_font  = pygame.font.SysFont("optima", 26, bold=True)
    small_font  = pygame.font.SysFont("optima", 20)
    score_font  = pygame.font.SysFont("chalkboard", 32, bold=True)
    hint_font   = pygame.font.SysFont("optima", 18)

    # ── key bindings ──
    P1_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6]
    P2_KEYS = [pygame.K_q, pygame.K_w, pygame.K_e, pygame.K_r, pygame.K_t, pygame.K_y]

    def new_game():
        board   = make_board()
        owned   = [[None] * COLS for _ in range(ROWS)]
        # seed corners
        owned[ROWS - 1][0]         = P1
        owned[0][COLS - 1]         = P2
        turn    = P1
        game_over = False
        winner  = None
        return board, owned, turn, game_over, winner

    board, owned, turn, game_over, winner = new_game()

    # ── instruction screen ──
    app_phase = "INSTRUCTIONS"
    instr_panel = pygame.Rect(WIN_W // 2 - 340, 80, 680, 460)
    start_btn   = pygame.Rect(WIN_W // 2 - 130, instr_panel.bottom - 80, 260, 54)

    def draw_instructions():
        screen.fill((30, 34, 50))
        pygame.draw.rect(screen, (248, 250, 255), instr_panel, border_radius=18)
        pygame.draw.rect(screen, (30, 44, 88), instr_panel, width=3, border_radius=18)

        t = label_font.render("How to Play — Filler", True, (20, 25, 55))
        screen.blit(t, (instr_panel.centerx - t.get_width() // 2, instr_panel.y + 24))

        lines = [
            "The board is filled with 6 random colors.",
            "Player 1 owns the bottom-left corner.",
            "Player 2 owns the top-right corner.",
            "",
            "On your turn, pick a new color.",
            "Your territory expands to every touching cell",
            "that matches the color you picked.",
            "",
            "Most cells when the board is full = winner!",
            "",
            "Player 1 keys:  1  2  3  4  5  6",
            "Player 2 keys:  Q  W  E  R  T  Y",
            "  (same color order for both players)",
            "",
            "H = return to hub   |   R = restart   |   Esc = quit",
        ]
        y = instr_panel.y + 72
        for line in lines:
            if line == "":
                y += 10
                continue
            s = small_font.render(line, True, (35, 40, 70))
            screen.blit(s, (instr_panel.x + 44, y))
            y += 26

        mp = pygame.mouse.get_pos()
        hover = start_btn.collidepoint(mp)
        pygame.draw.rect(screen, (52, 168, 98) if hover else (42, 140, 78), start_btn, border_radius=12)
        pygame.draw.rect(screen, (18, 72, 44), start_btn, width=2, border_radius=12)
        st = label_font.render("Start Game", True, (255, 255, 255))
        screen.blit(st, (start_btn.centerx - st.get_width() // 2, start_btn.centery - st.get_height() // 2))
        pygame.display.flip()

    def cell_rect(r: int, c: int) -> pygame.Rect:
        x = BOARD_X + MARGIN + c * (CELL + MARGIN)
        y = BOARD_Y + MARGIN + r * (CELL + MARGIN)
        return pygame.Rect(x, y, CELL, CELL)

    def draw_color_swatch(cx: int, cy: int, color_idx: int, key_label: str, highlight: bool, is_current: bool):
        """Draw a color choice button with key label."""
        sw = 48
        rect = pygame.Rect(cx - sw // 2, cy - sw // 2, sw, sw)
        base = COLORS[color_idx]
        bright = tuple(min(255, v + 50) for v in base)
        pygame.draw.rect(screen, bright if highlight else base, rect, border_radius=8)
        if is_current:
            pygame.draw.rect(screen, (255, 255, 255), rect, width=4, border_radius=8)
        else:
            pygame.draw.rect(screen, (200, 200, 200), rect, width=2, border_radius=8)
        k = hint_font.render(key_label, True, (255, 255, 255))
        screen.blit(k, (rect.centerx - k.get_width() // 2, rect.bottom + 4))

    def draw_game():
        screen.fill((22, 26, 38))

        # title
        t = title_font.render("Filler", True, (240, 240, 255))
        screen.blit(t, (WIN_W // 2 - t.get_width() // 2, 28))

        # board
        for r in range(ROWS):
            for c in range(COLS):
                rect = cell_rect(r, c)
                base_color = COLORS[board[r][c]]
                owner = owned[r][c]
                if owner == P1:
                    # P1 territory: slight warm tint overlay
                    pygame.draw.rect(screen, base_color, rect, border_radius=6)
                    overlay = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    overlay.fill((255, 255, 255, 30))
                    screen.blit(overlay, rect.topleft)
                    pygame.draw.rect(screen, (255, 230, 160), rect, width=2, border_radius=6)
                elif owner == P2:
                    pygame.draw.rect(screen, base_color, rect, border_radius=6)
                    overlay = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                    overlay.fill((255, 255, 255, 30))
                    screen.blit(overlay, rect.topleft)
                    pygame.draw.rect(screen, (160, 220, 255), rect, width=2, border_radius=6)
                else:
                    pygame.draw.rect(screen, base_color, rect, border_radius=6)

        # scores
        p1_count = count_owned(owned, P1)
        p2_count = count_owned(owned, P2)
        total     = ROWS * COLS

        # left panel — Player 1
        p1x = 70
        p1_label = label_font.render("Player 1", True, (255, 220, 140))
        screen.blit(p1_label, (p1x - p1_label.get_width() // 2, BOARD_Y + 10))
        p1_score = score_font.render(str(p1_count), True, (255, 255, 255))
        screen.blit(p1_score, (p1x - p1_score.get_width() // 2, BOARD_Y + 44))
        p1_sub = small_font.render("keys: 1–6", True, (160, 160, 190))
        screen.blit(p1_sub, (p1x - p1_sub.get_width() // 2, BOARD_Y + 88))

        # right panel — Player 2
        p2x = WIN_W - 70
        p2_label = label_font.render("Player 2", True, (140, 210, 255))
        screen.blit(p2_label, (p2x - p2_label.get_width() // 2, BOARD_Y + 10))
        p2_score = score_font.render(str(p2_count), True, (255, 255, 255))
        screen.blit(p2_score, (p2x - p2_score.get_width() // 2, BOARD_Y + 44))
        p2_sub = small_font.render("keys: Q–Y", True, (160, 160, 190))
        screen.blit(p2_sub, (p2x - p2_sub.get_width() // 2, BOARD_Y + 88))

        # whose turn indicator
        if not game_over:
            who = "Player 1's turn  (1–6)" if turn == P1 else "Player 2's turn  (Q–Y)"
            col = (255, 220, 140) if turn == P1 else (140, 210, 255)
            t2 = small_font.render(who, True, col)
            screen.blit(t2, (WIN_W // 2 - t2.get_width() // 2, BOARD_Y + board_py + 16))

        # color swatches row at bottom
        swatch_y   = BOARD_Y + board_py + 60
        swatch_gap = (board_px) // 6
        p1c = current_color(board, owned, P1)
        p2c = current_color(board, owned, P2)
        for i in range(len(COLORS)):
            sx = BOARD_X + MARGIN + i * swatch_gap + swatch_gap // 2
            is_p1_current = (i == p1c)
            is_p2_current = (i == p2c)
            border_col = (255, 255, 255)
            sw = 40
            rect = pygame.Rect(sx - sw // 2, swatch_y - sw // 2, sw, sw)
            pygame.draw.rect(screen, COLORS[i], rect, border_radius=7)
            if is_p1_current:
                pygame.draw.rect(screen, (255, 220, 140), rect, width=3, border_radius=7)
            elif is_p2_current:
                pygame.draw.rect(screen, (140, 210, 255), rect, width=3, border_radius=7)
            # key labels
            k1 = hint_font.render(str(i + 1), True, (200, 200, 200))
            k2 = hint_font.render(["Q","W","E","R","T","Y"][i], True, (200, 200, 200))
            screen.blit(k1, (rect.centerx - k1.get_width() // 2, rect.bottom + 2))
            screen.blit(k2, (rect.centerx - k2.get_width() // 2, rect.bottom + 18))

        # game over overlay
        if game_over:
            overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            if winner == 0:
                msg = "It's a Draw!"
                col = (255, 255, 255)
            else:
                msg = f"Player {winner} Wins!"
                col = (255, 220, 140) if winner == P1 else (140, 210, 255)
            wt = title_font.render(msg, True, col)
            screen.blit(wt, (WIN_W // 2 - wt.get_width() // 2, WIN_H // 2 - 60))
            sc = label_font.render(f"{p1_count} vs {p2_count}  (of {total} cells)", True, (220, 220, 220))
            screen.blit(sc, (WIN_W // 2 - sc.get_width() // 2, WIN_H // 2))
            rt = small_font.render("Press R to play again  |  H for hub  |  Esc to quit", True, (180, 180, 180))
            screen.blit(rt, (WIN_W // 2 - rt.get_width() // 2, WIN_H // 2 + 52))

        # bottom hint
        hint = hint_font.render("H = hub   Esc = quit   R = restart", True, (100, 100, 120))
        screen.blit(hint, (WIN_W // 2 - hint.get_width() // 2, WIN_H - 28))

        pygame.display.flip()

    def return_to_hub():
        if hub.exists():
            subprocess.Popen([sys.executable, str(hub)])
        pygame.quit()
        sys.exit(0)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                    continue
                if event.key == pygame.K_h:
                    return_to_hub()

                if app_phase == "INSTRUCTIONS":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        app_phase = "PLAY"
                    continue

                if event.key == pygame.K_r:
                    board, owned, turn, game_over, winner = new_game()
                    continue

                if not game_over and app_phase == "PLAY":
                    chosen = None
                    if turn == P1 and event.key in P1_KEYS:
                        chosen = P1_KEYS.index(event.key)
                    elif turn == P2 and event.key in P2_KEYS:
                        chosen = P2_KEYS.index(event.key)

                    if chosen is not None:
                        cur = current_color(board, owned, turn)
                        opp_cur = current_color(board, owned, P2 if turn == P1 else P1)
                        # can't pick your own current color or opponent's current color
                        if chosen == cur or chosen == opp_cur:
                            pass   # illegal move — do nothing
                        else:
                            flood_fill(board, owned, turn, chosen)
                            if is_board_full(owned):
                                game_over = True
                                p1c = count_owned(owned, P1)
                                p2c = count_owned(owned, P2)
                                if p1c > p2c:
                                    winner = P1
                                elif p2c > p1c:
                                    winner = P2
                                else:
                                    winner = 0
                            else:
                                turn = P2 if turn == P1 else P1

            if event.type == pygame.MOUSEBUTTONDOWN and app_phase == "INSTRUCTIONS":
                if start_btn.collidepoint(event.pos):
                    app_phase = "PLAY"

        if app_phase == "INSTRUCTIONS":
            draw_instructions()
        else:
            draw_game()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    run_game()
