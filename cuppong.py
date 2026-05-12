# this is the code for the Cup Pong game! The idea is to have this script launch when the user presses the "Cup Pong" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame


INITIAL_CUPS_PER_SIDE = 10
MAX_CUPS_PER_PLAYER = 20
ATTEMPTS_PER_ROUND = 2
# Side-view world: wh = height above table (up), wd = depth toward cups, wx = lateral.
GRAVITY_WORLD = 0.38
BALL_RADIUS = 9
MAX_THROW_POWER = 26.0
MIN_THROW_POWER = 7.5
DRAG_POWER_PER_PX = 0.11
LAUNCH_GRAB_RADIUS = 88
MIN_DRAG_TO_FIRE = 12
TABLE_DEPTH = 520.0
CUP_PLANE_WD = 480.0

# Realistic sink: ball must pass through cup mouth while falling; rim grazes don't score.
CUP_OPENING_HALF_FRAC = 0.34
# Lip plane in world height (above table); ball must descend through opening in wx.
CUP_LIP_WH_FRAC = 0.82
CUP_SINK_CENTER_FRAC = 0.88
CUP_SETTLE_SPEED = 2.8


def _lip_cross_wx_at_height(
    prev_wx: float,
    prev_wh: float,
    wx: float,
    wh: float,
    wh_lip: float,
) -> Optional[float]:
    """If path crosses wh_lip while descending in height, return lateral wx at crossing."""
    if wh >= prev_wh or abs(wh - prev_wh) < 1e-9:
        return None
    if prev_wh <= wh_lip or wh > wh_lip:
        return None
    t = (wh_lip - prev_wh) / (wh - prev_wh)
    if not (0.0 <= t <= 1.0):
        return None
    return prev_wx + t * (wx - prev_wx)


def _resolve_cup_rim_squeeze_world(
    ball_wd: float,
    ball_wx: float,
    ball_wh: float,
    ball_vd: float,
    ball_vwx: float,
    ball_vh: float,
    opp_wx: List[float],
    opp: List[bool],
    cup_r: float,
    sink_qualified: List[bool],
    sink_max_d: float,
    cup_plane_wd: float,
    interact_h: float,
) -> Tuple[float, float, float, float, float, float]:
    """Returns updated (wd, wx, wh, vd, vwx, vh). Planar squeeze in (wd, wx) near table height."""
    margin = cup_r + BALL_RADIUS + 1.35

    def rim_touch_count() -> int:
        t = 0
        if ball_wh > interact_h:
            return 0
        for i, wxi in enumerate(opp_wx):
            if i >= len(opp) or not opp[i]:
                continue
            d = math.hypot(ball_wd - cup_plane_wd, ball_wx - wxi)
            if d >= margin - 0.02:
                continue
            qualified = i < len(sink_qualified) and sink_qualified[i]
            if qualified and d <= sink_max_d:
                continue
            t += 1
        return t

    tc = rim_touch_count()
    if ball_vh > 0.28 and tc < 2:
        return ball_wd, ball_wx, ball_wh, ball_vd, ball_vwx, ball_vh

    for _ in range(10):
        sep_wd = 0.0
        sep_wx = 0.0
        touch = 0
        if ball_wh > interact_h:
            break
        for i, wxi in enumerate(opp_wx):
            if i >= len(opp) or not opp[i]:
                continue
            d = math.hypot(ball_wd - cup_plane_wd, ball_wx - wxi)
            if d >= margin - 0.02:
                continue
            qualified = i < len(sink_qualified) and sink_qualified[i]
            if qualified and d <= sink_max_d:
                continue
            if d < 1e-4:
                d = 1e-4
            nx = (ball_wd - cup_plane_wd) / d
            nwx = (ball_wx - wxi) / d
            pen = margin - d
            sep_wd += nx * pen
            sep_wx += nwx * pen
            touch += 1
        if touch == 0:
            break
        ball_wd += sep_wd
        ball_wx += sep_wx
        spd = math.hypot(ball_vd, ball_vwx, ball_vh)
        if touch >= 2:
            ball_vd *= 0.38
            ball_vwx *= 0.38
            ball_vh *= 0.38
        elif spd < 5.5:
            ball_vd *= 0.55
            ball_vwx *= 0.55
            ball_vh *= 0.55
        else:
            ball_vd *= 0.72
            ball_vwx *= 0.72
            ball_vh *= 0.72
        ball_vh -= 0.06 * touch

    return ball_wd, ball_wx, ball_wh, ball_vd, ball_vwx, ball_vh


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
    """Cup centers for a 10-cup triangle; extra cups grow outward from side edges."""
    if n <= 0:
        return []

    # Base GamePigeon-style 10-cup rack.
    base_rows = [1, 2, 3, 4]
    out: List[Tuple[float, float]] = []
    idx = 0
    y = apex_y
    for count in base_rows:
        row_w = (count - 1) * col_dx
        for j in range(count):
            if idx >= n:
                return out
            x = apex_x - row_w / 2 + j * col_dx
            out.append((x, y))
            idx += 1
        y += row_dy

    # Any penalty cups after the first 10 grow from the triangle sides horizontally.
    base_y = apex_y + (len(base_rows) - 1) * row_dy
    left_edge_x = apex_x - 1.5 * col_dx
    right_edge_x = apex_x + 1.5 * col_dx
    extra_idx = 0
    while idx < n:
        step = extra_idx // 2 + 1
        if extra_idx % 2 == 0:
            x = left_edge_x - step * col_dx
        else:
            x = right_edge_x + step * col_dx
        out.append((x, base_y))
        idx += 1
        extra_idx += 1

    return out


