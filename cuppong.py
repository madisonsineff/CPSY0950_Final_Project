# this is the code for the Cup Pong game! The idea is to have this script launch when the user presses the "Cup Pong" button on the home page
# we wanted to have a separate script for each game that can then go back to the home page at any time to switch between games
# having the games run as separate scripts creates more ease with the code --> site is easier to then navigate
# Coded by Madison Sineff and Pearl Chia, Debugged by Pearl Chia

from __future__ import annotations

# importing necessary libraries
import math
import pathlib
import subprocess
import sys
from dataclasses import dataclass, field
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
# World wd of the front rack row (physics, preview sim, cup perspective).
RACK_FRONT_ROW_WD = CUP_PLANE_WD - 3.0 * PYRAMID_ROW_WD

# Flat far rack: descending crossing of rim-height plane (world wh).
# Lateral distance from a standing cup's center <= cup_r * this counts as a sink (cup top / rim band).
CUP_RIM_PLANE_WH_FRAC = 0.62
CUP_TOP_SINK_FRAC = 0.58

# establishing background music for cup pong file (should be located in the master project folder)
def _cuppong_music_file() -> pathlib.Path:
    base = pathlib.Path(__file__).resolve().parent
    mp3 = base / "cup_pong_audio.mp3"
    if mp3.exists():
        return mp3
    return base / "cuppong_music.ogg"

# starting the background music for cup pong and making sure it loops forever, until the game is closed
def _start_cuppong_background_music() -> None:
    path = _cuppong_music_file()
    if not path.exists():
        return
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(0.32)
        pygame.mixer.music.play(-1)  # -1 = loop forever until stop() / quit
    except pygame.error:
        pass


def _stop_cuppong_background_music() -> None:
    try:
        pygame.mixer.music.stop()
    except (pygame.error, AttributeError):
        pass


def _return_to_hub() -> None:
    """Relaunch the main hub (same pattern as other games), then exit this process."""
    hub = pathlib.Path(__file__).resolve().parent / "GamePython_MAINHUB.py"
    if hub.exists():
        subprocess.Popen([sys.executable, str(hub)])
    _stop_cuppong_background_music()
    pygame.quit()
    sys.exit(0)


# World-space cup layout: 10-cup triangle (4 rows) plus extra penalty cups; used for physics and drawing.
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

# this function is used to map the table-world coordinates to the screen coordinates
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

# Each player's half-table is a trapezoid (near edge wide at bottom of screen, far edge narrower) for a 3/4-style view.
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

