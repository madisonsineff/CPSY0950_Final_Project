# this is the code for the Cup Pong game! The idea is to have this script launch when the user presses the "Cup Pong" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import pygame


INITIAL_CUPS_PER_SIDE = 10
ATTEMPTS_PER_ROUND = 2
GRAVITY = 0.42
BALL_RADIUS = 9
MAX_SPEED = 17.0
AIM_PULL_SCALE = 0.16
LAUNCH_GRAB_RADIUS = 72
MIN_DRAG_TO_FIRE = 14


def triangle_row_counts(total: int) -> List[int]:
    """Split total cups into rows 1,2,3,... until cups are placed; last row may be partial."""
    rows: List[int] = []
    remaining = total
    k = 1
    while remaining > 0:
        take = min(k, remaining)
        rows.append(take)
        remaining -= take
        k += 1
    return rows


def rack_positions(
    n: int,
    apex_x: float,
    apex_y: float,
    row_dy: float,
    col_dx: float,
) -> List[Tuple[float, float]]:
    """Cup centers: row 1 at apex, each row below has one more slot (triangle), then extras."""
    if n <= 0:
        return []
    rows = triangle_row_counts(n)
    out: List[Tuple[float, float]] = []
    y = apex_y
    idx = 0
    for r, count in enumerate(rows):
        row_w = (count - 1) * col_dx
        for j in range(count):
            if idx >= n:
                break
            x = apex_x - row_w / 2 + j * col_dx
            out.append((x, y))
            idx += 1
        y += row_dy
    return out[:n]


@dataclass
class ShotResult:
    success: bool
    message: str
    hit: bool = False
    target_cup: Optional[int] = None


class CupPongGame:
    """Two players, triangular racks; sink both tries in one turn → defender gains a cup."""

    def __init__(self, initial_cups_per_side: int = INITIAL_CUPS_PER_SIDE) -> None:
        if initial_cups_per_side <= 0:
            raise ValueError("initial_cups_per_side must be greater than 0.")

        self.initial_cups_per_side = initial_cups_per_side
        self.player_one_cups: List[bool] = [True] * initial_cups_per_side
        self.player_two_cups: List[bool] = [True] * initial_cups_per_side
        self.current_player = 1
        self.winner: Optional[int] = None
        self.attempts_left = ATTEMPTS_PER_ROUND
        self.hits_this_turn = 0

    def reset(self) -> None:
        n = self.initial_cups_per_side
        self.player_one_cups = [True] * n
        self.player_two_cups = [True] * n
        self.current_player = 1
        self.winner = None
        self.attempts_left = ATTEMPTS_PER_ROUND
        self.hits_this_turn = 0

    def finish_throw(self, cup_index_if_hit: Optional[int]) -> ShotResult:
        """Resolve one throw: cup_index_if_hit indexes a standing cup on the opponent rack."""
        if self.winner is not None:
            return ShotResult(False, "Game is over. Press R to reset.")

        hit = False
        msg = ""
        opp = self._opponent_cups()

        if cup_index_if_hit is not None and 0 <= cup_index_if_hit < len(opp):
            if opp[cup_index_if_hit]:
                opp[cup_index_if_hit] = False
                hit = True
                self.hits_this_turn += 1
                msg = "Hit! Cup removed."
                self._update_winner()
            else:
                msg = "Miss — that cup is already down."
        else:
            msg = "Miss."

        self.attempts_left -= 1
        extra = ""

        if self.winner is None and self.attempts_left <= 0:
            if self.hits_this_turn >= ATTEMPTS_PER_ROUND:
                self._add_penalty_cup_to_defender()
                extra += " Both throws in — opponent gains a cup!"
            self.hits_this_turn = 0
            self.attempts_left = ATTEMPTS_PER_ROUND
            self._switch_player()
            extra += f" Player {self.current_player}'s turn ({ATTEMPTS_PER_ROUND} throws)."

        return ShotResult(True, msg + extra, hit=hit, target_cup=cup_index_if_hit if hit else None)

    def _add_penalty_cup_to_defender(self) -> None:
        """Shooter sank every attempt this turn; defender (other player) gets one cup back."""
        defender = 2 if self.current_player == 1 else 1
        rack = self._cups_for_player(defender)
        rack.append(True)

    def remaining_cups(self, player: int) -> int:
        cups = self._cups_for_player(player)
        return sum(1 for is_up in cups if is_up)

    def _switch_player(self) -> None:
        self.current_player = 2 if self.current_player == 1 else 1

    def _update_winner(self) -> None:
        if self.remaining_cups(1) == 0:
            self.winner = 2
        elif self.remaining_cups(2) == 0:
            self.winner = 1

    def _opponent_cups(self) -> List[bool]:
        return self.player_two_cups if self.current_player == 1 else self.player_one_cups

    def _cups_for_player(self, player: int) -> List[bool]:
        if player == 1:
            return self.player_one_cups
        if player == 2:
            return self.player_two_cups
        raise ValueError("player must be 1 or 2.")

    def board_as_string(self) -> str:
        def line(cups: Sequence[bool]) -> str:
            return " ".join("O" if cup else "X" for cup in cups)

        return (
            "Cup Pong (O = standing, X = removed)\n"
            f"Player 2 rack (left target): {line(self.player_two_cups)}\n"
            f"Player 1 rack (right target): {line(self.player_one_cups)}\n"
            f"Current: Player {self.current_player} | Throws left: {self.attempts_left}"
        )


