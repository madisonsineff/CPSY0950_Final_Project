"""Cup Pong baseline skeleton.

Simple turn-based "cup pong" logic for two players.
You can later connect this game state to a GUI with clickable buttons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


DEFAULT_CUPS_PER_SIDE = 6


@dataclass
class ShotResult:
    """Result of a shot attempt."""

    success: bool
    message: str
    hit: bool = False
    target_cup: Optional[int] = None


class CupPongGame:
    """Core cup pong logic (UI-agnostic)."""

    def __init__(self, cups_per_side: int = DEFAULT_CUPS_PER_SIDE) -> None:
        if cups_per_side <= 0:
            raise ValueError("cups_per_side must be greater than 0.")

        self.cups_per_side = cups_per_side
        self.player_one_cups = [True] * cups_per_side
        self.player_two_cups = [True] * cups_per_side
        self.current_player = 1
        self.winner: Optional[int] = None

    def reset(self) -> None:
        """Reset game to initial state."""
        self.player_one_cups = [True] * self.cups_per_side
        self.player_two_cups = [True] * self.cups_per_side
        self.current_player = 1
        self.winner = None

    def take_shot(self, target_index: int) -> ShotResult:
        """Shoot at opponent cup by 0-based index."""
        if self.winner is not None:
            return ShotResult(False, "Game is over. Reset to play again.")

        if not (0 <= target_index < self.cups_per_side):
            return ShotResult(False, f"Target must be 1-{self.cups_per_side}.")

        target_cups = self._opponent_cups()

        if not target_cups[target_index]:
            return ShotResult(False, "That cup is already out.")

        # Skeleton rule: a chosen valid cup is always a hit.
        target_cups[target_index] = False
        self._update_winner()

        if self.winner is None:
            self._switch_player()

        return ShotResult(
            True,
            "Hit! Cup removed.",
            hit=True,
            target_cup=target_index,
        )

    def remaining_cups(self, player: int) -> int:
        """Return number of cups still standing for a player."""
        cups = self._cups_for_player(player)
        return sum(1 for is_up in cups if is_up)

    def _switch_player(self) -> None:
        self.current_player = 2 if self.current_player == 1 else 1

    def _update_winner(self) -> None:
        if self.remaining_cups(1) == 0:
            self.winner = 2
        elif self.remaining_cups(2) == 0:
            self.winner = 1

    def _opponent_cups(self) -> list[bool]:
        return self.player_two_cups if self.current_player == 1 else self.player_one_cups

    def _cups_for_player(self, player: int) -> list[bool]:
        if player == 1:
            return self.player_one_cups
        if player == 2:
            return self.player_two_cups
        raise ValueError("player must be 1 or 2.")

    def board_as_string(self) -> str:
        """Render a minimal text board for testing/debugging."""
        p1 = " ".join("O" if cup else "X" for cup in self.player_one_cups)
        p2 = " ".join("O" if cup else "X" for cup in self.player_two_cups)
        return (
            "Cup Pong (O = cup standing, X = cup removed)\n"
            f"Player 2 cups: {p2}\n"
            f"Player 1 cups: {p1}"
        )


def run_terminal_game() -> None:
    """Basic terminal runner for quick logic testing."""
    game = CupPongGame()
    print("Cup Pong (Skeleton)")
    print("Pick an opponent cup number to shoot (1-6), or q to quit.\n")

    while True:
        print(game.board_as_string())

        if game.winner is not None:
            print(f"\nPlayer {game.winner} wins!")
            break

        user_input = input(f"\nPlayer {game.current_player}, target cup: ").strip().lower()
        if user_input in {"q", "quit", "exit"}:
            print("Thanks for playing.")
            break

        if not user_input.isdigit():
            print(f"Please enter a number from 1 to {game.cups_per_side}.")
            continue

        target = int(user_input) - 1
        result = game.take_shot(target)
        print(result.message)


if __name__ == "__main__":
    run_terminal_game()