# Maps world (wd, wx, wh) into left or right lane; two lanes share one window.
def world_to_screen_lane(
    wd: float,  # world depth along table toward the rack
    wx: float,  # world lateral offset
    wh: float,  # world height above the felt
    lane: int, # lane number
    sw: int, # screen width
    sh: int, # screen height
    *,
    rack_flat_baseline_y: bool = False,
) -> Tuple[float, float]:
    """Same world model as world_to_screen, but mapped onto a narrow side-by-side lane (GamePigeon-style).

    If ``rack_flat_baseline_y`` is True (cup rack drawing only), ``table_y`` uses a fixed depth
    (``CUP_RACK_SCREEN_BASELINE_WD``) so every cup base shares one screen row; ``sx`` still uses the real ``wd``
    for depth along the trapezoid plus ``wx`` for lateral offset.
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

# this function is used to calculate the speed of the ball based on the stretch of the slingshot
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

# this function is used to simulate the trail of the ball after it is hit; returns so that UI can draw a green vs orange
def _simulate_shot_trail(
    lw: float,  # launch depth (world wd)
    lwx: float,  # launch lateral (world wx)
    lwh: float,  # launch height above felt (world wh)
    ball_vd: float,  # depth velocity (d wd / dt)
    ball_vwx: float,  # lateral velocity (d wx / dt)
    ball_vh: float,  # height velocity (d wh / dt)
    opp: List[bool], # boolean list of the opponent's cups
    opp_pts: List[Tuple[float, float]], # points of the opponent's cups
    cup_r: float, # radius of the cup
) -> Tuple[List[Tuple[float, float, float]], str]:
    """Advance a throw with the same rules as the BALL phase (no game mutation). Returns
    sampled world positions and an outcome tag; ``hit`` when crossing the rim plane inside
    the cup-top radius (closest cup), other tags for miss-colored preview."""
    wd, wx, wh = lw, lwx, lwh
    vd, vwx, vh = ball_vd, ball_vwx, ball_vh
    trail: List[Tuple[float, float, float]] = [(lw, lwx, lwh)]
    opening_plane_done = False
    rim_wh = cup_r * CUP_RIM_PLANE_WH_FRAC
    sink_r = cup_r * CUP_TOP_SINK_FRAC
    flight_ticks = 0
    while True: # while the ball is in the air, simulate the trail of the ball
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
            den = wh - prev_wh # den is the difference in height between the current and previous position of the ball
            if abs(den) > 1e-8:
                tr = (rim_wh - prev_wh) / den # tr is the time at which the ball crosses the rim
                if 0.0 <= tr <= 1.0:
                    opening_plane_done = True # opening_plane_done is True if the ball has crossed the rim
                    cx = prev_wx + tr * (wx - prev_wx) # cx is the lateral position of the ball at the time of the rim crossing
                    cd = prev_wd + tr * (wd - prev_wd) # cd is the depth of the ball at the time of the rim crossing
                    if cd < RACK_FRONT_ROW_WD - 32.0:
                        trail.append((wd, wx, wh)) # append the current position of the ball to the trail
                        return trail, "short_plane"
                    if cd > CUP_PLANE_WD + 48.0:
                        trail.append((wd, wx, wh)) # append the current position of the ball to the trail   
                        return trail, "long_plane"
                    best_i: Optional[int] = None # best_i is the index of the closest cup to the ball
                    best_d = float("inf") # best_d is the distance to the closest cup to the ball
                    for i, (wxi, wdi) in enumerate(opp_pts):
                        if i >= len(opp) or not opp[i]:
                            continue  # skip removed cups or out-of-range indices
                        d = math.hypot(cd - wdi, cx - wxi)
                        if d <= sink_r and d < best_d: # if the distance to the cup is less than the sink radius and less than the best distance, update the best distance and the best index
                            best_d = d
                            best_i = i # update the best index to the current index
                    if best_i is not None:
                        trail.append((wd, wx, wh)) # append the current position of the ball to the trail   
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
                    trail.append((wd, wx, wh)) # append the current position of the ball to the trail   
                    return trail, tag

        if wh <= 0.08 and abs(vh) < 0.52:
            spd_xy = math.hypot(vd, vwx)  # speed in the felt plane (depth + lateral)      
            if spd_xy < 3.05: # if the speed of the ball is less than 3.05, set the detail to the ground_short, ground_long, or ground_wide
                detail: Optional[str] = None
                if wd < RACK_FRONT_ROW_WD - 42.0:
                    detail = "ground_short" # if the depth of the ball is less than the rack front depth, set the detail to ground_short
                elif wd > CUP_PLANE_WD + 42.0:
                    detail = "ground_long" # if the depth of the ball is greater than the cup plane depth, set the detail to ground_long
                elif RACK_FRONT_ROW_WD - 28.0 < wd < CUP_PLANE_WD + 32.0:
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

        miss_air: Optional[str] = None # miss_air is the type of miss if the ball is in the air
        # Deeper threshold first: otherwise wd > CUP_PLANE + 95 masks "off table" forever.
        if wd > TABLE_DEPTH + 130.0:
            miss_air = "long_end" # if the depth of the ball is greater than the table depth, set the miss_air to long_end
        elif wd > CUP_PLANE_WD + 95.0:
            miss_air = "long_air" # if the depth of the ball is greater than the cup plane depth, set the miss_air to long_air
        elif wd < -42.0:
            miss_air = "behind" # if the depth of the ball is less than -42.0, set the miss_air to behind
        elif abs(wx) > 148.0:
            miss_air = "wide_air"  # world lateral offset too large
        elif wh > 410.0:
            miss_air = "high" # if the height of the ball is greater than 410.0, set the miss_air to high
        elif wh < -95.0:
            miss_air = "drop"
        elif flight_ticks > 640:
            miss_air = "timeout" # if the flight ticks are greater than 640, set the miss_air to timeout
        if miss_air is not None:
            trail.append((wd, wx, wh)) # append the current position of the ball to the trail   
            return trail, miss_air

        trail.append((wd, wx, wh)) # append the current position of the ball to the trail   

# this function is used to draw the side profile of the cup
def draw_cup_side_profile(
    surf: pygame.Surface, # surface to draw on
    base_x: float, # x coordinate of the base of the cup
    base_y: float, # y coordinate of the base of the cup
    scale: float, # scale of the cup
    fill: Tuple[int, int, int], # fill color of the cup
    edge: Tuple[int, int, int], # edge color of the cup
    is_up: bool, # whether the cup is up or down
    *,
    rim_interior: Optional[Tuple[int, int, int]] = None, # interior color of the rim
    height_scale: float = 1.0, # scale of the height of the cup
) -> None:
    """Side-on plastic cup: rim wider than base, opening ellipse, slight 3/4 shading."""
    bx, by = int(round(base_x)), int(round(base_y)) # bx is the x coordinate of the base of the cup and by is the y coordinate of the base of the cup; int(round(base_x)) is the x coordinate of the base of the cup and int(round(base_y)) is the y coordinate of the base of the cup
    hs = max(0.52, min(1.0, height_scale))
    wb = max(10, int(11 * scale)) # wb is the width of the base of the cup
    wt = max(16, int(20 * scale)) # wt is the width of the top of the cup
    h = max(22, int(40 * scale * hs)) # h is the height of the cup
    rim_h = max(3, int(6 * scale * hs)) # rim_h is the height of the rim of the cup

    rim_y = by - h # rim_y is the y coordinate of the rim of the cup

    if not is_up:  # cup knocked over: draw ellipse on felt
        rw, rh = int(wt * 0.85), max(5, int(8 * scale * hs)) # rw is the width of the rim of the cup and rh is the height of the rim of the cup
        pygame.draw.ellipse(surf, fill, (bx - rw // 2, by - rh - 2, rw, rh)) # draw the rim of the cup
        pygame.draw.ellipse(surf, edge, (bx - rw // 2, by - rh - 2, rw, rh), 1) # draw the edge of the rim of the cup
        return

    shad = (28, 32, 38) # shad is the shadow color of the cup
    pygame.draw.ellipse(surf, shad, (bx - wb // 2 - 2, by - 3, wb + 4, 8)) # draw the shadow of the cup

    body = [
        (bx - wb // 2, by), # body is the body of the cup
        (bx + wb // 2, by), # body is the body of the cup
        (bx + wt // 2, rim_y), # body is the body of the cup
        (bx - wt // 2, rim_y), # body is the body of the cup
    ]
    pygame.draw.polygon(surf, fill, body) # draw the body of the cup
    pygame.draw.polygon(surf, edge, body, 2) # draw the edge of the body of the cup

    rim_light = (
        rim_interior # rim_light is the color of the rim of the cup
        if rim_interior is not None
        else tuple(min(255, int(c + 40)) for c in fill) # if the rim interior is not None, set the rim light to the rim interior, otherwise set the rim light to the fill color + 40
    ) # rim_light is the color of the rim of the cup
    pygame.draw.ellipse(
        surf,
        rim_light, # draw the rim of the cup
        (bx - wt // 2 - 1, rim_y - rim_h + 1, wt + 2, rim_h + 3),
    ) # draw the rim of the cup
    pygame.draw.ellipse(
        surf,
        edge, # draw the edge of the rim of the cup
        (bx - wt // 2 - 1, rim_y - rim_h + 1, wt + 2, rim_h + 3),
        1,
    )
    inner = (max(0, fill[0] - 55), max(0, fill[1] - 50), max(0, fill[2] - 45)) # inner is the color of the inner of the cup
    if rim_interior is not None: # if the rim interior is not None, set the inner to the rim interior
        inner = (max(0, rim_interior[0] - 40), max(0, rim_interior[1] - 40), max(0, rim_interior[2] - 45)) # inner is the color of the inner of the cup
    pygame.draw.arc( # draw the arc of the inner of the cup
        surf,
        inner, # draw the inner of the cup
        (bx - wt // 2 + 2, rim_y - rim_h + 2, wt - 4, rim_h + 4), # draw the inner of the cup
        0.15 * math.pi, # draw the inner of the cup
        0.85 * math.pi, # draw the inner of the cup
        2, # draw the inner of the cup
    ) # draw the inner of the cup
    sh_col = (max(0, fill[0] - 35), max(0, fill[1] - 35), max(0, fill[2] - 30)) # sh_col is the color of the shadow of the cup
    pygame.draw.line(surf, sh_col, (bx - wt // 2 + 3, rim_y - 2), (bx - wt // 2 + 3, by - 4), 2) # draw the shadow of the cup
    pygame.draw.line(surf, edge, (bx - wb // 2, by), (bx + wb // 2, by), 2) # draw the edge of the cup

# this class is used to store the result of a shot
@dataclass
class ShotResult:
    success: bool # success is True if the shot was successful
    message: str # message is the message to be displayed to the user
    hit: bool = False # hit is True if the shot was a hit   
    target_cup: Optional[int] = None # target_cup is the index of the cup that was hit

# this class is used to store the game state
class CupPongGame:
    """Two racks; win by sinking every cup on the opponent's side (no cups left on that rack)."""

    def __init__(self, initial_cups_per_side: int = INITIAL_CUPS_PER_SIDE) -> None:
        if initial_cups_per_side <= 0: # if the initial number of cups per side is less than or equal to 0, raise an error
            raise ValueError("initial_cups_per_side must be greater than 0.")

        self.initial_cups_per_side = initial_cups_per_side # initial_cups_per_side is the initial number of cups per side
        self.player_one_cups: List[bool] = [True] * initial_cups_per_side # player_one_cups is the list of cups for player one
        self.player_two_cups: List[bool] = [True] * initial_cups_per_side # player_two_cups is the list of cups for player two
        self.current_player = 1 # current_player is the current player
        self.winner: Optional[int] = None # winner is the winner of the game
        self.attempts_left = ATTEMPTS_PER_ROUND # attempts_left is the number of attempts left
        self.hits_this_turn = 0 # hits_this_turn is the number of hits this turn

    def reset(self) -> None:
        """Restore racks and turn state for a new match."""
        n = self.initial_cups_per_side # n is the initial number of cups per side
        self.player_one_cups = [True] * n # player_one_cups is the list of cups for player one
        self.player_two_cups = [True] * n # player_two_cups is the list of cups for player two
        self.current_player = 1 # current_player is the current player
        self.winner = None # winner is the winner of the game
        self.attempts_left = ATTEMPTS_PER_ROUND # attempts_left is the number of attempts left
        self.hits_this_turn = 0 # hits_this_turn is the number of hits this turn

    def finish_throw(
        self,
        cup_index_if_hit: Optional[int], # cup_index_if_hit is the index of the cup that was hit
        *,
        miss_detail: Optional[str] = None,
    ) -> ShotResult: # ShotResult is the result of a shot
        """Resolve one throw: cup_index indexes a standing cup on the opponent rack."""
        if self.winner is not None:
            return ShotResult(False, "Game is over. Press R to reset.") # if the game is over, return a ShotResult with False and the message "Game is over. Press R to reset."

        hit = False # hit is False if the shot was not a hit
        msg = ""
        opp = self._opponent_cups() # opp is the list of cups for the opponent

        if cup_index_if_hit is not None and 0 <= cup_index_if_hit < len(opp):
            if opp[cup_index_if_hit]: # if the cup that was hit is up
                opp[cup_index_if_hit] = False
                hit = True # hit is True if the shot was a hit
                self.hits_this_turn += 1
                msg = "Sunk! The ball dropped in — that cup is grayed out." # msg is the message to be displayed to the user
                self._update_winner()
            else:
                msg = "Miss — that cup is already down." # msg is the message to be displayed to the user
        else:
            if miss_detail:
                msg = f"Miss — {miss_detail}." # msg is the message to be displayed to the user
            else:
                msg = "Miss."  # msg is the message to be displayed to the user

        self.attempts_left -= 1 # attempts_left is the number of attempts left
        extra = "" # extra is the extra message to be displayed to the user

        if self.winner is None and self.attempts_left <= 0: # if the game is not over and the number of attempts left is less than or equal to 0
            if self.hits_this_turn >= ATTEMPTS_PER_ROUND:
                shooter = self.current_player
                penalty_player = self._add_penalty_cup_to_shooter_stack()
                if penalty_player is not None:
                    extra += (
                        f" Player {shooter} went 2/2 — penalty cup on Player {penalty_player}'s rack."
                    )
                else:
                    extra += (
                        f" Player {shooter} went 2/2 — no penalty cup (max {MAX_CUPS_PER_PLAYER})."
                    ) # extra is the extra message to be displayed to the user  
            self.hits_this_turn = 0
            self.attempts_left = ATTEMPTS_PER_ROUND # attempts_left is the number of attempts left
            self._switch_player() # switch the player
            extra += f" Player {self.current_player}'s turn ({ATTEMPTS_PER_ROUND} throws)." # extra is the extra message to be displayed to the user  

        # return the result of the shot
        return ShotResult(True, msg + extra, hit=hit, target_cup=cup_index_if_hit if hit else None)

    # this function is used to add a penalty cup to the shooter's rack
    def _add_penalty_cup_to_shooter_stack(self) -> Optional[int]:
        """Two makes in one turn: add one cup to the shooter's own rack if under cap."""
        shooter = self.current_player # shooter is the current player
        rack = self._cups_for_player(shooter) # rack is the list of cups for the shooter
        if len(rack) >= MAX_CUPS_PER_PLAYER: # if the number of cups in the shooter's rack is greater than or equal to the maximum number of cups per player, return None
            return None # return None
        rack.append(True) # add a cup to the shooter's rack
        return shooter # return the shooter

    # this function is used to get the number of remaining cups for a player
    def remaining_cups(self, player: int) -> int:
        cups = self._cups_for_player(player) # cups is the list of cups for the player
        return sum(1 for is_up in cups if is_up) # return the number of remaining cups for the player

    # this function is used to switch the player
    def _switch_player(self) -> None:
        self.current_player = 2 if self.current_player == 1 else 1 # switch the player

    # this function is used to update the winner
    def _update_winner(self) -> None:
        if self.remaining_cups(1) == 0: # if the number of remaining cups for player 1 is 0, set the winner to 2
            self.winner = 2 # set the winner to 2
        elif self.remaining_cups(2) == 0: # if the number of remaining cups for player 2 is 0, set the winner to 1
            self.winner = 1 # set the winner to 1

    # this function is used to get the cups for the opponent
    def _opponent_cups(self) -> List[bool]: # return the cups for the opponent
        return self.player_two_cups if self.current_player == 1 else self.player_one_cups # return the cups for the opponent

    # this function is used to get the cups for a player
    def _cups_for_player(self, player: int) -> List[bool]:
        if player == 1: # if the player is player 1, return the cups for player 1
            return self.player_one_cups # return the cups for player 1
        if player == 2: # if the player is player 2, return the cups for player 2
            return self.player_two_cups # return the cups for player 2
        raise ValueError("player must be 1 or 2.") # raise an error if the player is not 1 or 2

    # this function is used to get the board as a string
    def board_as_string(self) -> str: # return the board as a string
        def line(cups: List[bool]) -> str:
            return " ".join("O" if c else "X" for c in cups) # return the line as a string  
        # return the board as a string          
        return (
            "Cup Pong — two racks (O = standing, X = removed)\n"
            f"Player 1 rack: {line(self.player_one_cups)}\n"
            f"Player 2 rack: {line(self.player_two_cups)}\n"
            f"Current: Player {self.current_player} | Throws left: {self.attempts_left}"
        )

