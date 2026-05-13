"""Connect Four game.

Core logic is separated into `ConnectFourGame`, and a Pygame
front-end renders a traditional 7×6 board with clickable columns.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from typing import Optional

import pygame


ROWS = 6
COLUMNS = 7
EMPTY = "."
PLAYER_ONE = "X"
PLAYER_TWO = "O"


@dataclass
class MoveResult:
    success: bool
    row: Optional[int] = None
    col: Optional[int] = None
    message: str = ""


class ConnectFourGame:
    """Core Connect Four game logic (UI-agnostic)."""

    def __init__(self) -> None:
        self.board = [[EMPTY for _ in range(COLUMNS)] for _ in range(ROWS)]
        self.current_player = PLAYER_ONE
        self.winner: Optional[str] = None
        self.is_draw = False
        self.last_move: Optional[tuple[int, int]] = None

    def reset(self) -> None:
        self.board = [[EMPTY for _ in range(COLUMNS)] for _ in range(ROWS)]
        self.current_player = PLAYER_ONE
        self.winner = None
        self.is_draw = False
        self.last_move = None

    def drop_piece(self, col: int) -> MoveResult:
        if self.winner or self.is_draw:
            return MoveResult(False, message="Game is over. Press R to restart.")

        if not (0 <= col < COLUMNS):
            return MoveResult(False, message=f"Column must be 1-{COLUMNS}.")

        for row in range(ROWS - 1, -1, -1):
            if self.board[row][col] == EMPTY:
                self.board[row][col] = self.current_player
                self.last_move = (row, col)
                self._update_game_state(row, col)

                if not self.winner and not self.is_draw:
                    self._switch_player()

                return MoveResult(True, row=row, col=col)

        return MoveResult(False, message="That column is full.")

    def _switch_player(self) -> None:
        self.current_player = PLAYER_TWO if self.current_player == PLAYER_ONE else PLAYER_ONE

    def _update_game_state(self, row: int, col: int) -> None:
        piece = self.board[row][col]
        if self._is_winning_move(row, col, piece):
            self.winner = piece
            return

        if all(self.board[0][c] != EMPTY for c in range(COLUMNS)):
            self.is_draw = True

    def _is_winning_move(self, row: int, col: int, piece: str) -> bool:
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (1, -1),
        ]

        for dr, dc in directions:
            count = 1
            count += self._count_in_direction(row, col, dr, dc, piece)
            count += self._count_in_direction(row, col, -dr, -dc, piece)
            if count >= 4:
                return True
        return False

    def _count_in_direction(self, row: int, col: int, dr: int, dc: int, piece: str) -> int:
        count = 0
        r = row + dr
        c = col + dc

        while 0 <= r < ROWS and 0 <= c < COLUMNS and self.board[r][c] == piece:
            count += 1
            r += dr
            c += dc
        return count


def run_pygame_game() -> None:
    """Pygame front-end: traditional Connect Four with clickable columns."""
    pygame.init()

    base_dir = pathlib.Path(__file__).resolve().parent
    bg_path = base_dir / "connect4background.jpg"

    width, height = 900, 700
    screen = pygame.display.set_mode((width, height), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Four in a Row")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("chalkboard", 38, bold=True)
    small_font = pygame.font.SysFont("optima", 22)
    title_font = pygame.font.SysFont("chalkboard", 52, bold=True)
    panel_title_font = pygame.font.SysFont("optima", 32, bold=True)
    panel_font = pygame.font.SysFont("optima", 22)

    background = None
    if bg_path.exists():
        try:
            background_img = pygame.image.load(str(bg_path)).convert()
            background = pygame.transform.smoothscale(background_img, (width, height))
        except pygame.error:
            background = None

    game = ConnectFourGame()

    board_top = 160
    board_height = height - board_top - 80
    cell_size = min(width // COLUMNS, board_height // ROWS)
    board_width = cell_size * COLUMNS
    board_pixel_height = cell_size * ROWS
    board_left = (width - board_width) // 2
    board_rect = pygame.Rect(board_left, board_top, board_width, board_pixel_height)

    cx, cy = width // 2, height // 2
    instr_panel = pygame.Rect(cx - 320, 120, 640, 440)
    start_rect = pygame.Rect(cx - 140, instr_panel.bottom - 90, 280, 56)

    running = True
    message = "Click a column to drop your piece."
    app_phase = "INSTRUCTIONS"

    def draw_instructions() -> None:
        if background is not None:
            screen.blit(background, (0, 0))
            dim = pygame.Surface((width, height), pygame.SRCALPHA)
            dim.fill((10, 12, 16, 175))
            screen.blit(dim, (0, 0))
        else:
            screen.fill((20, 40, 90))

        pygame.draw.rect(screen, (248, 250, 255), instr_panel, border_radius=18)
        pygame.draw.rect(screen, (30, 44, 88), instr_panel, width=3, border_radius=18)

        title = panel_title_font.render("How to play", True, (20, 25, 45))
        screen.blit(title, (instr_panel.centerx - title.get_width() // 2, instr_panel.y + 26))

        lines = [
            "Goal: be the first player to get 4 in a row.",
            "Rows can be horizontal, vertical, or diagonal.",
            "",
            "On your turn, click a column to drop your piece.",
            "Red goes first. Yellow goes second.",
            "",
            "Controls:",
            "  - Enter / Space: start game",
            "  - Esc: quit",
            "  - R: restart (after you start playing)",
        ]
        y = instr_panel.y + 80
        for line in lines:
            if line == "":
                y += 16
                continue
            surf = panel_font.render(line, True, (35, 40, 70))
            screen.blit(surf, (instr_panel.x + 44, y))
            y += 30

        mp = pygame.mouse.get_pos()
        hover = start_rect.collidepoint(mp)
        fill = (52, 168, 98) if hover else (42, 140, 78)
        pygame.draw.rect(screen, fill, start_rect, border_radius=12)
        pygame.draw.rect(screen, (18, 72, 44), start_rect, width=2, border_radius=12)
        st = panel_title_font.render("Start game", True, (255, 255, 255))
        screen.blit(st, (start_rect.centerx - st.get_width() // 2, start_rect.centery - st.get_height() // 2))

        pygame.display.flip()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                continue

            if app_phase == "INSTRUCTIONS":
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    app_phase = "PLAY"
                    message = "Click a column to drop your piece."
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and start_rect.collidepoint(event.pos):
                    app_phase = "PLAY"
                    message = "Click a column to drop your piece."
                continue

            # PLAY phase events
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    game.reset()
                    message = "New game started. Click a column."
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if board_rect.collidepoint(event.pos) and not game.winner and not game.is_draw:
                    rel_x = event.pos[0] - board_left
                    col = rel_x // cell_size
                    result = game.drop_piece(int(col))
                    if not result.success:
                        message = result.message
                    else:
                        if game.winner:
                            message = f"Player {game.winner} wins! Press R to restart."
                        elif game.is_draw:
                            message = "It's a draw. Press R to restart."
                        else:
                            message = f"Player {game.current_player}'s turn."

        if app_phase == "INSTRUCTIONS":
            draw_instructions()
            clock.tick(60)
            continue

        if background is not None:
            screen.blit(background, (0, 0))
        else:
            screen.fill((25, 60, 120))

        title_surface = title_font.render("Four in a Row", True, (255, 255, 255))
        screen.blit(title_surface, (width // 2 - title_surface.get_width() // 2, 36))

        msg_surface = small_font.render(message, True, (255, 255, 255))
        screen.blit(msg_surface, (width // 2 - msg_surface.get_width() // 2, 100))

        pygame.draw.rect(screen, (0, 0, 180), board_rect, border_radius=8)

        for r in range(ROWS):
            for c in range(COLUMNS):
                cx = board_left + c * cell_size + cell_size // 2
                cy = board_top + r * cell_size + cell_size // 2
                radius = cell_size // 2 - 6
                piece = game.board[r][c]
                if piece == PLAYER_ONE:
                    color = (255, 50, 50)
                elif piece == PLAYER_TWO:
                    color = (250, 230, 60)
                else:
                    color = (230, 230, 230)
                pygame.draw.circle(screen, color, (cx, cy), radius)

        help_lines = [
            "ESC: Quit   |   R: Restart",
        ]
        y = height - 60
        for line in help_lines:
            s = small_font.render(line, True, (230, 230, 230))
            screen.blit(s, (width // 2 - s.get_width() // 2, y))
            y += 26

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    # When launched from GamePython_MAINHUB.py, ensure the game actually starts.
    run_pygame_game()
