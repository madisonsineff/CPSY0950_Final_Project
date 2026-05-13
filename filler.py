"""Filler — GamePigeon-style color flood game for 2 players on the same keyboard.

Player 1 starts at the BOTTOM-LEFT corner.
Player 2 starts at the TOP-RIGHT corner.

Both players use the SAME number keys 1–6 to pick a color.
On your turn, press a number to flood-fill your territory with that color.
Most cells when the board is full = winner!

Controls
--------
Both players: 1  2  3  4  5  6   (pick a color on your turn)
H — return to hub at any time
Esc — quit
R — restart after game over

Audio
-----
Place a file named filler_audio.mp3 (or .ogg) next to this script for music.
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
    (220,  60,  55),   # 1 red
    (230, 185,  20),   # 2 yellow
    ( 55, 180,  90),   # 3 green
    ( 50, 140, 210),   # 4 blue
    (145,  80, 190),   # 5 purple
    ( 65,  75,  95),   # 6 dark
]
NUM_COLORS = len(COLORS)

ROWS, COLS = 8, 8
P1, P2 = 1, 2


# ── audio ─────────────────────────────────────────────────────────────────────

def _start_music():
    base = pathlib.Path(__file__).resolve().parent
    for name in ("filler_audio.mp3", "filler_audio.ogg"):
        p = base / name
        if p.exists():
            try:
                pygame.mixer.init()
                pygame.mixer.music.load(str(p))
                pygame.mixer.music.set_volume(0.30)
                pygame.mixer.music.play(-1)
            except pygame.error:
                pass
            return


def _stop_music():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


# ── board helpers ─────────────────────────────────────────────────────────────

def make_board() -> list[list[int]]:
    board = [[random.randrange(NUM_COLORS) for _ in range(COLS)] for _ in range(ROWS)]
    board[ROWS - 1][0] = 0
    board[0][COLS - 1] = 1
    return board


def flood_fill(board, owned, player, new_color):
    for r in range(ROWS):
        for c in range(COLS):
            if owned[r][c] == player:
                board[r][c] = new_color
    queue = [(r, c) for r in range(ROWS) for c in range(COLS) if owned[r][c] == player]
    visited = set(queue)
    while queue:
        r, c = queue.pop()
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and (nr,nc) not in visited:
                if board[nr][nc] == new_color and owned[nr][nc] is None:
                    visited.add((nr, nc))
                    owned[nr][nc] = player
                    board[nr][nc] = new_color
                    queue.append((nr, nc))


def count_owned(owned, player):
    return sum(owned[r][c] == player for r in range(ROWS) for c in range(COLS))


def is_full(owned):
    return all(owned[r][c] is not None for r in range(ROWS) for c in range(COLS))


def current_color(board, owned, player):
    for r in range(ROWS):
        for c in range(COLS):
            if owned[r][c] == player:
                return board[r][c]
    return 0


def new_game():
    board = make_board()
    owned = [[None]*COLS for _ in range(ROWS)]
    owned[ROWS-1][0] = P1
    owned[0][COLS-1] = P2
    return board, owned, P1, False, None


# ── main ─────────────────────────────────────────────────────────────────────

def run_game():
    pygame.init()
    _start_music()

    hub = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"

    # ── window is fixed 1200x800 to match all other games ──
    WIN_W = 1200
    WIN_H = 800

    # ── board sizing: fill most of the window nicely ──
    CELL     = 74
    GAP      = 4
    BOARD_PX = COLS * (CELL + GAP) + GAP   # 8*78+4 = 628
    BOARD_PY = ROWS * (CELL + GAP) + GAP   # 628

    # center the board horizontally, leave room top/bottom for UI
    BOARD_X  = (WIN_W - BOARD_PX) // 2     # ~286
    BOARD_Y  = 90                           # below title

    SIDE_W   = BOARD_X                     # panel width each side = same as left offset

    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Filler")
    clock = pygame.time.Clock()

    font_title      = pygame.font.SysFont("chalkboard", 42, bold=True)
    font_label      = pygame.font.SysFont("optima", 24, bold=True)
    font_score      = pygame.font.SysFont("chalkboard", 34, bold=True)
    font_small      = pygame.font.SysFont("optima", 20)
    font_hint       = pygame.font.SysFont("optima", 16)
    font_instr      = pygame.font.SysFont("optima", 21)
    font_instr_bold = pygame.font.SysFont("optima", 22, bold=True)

    board, owned, turn, game_over, winner = new_game()
    app_phase = "INSTRUCTIONS"

    panel_w   = 680
    panel_h   = 440
    panel     = pygame.Rect((WIN_W-panel_w)//2, (WIN_H-panel_h)//2, panel_w, panel_h)
    start_btn = pygame.Rect(panel.centerx-120, panel.bottom-66, 240, 48)

    def draw_instructions():
        screen.fill((28, 32, 46))
        pygame.draw.rect(screen, (245, 248, 255), panel, border_radius=14)
        pygame.draw.rect(screen, (30, 44, 88),    panel, width=3, border_radius=14)

        t = font_title.render("How to Play — Filler", True, (20, 25, 55))
        screen.blit(t, (panel.centerx - t.get_width()//2, panel.y + 16))
        pygame.draw.line(screen, (180,185,210),
                         (panel.x+24, panel.y+58), (panel.right-24, panel.y+58), 1)

        sections = [
            ("bold", "Goal"),
            ("text", "Claim the most squares before the board fills up!"),
            ("gap",  ""),
            ("bold", "Setup"),
            ("text", "Player 1 starts bottom-left.  Player 2 starts top-right."),
            ("gap",  ""),
            ("bold", "Taking a turn"),
            ("text", "Press 1–6 to pick a color. Your territory grows to every"),
            ("text", "touching square that already has that color."),
            ("text", "You can't pick your own color or your opponent's color."),
            ("gap",  ""),
            ("bold", "Color keys:  1=Red  2=Yellow  3=Green  4=Blue  5=Purple  6=Dark"),
            ("gap",  ""),
            ("text", "Both players share the same keys — just take turns!"),
            ("text", "H = hub   |   R = restart   |   Esc = quit"),
        ]

        y = panel.y + 66
        for kind, text in sections:
            if kind == "gap":
                y += 6
                continue
            fnt   = font_instr_bold if kind == "bold" else font_instr
            color = (20, 25, 55)    if kind == "bold" else (55, 60, 90)
            s = fnt.render(text, True, color)
            screen.blit(s, (panel.x + 28, y))
            y += 26

        mp = pygame.mouse.get_pos()
        hover = start_btn.collidepoint(mp)
        pygame.draw.rect(screen, (52,168,98) if hover else (42,140,78), start_btn, border_radius=10)
        pygame.draw.rect(screen, (18,72,44), start_btn, width=2, border_radius=10)
        st = font_label.render("Start Game", True, (255,255,255))
        screen.blit(st, (start_btn.centerx - st.get_width()//2,
                         start_btn.centery - st.get_height()//2))
        pygame.display.flip()

    def cell_rect(r, c):
        x = BOARD_X + GAP + c*(CELL+GAP)
        y = BOARD_Y + GAP + r*(CELL+GAP)
        return pygame.Rect(x, y, CELL, CELL)

    def draw_game():
        screen.fill((22, 26, 38))

        # title
        t = font_title.render("Filler", True, (240,240,255))
        screen.blit(t, (WIN_W//2 - t.get_width()//2, 18))

        # board cells
        for r in range(ROWS):
            for c in range(COLS):
                rect  = cell_rect(r, c)
                color = COLORS[board[r][c]]
                owner = owned[r][c]
                pygame.draw.rect(screen, color, rect, border_radius=6)
                if owner == P1:
                    pygame.draw.rect(screen, (255,225,120), rect, width=3, border_radius=6)
                elif owner == P2:
                    pygame.draw.rect(screen, (130,205,255), rect, width=3, border_radius=6)

        p1_count = count_owned(owned, P1)
        p2_count = count_owned(owned, P2)
        total    = ROWS * COLS

        # ── left panel: Player 1 ──
        px1 = BOARD_X // 2
        lbl = font_label.render("Player 1", True, (255,220,120))
        screen.blit(lbl, (px1 - lbl.get_width()//2, BOARD_Y + 20))
        sc = font_score.render(str(p1_count), True, (255,255,255))
        screen.blit(sc, (px1 - sc.get_width()//2, BOARD_Y + 52))
        p1c = current_color(board, owned, P1)
        pygame.draw.circle(screen, COLORS[p1c], (px1, BOARD_Y + 110), 18)
        pygame.draw.circle(screen, (255,225,120), (px1, BOARD_Y + 110), 18, 3)
        cur_lbl = font_hint.render("current", True, (180,180,200))
        screen.blit(cur_lbl, (px1 - cur_lbl.get_width()//2, BOARD_Y + 134))

        # ── right panel: Player 2 ──
        px2 = BOARD_X + BOARD_PX + (WIN_W - BOARD_X - BOARD_PX) // 2
        lbl2 = font_label.render("Player 2", True, (130,205,255))
        screen.blit(lbl2, (px2 - lbl2.get_width()//2, BOARD_Y + 20))
        sc2 = font_score.render(str(p2_count), True, (255,255,255))
        screen.blit(sc2, (px2 - sc2.get_width()//2, BOARD_Y + 52))
        p2c = current_color(board, owned, P2)
        pygame.draw.circle(screen, COLORS[p2c], (px2, BOARD_Y + 110), 18)
        pygame.draw.circle(screen, (130,205,255), (px2, BOARD_Y + 110), 18, 3)
        cur_lbl2 = font_hint.render("current", True, (180,180,200))
        screen.blit(cur_lbl2, (px2 - cur_lbl2.get_width()//2, BOARD_Y + 134))

        # ── color swatches below board ──
        sw      = 44
        sw_gap  = 10
        total_w = NUM_COLORS * sw + (NUM_COLORS-1) * sw_gap
        sw_x0   = WIN_W//2 - total_w//2
        sw_y    = BOARD_Y + BOARD_PY + 16

        for i in range(NUM_COLORS):
            sx   = sw_x0 + i*(sw+sw_gap)
            rect = pygame.Rect(sx, sw_y, sw, sw)
            pygame.draw.rect(screen, COLORS[i], rect, border_radius=6)
            if not game_over:
                cur_c = current_color(board, owned, turn)
                bw = 4 if i == cur_c else 1
                bc = (255,255,255) if i == cur_c else (90,95,110)
                pygame.draw.rect(screen, bc, rect, width=bw, border_radius=6)
            k = font_hint.render(str(i+1), True, (210,210,210))
            screen.blit(k, (rect.centerx - k.get_width()//2, rect.bottom + 4))

        # ── turn indicator ──
        if not game_over:
            tc = (255,220,120) if turn == P1 else (130,205,255)
            wt = font_small.render(f"Player {turn}'s turn — press 1 to 6", True, tc)
            screen.blit(wt, (WIN_W//2 - wt.get_width()//2, sw_y + sw + 22))

        # ── bottom hint ──
        h = font_hint.render("H = hub   R = restart   Esc = quit", True, (80,85,105))
        screen.blit(h, (WIN_W//2 - h.get_width()//2, WIN_H - 20))

        # ── game over overlay ──
        if game_over:
            ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 155))
            screen.blit(ov, (0, 0))
            if winner == 0:
                msg, mc = "It's a Draw!", (255,255,255)
            else:
                msg = f"Player {winner} Wins!"
                mc  = (255,220,120) if winner == P1 else (130,205,255)
            wt2 = font_title.render(msg, True, mc)
            screen.blit(wt2, (WIN_W//2 - wt2.get_width()//2, WIN_H//2 - 60))
            sc3 = font_label.render(f"{p1_count} vs {p2_count}  (of {total} squares)", True, (220,220,220))
            screen.blit(sc3, (WIN_W//2 - sc3.get_width()//2, WIN_H//2 + 4))
            re  = font_small.render("R = play again   |   H = hub   |   Esc = quit", True, (165,165,165))
            screen.blit(re, (WIN_W//2 - re.get_width()//2, WIN_H//2 + 48))

        pygame.display.flip()

    def return_to_hub():
        _stop_music()
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
                    num_keys = [pygame.K_1, pygame.K_2, pygame.K_3,
                                pygame.K_4, pygame.K_5, pygame.K_6]
                    if event.key in num_keys:
                        chosen  = num_keys.index(event.key)
                        cur     = current_color(board, owned, turn)
                        opp     = P2 if turn == P1 else P1
                        opp_cur = current_color(board, owned, opp)
                        if chosen != cur and chosen != opp_cur:
                            flood_fill(board, owned, turn, chosen)
                            if is_full(owned):
                                game_over = True
                                c1 = count_owned(owned, P1)
                                c2 = count_owned(owned, P2)
                                winner = P1 if c1 > c2 else (P2 if c2 > c1 else 0)
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

    _stop_music()
    pygame.quit()


if __name__ == "__main__":
    run_game()
