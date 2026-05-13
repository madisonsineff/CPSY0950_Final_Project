"""Connect Four — clean redesign with audio, hover indicator, and better instructions.

Two players take turns clicking (or using keys 1-7) to drop a piece into a column.
First to get 4 in a row — horizontal, vertical, or diagonal — wins!

Controls
--------
Click a column  OR  press 1–7 to drop a piece in that column
H — return to hub
R — restart
Esc — quit

Audio
-----
Place a file named  connect4_audio.mp3  (or .ogg) next to this script for music.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

import pygame

# ── game constants ────────────────────────────────────────────────────────────
ROWS    = 6
COLUMNS = 7
EMPTY   = "."
P1      = "X"   # red
P2      = "O"   # yellow

P1_COLOR  = (220,  55,  55)
P2_COLOR  = (240, 195,  20)
EMPTY_COLOR = (42,  48,  68)
BOARD_COLOR = (25,  35, 100)
BOARD_BORDER= (15,  22,  72)
BG_COLOR    = (18,  22,  36)

# ── logic ─────────────────────────────────────────────────────────────────────

@dataclass
class MoveResult:
    success: bool
    row:     Optional[int] = None
    col:     Optional[int] = None
    message: str = ""


class ConnectFourGame:
    def __init__(self):
        self.board          = [[EMPTY]*COLUMNS for _ in range(ROWS)]
        self.current_player = P1
        self.winner:  Optional[str]            = None
        self.win_cells: list[tuple[int,int]]   = []
        self.is_draw        = False
        self.last_move: Optional[tuple[int,int]] = None

    def reset(self):
        self.__init__()

    def drop_piece(self, col: int) -> MoveResult:
        if self.winner or self.is_draw:
            return MoveResult(False, message="Game over — press R to restart.")
        if not (0 <= col < COLUMNS):
            return MoveResult(False, message="Invalid column.")
        for row in range(ROWS-1, -1, -1):
            if self.board[row][col] == EMPTY:
                self.board[row][col] = self.current_player
                self.last_move = (row, col)
                self._update_state(row, col)
                if not self.winner and not self.is_draw:
                    self.current_player = P2 if self.current_player == P1 else P1
                return MoveResult(True, row=row, col=col)
        return MoveResult(False, message="That column is full!")

    def _update_state(self, row, col):
        piece = self.board[row][col]
        cells = self._winning_cells(row, col, piece)
        if cells:
            self.winner    = piece
            self.win_cells = cells
            return
        if all(self.board[0][c] != EMPTY for c in range(COLUMNS)):
            self.is_draw = True

    def _winning_cells(self, row, col, piece):
        for dr, dc in [(0,1),(1,0),(1,1),(1,-1)]:
            cells = [(row, col)]
            for sign in (1, -1):
                r, c = row+dr*sign, col+dc*sign
                while 0<=r<ROWS and 0<=c<COLUMNS and self.board[r][c]==piece:
                    cells.append((r, c))
                    r += dr*sign; c += dc*sign
            if len(cells) >= 4:
                return cells
        return []


# ── pygame front-end ──────────────────────────────────────────────────────────

def run_pygame_game():
    pygame.init()

    base_dir = pathlib.Path(__file__).resolve().parent
    hub_path = base_dir / "GamePython_MAINHUB.py"

    # ── audio ──
    def start_music():
        for name in ("connect4_audio.mp3", "connect4_audio.ogg"):
            p = base_dir / name
            if p.exists():
                try:
                    pygame.mixer.init()
                    pygame.mixer.music.load(str(p))
                    pygame.mixer.music.set_volume(0.30)
                    pygame.mixer.music.play(-1)
                except pygame.error:
                    pass
                return

    def stop_music():
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    start_music()

    # ── window ──
    CELL    = 82
    GAP     = 6
    BOARD_W = COLUMNS * CELL + (COLUMNS+1) * GAP
    BOARD_H = ROWS    * CELL + (ROWS+1)    * GAP
    TOP_H   = 90     # title + turn indicator
    BOT_H   = 52     # hint line
    WIN_W   = 1200
    WIN_H   = 800

    BOARD_X = (WIN_W - BOARD_W) // 2
    BOARD_Y = TOP_H

    screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Four in a Row")
    clock = pygame.time.Clock()

    font_title  = pygame.font.SysFont("chalkboard", 36, bold=True)
    font_label  = pygame.font.SysFont("optima", 22, bold=True)
    font_small  = pygame.font.SysFont("optima", 18)
    font_hint   = pygame.font.SysFont("optima", 14)
    font_instr  = pygame.font.SysFont("optima", 19)
    font_instr_bold = pygame.font.SysFont("optima", 20, bold=True)

    game      = ConnectFourGame()
    app_phase = "INSTRUCTIONS"

    # instruction panel
    panel_w = min(580, WIN_W - 40)
    panel_h = 420
    panel   = pygame.Rect((WIN_W-panel_w)//2, (WIN_H-panel_h)//2, panel_w, panel_h)
    start_btn = pygame.Rect(panel.centerx-110, panel.bottom-60, 220, 44)

    def col_from_x(x):
        rel = x - BOARD_X - GAP
        if rel < 0:
            return None
        c = rel // (CELL + GAP)
        if 0 <= c < COLUMNS:
            # make sure x is actually inside a cell, not in a gap
            cell_start = BOARD_X + GAP + c*(CELL+GAP)
            if x < cell_start or x > cell_start + CELL:
                return None
            return c
        return None

    def circle_center(r, c):
        cx = BOARD_X + GAP + c*(CELL+GAP) + CELL//2
        cy = BOARD_Y + GAP + r*(CELL+GAP) + CELL//2
        return cx, cy

    def draw_instructions():
        screen.fill(BG_COLOR)
        pygame.draw.rect(screen, (245,248,255), panel, border_radius=14)
        pygame.draw.rect(screen, (30,44,88),    panel, width=3, border_radius=14)

        t = font_title.render("How to Play — Four in a Row", True, (20,25,55))
        screen.blit(t, (panel.centerx - t.get_width()//2, panel.y+14))
        pygame.draw.line(screen, (180,185,210),
                         (panel.x+24, panel.y+52), (panel.right-24, panel.y+52), 1)

        # small color dots next to player names
        pygame.draw.circle(screen, P1_COLOR,  (panel.x+38, panel.y+78), 9)
        pygame.draw.circle(screen, P2_COLOR,  (panel.x+38, panel.y+104), 9)
        r1 = font_instr_bold.render("Red goes first (Player 1)", True, (20,25,55))
        r2 = font_instr_bold.render("Yellow goes second (Player 2)", True, (20,25,55))
        screen.blit(r1, (panel.x+54, panel.y+68))
        screen.blit(r2, (panel.x+54, panel.y+94))

        pygame.draw.line(screen, (200,205,220),
                         (panel.x+24, panel.y+124), (panel.right-24, panel.y+124), 1)

        sections = [
            ("bold", "Goal"),
            ("text", "Be the first to get 4 of your pieces in a row."),
            ("text", "Rows can be horizontal, vertical, or diagonal."),
            ("gap",  ""),
            ("bold", "How to play"),
            ("text", "Click any column to drop your piece into it."),
            ("text", "You can also press keys 1–7 (left to right column)."),
            ("text", "Pieces fall to the lowest available slot."),
            ("gap",  ""),
            ("bold", "Controls"),
            ("text", "Click or press 1–7 to drop   |   R = restart   |   H = hub   |   Esc = quit"),
        ]

        y = panel.y + 132
        for kind, text in sections:
            if kind == "gap":
                y += 6
                continue
            fnt   = font_instr_bold if kind == "bold" else font_instr
            color = (20,25,55) if kind == "bold" else (55,60,90)
            s = fnt.render(text, True, color)
            screen.blit(s, (panel.x+24, y))
            y += 25

        mp = pygame.mouse.get_pos()
        hover = start_btn.collidepoint(mp)
        pygame.draw.rect(screen, (52,168,98) if hover else (42,140,78), start_btn, border_radius=10)
        pygame.draw.rect(screen, (18,72,44), start_btn, width=2, border_radius=10)
        st = font_label.render("Start Game", True, (255,255,255))
        screen.blit(st, (start_btn.centerx-st.get_width()//2, start_btn.centery-st.get_height()//2))
        pygame.display.flip()

    def draw_game(hover_col):
        screen.fill(BG_COLOR)

        # title
        t = font_title.render("Four in a Row", True, (240,240,255))
        screen.blit(t, (WIN_W//2 - t.get_width()//2, 12))

        # turn / status line
        if game.winner:
            who = "Red" if game.winner == P1 else "Yellow"
            wc  = P1_COLOR if game.winner == P1 else P2_COLOR
            msg = f"{who} wins!  Press R to play again."
        elif game.is_draw:
            msg, wc = "It's a draw!  Press R to play again.", (200,200,200)
        else:
            who = "Red" if game.current_player == P1 else "Yellow"
            wc  = P1_COLOR if game.current_player == P1 else P2_COLOR
            msg = f"{who}'s turn — click a column or press 1–7"

        # colored dot + message
        dot_x = WIN_W//2 - font_small.size(msg)[0]//2 - 14
        pygame.draw.circle(screen, wc, (dot_x, 62), 7)
        ms = font_small.render(msg, True, wc)
        screen.blit(ms, (dot_x+14, 54))

        # hover arrow above board
        if hover_col is not None and not game.winner and not game.is_draw:
            ax = BOARD_X + GAP + hover_col*(CELL+GAP) + CELL//2
            ay = BOARD_Y - 18
            ac = P1_COLOR if game.current_player == P1 else P2_COLOR
            pts = [(ax, ay+2), (ax-10, ay-12), (ax+10, ay-12)]
            pygame.draw.polygon(screen, ac, pts)

        # board background
        pygame.draw.rect(screen, BOARD_COLOR,  (BOARD_X, BOARD_Y, BOARD_W, BOARD_H), border_radius=10)
        pygame.draw.rect(screen, BOARD_BORDER, (BOARD_X, BOARD_Y, BOARD_W, BOARD_H), width=3, border_radius=10)

        # pieces
        radius = CELL//2 - 6
        for r in range(ROWS):
            for c in range(COLUMNS):
                cx, cy = circle_center(r, c)
                piece  = game.board[r][c]
                if piece == P1:
                    col = P1_COLOR
                elif piece == P2:
                    col = P2_COLOR
                else:
                    # hover preview: lighten empty cell in hovered column
                    if c == hover_col and not game.winner and not game.is_draw:
                        pc = P1_COLOR if game.current_player == P1 else P2_COLOR
                        col = tuple(min(255, v//3) for v in pc)
                    else:
                        col = EMPTY_COLOR
                pygame.draw.circle(screen, col, (cx, cy), radius)
                # shine highlight
                pygame.draw.circle(screen, (255,255,255,60), (cx-radius//4, cy-radius//4), radius//4)

        # highlight winning cells
        if game.win_cells:
            for r, c in game.win_cells:
                cx, cy = circle_center(r, c)
                pygame.draw.circle(screen, (255,255,255), (cx,cy), radius+4, 3)

        # bottom hint
        h = font_hint.render("H = hub   R = restart   Esc = quit", True, (80,85,105))
        screen.blit(h, (WIN_W//2 - h.get_width()//2, WIN_H - 18))

        pygame.display.flip()

    def return_to_hub():
        stop_music()
        if hub_path.exists():
            subprocess.Popen([sys.executable, str(hub_path)])
        pygame.quit()
        sys.exit(0)

    col_keys = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                pygame.K_5, pygame.K_6, pygame.K_7]
    hover_col = None
    running   = True

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
                    game.reset()
                    continue

                if app_phase == "PLAY" and not game.winner and not game.is_draw:
                    if event.key in col_keys:
                        game.drop_piece(col_keys.index(event.key))

            if event.type == pygame.MOUSEMOTION and app_phase == "PLAY":
                hover_col = col_from_x(event.pos[0])

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if app_phase == "INSTRUCTIONS":
                    if start_btn.collidepoint(event.pos):
                        app_phase = "PLAY"
                elif app_phase == "PLAY" and not game.winner and not game.is_draw:
                    c = col_from_x(event.pos[0])
                    if c is not None:
                        game.drop_piece(c)

        if app_phase == "INSTRUCTIONS":
            draw_instructions()
        else:
            draw_game(hover_col)
        clock.tick(60)

    stop_music()
    pygame.quit()


if __name__ == "__main__":
    run_pygame_game()