def run_terminal_game() -> None:
    game = CupPongGame()
    n = len(game.player_two_cups)
    print("Cup Pong (terminal) — m = miss, k = hit cup k (1-indexed), q = quit")
    print(f"{INITIAL_CUPS_PER_SIDE} cups per triangle; {ATTEMPTS_PER_ROUND} tries per turn.\n")

    while True:
        print(game.board_as_string())
        if game.winner is not None:
            print(f"\nPlayer {game.winner} wins!")
            break

        mx = len(game._opponent_cups())
        user_input = input(
            f"\nPlayer {game.current_player} ({game.attempts_left} throw(s) left): "
        ).strip().lower()
        if user_input in {"q", "quit", "exit"}:
            print("Thanks for playing.")
            break
        if user_input == "m":
            r = game.finish_throw(None)
            print(r.message)
            continue
        if not user_input.isdigit():
            print(f"Enter m or 1-{mx}.")
            continue
        t = int(user_input) - 1
        r = game.finish_throw(t)
        print(r.message)


def run_pygame_gui() -> None:
    pygame.init()
    size = (1040, 700)
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Cup Pong — two racks, drag to aim")
    clock = pygame.time.Clock()

    bg = (34, 40, 49)
    table = (42, 92, 62)
    cup_p1 = (200, 220, 255)
    cup_p2 = (255, 200, 200)
    cup_out = (80, 80, 90)
    ring = (255, 220, 80)
    ball_c = (255, 250, 220)
    text_c = (240, 240, 245)
    highlight = (255, 255, 120)

    font_lg = pygame.font.SysFont("optima", 30, bold=True)
    font_md = pygame.font.SysFont("optima", 20)
    font_sm = pygame.font.SysFont("optima", 16)

    game = CupPongGame()
    cup_r = 22
    row_dy = 46
    col_dx = 48

    # Adjacent triangles (apex toward top); P2 rack left, P1 rack right.
    apex_p2 = pygame.Vector2(320, 118)
    apex_p1 = pygame.Vector2(size[0] - 320, 118)

    launcher_p1 = pygame.Vector2(apex_p1.x, size[1] - 88)
    launcher_p2 = pygame.Vector2(apex_p2.x, 88)

    def positions_p1() -> List[Tuple[float, float]]:
        return rack_positions(len(game.player_one_cups), apex_p1.x, apex_p1.y, row_dy, col_dx)

    def positions_p2() -> List[Tuple[float, float]]:
        return rack_positions(len(game.player_two_cups), apex_p2.x, apex_p2.y, row_dy, col_dx)

    def launcher() -> pygame.Vector2:
        return launcher_p1 if game.current_player == 1 else launcher_p2

    def dist_to_launcher(pos: Tuple[int, int]) -> float:
        lx, ly = launcher()
        return math.hypot(pos[0] - lx, pos[1] - ly)

    phase = "IDLE"
    aim_start: Optional[Tuple[int, int]] = None
    ball_pos = pygame.Vector2()
    ball_vel = pygame.Vector2()
    flight_ticks = 0
    status = "Player 1 shoots at the LEFT triangle (Player 2's cups)."
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r and game.winner is not None:
                    game.reset()
                    phase = "IDLE"
                    status = "New game — Player 1's turn (shoot LEFT rack)."
            elif game.winner is None and phase == "IDLE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if dist_to_launcher(event.pos) <= LAUNCH_GRAB_RADIUS:
                        aim_start = event.pos
                        phase = "AIMING"
            elif game.winner is None and phase == "AIMING":
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and aim_start is not None:
                    mx, my = event.pos
                    sx, sy = aim_start
                    drag = math.hypot(mx - sx, my - sy)
                    if drag < MIN_DRAG_TO_FIRE:
                        phase = "IDLE"
                        aim_start = None
                        status = "Drag farther from the dot to throw."
                    else:
                        lv = launcher()
                        vx = (mx - lv.x) * AIM_PULL_SCALE
                        vy = (my - lv.y) * AIM_PULL_SCALE
                        spd = math.hypot(vx, vy)
                        if spd > MAX_SPEED:
                            vx *= MAX_SPEED / spd
                            vy *= MAX_SPEED / spd
                        if spd < 3.0:
                            vx *= 3.0 / max(spd, 0.001)
                            vy *= 3.0 / max(spd, 0.001)
                        ball_pos.update(lv.x, lv.y)
                        ball_vel.update(vx, vy)
                        phase = "BALL"
                        flight_ticks = 0
                    aim_start = None

        if phase == "BALL" and game.winner is None:
            ball_vel.y += GRAVITY
            ball_pos += ball_vel
            flight_ticks += 1

            hit_idx: Optional[int] = None
            if game.current_player == 1:
                opp_pts = positions_p2()
                opp = game.player_two_cups
            else:
                opp_pts = positions_p1()
                opp = game.player_one_cups

            for i, (cxi, cyi) in enumerate(opp_pts):
                if i >= len(opp) or not opp[i]:
                    continue
                d = math.hypot(ball_pos.x - cxi, ball_pos.y - cyi)
                if d <= cup_r + BALL_RADIUS:
                    hit_idx = i
                    break

            if hit_idx is not None:
                res = game.finish_throw(hit_idx)
                status = res.message
                phase = "IDLE"
            elif (
                ball_pos.x < -40
                or ball_pos.x > size[0] + 40
                or ball_pos.y < -40
                or ball_pos.y > size[1] + 40
                or flight_ticks > 520
            ):
                res = game.finish_throw(None)
                status = res.message
                phase = "IDLE"
            else:
                if ball_pos.x < BALL_RADIUS + 16 or ball_pos.x > size[0] - BALL_RADIUS - 16:
                    ball_vel.x *= -0.72
                    ball_pos.x = max(BALL_RADIUS + 17, min(size[0] - BALL_RADIUS - 17, ball_pos.x))

        screen.fill(bg)
        pygame.draw.rect(screen, table, (28, 200, size[0] - 56, 300), border_radius=16)

        def draw_rack(cups: List[bool], pts: List[Tuple[float, float]], up_color: Tuple[int, int, int]) -> None:
            for i, (x, y) in enumerate(pts):
                if i >= len(cups):
                    break
                col = up_color if cups[i] else cup_out
                xi, yi = int(x), int(y)
                pygame.draw.circle(screen, col, (xi, yi), cup_r)
                pygame.draw.circle(screen, (25, 25, 35), (xi, yi), cup_r, 2)

        draw_rack(game.player_two_cups, positions_p2(), cup_p2)
        draw_rack(game.player_one_cups, positions_p1(), cup_p1)

        lp1 = (int(launcher_p1.x), int(launcher_p1.y))
        lp2 = (int(launcher_p2.x), int(launcher_p2.y))
        pygame.draw.circle(screen, ring, lp1, 10, width=2)
        pygame.draw.circle(screen, ring, lp2, 10, width=2)

        if game.winner is None:
            cur = launcher()
            pygame.draw.circle(screen, highlight, (int(cur.x), int(cur.y)), 14, width=3)
            if game.current_player == 1:
                turn_txt = (
                    f"PLAYER 1 — shoot the LEFT rack  |  Throws left: {game.attempts_left}"
                )
            else:
                turn_txt = (
                    f"PLAYER 2 — shoot the RIGHT rack  |  Throws left: {game.attempts_left}"
                )
            tw = font_lg.render(turn_txt, True, ring)
            screen.blit(tw, (size[0] // 2 - tw.get_width() // 2, 14))

            if phase == "AIMING" and aim_start is not None:
                mx, my = pygame.mouse.get_pos()
                pygame.draw.line(screen, (200, 200, 255), (int(cur.x), int(cur.y)), (mx, my), 2)

            if phase == "BALL":
                pygame.draw.circle(screen, ball_c, (int(ball_pos.x), int(ball_pos.y)), BALL_RADIUS)
                pygame.draw.circle(
                    screen, (40, 35, 30), (int(ball_pos.x), int(ball_pos.y)), BALL_RADIUS, 2
                )
        else:
            w = font_lg.render(f"PLAYER {game.winner} WINS!  (cleared the other rack)  R = new game", True, ring)
            screen.blit(w, (size[0] // 2 - w.get_width() // 2, 14))

        screen.blit(
            font_md.render("Player 2 cups — LEFT triangle", True, text_c),
            (int(apex_p2.x) - 110, int(apex_p2.y) - 36),
        )
        screen.blit(
            font_md.render("Player 1 cups — RIGHT triangle", True, text_c),
            (int(apex_p1.x) - 120, int(apex_p1.y) - 36),
        )

        inst = (
            "Drag from your yellow-highlighted launcher. Clear the other player's cups to win. "
            f"If both throws in one turn land in cups, they get an extra cup back. {ATTEMPTS_PER_ROUND} throws per turn."
        )
        screen.blit(font_sm.render(inst, True, (180, 185, 200)), (18, size[1] - 86))
        bar = font_sm.render(status[:100], True, text_c)
        screen.blit(bar, (size[0] // 2 - bar.get_width() // 2, size[1] - 56))
        screen.blit(
            font_sm.render("Esc quit  |  R after win", True, (140, 145, 160)),
            (size[0] // 2 - 110, size[1] - 28),
        )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("terminal", "-t", "--terminal"):
        run_terminal_game()
    else:
        run_pygame_gui()