def rack_world_wx(n: int, center_wx: float, col_dx: float) -> List[float]:
    """Lateral world positions (wx) for cups on the far plane; same triangle + extras as rack_positions."""
    if n <= 0:
        return []
    base_rows = [1, 2, 3, 4]
    out: List[float] = []
    idx = 0
    for count in base_rows:
        row_w = (count - 1) * col_dx
        for j in range(count):
            if idx >= n:
                return out
            out.append(center_wx - row_w / 2 + j * col_dx)
            idx += 1
    left_edge_x = center_wx - 1.5 * col_dx
    right_edge_x = center_wx + 1.5 * col_dx
    extra_idx = 0
    while idx < n:
        step = extra_idx // 2 + 1
        if extra_idx % 2 == 0:
            out.append(left_edge_x - step * col_dx)
        else:
            out.append(right_edge_x + step * col_dx)
        idx += 1
        extra_idx += 1
    return out


def world_to_screen(wd: float, wx: float, wh: float, sw: int, sh: int) -> Tuple[float, float]:
    """Map table-world coords to screen (side / perspective toward far cups)."""
    t = max(0.0, min(1.2, wd / TABLE_DEPTH))
    near_y = float(sh) - 100.0
    far_y = 130.0 + (1.0 - t) * 50.0
    table_y = near_y - t * (near_y - far_y) * 0.88
    sx = 105.0 + t * (float(sw) - 210.0) + wx * (1.05 - 0.42 * t)
    sy = table_y - wh * 1.12 - t * 38.0
    return sx, sy


@dataclass
class ShotResult:
    success: bool
    message: str
    hit: bool = False
    target_cup: Optional[int] = None


