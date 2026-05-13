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
PYRAMID_ROW_WD = 56.0
# Drawing only: table-surface Y uses this depth for every cup so bases line up (level rack).
CUP_RACK_SCREEN_BASELINE_WD = CUP_PLANE_WD - 1.5 * PYRAMID_ROW_WD

# Flat far rack: descending crossing of rim-height plane (world wh).
# Lateral distance from a standing cup's center <= cup_r * this counts as a sink (cup top / rim band).
CUP_RIM_PLANE_WH_FRAC = 0.62
CUP_TOP_SINK_FRAC = 0.58


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
    """(wx, wd) per cup: 4-row pyramid with the single cup nearest the launcher (small wd), base row farthest (apex_wd)."""
    if n <= 0:
        return []
    base_rows = [1, 2, 3, 4]
    out: List[Tuple[float, float]] = []
    idx = 0
    max_r = len(base_rows) - 1
    for r, count in enumerate(base_rows):
        wd_row = apex_wd - (max_r - r) * PYRAMID_ROW_WD
        row_w = (count - 1) * col_dx
        for j in range(count):
            if idx >= n:
                return out
            wx = center_wx - row_w / 2 + j * col_dx
            out.append((wx, wd_row))
            idx += 1
    left_edge_x = center_wx - 1.5 * col_dx
    right_edge_x = center_wx + 1.5 * col_dx
    base_wd = apex_wd
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

    near_y = float(sh) - 48.0
    far_y = 168.0
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
    near_y = float(sh) - 48.0
    far_y = 168.0
    if lane == 1:
        near_l = margin
        near_r = mid - gap * 0.5
    else:
        near_l = mid + gap * 0.5
        near_r = float(sw) - margin
    width = near_r - near_l
    ins = width * 0.30
    far_l = near_l + ins
    far_r = near_r - ins
    return near_l, near_r, far_l, far_r, near_y, far_y


def world_to_screen_lane(
    wd: float,
    wx: float,
    wh: float,
    lane: int,
    sw: int,
    sh: int,
    *,
    rack_flat_baseline_y: bool = False,
) -> Tuple[float, float]:
    """Same world model as world_to_screen, but mapped onto a narrow side-by-side lane (GamePigeon-style).

    If ``rack_flat_baseline_y`` is True (cup rack drawing only), the felt height for ``wh`` uses a fixed
    depth so every cup sits on one horizontal screen line; horizontal perspective still uses ``wd``.
    """
    near_l, near_r, far_l, far_r, near_y, far_y = lane_trapezoid_bounds(sw, sh, lane)
    t_depth = max(0.0, min(1.2, wd / TABLE_DEPTH))
    near_cx = 0.5 * (near_l + near_r)
    far_cx = 0.5 * (far_l + far_r)
    table_cx = near_cx + t_depth * (far_cx - near_cx)
    wd_surface = CUP_RACK_SCREEN_BASELINE_WD if rack_flat_baseline_y else wd
    u_surface = max(0.0, min(1.0, wd_surface / max(40.0, CUP_PLANE_WD)))
    table_y = near_y + u_surface * (far_y - near_y)
    lateral_scale = 1.0 - 0.46 * min(t_depth, 1.0)
    sx = table_cx + wx * lateral_scale
    sy = table_y - wh * 1.22
    return sx, sy


def slingshot_speed_for_stretch_norm(t: float) -> float:
    """Normalized pull 0..1 -> launch speed (world). Low = short; high = past the far cup line."""
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


