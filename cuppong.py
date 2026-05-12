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
GRAVITY_WORLD = 0.44
BALL_RADIUS = 9
LAUNCH_GRAB_RADIUS = 92
# Slingshot: pull away from the ball anchor; stretch maps to depth / row band.
MAX_SLING_PULL = 210.0
MIN_SLING_PULL = 20.0
TABLE_DEPTH = 520.0
CUP_PLANE_WD = 480.0
# Along-table spacing between pyramid rows (apex = deepest wd; front row toward player).
PYRAMID_ROW_WD = 52.0

# Realistic sink: ball must pass through cup mouth while falling; rim grazes don't score.
CUP_OPENING_HALF_FRAC = 0.30
# Lip plane in world height (above table); ball must descend through opening in wx.
CUP_LIP_WH_FRAC = 0.82
CUP_SINK_CENTER_FRAC = 0.92
CUP_SETTLE_SPEED = 2.8


def _lip_cross_table_point(
    prev_wx: float,
    prev_wh: float,
    prev_wd: float,
    wx: float,
    wh: float,
    wd: float,
    wh_lip: float,
) -> Optional[Tuple[float, float]]:
    """At lip height crossing while falling, return (wx, wd) on the segment."""
    if wh >= prev_wh or abs(wh - prev_wh) < 1e-9:
        return None
    if prev_wh <= wh_lip or wh > wh_lip:
        return None
    t = (wh_lip - prev_wh) / (wh - prev_wh)
    if not (0.0 <= t <= 1.0):
        return None
    return prev_wx + t * (wx - prev_wx), prev_wd + t * (wd - prev_wd)


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
    opp_pts: List[Tuple[float, float]],
    opp: List[bool],
    cup_r: float,
    sink_qualified: List[bool],
    sink_max_d: float,
    interact_h: float,
) -> Tuple[float, float, float, float, float, float]:
    """Returns updated (wd, wx, wh, vd, vwx, vh). Planar squeeze in (wd, wx) near table height."""
    margin = cup_r + BALL_RADIUS + 1.35

    def rim_touch_count() -> int:
        t = 0
        if ball_wh > interact_h:
            return 0
        for i, (wxi, wdi) in enumerate(opp_pts):
            if i >= len(opp) or not opp[i]:
                continue
            d = math.hypot(ball_wd - wdi, ball_wx - wxi)
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
        for i, (wxi, wdi) in enumerate(opp_pts):
            if i >= len(opp) or not opp[i]:
                continue
            d = math.hypot(ball_wd - wdi, ball_wx - wxi)
            if d >= margin - 0.02:
                continue
            qualified = i < len(sink_qualified) and sink_qualified[i]
            if qualified and d <= sink_max_d:
                continue
            if d < 1e-4:
                d = 1e-4
            nx = (ball_wd - wdi) / d
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


def rack_world_placements(
    n: int, center_wx: float, col_dx: float, apex_wd: float
) -> List[Tuple[float, float]]:
    """(wx, wd) per cup: 4-row pyramid with apex farthest up-table (largest wd), front row nearest you."""
    if n <= 0:
        return []
    base_rows = [1, 2, 3, 4]
    out: List[Tuple[float, float]] = []
    idx = 0
    for r, count in enumerate(base_rows):
        wd_row = apex_wd - r * PYRAMID_ROW_WD
        row_w = (count - 1) * col_dx
        for j in range(count):
            if idx >= n:
                return out
            wx = center_wx - row_w / 2 + j * col_dx
            out.append((wx, wd_row))
            idx += 1
    left_edge_x = center_wx - 1.5 * col_dx
    right_edge_x = center_wx + 1.5 * col_dx
    base_wd = apex_wd - 3 * PYRAMID_ROW_WD
    extra_idx = 0
    while idx < n:
        step = extra_idx // 2 + 1
        if extra_idx % 2 == 0:
            wx = left_edge_x - step * col_dx
        else:
            wx = right_edge_x + step * col_dx
        out.append((wx, base_wd))
        idx += 1
        extra_idx += 1
    return out