class CupPongGame:
    """Two players alternate throws at one shared rack; last cup wins for the shooter."""

    def __init__(self, initial_cups_per_side: int = INITIAL_CUPS_PER_SIDE) -> None:
        if initial_cups_per_side <= 0:
            raise ValueError("initial_cups_per_side must be greater than 0.")

        self.initial_cups_per_side = initial_cups_per_side
        self.cups: List[bool] = [True] * initial_cups_per_side
        self.current_player = 1
        self.winner: Optional[int] = None
        self.attempts_left = ATTEMPTS_PER_ROUND
        self.hits_this_turn = 0

    def reset(self) -> None:
        n = self.initial_cups_per_side
        self.cups = [True] * n
        self.current_player = 1
        self.winner = None
        self.attempts_left = ATTEMPTS_PER_ROUND
        self.hits_this_turn = 0

    def finish_throw(self, cup_index_if_hit: Optional[int]) -> ShotResult:
        """Resolve one throw: cup_index_if_hit indexes a standing cup on the shared rack."""
        if self.winner is not None:
            return ShotResult(False, "Game is over. Press R to reset.")

        hit = False
        msg = ""
        rack = self.cups

        if cup_index_if_hit is not None and 0 <= cup_index_if_hit < len(rack):
            if rack[cup_index_if_hit]:
                rack[cup_index_if_hit] = False
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
                shooter = self.current_player
                receiver = self._add_penalty_cup_on_perfect_turn()
                if receiver is not None:
                    extra += (
                        f" Player {shooter} went 2/2 — penalty cup added to the rack."
                    )
                else:
                    extra += (
                        f" Player {shooter} went 2/2 — no penalty cup (max {MAX_CUPS_PER_PLAYER} reached)."
                    )
            self.hits_this_turn = 0
            self.attempts_left = ATTEMPTS_PER_ROUND
            self._switch_player()
            extra += f" Player {self.current_player}'s turn ({ATTEMPTS_PER_ROUND} throws)."

        return ShotResult(True, msg + extra, hit=hit, target_cup=cup_index_if_hit if hit else None)

    def _add_penalty_cup_on_perfect_turn(self) -> Optional[int]:
        """Two makes in one turn: add one cup back to the shared rack if under cap."""
        if len(self.cups) >= MAX_CUPS_PER_PLAYER:
            return None
        self.cups.append(True)
        return self.current_player

    def remaining_cups(self) -> int:
        return sum(1 for is_up in self.cups if is_up)

    def _switch_player(self) -> None:
        self.current_player = 2 if self.current_player == 1 else 1

    def _update_winner(self) -> None:
        if self.remaining_cups() == 0:
            self.winner = self.current_player

    def board_as_string(self) -> str:
        line = " ".join("O" if cup else "X" for cup in self.cups)
        return (
            "Cup Pong — shared rack (O = standing, X = removed)\n"
            f"Cups: {line}\n"
            f"Current: Player {self.current_player} | Throws left: {self.attempts_left}"
        )