# this function is used to run the terminal game
def run_terminal_game() -> None:
    game = CupPongGame() # game is the game object
    n = len(game._opponent_cups()) # n is the number of cups for the opponent
    print("Cup Pong (terminal) — m = miss, k = hit cup k (1-indexed), q = quit") # print the instructions for the terminal game
    print(f"{INITIAL_CUPS_PER_SIDE} cups per triangle; {ATTEMPTS_PER_ROUND} tries per turn.\n") # print the initial cups per side and the attempts per turn

    while True: # while the game is not over
        print(game.board_as_string()) # print the board
        if game.winner is not None: # if the game is over, print the winner
            print(f"\nPlayer {game.winner} wins!") # print the winner
            break

        mx = len(game._opponent_cups()) # mx is the number of cups for the opponent
        user_input = input(
            f"\nPlayer {game.current_player} ({game.attempts_left} throw(s) left): "
        ).strip().lower() # user_input is the user's input
        if user_input in {"q", "quit", "exit"}:
            print("Thanks for playing.") # print the thanks for playing message 
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

# this function is used to wrap text to width
def _wrap_text_to_width(
    font: pygame.font.Font, # font is the font to be used
    text: str, # text is the text to be wrapped
    max_width: int, # max_width is the maximum width of the text
) -> List[str]: # return the wrapped text
    """Word-wrap one paragraph so each rendered line fits within ``max_width`` pixels."""
    text = text.strip()
    if not text:
        return [] # return an empty list if the text is empty
    words = text.split()
    lines: List[str] = [] # lines is the list of lines  
    current = "" # current is the current line
    for word in words:
        trial = f"{current} {word}".strip() if current else word # trial is the trial line
        if font.size(trial)[0] <= max_width:
            current = trial # current is the current line
        else:
            if current:
                lines.append(current) # add the current line to the list of lines
            if font.size(word)[0] <= max_width:
                current = word # current is the current line
            else:
                chunk = "" # chunk is the chunk of text
                for ch in word:
                    nxt = chunk + ch # nxt is the next line
                    if font.size(nxt)[0] <= max_width:
                        chunk = nxt # chunk is the chunk of text
                    else:
                        if chunk:
                            lines.append(chunk) # add the chunk to the list of lines
                        chunk = ch # chunk is the chunk of text
                current = chunk
    if current: # if the current line is not empty, add it to the list of lines
        lines.append(current)
    return lines # return the list of lines

