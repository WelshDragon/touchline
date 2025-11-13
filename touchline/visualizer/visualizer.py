# Copyright (C) 2025 Richard Owen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import threading
import time
from typing import Callable, Optional, Tuple

try:
    import pygame
except Exception:
    pygame = None

from touchline.engine.match_engine import RealTimeMatchEngine
from touchline.engine.physics import Vector2D


def _world_to_screen(
    pos: Vector2D, pitch_width: float, pitch_height: float, screen_size: Tuple[int, int]
) -> Tuple[int, int]:
    """Deprecated: kept for compatibility if imported elsewhere."""
    w, h = screen_size
    sx = int((pos.x + pitch_width / 2) / pitch_width * w)
    sy = int((pitch_height / 2 - pos.y) / pitch_height * h)
    return sx, sy


def start_visualizer(
    engine: RealTimeMatchEngine,
    screen_size: Tuple[int, int] = (1050, 680),
    fps: int = 30,
    # start_callback may return a Thread if it starts the engine so the
    # visualizer can keep a reference and join it on shutdown.
    start_callback: Optional[Callable[[], Optional[threading.Thread]]] = None,
) -> None:
    """Start a pygame visualizer for the match engine.

    This uses the standard `pygame` API and is compatible with running under
    pygame-web (the same code works in the browser build of pygame). If
    `pygame` is not installed the function will return immediately.
    """
    if pygame is None:
        # pygame not available; skip visualizer
        return

    pygame.init()
    screen = pygame.display.set_mode(screen_size, pygame.RESIZABLE)
    # pygame.display.toggle_fullscreen()
    pygame.display.set_caption("Football Simulator")
    clock = pygame.time.Clock()

    # Colors
    GREEN = (38, 160, 72)
    LINE = (245, 245, 245)
    HOME = (200, 30, 30)
    AWAY = (30, 90, 200)
    BALL = (245, 245, 245)
    GOAL_FRAME = (250, 250, 100)
    GOAL_NET = (230, 230, 230)
    TEXT = (20, 20, 20)

    font = pygame.font.SysFont(None, 18)

    pitch = engine.state.pitch
    running = True
    # Button definition (Start)
    button_w, button_h = 140, 36
    button_color = (70, 160, 70)
    button_hover = (90, 190, 90)
    button_text = font.render("Start Match", True, (255, 255, 255))
    stop_button_text = font.render("Stop Match", True, (255, 255, 255))
    stop_button_color = (180, 50, 50)
    stop_button_hover = (210, 70, 70)

    # If we start the engine from here we keep a reference to the thread so
    # we can join it on shutdown. If the caller provided a start_callback we
    # don't assume ownership of the thread.
    engine_thread = None

    # Run visualizer loop regardless of whether the match has started.
    while running:
        mouse_pos = pygame.mouse.get_pos()
        # Always recalculate button_rect to keep it in the top right
        button_rect = pygame.Rect(screen_size[0] - button_w - 10, 10, button_w, button_h)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                engine.stop_match()
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    engine.stop_match()
                    running = False
            elif event.type == pygame.VIDEORESIZE:
                screen_size = (event.w, event.h)
                screen = pygame.display.set_mode(screen_size, pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # If start button clicked and match not running -> trigger start
                if not engine.is_running and button_rect.collidepoint(event.pos):
                    if start_callback:
                        try:
                            started = start_callback()
                            if isinstance(started, threading.Thread):
                                engine_thread = started
                        except Exception:
                            pass
                    else:
                        engine_thread = threading.Thread(target=engine.start_match)
                        engine_thread.start()
                elif engine.is_running and button_rect.collidepoint(event.pos):
                    try:
                        engine.stop_match()
                    except Exception:
                        pass
                    shutdown_start = time.time()
                    shutdown_timeout = 3.0
                    while time.time() - shutdown_start < shutdown_timeout and (
                        engine.is_running or (engine_thread is not None and engine_thread.is_alive())
                    ):
                        overlay = pygame.Surface(screen_size, pygame.SRCALPHA)
                        overlay.fill((0, 0, 0, 120))
                        screen.blit(overlay, (0, 0))
                        msg = "Shutting down... Waiting for threads to finish"
                        sub = font.render(msg, True, (255, 255, 255))
                        bx = (screen_size[0] - sub.get_width()) // 2
                        by = (screen_size[1] - sub.get_height()) // 2
                        screen.blit(sub, (bx, by))
                        pygame.display.flip()
                        for e in pygame.event.get():
                            if e.type == pygame.QUIT:
                                pass
                        clock.tick(fps)
                    if engine_thread is not None and engine_thread.is_alive():
                        engine_thread.join(timeout=3.0)
                    running = False

        screen.fill((0, 0, 0))

        # Compute goal dimensions and margins so nets are visible outside the pitch
        goal_width_m = 7.32
        goal_depth_m = 2.44
        goal_w_px = int(goal_width_m / pitch.height * screen_size[1])
        goal_d_px = int(goal_depth_m / pitch.width * screen_size[0])

        margin_x = max(8, goal_d_px + 6)  # enough room for net plus a small gap
        margin_y = 0
        pitch_rect = pygame.Rect(
            margin_x,
            margin_y,
            screen_size[0] - 2 * margin_x,
            screen_size[1] - 2 * margin_y,
        )

        # Local mapper using the inner pitch rect, so pitch fits inside margins
        # Bind pitch rect components locally to avoid capturing variables in nested scope
        _pr_left, _pr_top = pitch_rect.left, pitch_rect.top
        _pr_w, _pr_h = pitch_rect.width, pitch_rect.height

        def w2s(
            pos: Vector2D,
            left: int = _pr_left,
            top: int = _pr_top,
            pw: int = _pr_w,
            ph: int = _pr_h,
        ) -> Tuple[int, int]:
            """World -> screen mapper bound to current pitch_rect dimensions."""
            sx = int((pos.x + pitch.width / 2) / pitch.width * pw) + left
            sy = int((pitch.height / 2 - pos.y) / pitch.height * ph) + top
            return sx, sy

        # Draw pitch background (inside margins)
        pygame.draw.rect(screen, GREEN, pitch_rect)

        # Pitch border lines
        pygame.draw.rect(screen, LINE, pitch_rect, 4)

        # Center line
        pygame.draw.line(
            screen,
            LINE,
            (pitch_rect.centerx, pitch_rect.top),
            (pitch_rect.centerx, pitch_rect.bottom),
            2,
        )

        # Center circle
        center_px = (pitch_rect.centerx, pitch_rect.centery)
        center_radius = int((9.15 / pitch.width) * pitch_rect.width)  # 9.15m radius
        pygame.draw.circle(screen, LINE, center_px, center_radius, 2)

        # Draw goals (simple rectangle + inner net depth) at pitch edges
        # Vertical start so goal centered on halfway line vertically within pitch_rect
        goal_y = pitch_rect.centery - goal_w_px // 2
        # Left goal (extends leftwards outside pitch border visually by drawing inside with depth)
        # We'll draw the frame on the pitch edge, and a lighter net rectangle behind it.
        left_goal_x = pitch_rect.left
        # Net (slightly translucent look using surface)
        net_surface = pygame.Surface((goal_d_px, goal_w_px), pygame.SRCALPHA)
        net_surface.fill((*GOAL_NET, 60))
        screen.blit(net_surface, (left_goal_x - goal_d_px, goal_y))
        # Frame (front) - rectangle at pitch edge
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (left_goal_x - 2, goal_y, 4, goal_w_px),
        )  # left post thickness
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (left_goal_x - goal_d_px, goal_y - 2, goal_d_px + 2, 4),
        )  # top bar
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (left_goal_x - goal_d_px, goal_y + goal_w_px - 2, goal_d_px + 2, 4),
        )  # bottom bar

        # Right goal
        right_goal_front = pitch_rect.right
        # Net
        net_surface_r = pygame.Surface((goal_d_px, goal_w_px), pygame.SRCALPHA)
        net_surface_r.fill((*GOAL_NET, 60))
        screen.blit(net_surface_r, (right_goal_front, goal_y))
        # Frame (mirror of left)
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (right_goal_front - 2, goal_y, 4, goal_w_px),
        )  # right post
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (right_goal_front, goal_y - 2, goal_d_px + 2, 4),
        )  # top bar
        pygame.draw.rect(
            screen,
            GOAL_FRAME,
            (right_goal_front, goal_y + goal_w_px - 2, goal_d_px + 2, 4),
        )  # bottom bar

        # Draw penalty areas (simplified) inside pitch bounds
        left_pen_w = int((pitch.penalty_area_depth / pitch.width) * pitch_rect.width)
        left_pen_h = int((pitch.penalty_area_width / pitch.height) * pitch_rect.height)
        left_pen_x = pitch_rect.left
        left_pen_y = pitch_rect.centery - left_pen_h // 2
        pygame.draw.rect(screen, LINE, (left_pen_x, left_pen_y, left_pen_w, left_pen_h), 2)
        # Right penalty box
        right_pen_x = pitch_rect.right - left_pen_w
        pygame.draw.rect(screen, LINE, (right_pen_x, left_pen_y, left_pen_w, left_pen_h), 2)

        # Draw players
        home_count = away_count = 0
        for p in engine.state.player_states.values():
            pos = p.state.position
            sx, sy = w2s(pos)
            is_home = p.team == engine.state.home_team
            color = HOME if is_home else AWAY
            if is_home:
                home_count += 1
            else:
                away_count += 1
            radius = 10
            # If player has ball, draw an outline
            if p.state.is_with_ball:
                pygame.draw.circle(screen, (255, 215, 0), (sx, sy), radius + 4)  # gold outline
            pygame.draw.circle(screen, color, (sx, sy), radius)
            # Draw player id
            txt = font.render(str(p.player_id), True, TEXT)
            screen.blit(txt, (sx - txt.get_width() // 2, sy - txt.get_height() // 2))

        # Draw ball
        ball_pos = engine.state.ball.position
        bx, by = w2s(ball_pos)
        pygame.draw.circle(screen, BALL, (bx, by), 6)

        # HUD: time and score
        match_min = int(engine.state.match_time // 60)
        score_text = (
            f"{engine.state.home_team.name} {engine.state.home_score} - "
            f"{engine.state.away_score} {engine.state.away_team.name}"
        )
        time_text = f"Time: {match_min:02d}:{int(engine.state.match_time % 60):02d}"
        screen.blit(font.render(score_text, True, TEXT), (10, 10))
        screen.blit(font.render(time_text, True, TEXT), (10, 30))

        # Draw Start or Stop button
        hover = button_rect.collidepoint(mouse_pos)
        if not engine.is_running:
            pygame.draw.rect(screen, button_hover if hover else button_color, button_rect, border_radius=6)
            bt_x = button_rect.x + (button_rect.w - button_text.get_width()) // 2
            bt_y = button_rect.y + (button_rect.h - button_text.get_height()) // 2
            screen.blit(button_text, (bt_x, bt_y))
        else:
            pygame.draw.rect(screen, stop_button_hover if hover else stop_button_color, button_rect, border_radius=6)
            sb_x = button_rect.x + (button_rect.w - stop_button_text.get_width()) // 2
            sb_y = button_rect.y + (button_rect.h - stop_button_text.get_height()) // 2
            screen.blit(stop_button_text, (sb_x, sb_y))

        # debug_lines = []
        # if hasattr(engine, "debugger") and engine.debugger is not None:
        #     try:
        #         debug_lines = engine.debugger.get_recent_events(limit=12)
        #     except Exception:
        #         debug_lines = []

        # if debug_lines:
        #     line_height = log_font.get_linesize()
        #     panel_height = line_height * len(debug_lines) + 12
        #     log_surface = pygame.Surface((screen_size[0], panel_height), pygame.SRCALPHA)
        #     log_surface.fill((0, 0, 0, 140))
        #     screen.blit(log_surface, (0, screen_size[1] - panel_height))

        #     base_y = screen_size[1] - panel_height + 6
        #     for idx, entry in enumerate(debug_lines):
        #         text_surf = log_font.render(entry, True, (235, 235, 235))
        #         screen.blit(text_surf, (12, base_y + idx * line_height))

        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()