def run_terminal_game() -> None:
    game = CupPongGame()
    n = len(game.cups)
    print("Cup Pong (terminal) — m = miss, k = hit cup k (1-indexed), q = quit")
    print(f"{INITIAL_CUPS_PER_SIDE} cups per triangle; {ATTEMPTS_PER_ROUND} tries per turn.\n")

    while True:
        print(game.board_as_string())
        if game.winner is not None:
            print(f"\nPlayer {game.winner} wins!")
            break

        mx = len(game.cups)
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
    size = (1080, 720)
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Cup Pong — side view, shared rack")
    clock = pygame.time.Clock()

    bg = (32, 38, 48)
    felt = (38, 88, 58)
    wood = (92, 62, 38)
    cup_up = (220, 210, 255)
    cup_out = (70, 72, 82)
    rim_c = (35, 32, 40)
    ring = (255, 215, 70)
    ball_c = (252, 248, 220)
    text_c = (238, 240, 245)
    highlight = (255, 255, 110)

    font_lg = pygame.font.SysFont("optima", 30, bold=True)
    font_md = pygame.font.SysFont("optima", 20)
    font_sm = pygame.font.SysFont("optima", 16)

    game = CupPongGame()
    cup_r = 24.0
    col_dx = 46.0
    cup_center_wx = 0.0
    LAUNCH_WD = 36.0
    LAUNCH_WH = 6.0
    RIM_INTERACT_H = 52.0

    def cup_lateral_positions() -> List[float]:
        return rack_world_wx(len(game.cups), cup_center_wx, col_dx)

    def launcher_screen() -> Tuple[float, float]:
        return world_to_screen(LAUNCH_WD, 0.0, LAUNCH_WH, size[0], size[1])

    def dist_to_launcher_screen(pos: Tuple[int, int]) -> float:
        lx, ly = launcher_screen()
        return math.hypot(pos[0] - lx, pos[1] - ly)

    def draw_table() -> None:
        sw, sh = size[0], size[1]
        near_l, near_r = 70.0, float(sw) - 70.0
        far_l, far_r = 260.0, float(sw) - 260.0
        ny = float(sh) - 55.0
        fy = 210.0
        pts = [
            (int(near_l), int(ny)),
            (int(near_r), int(ny)),
            (int(far_r), int(fy)),
            (int(far_l), int(fy)),
        ]
        pygame.draw.polygon(screen, felt, pts)
        pygame.draw.polygon(screen, wood, pts, width=4)
        pygame.draw.line(screen, (55, 40, 28), (int(near_l), int(ny)), (int(near_r), int(ny)), 6)

    def draw_cups_side() -> None:
        opp = game.cups
        wxs = cup_lateral_positions()
        for i, wxi in enumerate(wxs):
            if i >= len(opp):
                break
            sx, sy = world_to_screen(CUP_PLANE_WD, wxi, 0.0, size[0], size[1])
            col = cup_up if opp[i] else cup_out
            rx = int(cup_r * 0.95)
            ry = int(cup_r * 1.5)
            pygame.draw.ellipse(screen, col, (int(sx - rx), int(sy - ry), 2 * rx, 2 * ry))
            pygame.draw.ellipse(screen, rim_c, (int(sx - rx), int(sy - ry), 2 * rx, 2 * ry), 2)

    phase = "IDLE"
    aim_start: Optional[Tuple[int, int]] = None
    ball_wd = LAUNCH_WD
    ball_wx = 0.0
    ball_wh = LAUNCH_WH
    ball_vd = 0.0
    ball_vwx = 0.0
    ball_vh = 0.0
    flight_ticks = 0
    status = "Player 1 — drag from the yellow dot toward the cups (longer drag = harder)."
    sink_qualified: List[bool] = []
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
                    status = "New game — Player 1's turn."
            elif game.winner is None and phase == "IDLE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if dist_to_launcher_screen(event.pos) <= LAUNCH_GRAB_RADIUS:
                        aim_start = event.pos
                        phase = "AIMING"
            elif game.winner is None and phase == "AIMING":
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and aim_start is not None:
                    mx, my = event.pos
                    lsx, lsy = launcher_screen()
                    du, dv = mx - lsx, my - lsy
                    drag_len = math.hypot(du, dv)
                    if drag_len < MIN_DRAG_TO_FIRE:
                        phase = "IDLE"
                        aim_start = None
                        status = "Drag farther from your dot to throw."
                    else:
                        power = max(
                            MIN_THROW_POWER,
                            min(MAX_THROW_POWER, drag_len * DRAG_POWER_PER_PX),
                        )
                        ux, uy = du / drag_len, dv / drag_len
                        ball_vd = max(0.12, ux) * power * 1.08
                        ball_vh = -uy * power * 1.12
                        ball_vwx = ux * power * 0.14 + math.copysign(0.35, du) * abs(uy) * power * 0.08
                        ball_wd = LAUNCH_WD
                        ball_wx = 0.0
                        ball_wh = LAUNCH_WH
                        phase = "BALL"
                        flight_ticks = 0
                        sink_qualified = []
                    aim_start = None

        if phase == "BALL" and game.winner is None:
            prev_wd = ball_wd
            prev_wx = ball_wx
            prev_wh = ball_wh

            ball_vh -= GRAVITY_WORLD
            ball_wd += ball_vd
            ball_wx += ball_vwx
            ball_wh += ball_vh
            flight_ticks += 1

            opp = game.cups
            opp_wx = cup_lateral_positions()
            n_opp = len(opp_wx)
            if len(sink_qualified) < n_opp:
                sink_qualified.extend([False] * (n_opp - len(sink_qualified)))
            elif len(sink_qualified) > n_opp:
                del sink_qualified[n_opp:]

            opening_half = cup_r * CUP_OPENING_HALF_FRAC
            sink_max_d = cup_r - BALL_RADIUS * CUP_SINK_CENTER_FRAC
            wh_lip = cup_r * CUP_LIP_WH_FRAC
            speed = math.hypot(ball_vd, ball_vwx, ball_vh)

            for i, wxi in enumerate(opp_wx):
                if i >= len(opp) or not opp[i]:
                    continue
                cross_wx = _lip_cross_wx_at_height(prev_wx, prev_wh, ball_wx, ball_wh, wh_lip)
                if cross_wx is not None and abs(cross_wx - wxi) <= opening_half:
                    sink_qualified[i] = True

            hit_idx: Optional[int] = None
            best_d = float("inf")
            for i, wxi in enumerate(opp_wx):
                if i >= len(opp) or not opp[i]:
                    continue
                planar = math.hypot(ball_wd - CUP_PLANE_WD, ball_wx - wxi)
                if planar > sink_max_d:
                    continue
                if not sink_qualified[i]:
                    continue
                descending = ball_vh <= -0.32
                settled = speed < CUP_SETTLE_SPEED and planar <= cup_r * 0.5
                if descending or settled:
                    if planar < best_d:
                        best_d = planar
                        hit_idx = i

            if hit_idx is not None:
                res = game.finish_throw(hit_idx)
                status = res.message
                phase = "IDLE"
            elif (
                ball_wd > TABLE_DEPTH + 140
                or ball_wd < -35
                or ball_wh < -120
                or ball_wh > 420
                or abs(ball_wx) > 220
                or flight_ticks > 640
            ):
                res = game.finish_throw(None)
                status = res.message
                phase = "IDLE"
            else:
                nw, nwx, nwh, nvd, nvwx, nvh = _resolve_cup_rim_squeeze_world(
                    ball_wd,
                    ball_wx,
                    ball_wh,
                    ball_vd,
                    ball_vwx,
                    ball_vh,
                    opp_wx,
                    opp,
                    cup_r,
                    sink_qualified,
                    sink_max_d,
                    CUP_PLANE_WD,
                    RIM_INTERACT_H,
                )
                ball_wd, ball_wx, ball_wh = nw, nwx, nwh
                ball_vd, ball_vwx, ball_vh = nvd, nvwx, nvh

        screen.fill(bg)
        draw_table()
        draw_cups_side()

        lsx, lsy = launcher_screen()
        pygame.draw.circle(screen, ring, (int(lsx), int(lsy)), 11, width=2)

        if game.winner is None:
            pygame.draw.circle(screen, highlight, (int(lsx), int(lsy)), 15, width=3)
            turn_txt = f"PLAYER {game.current_player} — shared rack  |  Throws: {game.attempts_left}"
            tw = font_lg.render(turn_txt, True, ring)
            screen.blit(tw, (size[0] // 2 - tw.get_width() // 2, 12))

            if phase == "BALL":
                bx, by = world_to_screen(ball_wd, ball_wx, ball_wh, size[0], size[1])
                pygame.draw.circle(screen, ball_c, (int(bx), int(by)), BALL_RADIUS)
                pygame.draw.circle(screen, (45, 40, 35), (int(bx), int(by)), BALL_RADIUS, 2)
        else:
            w = font_lg.render(
                f"PLAYER {game.winner} WINS!  (cleared the rack)  R = new game", True, ring
            )
            screen.blit(w, (size[0] // 2 - w.get_width() // 2, 12))

        screen.blit(
            font_md.render("You — at the near end of the table", True, text_c),
            (24, size[1] - 118),
        )
        screen.blit(
            font_md.render("Cups — far end (same rack for both players)", True, text_c),
            (24, size[1] - 92),
        )

        bar = font_sm.render(status[:108], True, text_c)
        screen.blit(bar, (size[0] // 2 - bar.get_width() // 2, size[1] - 56))
        screen.blit(
            font_sm.render("Esc quit  |  R after win", True, (130, 135, 150)),
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