# this function is used to wrap the instruction paragraphs
def _wrap_instruction_paragraphs(
    font: pygame.font.Font, # font is the font to be used
    paragraphs: List[str], # paragraphs is the list of paragraphs
    max_width: int, # max_width is the maximum width of the text
) -> List[str]: # return the wrapped text
    """Word-wrap each non-empty paragraph; insert a blank line between paragraphs."""
    out: List[str] = [] # out is the list of wrapped text
    first = True # first is True if the first paragraph
    for raw in paragraphs:
        para = raw.strip() # para is the paragraph
        if not para: # if the paragraph is empty, continue
            continue
        if not first: # if the first paragraph is not empty, add a blank line to the list of wrapped text
            out.append("") # add a blank line to the list of wrapped text
        first = False # first is False if the first paragraph is not empty
        out.extend(_wrap_text_to_width(font, para, max_width)) # add the wrapped text to the list of wrapped text
    return out # return the list of wrapped text    

# --- pygame GUI helpers (pure drawing; keeps run_pygame_gui readable) ---


def _draw_filled_round_rect(
    surf: pygame.Surface,
    rect: pygame.Rect,
    fill: Tuple[int, int, int],
    border: Tuple[int, int, int],
    border_width: int,
    radius: int,
) -> None:
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, width=border_width, border_radius=radius)