def _simulate_shot_trail(
    lw: float,
    lwx: float,
    lwh: float,
    ball_vd: float,
    ball_vwx: float,
    ball_vh: float,
    opp: List[bool],
    opp_pts: List[Tuple[float, float]],
    cup_r: float,
) -> Tuple[List[Tuple[float, float, float]], str]:
    """Advance a throw with the same rules as the BALL phase (no game mutation). Returns
    sampled world positions and an outcome tag; ``hit`` when crossing the rim plane inside
    the cup-top radius (closest cup), other tags for miss-colored preview."""
    wd, wx, wh = lw, lwx, lwh
    vd, vwx, vh = ball_vd, ball_vwx, ball_vh
    trail: List[Tuple[float, float, float]] = [(lw, lwx, lwh)]
    opening_plane_done = False
    rack_front_wd = CUP_PLANE_WD - 3.0 * PYRAMID_ROW_WD
    rim_wh = cup_r * CUP_RIM_PLANE_WH_FRAC
    sink_r = cup_r * CUP_TOP_SINK_FRAC
    flight_ticks = 0
    while True:
        prev_wd, prev_wx, prev_wh = wd, wx, wh
        vh -= GRAVITY_WORLD
        wd += vd
        wx += vwx
        wh += vh
        flight_ticks += 1

        if wh < 0.0:
            wh = 0.0
            if vh < 0.0:
                vh *= -0.38
            if abs(vh) < 0.55:
                vh = 0.0
            vd *= 0.86
            vwx *= 0.85

        if (
            not opening_plane_done
            and prev_wh > rim_wh >= wh
            and vh < -0.06
        ):
            den = wh - prev_wh
            if abs(den) > 1e-8:
                tr = (rim_wh - prev_wh) / den
                if 0.0 <= tr <= 1.0:
                    opening_plane_done = True
                    cx = prev_wx + tr * (wx - prev_wx)
                    cd = prev_wd + tr * (wd - prev_wd)
                    if cd < rack_front_wd - 32.0:
                        trail.append((wd, wx, wh))
                        return trail, "short_plane"
                    if cd > CUP_PLANE_WD + 48.0:
                        trail.append((wd, wx, wh))
                        return trail, "long_plane"
                    best_i: Optional[int] = None
                    best_d = float("inf")
                    for i, (wxi, wdi) in enumerate(opp_pts):
                        if i >= len(opp) or not opp[i]:
                            continue
                        d = math.hypot(cd - wdi, cx - wxi)
                        if d <= sink_r and d < best_d:
                            best_d = d
                            best_i = i
                    if best_i is not None:
                        trail.append((wd, wx, wh))
                        return trail, "hit"
                    min_d = min(
                        (
                            math.hypot(cd - wdi, cx - wxi)
                            for i, (wxi, wdi) in enumerate(opp_pts)
                            if i < len(opp) and opp[i]
                        ),
                        default=999.0,
                    )
                    tag = "past" if min_d > sink_r + 22.0 else "off_cluster"
                    trail.append((wd, wx, wh))
                    return trail, tag

        if wh <= 0.08 and abs(vh) < 0.52:
            spd_xy = math.hypot(vd, vwx)
            if spd_xy < 3.05:
                detail: Optional[str] = None
                if wd < rack_front_wd - 42.0:
                    detail = "ground_short"
                elif wd > CUP_PLANE_WD + 42.0:
                    detail = "ground_long"
                elif rack_front_wd - 28.0 < wd < CUP_PLANE_WD + 32.0:
                    min_drack = min(
                        (
                            math.hypot(wd - wdi, wx - wxi)
                            for i, (wxi, wdi) in enumerate(opp_pts)
                            if i < len(opp) and opp[i]
                        ),
                        default=999.0,
                    )
                    if min_drack > sink_r + 18.0:
                        detail = "ground_wide"
                if detail is not None:
                    trail.append((wd, wx, wh))
                    return trail, detail

        miss_air: Optional[str] = None
        if wd > CUP_PLANE_WD + 95.0:
            miss_air = "long_air"
        elif wd > TABLE_DEPTH + 130.0:
            miss_air = "long_end"
        elif wd < -42.0:
            miss_air = "behind"
        elif abs(wx) > 148.0:
            miss_air = "wide_air"
        elif wh > 410.0:
            miss_air = "high"
        elif wh < -95.0:
            miss_air = "drop"
        elif flight_ticks > 640:
            miss_air = "timeout"
        if miss_air is not None:
            trail.append((wd, wx, wh))
            return trail, miss_air

        trail.append((wd, wx, wh))