def world_to_screen(wd: float, wx: float, wh: float, sw: int, sh: int) -> Tuple[float, float]:
    """Map table-world coords; wh=0 sits on the felt (matches trapezoid near/far edges)."""
    t_depth = max(0.0, min(1.2, wd / TABLE_DEPTH))
    near_l, near_r = 70.0, float(sw) - 70.0
    far_l, far_r = 260.0, float(sw) - 260.0
    near_cx = 0.5 * (near_l + near_r)
    far_cx = 0.5 * (far_l + far_r)
    table_cx = near_cx + t_depth * (far_cx - near_cx)

    near_y = float(sh) - 52.0
    far_y = 192.0
    u_surface = max(0.0, min(1.0, wd / max(40.0, CUP_PLANE_WD)))
    table_y = near_y + u_surface * (far_y - near_y)

    lateral_scale = 1.05 - 0.42 * min(t_depth, 1.0)
    sx = table_cx + wx * lateral_scale
    sy = table_y - wh * 1.22
    return sx, sy


def lane_trapezoid_bounds(sw: int, sh: int, lane: int) -> Tuple[float, float, float, float, float, float]:
    """Left lane = 1, right lane = 2. Returns near_l, near_r, far_l, far_r, near_y, far_y."""
    gap = 22.0
    mid = float(sw) * 0.5
    margin = 24.0
    near_y = float(sh) - 52.0
    far_y = 192.0
    if lane == 1:
        near_l = margin
        near_r = mid - gap * 0.5
    else:
        near_l = mid + gap * 0.5
        near_r = float(sw) - margin
    width = near_r - near_l
    ins = width * 0.22
    far_l = near_l + ins
    far_r = near_r - ins
    return near_l, near_r, far_l, far_r, near_y, far_y


def world_to_screen_lane(wd: float, wx: float, wh: float, lane: int, sw: int, sh: int) -> Tuple[float, float]:
    """Same world model as world_to_screen, but mapped onto a narrow side-by-side lane (GamePigeon-style)."""
    near_l, near_r, far_l, far_r, near_y, far_y = lane_trapezoid_bounds(sw, sh, lane)
    t_depth = max(0.0, min(1.2, wd / TABLE_DEPTH))
    near_cx = 0.5 * (near_l + near_r)
    far_cx = 0.5 * (far_l + far_r)
    table_cx = near_cx + t_depth * (far_cx - near_cx)
    u_surface = max(0.0, min(1.0, wd / max(40.0, CUP_PLANE_WD)))
    table_y = near_y + u_surface * (far_y - near_y)
    lateral_scale = 1.02 - 0.40 * min(t_depth, 1.0)
    sx = table_cx + wx * lateral_scale
    sy = table_y - wh * 1.22
    return sx, sy


def slingshot_speed_for_stretch_norm(t: float) -> float:
    """Normalized pull length 0..1 -> launch speed (world). Tiers: short / rows 4..1 / long."""
    t = max(0.0, min(1.0, t))
    if t < 0.065:
        return 4.8 + t * 28.0
    if t < 0.26:
        return 6.6 + (t - 0.065) * 26.0
    if t < 0.44:
        return 11.67 + (t - 0.26) * 27.0
    if t < 0.60:
        return 16.53 + (t - 0.44) * 26.5
    if t < 0.78:
        return 20.77 + (t - 0.60) * 24.0
    return 25.09 + (t - 0.78) * 45.0