def _draw_labeled_round_button(
    surf: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.font.Font,
    label: str,
    text_rgb: Tuple[int, int, int],
    fill_idle: Tuple[int, int, int],
    fill_hover: Tuple[int, int, int],
    border_rgb: Tuple[int, int, int],
    border_width: int,
    radius: int,
    mouse_pos: Tuple[int, int],
) -> None:
    fill = fill_idle if not rect.collidepoint(mouse_pos) else fill_hover
    _draw_filled_round_rect(surf, rect, fill, border_rgb, border_width, radius)
    surf_text = font.render(label, True, text_rgb)
    surf.blit(
        surf_text,
        (rect.centerx - surf_text.get_width() // 2, rect.centery - surf_text.get_height() // 2),
    )


def _blit_text_with_drop_shadow(
    surf: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: Tuple[int, int, int],
    shadow: Tuple[int, int, int],
    pos: Tuple[int, int],
) -> None:
    shadow_surf = font.render(text, True, shadow)
    main_surf = font.render(text, True, color)
    x, y = pos
    surf.blit(shadow_surf, (x + 2, y + 2))
    surf.blit(main_surf, (x, y))


@dataclass
class CupPongGuiSession:
    """Mutable per-window state for :func:`run_pygame_gui` (one instance per run)."""

    phase: str = "IDLE"
    sunk_anim_ticks: int = 0
    sunk_lane: int = 1
    opening_plane_done: bool = False
    ball_wd: float = 0.0
    ball_wx: float = 0.0
    ball_wh: float = 0.0
    ball_vd: float = 0.0
    ball_vwx: float = 0.0
    ball_vh: float = 0.0
    flight_ticks: int = 0
    running: bool = True
    shot_preview_trail: List[Tuple[float, float, float]] = field(default_factory=list)
    shot_preview_lane: int = 1
    shot_preview_outcome: str = ""
    app_phase: str = "INSTRUCTIONS"
    sunk_ball: Tuple[float, float, float] = (0.0, 0.0, 0.0)


# this function is used to run the pygame gui
def run_pygame_gui() -> None:
    pygame.init() # initialize pygame
    size = (1200, 800) # size is the size of the screen
    screen = pygame.display.set_mode(size, pygame.HWSURFACE | pygame.DOUBLEBUF) # screen is the screen object
    pygame.display.set_caption("Cup Pong") # set the caption of the screen
    clock = pygame.time.Clock() # clock is the clock object
    _start_cuppong_background_music() # start the background music

    # GamePigeon-style: wood floor, bright green felt, white trim, red cups / white rims.
    floor_a = (218, 186, 142) # floor_a is the color of the floor
    floor_b = (205, 170, 125) # floor_b is the color of the floor
    felt_gp = (0, 149, 87) # felt_gp is the color of the felt
    felt_dark = (0, 118, 72) # felt_dark is the color of the felt
    trim_white = (255, 255, 255) # trim_white is the color of the trim
    cup_red_a = (215, 52, 62) # cup_red_a is the color of the cup
    cup_red_b = (200, 46, 58) # cup_red_b is the color of the cup
    cup_out = (95, 98, 108) # cup_out is the color of the cup
    rim_white = (252, 252, 255) # rim_white is the color of the rim
    rim_edge = (180, 182, 190) # rim_edge is the color of the rim
    ball_white = (255, 255, 255) # ball_white is the color of the ball
    ball_outline = (190, 192, 198) # ball_outline is the color of the ball
    turn_shadow = (32, 30, 28) # turn_shadow is the color of the turn
    turn_text = (255, 252, 248) # turn_text is the color of the turn

    font_lg = pygame.font.SysFont("optima", 30, bold=True) # font_lg is the font for the large text
    font_win_title = pygame.font.SysFont("optima", 52, bold=True) # font_win_title is the font for the win title
    font_win_sub = pygame.font.SysFont("optima", 22) # font_win_sub is the font for the win sub
    font_win_btn = pygame.font.SysFont("optima", 26, bold=True) # font_win_btn is the font for the win button
    font_instr_title = pygame.font.SysFont("optima", 38, bold=True) # font_instr_title is the font for the instruction title
    font_instr_body = pygame.font.SysFont("optima", 21) # font_instr_body is the font for the instruction body

    game = CupPongGame()
    cup_r = 24.0 # cup_r is the radius of the cup
    RACK_CENTER_WX = 0.0 # RACK_CENTER_WX is the center of the rack
    LANE_COL_DX = 52.0 # LANE_COL_DX is the column of the lane
    LAUNCH_WD = 36.0  # launch anchor depth in world space (wd)
    LAUNCH_WH = 6.0 # LAUNCH_WH is the height of the launch
    # Frames at 60 FPS before next shot after a sink (shorter = faster handoff to next player / next throw).
    SUNK_ANIM_FRAMES = 9 # SUNK_ANIM_FRAMES is the number of frames at 60 FPS before next shot after a sink

    def cup_placements_for_side(rack_owner: int) -> List[Tuple[float, float]]:
        rack = game.player_one_cups if rack_owner == 1 else game.player_two_cups
        return rack_world_placements(len(rack), RACK_CENTER_WX, LANE_COL_DX, CUP_PLANE_WD)

    def opponent_rack_for_shooter(shooter: int) -> Tuple[List[bool], List[Tuple[float, float]]]:
        if shooter == 1:
            return game.player_two_cups, cup_placements_for_side(2)
        return game.player_one_cups, cup_placements_for_side(1)
    # this function is used to get the launch world
    def launch_world() -> Tuple[float, float, float]:
        """World launcher anchor (wd, wx, wh). Same for both players; lane mapping picks left vs right table."""
        return LAUNCH_WD, RACK_CENTER_WX, LAUNCH_WH

    def shooter_lane(player: int) -> int: # shooter_lane is the lane of the shooter
        return 1 if player == 1 else 2 # return 1 if the player is 1, otherwise 2

    def launcher_screen_for_player(player: int) -> Tuple[float, float]: # launcher_screen_for_player is the screen for the launcher
        wd0, wx0, wh0 = launch_world() # wd0 is the distance of the launcher, wx0 is the x position of the launcher, wh0 is the height of the launcher
        return world_to_screen_lane(wd0, wx0, wh0, shooter_lane(player), size[0], size[1]) # return the screen for the launcher

    def active_launcher_screen() -> Tuple[float, float]: # active_launcher_screen is the screen for the active launcher
        return launcher_screen_for_player(game.current_player) # return the screen for the active launcher

    def dist_to_active_launcher(pos: Tuple[int, int]) -> float:
        lx, ly = active_launcher_screen()
        return math.hypot(pos[0] - lx, pos[1] - ly)

    sw, sh = size[0], size[1] # sw is the width of the screen, sh is the height of the screen
    cx, cy = sw // 2, sh // 2 # cx is the x position of the center of the screen, cy is the y position of the center of the screen
    win_panel = pygame.Rect(cx - 280, cy - 175, 560, 350) # win_panel is the rectangle for the win panel
    win_btn_play = pygame.Rect(cx - 250, win_panel.bottom - 100, 240, 50) # win_btn_play is the rectangle for the win button play
    win_btn_home = pygame.Rect(cx + 10, win_panel.bottom - 100, 240, 50) # win_btn_home is the rectangle for the win button home
    instr_panel = pygame.Rect(cx - 330, 56, 660, sh - 200) # instr_panel is the rectangle for the instruction panel
    instr_start_rect = pygame.Rect(cx - 140, sh - 118, 280, 52) # instr_start_rect is the rectangle for the instruction start rect

    # this function is used to draw the instructions screen
    def draw_instructions_screen() -> None:
        mp = pygame.mouse.get_pos()
        _draw_filled_round_rect(screen, instr_panel, (248, 246, 242), (58, 60, 72), 2, 18)
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
        wrapped = _wrap_instruction_paragraphs(font_instr_body, body_paragraphs, max_text_w)
        line_gap = 26
        y = instr_panel.y + 78
        for line in wrapped:
            if line == "":
                y += 12
                continue
            surf = font_instr_body.render(line, True, (55, 58, 72))
            screen.blit(surf, (instr_panel.x + pad_x, y))
            y += line_gap
        _draw_labeled_round_button(
            screen,
            instr_start_rect,
            font_win_btn,
            "Start game",
            (255, 255, 255),
            (42, 140, 78),
            (52, 168, 98),
            (18, 72, 44),
            2,
            12,
            mp,
        )
        hint_text = "Or press Enter / Space to begin"
        hint_lines = _wrap_text_to_width(font_instr_body, hint_text, max_text_w)
        hy = instr_start_rect.bottom + 12
        for hl in hint_lines:
            hs = font_instr_body.render(hl, True, (120, 122, 132))
            screen.blit(hs, (cx - hs.get_width() // 2, hy))
            hy += line_gap - 4

    # this function is used to reset the match from the ui
    def reset_match_from_ui() -> None:
        game.reset()
        session.phase = "IDLE"
        session.sunk_anim_ticks = 0
        session.sunk_lane = 1
        session.opening_plane_done = False
        session.shot_preview_trail.clear()
        session.shot_preview_outcome = ""
        lw, lwx, lwh = launch_world()
        session.ball_wd, session.ball_wx, session.ball_wh = lw, lwx, lwh
        session.ball_vd = 0.0
        session.ball_vwx = 0.0
        session.ball_vh = 0.0
        session.flight_ticks = 0

    # this function is used to draw the win overlay
    def draw_win_overlay() -> None:
        wn = game.winner
        if wn is None:
            return
        title = f"Player {wn} wins!"
        sub = "Cleared the opponent's rack."
        hint = "Play again  ·  R or Enter     |     Home  ·  H or button below"
        ty = win_panel.y + 36
        tx = cx - font_win_title.size(title)[0] // 2
        _blit_text_with_drop_shadow(screen, font_win_title, title, (28, 30, 38), (200, 200, 205), (tx, ty))
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((15, 18, 22, 175))
        screen.blit(dim, (0, 0))
        _draw_filled_round_rect(screen, win_panel, (252, 250, 248), (55, 58, 68), 3, 20)
        su = font_win_sub.render(sub, True, (80, 82, 92))
        screen.blit(su, (cx - su.get_width() // 2, ty + 62))
        hi = font_win_sub.render(hint, True, (110, 112, 125))
        screen.blit(hi, (cx - hi.get_width() // 2, ty + 96))
        mp = pygame.mouse.get_pos()
        for rect, label in ((win_btn_play, "Play again"), (win_btn_home, "Home")):
            _draw_labeled_round_button(
                screen,
                rect,
                font_win_btn,
                label,
                (255, 255, 255),
                (52, 118, 220),
                (72, 138, 240),
                (24, 48, 100),
                2,
                12,
                mp,
            )

    def draw_floor() -> None: # draw the floor
        sw, sh = size[0], size[1] # sw is the width of the screen, sh is the height of the screen
        stripe = 40 # stripe is the width of the stripe
        for x in range(0, sw + stripe, stripe): # for the x position of the stripe
            c = floor_a if (x // stripe) % 2 == 0 else floor_b # c is the color of the stripe
            pygame.draw.rect(screen, c, (x, 0, stripe, sh)) # draw the stripe

    def draw_table() -> None: # draw the table
        sw, sh = size[0], size[1] # sw is the width of the screen, sh is the height of the screen
        for lane in (1, 2): # for the lane
            nl, nr, fl, fr, ny, fy = lane_trapezoid_bounds(sw, sh, lane) # nl is the left position of the lane, nr is the right position of the lane, fl is the left position of the lane, fr is the right position of the lane, ny is the y position of the lane, fy is the y position of the lane
            pts = [(int(nl), int(ny)), (int(nr), int(ny)), (int(fr), int(fy)), (int(fl), int(fy))] # pts is the points of the lane
            pygame.draw.polygon(screen, felt_dark, pts) # draw the felt dark of the lane
            pygame.draw.polygon(screen, felt_gp, pts) # draw the felt gp of the lane
            pygame.draw.polygon(screen, trim_white, pts, width=3) # draw the trim white of the lane
            ncx = 0.5 * (nl + nr) # ncx is the x position of the center of the lane
            fcx = 0.5 * (fl + fr) # fcx is the x position of the center of the lane
            pygame.draw.line(screen, trim_white, (int(ncx), int(ny)), (int(fcx), int(fy)), 2) # draw the trim white of the lane

    def draw_cups_side() -> None: # draw the cups side  
        vis_scale = cup_r / 11.0 # vis_scale is the scale of the cups
        front_wd = RACK_FRONT_ROW_WD
        to_draw: List[Tuple[float, float, float, Tuple[int, int, int], bool, float, float]] = [] # to_draw is the list of the cups to draw
        for placements, cups, fill, lane in (
            (cup_placements_for_side(2), game.player_two_cups, cup_red_b, 1), # for the placements, cups, fill, and lane
            (cup_placements_for_side(1), game.player_one_cups, cup_red_a, 2), # for the placements, cups, fill, and lane
        ):
            for i, (wxi, wdi) in enumerate(placements): # for the i and the wxi and the wdi
                if i >= len(cups): # if the i is greater than or equal to the length of the cups, break
                    break
                sx, sy = world_to_screen_lane(wdi, wxi, 0.0, lane, size[0], size[1])
                fill_use = fill if cups[i] else cup_out
                depth_vis = (wdi - front_wd) / max(1.0, 3.0 * PYRAMID_ROW_WD) # depth_vis is the depth of the cups
                depth_vis = max(0.0, min(1.0, depth_vis))
                scale_i = vis_scale * (0.82 + 0.18 * depth_vis)
                # Shorter bodies toward the back row (perspective) without shrinking width as much.
                height_scale = 1.0 - 0.44 * depth_vis # height_scale is the scale of the height of the cups
                to_draw.append((wdi, sx, sy, fill_use, cups[i], scale_i, height_scale)) 
        to_draw.sort(key=lambda row: (-row[0], row[1]))
        for _, sx, sy, fill, standing, sc, hsc in to_draw:
            if standing: # if the standing is True, draw the cup side profile
                draw_cup_side_profile(screen, sx, sy, sc, fill, rim_edge, True, rim_interior=rim_white, height_scale=hsc) # draw the cup side profile
            else: # if the standing is False, draw the cup side profile
                draw_cup_side_profile(screen, sx, sy, sc, fill, rim_edge, False, height_scale=hsc) # draw the cup side profile

    session = CupPongGuiSession()
    _lw0, _lwx0, _lwh0 = launch_world()
    session.ball_wd, session.ball_wx, session.ball_wh = _lw0, _lwx0, _lwh0

    while session.running:
        for event in pygame.event.get(): # for the event
            if event.type == pygame.QUIT:
                session.running = False # session.running is False if the game is not session.running
                continue # continue to the next event
            if session.app_phase == "INSTRUCTIONS":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: # if the key is the escape key, set the session.running to False
                        session.running = False # session.running is False if the game is not session.running
                    elif event.key in (
                        pygame.K_RETURN,
                        pygame.K_SPACE, # if the key is the return key or the space key, set the session.app_phase to "PLAY"    
                    ):
                        session.app_phase = "PLAY" # session.app_phase is the session.phase of the app
                elif (
                    event.type == pygame.MOUSEBUTTONDOWN # if the type of the event is the mouse button down, set the session.app_phase to "PLAY"    
                    and event.button == 1 # if the button is the left mouse button, set the session.app_phase to "PLAY"    
                    and instr_start_rect.collidepoint(event.pos) # if the position of the event is in the instruction start rect, set the session.app_phase to "PLAY"    
                ):
                    session.app_phase = "PLAY" # session.app_phase is the session.phase of the app
                continue
            if event.type == pygame.KEYDOWN: # if the type of the event is the key down, set the session.running to False
                if event.key == pygame.K_ESCAPE:
                    session.running = False # session.running is False if the game is not session.running
                elif game.winner is not None:
                    if event.key in (pygame.K_h, pygame.K_HOME):
                        _return_to_hub()
                    elif event.key in (pygame.K_r, pygame.K_RETURN):
                        reset_match_from_ui()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1: # if the type of the event is the mouse button down and the button is the left mouse button, set the session.running to False
                if game.winner is not None:
                    if win_btn_play.collidepoint(event.pos): # if the position of the event is in the win button play, set the session.running to False
                        reset_match_from_ui() # reset the match from the ui
                    elif win_btn_home.collidepoint(event.pos):
                        _return_to_hub()
                elif game.winner is None and session.phase == "IDLE":
                    if dist_to_active_launcher(event.pos) <= LAUNCH_GRAB_RADIUS: # if the distance to the active launcher is less than or equal to the launch grab radius, set the session.phase to "SLING"
                        session.phase = "SLING"
            elif game.winner is None and session.phase == "SLING":
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    asx, asy = active_launcher_screen() # asx is the x position of the active launcher, asy is the y position of the active launcher
                    mx, my = float(event.pos[0]), float(event.pos[1]) # mx is the x position of the mouse, my is the y position of the mouse
                    dx, dy = mx - asx, my - asy
                    stretch = math.hypot(dx, dy) # stretch is the stretch of the sling
                    if stretch < MIN_SLING_PULL: # if the stretch is less than the minimum sling pull, set the session.phase to "IDLE"
                        session.phase = "IDLE" # session.phase is the session.phase of the game
                        session.shot_preview_trail = [] # session.shot_preview_trail is the trail of the shot preview
                        session.shot_preview_outcome = "" # session.shot_preview_outcome is the outcome of the shot preview
                    else:
                        cap = min(stretch, MAX_SLING_PULL) # cap is the cap of the sling
                        pfx = -dx / stretch  # horizontal component of pull direction (screen space)
                        pfy = -dy / stretch  # vertical component of pull direction (screen space)
                        flen = math.hypot(pfx, pfy) or 1.0
                        pfx /= flen  # unit pull direction
                        pfy /= flen
                        t = cap / MAX_SLING_PULL # t is the t of the sling
                        sp = slingshot_speed_for_stretch_norm(t) # sp is the speed of the sling
                        Dwd = max(0.1, -pfy)  # aim vector: depth component (mapped from screen pull)
                        Dwx = pfx * 0.98
                        Dwh = -abs(pfy) * 0.84 - 0.44
                        m3 = math.hypot(Dwd, Dwx, Dwh)  # normalize to unit launch direction in world space
                        if m3 < 1e-6:
                            Dwd, Dwx, Dwh = 1.0, 0.0, -0.45
                            m3 = math.hypot(Dwd, Dwx, Dwh)
                        Dwd /= m3
                        Dwx /= m3
                        Dwh /= m3
                        lw, lwx, lwh = launch_world()
                        session.ball_wd, session.ball_wx, session.ball_wh = lw, lwx, lwh
                        session.ball_vd = Dwd * sp
                        session.ball_vwx = Dwx * sp
                        session.ball_vh = -Dwh * sp  # negate aim so toss goes up in world wh
                        opp_sim, pts_sim = opponent_rack_for_shooter(game.current_player)
                        session.shot_preview_trail, session.shot_preview_outcome = _simulate_shot_trail(
                            lw, lwx, lwh, session.ball_vd, session.ball_vwx, session.ball_vh, opp_sim, pts_sim, cup_r
                        )
                        session.shot_preview_lane = shooter_lane(game.current_player)
                        session.phase = "BALL" # session.phase is the session.phase of the game
                        session.flight_ticks = 0  # reset shot integration step counter
                        session.opening_plane_done = False # session.opening_plane_done is True if the opening plane is done
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                    session.phase = "IDLE" # session.phase is the session.phase of the game
                    session.shot_preview_trail = [] # session.shot_preview_trail is the trail of the shot preview
                    session.shot_preview_outcome = "" # session.shot_preview_outcome is the outcome of the shot preview

        if session.app_phase == "INSTRUCTIONS":
            draw_floor() # draw the floor
            draw_instructions_screen() # draw the instructions screen
            pygame.display.flip()
            clock.tick(60) # tick the clock
            continue

        if session.phase == "SUNK":
            session.sunk_anim_ticks -= 1 # session.sunk_anim_ticks is the number of frames at 60 FPS before next shot after a sink
            if session.sunk_anim_ticks <= 0: # if the session.sunk_anim_ticks is less than or equal to 0, set the session.phase to "IDLE"
                session.phase = "IDLE" # session.phase is the session.phase of the game

        if session.phase == "BALL" and game.winner is None:
            prev_wd = session.ball_wd
            prev_wx = session.ball_wx  # previous world lateral (wx)
            prev_wh = session.ball_wh  # previous world height (wh)

            session.ball_vh -= GRAVITY_WORLD  # gravity acts on world height (wh)
            session.ball_wd += session.ball_vd
            session.ball_wx += session.ball_vwx
            session.ball_wh += session.ball_vh
            session.flight_ticks += 1  # physics steps this shot (guarded by max to avoid infinite loop)

            if session.ball_wh < 0.0: # if the session.ball_wh is less than 0, set the session.ball_wh to 0
                session.ball_wh = 0.0 # session.ball_wh is the height of the ball
                if session.ball_vh < 0.0: # if the session.ball_vh is less than 0, set the session.ball_vh to 0
                    session.ball_vh *= -0.38
                if abs(session.ball_vh) < 0.55:
                    session.ball_vh = 0.0
                session.ball_vd *= 0.86  # felt friction damping on depth motion
                session.ball_vwx *= 0.85  # felt friction damping on lateral motion

            opp, opp_pts = opponent_rack_for_shooter(game.current_player)

            rim_wh = cup_r * CUP_RIM_PLANE_WH_FRAC  # world wh where rim opening is tested
            sink_r = cup_r * CUP_TOP_SINK_FRAC # sink_r is the radius of the sink

            shot_done = False # shot_done is True if the shot is done   

            # Descending through rim-height plane: within cup-top radius of a standing cup = sink (closest cup).
            if (
                not session.opening_plane_done
                and prev_wh > rim_wh >= session.ball_wh
                and session.ball_vh < -0.06
            ):
                den = session.ball_wh - prev_wh # den is the difference in the height of the ball and the previous height of the ball
                if abs(den) > 1e-8:
                    tr = (rim_wh - prev_wh) / den  # fraction along segment where ball crosses rim height
                    if 0.0 <= tr <= 1.0:
                        session.opening_plane_done = True
                        cross_wx = prev_wx + tr * (session.ball_wx - prev_wx)  # lateral (wx) at rim crossing
                        cd = prev_wd + tr * (session.ball_wd - prev_wd)  # depth (wd) at rim crossing
                        if cd < RACK_FRONT_ROW_WD - 32.0:
                            game.finish_throw(
                                None, miss_detail="short — ball never reached the cup row" # miss_detail is the detail of the miss
                            )
                            session.phase = "IDLE" # session.phase is the session.phase of the game
                            shot_done = True
                        elif cd > CUP_PLANE_WD + 48.0:
                            game.finish_throw(
                                None, miss_detail="long — past the cup row in depth"
                            )
                            session.phase = "IDLE"
                            shot_done = True
                        else:
                            best_i: Optional[int] = None # best_i is the index of the best cup
                            best_d = float("inf") # best_d is the distance to the best cup
                            for i, (wxi, wdi) in enumerate(opp_pts):
                                if i >= len(opp) or not opp[i]: # if the index is greater than or equal to the number of cups or the cup is not in the list, continue   
                                    continue
                                d = math.hypot(cd - wdi, cross_wx - wxi) # d is the distance to the cup
                                if d <= sink_r and d < best_d:
                                    best_d = d # best_d is the distance to the best cup
                                    best_i = i # best_i is the index of the best cup
                            if best_i is not None:
                                game.finish_throw(best_i) # game.finish_throw is the function to finish the throw
                                sunk_wxi, sunk_wdi = opp_pts[best_i]  # (wx, wd) cup center in world space
                                session.sunk_ball = (sunk_wdi, sunk_wxi, cup_r * 0.42) # session.sunk_ball is the ball that was sunk
                                session.sunk_lane = shooter_lane(game.current_player)
                                session.sunk_anim_ticks = SUNK_ANIM_FRAMES # session.sunk_anim_ticks is the number of frames at 60 FPS before the sunk animation
                                session.phase = "SUNK" # session.phase is the session.phase of the game
                                shot_done = True # shot_done is True if the shot is done
                            else:
                                min_d = min((math.hypot(cd - wdi, cross_wx - wxi) for i, (wxi, wdi) in enumerate(opp_pts) if i < len(opp) and opp[i]), default=999.0) # min_d is the minimum distance to the cups
                                if min_d > sink_r + 22.0: # if the minimum distance to the cups is greater than the sink radius plus 22.0, set the session.phase to "IDLE"
                                    game.finish_throw(
                                        None, miss_detail="past the cups (opening plane)" # miss_detail is the detail of the miss
                                    )
                                else:
                                    game.finish_throw(None, miss_detail="between cups at rim height") # miss_detail is the detail of the miss
                                session.phase = "IDLE" # session.phase is the session.phase of the game
                                shot_done = True # shot_done is True if the shot is done

            if not shot_done and session.ball_wh <= 0.08 and abs(session.ball_vh) < 0.52: # if the session.ball_wh is less than or equal to 0.08 and the absolute value of the session.ball_vh is less than 0.52, set the session.phase to "IDLE"
                spd_xy = math.hypot(session.ball_vd, session.ball_vwx)  # speed in felt plane (depth + lateral)
                if spd_xy < 3.05:
                    detail: Optional[str] = None # detail is the detail of the miss             
                    if session.ball_wd < RACK_FRONT_ROW_WD - 42.0:
                        detail = "short — stopped on the felt before the rack" # detail is the detail of the miss
                    elif session.ball_wd > CUP_PLANE_WD + 42.0:
                        detail = "long — rolled past the cups on the felt"
                    elif RACK_FRONT_ROW_WD - 28.0 < session.ball_wd < CUP_PLANE_WD + 32.0:
                        min_drack = min(
                            (
                                math.hypot(session.ball_wd - wdi, session.ball_wx - wxi) # min_drack is the minimum distance to the cups
                                for i, (wxi, wdi) in enumerate(opp_pts)
                                if i < len(opp) and opp[i]
                            ),
                            default=999.0, # default is the default value of the minimum distance to the cups
                        )
                        if min_drack > sink_r + 18.0:
                            detail = "wide — on the felt but outside the cups" # detail is the detail of the miss
                    if detail is not None:
                        game.finish_throw(None, miss_detail=detail) # game.finish_throw is the function to finish the throw
                        session.phase = "IDLE" # session.phase is the session.phase of the game
                        shot_done = True

            if not shot_done:
                miss_air: Optional[str] = None # miss_air is the detail of the miss
                if session.ball_wd > TABLE_DEPTH + 130.0:
                    miss_air = "long — off the end of the table" # miss_air is the detail of the miss
                elif session.ball_wd > CUP_PLANE_WD + 95.0:
                    miss_air = "long — past the cups" # miss_air is the detail of the miss
                elif session.ball_wd < -42.0:
                    miss_air = "behind you — not toward the rack" # miss_air is the detail of the miss
                elif abs(session.ball_wx) > 148.0:
                    miss_air = "wide — far off to the side" # miss_air is the detail of the miss
                elif session.ball_wh > 410.0:
                    miss_air = "too high" # miss_air is the detail of the miss
                elif session.ball_wh < -95.0:
                    miss_air = "dropped out of play" # miss_air is the detail of the miss
                elif session.flight_ticks > 640:
                    miss_air = "timed out" # miss_air is the detail of the miss

                if miss_air is not None:
                    game.finish_throw(None, miss_detail=miss_air) # game.finish_throw is the function to finish the throw
                    session.phase = "IDLE" # session.phase is the session.phase of the game

        draw_floor() # draw the floor
        draw_table() # draw the table
        draw_cups_side() # draw the cups side   

        ghost = pygame.Surface((28, 28), pygame.SRCALPHA) # ghost is the surface of the ghost
        pygame.draw.circle(ghost, (200, 200, 210, 100), (14, 14), 9)

        for pl in (1, 2):
            lx, ly = launcher_screen_for_player(pl) # lx is the x position of the launcher, ly is the y position of the launcher
            ix, iy = int(lx), int(ly)
            if game.winner is not None:
                pygame.draw.circle(screen, ball_outline, (ix, iy), 7) # draw the ball outline
                continue
            if pl == game.current_player:
                pygame.draw.circle(screen, ball_white, (ix, iy), 8) # draw the ball white
                pygame.draw.circle(screen, (0, 130, 78), (ix, iy), 11, 2) # draw the ball outline
            else:
                screen.blit(ghost, (ix - 14, iy - 14)) # draw the ghost

        if game.winner is None:
            aim = "Left table" if game.current_player == 1 else "Right table" # aim is the aim of the current player
            turn_txt = f"Player {game.current_player} — {aim}  ·  Throws {game.attempts_left}" # turn_txt is the text of the turn
            tx = size[0] // 2 - font_lg.size(turn_txt)[0] // 2
            ty = 14
            _blit_text_with_drop_shadow(screen, font_lg, turn_txt, turn_text, turn_shadow, (tx, ty))

        if game.winner is None and session.phase == "SLING":
            asx, asy = active_launcher_screen() # asx is the x position of the active launcher, asy is the y position of the active launcher
            mx, my = pygame.mouse.get_pos() # mx is the x position of the mouse, my is the y position of the mouse
            dx, dy = float(mx - asx), float(my - asy) # dx is the difference in the x position of the mouse and the x position of the active launcher, dy is the difference in the y position of the mouse and the y position of the active launcher
            plen = math.hypot(dx, dy) # plen is the length of the pull
            if plen > 0.5:
                cap_len = min(plen, MAX_SLING_PULL) # cap_len is the length of the pull
                bx = asx + dx / plen * cap_len # bx is the x position of the ball
                by = asy + dy / plen * cap_len # by is the y position of the ball
            else:
                bx, by = asx, asy # bx is the x position of the ball, by is the y position of the ball
            pygame.draw.line(screen, (235, 235, 242), (int(asx), int(asy)), (int(bx), int(by)), 3) # draw the line
            br = max(6, BALL_RADIUS - 1) # br is the radius of the ball
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), br) # draw the ball white
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), br, 2) # draw the ball outline

        if session.phase == "BALL":
            if session.shot_preview_trail:
                hit_col = (200, 255, 220) # hit_col is the color of the hit
                miss_col = (255, 210, 160) # miss_col is the color of the miss
                pcol = hit_col if session.shot_preview_outcome == "hit" else miss_col
                pts_scr: List[Tuple[int, int]] = [] # pts_scr is the list of points on the screen
                step = 1 # step is the step of the trail
                if len(session.shot_preview_trail) > 360:
                    step = 2 # step is the step of the trail
                for ti in range(0, len(session.shot_preview_trail), step):
                    twd, twx, twh = session.shot_preview_trail[ti]  # world sample (wd, wx, wh)
                    sx, sy = world_to_screen_lane(
                        twd, twx, twh, session.shot_preview_lane, size[0], size[1] # sx is the x position of the trail, sy is the y position of the trail
                    )
                    pts_scr.append((int(sx), int(sy)))
                if len(pts_scr) >= 2:
                    pygame.draw.lines(screen, pcol, False, pts_scr, 2) # draw the lines
            bl = shooter_lane(game.current_player) # bl is the lane of the shooter
            bx, by = world_to_screen_lane(session.ball_wd, session.ball_wx, session.ball_wh, bl, size[0], size[1]) # bx is the x position of the ball, by is the y position of the ball
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), BALL_RADIUS) # draw the ball white
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), BALL_RADIUS, 2) # draw the ball outline    
        elif session.phase == "SUNK":
            sd, sxw, swh = session.sunk_ball
            bx, by = world_to_screen_lane(sd, sxw, swh, session.sunk_lane, size[0], size[1]) # bx is the x position of the ball, by is the y position of the ball
            pygame.draw.circle(screen, ball_white, (int(bx), int(by)), BALL_RADIUS) # draw the ball white
            pygame.draw.circle(screen, ball_outline, (int(bx), int(by)), BALL_RADIUS, 2) # draw the ball outline    

        if game.winner is not None:
            draw_win_overlay() # draw the win overlay

        pygame.display.flip() # update the display
        clock.tick(60) # tick the clock

    _stop_cuppong_background_music() # stop the background music
    pygame.quit() # quit the game


if __name__ == "__main__": # if the name of the module is "__main__", run the game
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("terminal", "-t", "--terminal"):
        run_terminal_game() # run the terminal game
    else:
        run_pygame_gui() # run the pygame gui