def draw_cup_side_profile(
    surf: pygame.Surface,
    base_x: float,
    base_y: float,
    scale: float,
    fill: Tuple[int, int, int],
    edge: Tuple[int, int, int],
    is_up: bool,
    *,
    rim_interior: Optional[Tuple[int, int, int]] = None,
    height_scale: float = 1.0,
) -> None:
    """Side-on plastic cup: rim wider than base, opening ellipse, slight 3/4 shading."""
    bx, by = int(round(base_x)), int(round(base_y))
    hs = max(0.52, min(1.0, height_scale))
    wb = max(10, int(11 * scale))
    wt = max(16, int(20 * scale))
    h = max(22, int(40 * scale * hs))
    rim_h = max(3, int(6 * scale * hs))

    rim_y = by - h

    if not is_up:
        rw, rh = int(wt * 0.85), max(5, int(8 * scale * hs))
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

    rim_light = (
        rim_interior
        if rim_interior is not None
        else tuple(min(255, int(c + 40)) for c in fill)
    )
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
    if rim_interior is not None:
        inner = (max(0, rim_interior[0] - 40), max(0, rim_interior[1] - 40), max(0, rim_interior[2] - 45))
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
    """Two racks; win by sinking every cup on the opponent's side (no cups left on that rack)."""

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


def _wrap_text_to_width(
    font: pygame.font.Font,
    text: str,
    max_width: int,
) -> List[str]:
    """Word-wrap one paragraph so each rendered line fits within ``max_width`` pixels."""
    text = text.strip()
    if not text:
        return []
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip() if current else word
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            if font.size(word)[0] <= max_width:
                current = word
            else:
                chunk = ""
                for ch in word:
                    nxt = chunk + ch
                    if font.size(nxt)[0] <= max_width:
                        chunk = nxt
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = ch
                current = chunk
    if current:
        lines.append(current)
    return lines


def _wrap_instruction_paragraphs(
    font: pygame.font.Font,
    paragraphs: List[str],
    max_width: int,
) -> List[str]:
    """Word-wrap each non-empty paragraph; insert a blank line between paragraphs."""
    out: List[str] = []
    first = True
    for raw in paragraphs:
        para = raw.strip()
        if not para:
            continue
        if not first:
            out.append("")
        first = False
        out.extend(_wrap_text_to_width(font, para, max_width))
    return out