def draw_cup_side_profile(
    surf: pygame.Surface,
    base_x: float,
    base_y: float,
    scale: float,
    fill: Tuple[int, int, int],
    edge: Tuple[int, int, int],
    is_up: bool,
) -> None:
    """Side-on plastic cup: rim wider than base, opening ellipse, slight 3/4 shading."""
    bx, by = int(round(base_x)), int(round(base_y))
    wb = max(10, int(11 * scale))
    wt = max(16, int(20 * scale))
    h = max(28, int(40 * scale))
    rim_h = max(4, int(6 * scale))

    rim_y = by - h

    if not is_up:
        rw, rh = int(wt * 0.85), max(6, int(8 * scale))
        pygame.draw.ellipse(surf, fill, (bx - rw // 2, by - rh - 2, rw, rh))
        pygame.draw.ellipse(surf, edge, (bx - rw // 2, by - rh - 2, rw, rh), 1)
        return

    shad = (28, 32, 38)
    pygame.draw.ellipse(surf, shad, (bx - wb // 2 - 2, by - 3, wb + 4, 8))

    body = [
        (bx - wb // 2, by),
        (bx + wb // 2, by),
        (bx + wt // 2, rim_y),
        (bx - wt // 2, rim_y),
    ]
    pygame.draw.polygon(surf, fill, body)
    pygame.draw.polygon(surf, edge, body, 2)

    rim_light = tuple(min(255, int(c + 40)) for c in fill)
    pygame.draw.ellipse(
        surf,
        rim_light,
        (bx - wt // 2 - 1, rim_y - rim_h + 1, wt + 2, rim_h + 3),
    )
    pygame.draw.ellipse(
        surf,
        edge,
        (bx - wt // 2 - 1, rim_y - rim_h + 1, wt + 2, rim_h + 3),
        1,
    )
    inner = (max(0, fill[0] - 55), max(0, fill[1] - 50), max(0, fill[2] - 45))
    pygame.draw.arc(
        surf,
        inner,
        (bx - wt // 2 + 2, rim_y - rim_h + 2, wt - 4, rim_h + 4),
        0.15 * math.pi,
        0.85 * math.pi,
        2,
    )
    sh_col = (max(0, fill[0] - 35), max(0, fill[1] - 35), max(0, fill[2] - 30))
    pygame.draw.line(surf, sh_col, (bx - wt // 2 + 3, rim_y - 2), (bx - wt // 2 + 3, by - 4), 2)
    pygame.draw.line(surf, edge, (bx - wb // 2, by), (bx + wb // 2, by), 2)


@dataclass
class ShotResult:
    success: bool
    message: str
    hit: bool = False
    target_cup: Optional[int] = None


class CupPongGame:
    """Two racks; players alternate shooting at the opponent's cups on the far end."""

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

    def finish_throw(
        self,
        cup_index_if_hit: Optional[int],
        *,
        miss_detail: Optional[str] = None,
    ) -> ShotResult:
        """Resolve one throw: cup_index indexes a standing cup on the opponent rack."""
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
                msg = "Sunk! The ball dropped in — that cup is grayed out."
                self._update_winner()
            else:
                msg = "Miss — that cup is already down."
        else:
            if miss_detail:
                msg = f"Miss — {miss_detail}."
            else:
                msg = "Miss."

        self.attempts_left -= 1
        extra = ""

        if self.winner is None and self.attempts_left <= 0:
            if self.hits_this_turn >= ATTEMPTS_PER_ROUND:
                shooter = self.current_player
                receiver = self._add_penalty_cup_to_shooter_stack()
                if receiver is not None:
                    extra += (
                        f" Player {shooter} went 2/2 — penalty cup on Player {receiver}'s rack."
                    )
                else:
                    extra += (
                        f" Player {shooter} went 2/2 — no penalty cup (max {MAX_CUPS_PER_PLAYER})."
                    )
            self.hits_this_turn = 0
            self.attempts_left = ATTEMPTS_PER_ROUND
            self._switch_player()
            extra += f" Player {self.current_player}'s turn ({ATTEMPTS_PER_ROUND} throws)."

        return ShotResult(True, msg + extra, hit=hit, target_cup=cup_index_if_hit if hit else None)

    def _add_penalty_cup_to_shooter_stack(self) -> Optional[int]:
        """Two makes in one turn: add one cup to the shooter's own rack if under cap."""
        shooter = self.current_player
        rack = self._cups_for_player(shooter)
        if len(rack) >= MAX_CUPS_PER_PLAYER:
            return None
        rack.append(True)
        return shooter

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
        def line(cups: List[bool]) -> str:
            return " ".join("O" if c else "X" for c in cups)

        return (
            "Cup Pong — two racks (O = standing, X = removed)\n"
            f"Player 1 rack: {line(self.player_one_cups)}\n"
            f"Player 2 rack: {line(self.player_two_cups)}\n"
            f"Current: Player {self.current_player} | Throws left: {self.attempts_left}"
        )


def run_terminal_game() -> None:
    game = CupPongGame()
    n = len(game._opponent_cups())
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
    size = (1080, 720)
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Cup Pong — two lanes (GamePigeon-style)")
    clock = pygame.time.Clock()

    bg = (32, 38, 48)
    felt = (38, 88, 58)
    wood = (92, 62, 38)
    cup_p1_col = (200, 220, 255)
    cup_p2_col = (255, 200, 200)
    cup_out = (86, 88, 96)
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
    RACK_CENTER_WX = 0.0
    LANE_COL_DX = 44.0
    LAUNCH_WD = 36.0
    LAUNCH_WH = 6.0
    RIM_INTERACT_H = 52.0
    # Frames at 60 FPS before next shot after a sink (shorter = faster handoff to next player / next throw).
    SUNK_ANIM_FRAMES = 9

    def cup_placements_p1() -> List[Tuple[float, float]]:
        return rack_world_placements(
            len(game.player_one_cups), RACK_CENTER_WX, LANE_COL_DX, CUP_PLANE_WD
        )

    def cup_placements_p2() -> List[Tuple[float, float]]:
        return rack_world_placements(
            len(game.player_two_cups), RACK_CENTER_WX, LANE_COL_DX, CUP_PLANE_WD
        )

    def launch_world(player: int) -> Tuple[float, float, float]:
        return LAUNCH_WD, RACK_CENTER_WX, LAUNCH_WH

    def shooter_lane(player: int) -> int:
        return 1 if player == 1 else 2

    def launcher_screen_for_player(player: int) -> Tuple[float, float]:
        wd0, wx0, wh0 = launch_world(player)
        return world_to_screen_lane(wd0, wx0, wh0, shooter_lane(player), size[0], size[1])

    def active_launcher_screen() -> Tuple[float, float]:
        return launcher_screen_for_player(game.current_player)

    def dist_to_active_launcher(pos: Tuple[int, int]) -> float:
        lx, ly = active_launcher_screen()
        return math.hypot(pos[0] - lx, pos[1] - ly)

    def draw_table() -> None:
        sw, sh = size[0], size[1]
        pygame.draw.rect(screen, (148, 118, 82), (0, int(sh) - 155, sw, 155))
        pygame.draw.rect(screen, (175, 148, 112), (0, int(sh) - 168, sw, 18))
        line_w = (235, 240, 248)
        for lane in (1, 2):
            nl, nr, fl, fr, ny, fy = lane_trapezoid_bounds(sw, sh, lane)
            pts = [
                (int(nl), int(ny)),
                (int(nr), int(ny)),
                (int(fr), int(fy)),
                (int(fl), int(fy)),
            ]
            pygame.draw.polygon(screen, felt, pts)
            pygame.draw.polygon(screen, wood, pts, width=3)
            pygame.draw.line(screen, (55, 40, 28), (int(nl), int(ny)), (int(nr), int(ny)), 5)
            ncx = 0.5 * (nl + nr)
            fcx = 0.5 * (fl + fr)
            pygame.draw.line(screen, line_w, (int(ncx), int(ny)), (int(fcx), int(fy)), 2)

    def draw_cups_side() -> None:
        vis_scale = cup_r / 11.0
        front_wd = CUP_PLANE_WD - 3.0 * PYRAMID_ROW_WD
        to_draw: List[Tuple[float, float, float, Tuple[int, int, int], bool, float]] = []
        for placements, cups, fill, lane in (
            (cup_placements_p2(), game.player_two_cups, cup_p2_col, 1),
            (cup_placements_p1(), game.player_one_cups, cup_p1_col, 2),
        ):
            for i, (wxi, wdi) in enumerate(placements):
                if i >= len(cups):
                    break
                sx, sy = world_to_screen_lane(wdi, wxi, 0.0, lane, size[0], size[1])
                fill_use = fill if cups[i] else cup_out
                depth_vis = (wdi - front_wd) / max(1.0, 3.0 * PYRAMID_ROW_WD)
                depth_vis = max(0.0, min(1.0, depth_vis))
                scale_i = vis_scale * (0.86 + 0.14 * depth_vis)
                to_draw.append((wdi, sx, sy, fill_use, cups[i], scale_i))
        to_draw.sort(key=lambda row: (-row[0], row[1]))
        for _, sx, sy, fill, standing, sc in to_draw:
            draw_cup_side_profile(screen, sx, sy, sc, fill, rim_c, standing)

    phase = "IDLE"
    sunk_anim_ticks = 0
    sunk_ball: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    sunk_lane = 1
    _lw0, _lwx0, _lwh0 = launch_world(1)
    ball_wd = _lw0
    ball_wx = _lwx0
    ball_wh = _lwh0
    ball_vd = 0.0
    ball_vwx = 0.0
    ball_vh = 0.0
    flight_ticks = 0
    status = "Player 1 — slingshot: pull back from your ball, release to fire (left lane → pink)."
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
                    sunk_anim_ticks = 0
                    sunk_lane = 1
                    status = "New game — P1: slingshot on the left lane (pink cups)."
                    lw, lwx, lwh = launch_world(1)
                    ball_wd, ball_wx, ball_wh = lw, lwx, lwh
            elif game.winner is None and phase == "IDLE":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if dist_to_active_launcher(event.pos) <= LAUNCH_GRAB_RADIUS:
                        phase = "SLING"
            elif game.winner is None and phase == "SLING":
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    asx, asy = active_launcher_screen()
                    mx, my = float(event.pos[0]), float(event.pos[1])
                    dx, dy = mx - asx, my - asy
                    stretch = math.hypot(dx, dy)
                    if stretch < MIN_SLING_PULL:
                        phase = "IDLE"
                        status = "Pull back farther from the ball to shoot."
                    else:
                        cap = min(stretch, MAX_SLING_PULL)
                        pfx = -dx / stretch
                        pfy = -dy / stretch
                        flen = math.hypot(pfx, pfy) or 1.0
                        pfx /= flen
                        pfy /= flen
                        t = cap / MAX_SLING_PULL
                        sp = slingshot_speed_for_stretch_norm(t)
                        Dwd = max(0.1, -pfy)
                        Dwx = pfx * 0.98
                        Dwh = -abs(pfy) * 0.68 - 0.26
                        m3 = math.hypot(Dwd, Dwx, Dwh)
                        if m3 < 1e-6:
                            Dwd, Dwx, Dwh = 1.0, 0.0, -0.45
                            m3 = math.hypot(Dwd, Dwx, Dwh)
                        Dwd /= m3
                        Dwx /= m3
                        Dwh /= m3
                        cp = game.current_player
                        lw, lwx, lwh = launch_world(cp)
                        ball_wd, ball_wx, ball_wh = lw, lwx, lwh
                        ball_vd = Dwd * sp
                        ball_vwx = Dwx * sp
                        ball_vh = Dwh * sp
                        phase = "BALL"
                        flight_ticks = 0
                        sink_qualified = []
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    phase = "IDLE"
                    status = "Slingshot cancelled."

        if phase == "SUNK":
            sunk_anim_ticks -= 1
            if sunk_anim_ticks <= 0:
                phase = "IDLE"

        if phase == "BALL" and game.winner is None:
            rack_front_wd = CUP_PLANE_WD - 3.0 * PYRAMID_ROW_WD
            prev_wd = ball_wd
            prev_wx = ball_wx
            prev_wh = ball_wh

            ball_vh -= GRAVITY_WORLD
            ball_wd += ball_vd
            ball_wx += ball_vwx
            ball_wh += ball_vh
            flight_ticks += 1

            if ball_wh < 0.0:
                ball_wh = 0.0
                if ball_vh < 0.0:
                    ball_vh *= -0.38
                if abs(ball_vh) < 0.55:
                    ball_vh = 0.0
                ball_vd *= 0.86
                ball_vwx *= 0.85

            if game.current_player == 1:
                opp = game.player_two_cups
                opp_pts = cup_placements_p2()
            else:
                opp = game.player_one_cups
                opp_pts = cup_placements_p1()
            n_opp = len(opp_pts)
            if len(sink_qualified) < n_opp:
                sink_qualified.extend([False] * (n_opp - len(sink_qualified)))
            elif len(sink_qualified) > n_opp:
                del sink_qualified[n_opp:]

            opening_r = cup_r * CUP_OPENING_HALF_FRAC * 1.0
            sink_max_d = cup_r - BALL_RADIUS * CUP_SINK_CENTER_FRAC
            wh_lip = cup_r * CUP_LIP_WH_FRAC
            speed = math.hypot(ball_vd, ball_vwx, ball_vh)

            lip_pt = _lip_cross_table_point(
                prev_wx, prev_wh, prev_wd, ball_wx, ball_wh, ball_wd, wh_lip
            )
            for i, (wxi, wdi) in enumerate(opp_pts):
                if i >= len(opp) or not opp[i]:
                    continue
                if lip_pt is not None:
                    cx, cd = lip_pt
                    if math.hypot(cx - wxi, cd - wdi) <= opening_r:
                        sink_qualified[i] = True

            hit_idx: Optional[int] = None
            best_d = float("inf")
            for i, (wxi, wdi) in enumerate(opp_pts):
                if i >= len(opp) or not opp[i]:
                    continue
                planar = math.hypot(ball_wd - wdi, ball_wx - wxi)
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

            shot_done = False
            if hit_idx is not None:
                wxi, wdi = opp_pts[hit_idx]
                res = game.finish_throw(hit_idx)
                status = res.message
                sunk_ball = (wdi, wxi, cup_r * 0.42)
                sunk_lane = 1 if game.current_player == 1 else 2
                sunk_anim_ticks = SUNK_ANIM_FRAMES
                phase = "SUNK"
                shot_done = True
            elif ball_wh <= 0.08 and abs(ball_vh) < 0.52:
                spd_xy = math.hypot(ball_vd, ball_vwx)
                if spd_xy < 3.05:
                    detail: Optional[str] = None
                    if ball_wd < rack_front_wd - 48.0:
                        detail = "short — stopped on the felt before the rack"
                    elif ball_wd > CUP_PLANE_WD + 36.0:
                        detail = "long — rolled past the cups on the felt"
                    elif rack_front_wd - 30.0 < ball_wd < CUP_PLANE_WD + 26.0:
                        min_drack = min(
                            (
                                math.hypot(ball_wd - wdi, ball_wx - wxi)
                                for i, (wxi, wdi) in enumerate(opp_pts)
                                if i < len(opp) and opp[i]
                            ),
                            default=999.0,
                        )
                        if min_drack > 98.0:
                            detail = "wide — on the felt but outside the cups"
                    if detail is not None:
                        res = game.finish_throw(None, miss_detail=detail)
                        status = res.message
                        phase = "IDLE"
                        shot_done = True

            if not shot_done:
                miss_air: Optional[str] = None
                if ball_wd > CUP_PLANE_WD + 95.0:
                    miss_air = "long — past the cups"
                elif ball_wd > TABLE_DEPTH + 130.0:
                    miss_air = "long — off the end of the table"
                elif ball_wd < -42.0:
                    miss_air = "behind you — not toward the rack"
                elif abs(ball_wx) > 148.0:
                    miss_air = "wide — far off to the side"
                elif ball_wh > 410.0:
                    miss_air = "too high"
                elif ball_wh < -95.0:
                    miss_air = "dropped out of play"
                elif flight_ticks > 640:
                    miss_air = "timed out"

                if miss_air is not None:
                    res = game.finish_throw(None, miss_detail=miss_air)
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
                        opp_pts,
                        opp,
                        cup_r,
                        sink_qualified,
                        sink_max_d,
                        RIM_INTERACT_H,
                    )
                    ball_wd, ball_wx, ball_wh = nw, nwx, nwh
                    ball_vd, ball_vwx, ball_vh = nvd, nvwx, nvh

        screen.fill(bg)
        draw_table()
        draw_cups_side()

        for pl, lc in ((1, cup_p1_col), (2, cup_p2_col)):
            lx, ly = launcher_screen_for_player(pl)
            pygame.draw.circle(screen, lc, (int(lx), int(ly)), 7)
            pygame.draw.circle(screen, ring, (int(lx), int(ly)), 11, width=2)

        if game.winner is None:
            alx, aly = active_launcher_screen()
            pygame.draw.circle(screen, highlight, (int(alx), int(aly)), 15, width=3)
            aim_hint = "LEFT lane (pink) — slingshot" if game.current_player == 1 else "RIGHT lane (blue) — slingshot"
            turn_txt = f"PLAYER {game.current_player} — aim {aim_hint}  |  Throws: {game.attempts_left}"
            tw = font_lg.render(turn_txt, True, ring)
            screen.blit(tw, (size[0] // 2 - tw.get_width() // 2, 12))
        else:
            w = font_lg.render(
                f"PLAYER {game.winner} WINS!  (cleared opponent's rack)  R = new game", True, ring
            )
            screen.blit(w, (size[0] // 2 - w.get_width() // 2, 12))

        if game.winner is None and phase == "SLING":
            asx, asy = active_launcher_screen()
            mx, my = pygame.mouse.get_pos()
            dx, dy = float(mx - asx), float(my - asy)
            plen = math.hypot(dx, dy)
            if plen > 0.5:
                cap_len = min(plen, MAX_SLING_PULL)
                bx = asx + dx / plen * cap_len
                by = asy + dy / plen * cap_len
            else:
                bx, by = asx, asy
            pygame.draw.line(screen, (175, 205, 130), (int(asx), int(asy)), (int(bx), int(by)), 3)
            pygame.draw.circle(screen, ball_c, (int(bx), int(by)), max(6, BALL_RADIUS - 1))
            pygame.draw.circle(screen, (45, 40, 35), (int(bx), int(by)), max(6, BALL_RADIUS - 1), 2)

        if phase == "BALL":
            bl = shooter_lane(game.current_player)
            bx, by = world_to_screen_lane(ball_wd, ball_wx, ball_wh, bl, size[0], size[1])
            pygame.draw.circle(screen, ball_c, (int(bx), int(by)), BALL_RADIUS)
            pygame.draw.circle(screen, (45, 40, 35), (int(bx), int(by)), BALL_RADIUS, 2)
        elif phase == "SUNK":
            sd, sxw, swh = sunk_ball
            bx, by = world_to_screen_lane(sd, sxw, swh, sunk_lane, size[0], size[1])
            pygame.draw.circle(screen, ball_c, (int(bx), int(by)), BALL_RADIUS)
            pygame.draw.circle(screen, (45, 40, 35), (int(bx), int(by)), BALL_RADIUS, 2)

        screen.blit(
            font_md.render(
                "Slingshot: click your ball, pull back (more stretch = more depth), release — right-click cancels",
                True,
                text_c,
            ),
            (24, size[1] - 118),
        )
        screen.blit(
            font_md.render(
                "Power bands: tiny pull = short; then rows 4→3→2→1; max pull = past cups. Rim-only = miss.",
                True,
                text_c,
            ),
            (24, size[1] - 92),
        )

        bar = font_sm.render(status[:108], True, text_c)
        screen.blit(bar, (size[0] // 2 - bar.get_width() // 2, size[1] - 56))
        screen.blit(
            font_sm.render("Esc quit  |  R after win  |  right-click cancels slingshot", True, (130, 135, 150)),
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
