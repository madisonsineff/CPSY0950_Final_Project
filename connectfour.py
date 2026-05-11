"""Connect Four baseline skeleton.

This file gives you a playable terminal version with clean game logic.
You can later connect these methods to a GUI/buttons for your game console.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


ROWS = 6
COLUMNS = 7
EMPTY = "."
PLAYER_ONE = "X"
PLAYER_TWO = "O"


@dataclass
class MoveResult:
    """Result of trying to place a piece in a column."""

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
        """Start a fresh game."""
        self.board = [[EMPTY for _ in range(COLUMNS)] for _ in range(ROWS)]
        self.current_player = PLAYER_ONE
        self.winner = None
        self.is_draw = False
        self.last_move = None

    def drop_piece(self, col: int) -> MoveResult:
        """Drop current player's piece into a 0-based column."""
        if self.winner or self.is_draw:
            return MoveResult(False, message="Game is over. Reset to play again.")

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
        """Check 4-in-a-row in all directions from last move."""
        directions = [
            (0, 1),   # horizontal
            (1, 0),   # vertical
            (1, 1),   # diagonal down-right
            (1, -1),  # diagonal down-left
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

    def board_as_string(self) -> str:
        """String board for terminal/debug display."""
        lines = [" ".join(str(i + 1) for i in range(COLUMNS))]
        lines.extend(" ".join(row) for row in self.board)
        return "\n".join(lines)


def run_terminal_game() -> None:
    """Simple playable loop for testing the game logic."""
    game = ConnectFourGame()
    print("Connect Four (Skeleton)")
    print("Type a column number (1-7), or q to quit.\n")

    while True:
        print(game.board_as_string())
        if game.winner:
            print(f"\nPlayer {game.winner} wins!")
            break
        if game.is_draw:
            print("\nIt's a draw!")
            break

        user_input = input(f"\nPlayer {game.current_player}, choose column: ").strip().lower()
        if user_input in {"q", "quit", "exit"}:
            print("Thanks for playing.")
            break

        if not user_input.isdigit():
            print("Please enter a number from 1 to 7.")
            continue

        chosen_col = int(user_input) - 1
        result = game.drop_piece(chosen_col)
        if not result.success:
            print(result.message)


if __name__ == "__main__":
    run_terminal_game()