def run_pygame_gui() -> None:
    pygame.init()
    size = (1080, 720)
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("Cup Pong")
    clock = pygame.time.Clock()

    # GamePigeon-style: wood floor, bright green felt, white trim, red cups / white rims.
    floor_a = (218, 186, 142)
    floor_b = (205, 170, 125)
    felt_gp = (0, 149, 87)
    felt_dark = (0, 118, 72)
    trim_white = (255, 255, 255)
    cup_red_a = (215, 52, 62)
    cup_red_b = (200, 46, 58)
    cup_out = (95, 98, 108)
    rim_white = (252, 252, 255)
    rim_edge = (180, 182, 190)
    ball_white = (255, 255, 255)
    ball_outline = (190, 192, 198)
    turn_shadow = (32, 30, 28)
    turn_text = (255, 252, 248)

    font_lg = pygame.font.SysFont("optima", 30, bold=True)
    font_win_title = pygame.font.SysFont("optima", 52, bold=True)
    font_win_sub = pygame.font.SysFont("optima", 22)
    font_win_btn = pygame.font.SysFont("optima", 26, bold=True)
    font_instr_title = pygame.font.SysFont("optima", 38, bold=True)
    font_instr_body = pygame.font.SysFont("optima", 21)

    game = CupPongGame()
    cup_r = 24.0
    RACK_CENTER_WX = 0.0
    LANE_COL_DX = 52.0
    LAUNCH_WD = 36.0
    LAUNCH_WH = 6.0
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

    sw, sh = size[0], size[1]
    cx, cy = sw // 2, sh // 2
    win_panel = pygame.Rect(cx - 280, cy - 175, 560, 350)
    win_btn_play = pygame.Rect(cx - 250, win_panel.bottom - 100, 240, 50)
    win_btn_home = pygame.Rect(cx + 10, win_panel.bottom - 100, 240, 50)
    instr_panel = pygame.Rect(cx - 330, 56, 660, sh - 200)
    instr_start_rect = pygame.Rect(cx - 140, sh - 118, 280, 52)

    def draw_instructions_screen() -> None:
        pygame.draw.rect(screen, (248, 246, 242), instr_panel, border_radius=18)
        pygame.draw.rect(screen, (58, 60, 72), instr_panel, width=2, border_radius=18)
        title = font_instr_title.render("Cup Pong — How to play", True, (28, 30, 40))
        screen.blit(title, (cx - title.get_width() // 2, instr_panel.y + 22))
        pad_x = 36
        max_text_w = max(160, instr_panel.width - 2 * pad_x)
        body_paragraphs = [
            "Welcome to Cup Pong! In this game, the goal is to clear your opponent's cups before they clear yours.",
            "To do this, launch the ping pong ball so it sinks into their cups. When it's your turn, click your ball, drag the mouse back to aim like a slingshot, and release. Pull back farther for a stronger shot; move side to side before release to aim left or right.",
            "Each player has two throws per round. If one player makes both throws in a round, the other player receives a penalty of one extra cup on their rack.",
            "Good luck, and have fun!",
        ]
        wrapped = _wrap_instruction_paragraphs(
            font_instr_body, body_paragraphs, max_text_w
        )
        line_gap = 26
        y = instr_panel.y + 78
        for line in wrapped:
            if line == "":
                y += 12
                continue
            surf = font_instr_body.render(line, True, (55, 58, 72))
            screen.blit(surf, (instr_panel.x + pad_x, y))
            y += line_gap
        mp = pygame.mouse.get_pos()
        hover = instr_start_rect.collidepoint(mp)
        fill = (42, 140, 78) if not hover else (52, 168, 98)
        pygame.draw.rect(screen, fill, instr_start_rect, border_radius=12)
        pygame.draw.rect(screen, (18, 72, 44), instr_start_rect, width=2, border_radius=12)
        st = font_win_btn.render("Start game", True, (255, 255, 255))
        screen.blit(
            st,
            (
                instr_start_rect.centerx - st.get_width() // 2,
                instr_start_rect.centery - st.get_height() // 2,
            ),
        )
        hint_text = "Or press Enter / Space to begin"
        hint_lines = _wrap_text_to_width(font_instr_body, hint_text, max_text_w)
        hy = instr_start_rect.bottom + 12
        for hl in hint_lines:
            hs = font_instr_body.render(hl, True, (120, 122, 132))
            screen.blit(hs, (cx - hs.get_width() // 2, hy))
            hy += line_gap - 4

    def reset_match_from_ui() -> None:
        nonlocal phase, sunk_anim_ticks, sunk_lane, opening_plane_done
        nonlocal shot_preview_trail, shot_preview_outcome
        nonlocal ball_wd, ball_wx, ball_wh, ball_vd, ball_vwx, ball_vh, flight_ticks
        game.reset()
        phase = "IDLE"
        sunk_anim_ticks = 0
        sunk_lane = 1
        opening_plane_done = False
        shot_preview_trail = []
        shot_preview_outcome = ""
        lw, lwx, lwh = launch_world(1)
        ball_wd, ball_wx, ball_wh = lw, lwx, lwh
        ball_vd = 0.0
        ball_vwx = 0.0
        ball_vh = 0.0
        flight_ticks = 0

    def draw_win_overlay() -> None:
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((15, 18, 22, 175))
        screen.blit(dim, (0, 0))
        pygame.draw.rect(screen, (252, 250, 248), win_panel, border_radius=20)
        pygame.draw.rect(screen, (55, 58, 68), win_panel, width=3, border_radius=20)
        wn = game.winner
        if wn is None:
            return
        title = f"Player {wn} wins!"
        sub = "Cleared the opponent's rack."
        hint = "Play again  ·  R or Enter     |     Home  ·  H or button below"
        ts = font_win_title.render(title, True, (28, 30, 38))
        tsh = font_win_title.render(title, True, (200, 200, 205))
        tx = cx - ts.get_width() // 2
        ty = win_panel.y + 36
        screen.blit(tsh, (tx + 2, ty + 2))
        screen.blit(ts, (tx, ty))
        su = font_win_sub.render(sub, True, (80, 82, 92))
        screen.blit(su, (cx - su.get_width() // 2, ty + 62))
        hi = font_win_sub.render(hint, True, (110, 112, 125))
        screen.blit(hi, (cx - hi.get_width() // 2, ty + 96))
        mp = pygame.mouse.get_pos()
        for rect, label in ((win_btn_play, "Play again"), (win_btn_home, "Home")):
            hover = rect.collidepoint(mp)
            fill = (52, 118, 220) if not hover else (72, 138, 240)
            pygame.draw.rect(screen, fill, rect, border_radius=12)
            pygame.draw.rect(screen, (24, 48, 100), rect, width=2, border_radius=12)
            bt = font_win_btn.render(label, True, (255, 255, 255))
            screen.blit(bt, (rect.centerx - bt.get_width() // 2, rect.centery - bt.get_height() // 2))

    def draw_floor() -> None:
        sw, sh = size[0], size[1]
        stripe = 40
        for x in range(0, sw + stripe, stripe):
            c = floor_a if (x // stripe) % 2 == 0 else floor_b
            pygame.draw.rect(screen, c, (x, 0, stripe, sh))

    def draw_table() -> None:
        sw, sh = size[0], size[1]
        for lane in (1, 2):
            nl, nr, fl, fr, ny, fy = lane_trapezoid_bounds(sw, sh, lane)
            pts = [
                (int(nl), int(ny)),
                (int(nr), int(ny)),
                (int(fr), int(fy)),
                (int(fl), int(fy)),
            ]
            pygame.draw.polygon(screen, felt_dark, pts)
            pygame.draw.polygon(screen, felt_gp, pts)
            pygame.draw.polygon(screen, trim_white, pts, width=3)
            ncx = 0.5 * (nl + nr)
            fcx = 0.5 * (fl + fr)
            pygame.draw.line(screen, trim_white, (int(ncx), int(ny)), (int(fcx), int(fy)), 2)

    def draw_cups_side() -> None:
        vis_scale = cup_r / 11.0
        front_wd = CUP_PLANE_WD - 3.0 * PYRAMID_ROW_WD
        to_draw: List[
            Tuple[float, float, float, Tuple[int, int, int], bool, float, float]
        ] = []
        for placements, cups, fill, lane in (
            (cup_placements_p2(), game.player_two_cups, cup_red_b, 1),
            (cup_placements_p1(), game.player_one_cups, cup_red_a, 2),
        ):
            for i, (wxi, wdi) in enumerate(placements):
                if i >= len(cups):
                    break
                sx, sy = world_to_screen_lane(wdi, wxi, 0.0, lane, size[0], size[1])
                fill_use = fill if cups[i] else cup_out
                depth_vis = (wdi - front_wd) / max(1.0, 3.0 * PYRAMID_ROW_WD)
                depth_vis = max(0.0, min(1.0, depth_vis))
                scale_i = vis_scale * (0.82 + 0.18 * depth_vis)
                # Shorter bodies toward the back row (perspective) without shrinking width as much.
                height_scale = 1.0 - 0.44 * depth_vis
                to_draw.append((wdi, sx, sy, fill_use, cups[i], scale_i, height_scale))
        to_draw.sort(key=lambda row: (-row[0], row[1]))
        for _, sx, sy, fill, standing, sc, hsc in to_draw:
            if standing:
                draw_cup_side_profile(
                    screen,
                    sx,
                    sy,
                    sc,
                    fill,
                    rim_edge,
                    True,
                    rim_interior=rim_white,
                    height_scale=hsc,
                )
            else:
                draw_cup_side_profile(
                    screen, sx, sy, sc, fill, rim_edge, False, height_scale=hsc
                )

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
    opening_plane_done = False
    running = True
    shot_preview_trail: List[Tuple[float, float, float]] = []
    shot_preview_lane = 1
    shot_preview_outcome = ""
    app_phase = "INSTRUCTIONS"

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if app_phase == "INSTRUCTIONS":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (
                        pygame.K_RETURN,
                        pygame.K_SPACE,
                    ):
                        app_phase = "PLAY"
                elif (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and instr_start_rect.collidepoint(event.pos)
                ):
                    app_phase = "PLAY"
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game.winner is not None:
                    if event.key in (pygame.K_h, pygame.K_HOME):
                        pygame.quit()
                        sys.exit(0)
                    elif event.key in (pygame.K_r, pygame.K_RETURN):
                        reset_match_from_ui()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if game.winner is not None:
                    if win_btn_play.collidepoint(event.pos):
                        reset_match_from_ui()
                    elif win_btn_home.collidepoint(event.pos):
                        pygame.quit()
                        sys.exit(0)
                elif game.winner is None and phase == "IDLE":
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
                        shot_preview_trail = []
                        shot_preview_outcome = ""
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
                        Dwh = -abs(pfy) * 0.84 - 0.44
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
                        # Dwh from aim vector points "into table"; negate so negative Dwh -> upward wh (parabolic toss).
                        ball_vh = -Dwh * sp
                        if game.current_player == 1:
                            opp_sim = game.player_two_cups
                            pts_sim = cup_placements_p2()
                        else:
                            opp_sim = game.player_one_cups
                            pts_sim = cup_placements_p1()
                        shot_preview_trail, shot_preview_outcome = _simulate_shot_trail(
                            lw,
                            lwx,
                            lwh,
                            ball_vd,
                            ball_vwx,
                            ball_vh,
                            opp_sim,
                            pts_sim,
                            cup_r,
                        )
                        shot_preview_lane = 1 if cp == 1 else 2
                        phase = "BALL"
                        flight_ticks = 0
                        opening_plane_done = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    phase = "IDLE"
                    shot_preview_trail = []
                    shot_preview_outcome = ""

        if app_phase == "INSTRUCTIONS":
            draw_floor()
            draw_instructions_screen()
            pygame.display.flip()
            clock.tick(60)
            continue

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

            rim_wh = cup_r * CUP_RIM_PLANE_WH_FRAC
            sink_r = cup_r * CUP_TOP_SINK_FRAC

            shot_done = False

            # Descending through rim-height plane: within cup-top radius of a standing cup = sink (closest cup).
            if (
                not opening_plane_done
                and prev_wh > rim_wh >= ball_wh
                and ball_vh < -0.06
            ):
                den = ball_wh - prev_wh
                if abs(den) > 1e-8:
                    tr = (rim_wh - prev_wh) / den
                    if 0.0 <= tr <= 1.0:
                        opening_plane_done = True
                        cross_wx = prev_wx + tr * (ball_wx - prev_wx)
                        cd = prev_wd + tr * (ball_wd - prev_wd)
                        if cd < rack_front_wd - 32.0:
                            game.finish_throw(
                                None, miss_detail="short — ball never reached the cup row"
                            )
                            phase = "IDLE"
                            shot_done = True
                        elif cd > CUP_PLANE_WD + 48.0:
                            game.finish_throw(
                                None, miss_detail="long — past the cup row in depth"
                            )
                            phase = "IDLE"
                            shot_done = True
                        else:
                            best_i: Optional[int] = None
                            best_d = float("inf")
                            for i, (wxi, wdi) in enumerate(opp_pts):
                                if i >= len(opp) or not opp[i]:
                                    continue
                                d = math.hypot(cd - wdi, cross_wx - wxi)
                                if d <= sink_r and d < best_d:
                                    best_d = d
                                    best_i = i
                            if best_i is not None:
                                game.finish_throw(best_i)
                                sunk_wxi, sunk_wdi = opp_pts[best_i]
                                sunk_ball = (sunk_wdi, sunk_wxi, cup_r * 0.42)
                                sunk_lane = 1 if game.current_player == 1 else 2
                                sunk_anim_ticks = SUNK_ANIM_FRAMES
                                phase = "SUNK"
                                shot_done = True
                            else:
                                min_d = min(
                                    (
                                        math.hypot(cd - wdi, cross_wx - wxi)
                                        for i, (wxi, wdi) in enumerate(opp_pts)
                                        if i < len(opp) and opp[i]
                                    ),
                                    default=999.0,
                                )
                                if min_d > sink_r + 22.0:
                                    game.finish_throw(
                                        None,
                                        miss_detail="past the cups (opening plane)",
                                    )
                                else:
                                    game.finish_throw(
                                        None,
                                        miss_detail="between cups at rim height",
                                    )
                                phase = "IDLE"
                                shot_done = True

            if not shot_done and ball_wh <= 0.08 and abs(ball_vh) < 0.52:
                spd_xy = math.hypot(ball_vd, ball_vwx)
                if spd_xy < 3.05:
                    detail: Optional[str] = None
                    if ball_wd < rack_front_wd - 42.0:
                        detail = "short — stopped on the felt before the rack"
                    elif ball_wd > CUP_PLANE_WD + 42.0:
                        detail = "long — rolled past the cups on the felt"
                    elif rack_front_wd - 28.0 < ball_wd < CUP_PLANE_WD + 32.0:
                        min_drack = min(
                            (
                                math.hypot(ball_wd - wdi, ball_wx - wxi)
                                for i, (wxi, wdi) in enumerate(opp_pts)
                                if i < len(opp) and opp[i]
                            ),
                            default=999.0,
                        )
                        if min_drack > sink_r + 18.0:
                            detail = "wide — on the felt but outside the cups"
                    if detail is not None:
                        game.finish_throw(None, miss_detail=detail)
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
                    game.finish_throw(None, miss_detail=miss_air)
                    phase = "IDLE"

        draw_floor()
        draw_table()
        draw_cups_side()

        ghost = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(ghost, (200, 200, 210, 100), (14, 14), 9)

        for pl in (1, 2):
            lx, ly = launcher_screen_for_player(pl)
            ix, iy = int(lx), int(ly)
            if game.winner is not None:
                pygame.draw.circle(screen, ball_outline, (ix, iy), 7)
                continue
            if pl == game.current_player:
                pygame.draw.circle(screen, ball_white, (ix, iy), 8)
                pygame.draw.circle(screen, (0, 130, 78), (ix, iy), 11, 2)
            else:
                screen.blit(ghost, (ix - 14, iy - 14))

        if game.winner is None:
            aim = "Left table" if game.current_player == 1 else "Right table"
            turn_txt = f"Player {game.current_player} — {aim}  ·  Throws {game.attempts_left}"
            tw = font_lg.render(turn_txt, True, turn_text)
            tsh = font_lg.render(turn_txt, True, turn_shadow)
            tx = size[0] // 2 - tw.get_width() // 2
            ty = 14
            screen.blit(tsh, (tx + 2, ty + 2))
            screen.blit(tw, (tx, ty))

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
            pygame.draw.line(screen, (235, 235, 242), (int(asx), int(asy)), (int(bx), int(by)), 3)
            br = max(6, BALL_RADIUS - 1)
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), br)
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), br, 2)

        if phase == "BALL":
            if shot_preview_trail:
                hit_col = (200, 255, 220)
                miss_col = (255, 210, 160)
                pcol = hit_col if shot_preview_outcome == "hit" else miss_col
                pts_scr: List[Tuple[int, int]] = []
                step = 1
                if len(shot_preview_trail) > 360:
                    step = 2
                for ti in range(0, len(shot_preview_trail), step):
                    twd, twx, twh = shot_preview_trail[ti]
                    sx, sy = world_to_screen_lane(
                        twd, twx, twh, shot_preview_lane, size[0], size[1]
                    )
                    pts_scr.append((int(sx), int(sy)))
                if len(pts_scr) >= 2:
                    pygame.draw.lines(screen, pcol, False, pts_scr, 2)
            bl = shooter_lane(game.current_player)
            bx, by = world_to_screen_lane(ball_wd, ball_wx, ball_wh, bl, size[0], size[1])
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), BALL_RADIUS)
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), BALL_RADIUS, 2)
        elif phase == "SUNK":
            sd, sxw, swh = sunk_ball
            bx, by = world_to_screen_lane(sd, sxw, swh, sunk_lane, size[0], size[1])
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), BALL_RADIUS)
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), BALL_RADIUS, 2)

        if game.winner is not None:
            draw_win_overlay()

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("terminal", "-t", "--terminal"):
        run_terminal_game()
    else:
        run_pygame_gui()
