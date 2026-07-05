from dataclasses import replace

import pygame

from core.settings_repository import AppConfig
from game_screen.game_screen import GameScreen


class StartMenuScreen(GameScreen):
    SCREEN_SIZE = (912, 513)
    BG_COLOR = (38, 29, 20)
    PANEL_COLOR = (225, 211, 182)
    PANEL_BORDER_COLOR = (92, 67, 46)
    TEXT_COLOR = (37, 26, 18)
    MUTED_TEXT_COLOR = (86, 71, 58)
    ACCENT_COLOR = (139, 89, 48)
    ACCENT_HOVER_COLOR = (162, 106, 58)
    TOGGLE_ON_COLOR = (96, 138, 83)
    TOGGLE_OFF_COLOR = (138, 84, 75)
    SLIDER_TRACK_COLOR = (176, 153, 124)
    SLIDER_FILL_COLOR = (121, 84, 55)
    DECK_SKINS = ("classic", "red", "blue")

    def __init__(self, settings_repository, on_play=None, on_back=None):
        super().__init__(background_color=self.BG_COLOR)
        self.settings_repository = settings_repository
        self.on_play = on_play
        self.on_back = on_back
        self.config = settings_repository.load()
        self.saved_config = self.config
        self.hovered_control_id = None
        self.active_slider_id = None
        self.font_title = None
        self.font_section = None
        self.font_text = None
        self.font_small = None
        self.control_rects = {}
        self.status_text = "настройки не изменены"

    def start(self):
        super().start()
        self._build_fonts()

    def finish(self):
        super().finish()
        self.active_slider_id = None

    def update(self, dt):
        super().update(dt)
        self._update_status()

    def draw(self, screen):
        self._build_fonts()
        screen.fill(self.BG_COLOR)
        self.control_rects = {}

        main_rect = pygame.Rect(24, 22, 864, 469)
        header_rect = pygame.Rect(main_rect.x, main_rect.y, main_rect.width, 42)
        action_rect = pygame.Rect(main_rect.x + 212, main_rect.bottom - 72, 440, 44)
        status_rect = pygame.Rect(main_rect.x, main_rect.bottom - 26, main_rect.width, 20)
        content_rect = pygame.Rect(main_rect.x + 20, header_rect.bottom + 14, main_rect.width - 40, 314)
        left_column_x = content_rect.x
        right_column_x = content_rect.x + 420

        pygame.draw.rect(screen, self.PANEL_COLOR, main_rect, border_radius=8)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, main_rect, width=2, border_radius=8)
        screen.blit(self.font_title.render("START MENU", True, self.TEXT_COLOR), (main_rect.x + 332, main_rect.y + 8))

        self._draw_button(screen, "back_button", pygame.Rect(header_rect.x + 8, header_rect.y + 6, 94, 30), "Назад")
        self._draw_button(screen, "close_button", pygame.Rect(header_rect.right - 154, header_rect.y + 6, 146, 30), "Закрыть игру")

        self._draw_section_title(screen, "Игра", left_column_x, content_rect.y)
        self._draw_stepper_row(
            screen,
            label="Число игроков:",
            value=str(self.config.player_count),
            dec_id="player_count_decrement",
            value_id="player_count_value",
            inc_id="player_count_increment",
            row_y=content_rect.y + 38,
            label_x=left_column_x,
            control_x=left_column_x + 188,
        )
        self._draw_select_row(
            screen,
            label="Портрет игрока:",
            value=f"Portrait {self.config.player_portrait_id}",
            control_id="player_portrait_id",
            row_y=content_rect.y + 78,
            label_x=left_column_x,
            control_x=left_column_x + 188,
            width=182,
        )

        bots_y = content_rect.y + 126
        self._draw_section_title(screen, "Боты", left_column_x, bots_y)
        self._draw_select_row(
            screen,
            label="Сложность:",
            value=self.config.bot_difficulty.title(),
            control_id="bot_difficulty",
            row_y=bots_y + 38,
            label_x=left_column_x,
            control_x=left_column_x + 188,
            width=182,
        )
        self._draw_slider_row(
            screen,
            label="Скорость хода:",
            control_id="bot_turn_speed",
            row_y=bots_y + 78,
            normalized=self._delay_to_normalized(self.config.bot_turn_delay_ms),
            label_x=left_column_x,
            control_x=left_column_x + 188,
            width=210,
        )

        self._draw_section_title(screen, "Колода", right_column_x, content_rect.y)
        self._draw_select_row(
            screen,
            label="Рубашка:",
            value=self.config.deck_skin.title(),
            control_id="deck_skin",
            row_y=content_rect.y + 38,
            label_x=right_column_x,
            control_x=right_column_x + 170,
            width=140,
        )
        self._draw_toggle_row(
            screen,
            label="Анимация:",
            control_id="deck_animation_enabled",
            row_y=content_rect.y + 78,
            enabled=self.config.deck_animation_enabled,
            label_x=right_column_x,
            control_x=right_column_x + 170,
        )

        audio_y = content_rect.y + 126
        self._draw_section_title(screen, "Аудио", right_column_x, audio_y)
        self._draw_toggle_row(
            screen,
            label="Музыка:",
            control_id="music_enabled",
            row_y=audio_y + 38,
            enabled=self.config.music_enabled,
            label_x=right_column_x,
            control_x=right_column_x + 170,
        )
        self._draw_toggle_row(
            screen,
            label="Звуки:",
            control_id="sfx_enabled",
            row_y=audio_y + 76,
            enabled=self.config.sfx_enabled,
            label_x=right_column_x,
            control_x=right_column_x + 170,
        )
        self._draw_slider_row(
            screen,
            label="Громкость музыки:",
            control_id="music_volume",
            row_y=audio_y + 114,
            normalized=self.config.music_volume,
            label_x=right_column_x,
            control_x=right_column_x + 170,
            width=180,
        )
        self._draw_slider_row(
            screen,
            label="Громкость звуков:",
            control_id="sfx_volume",
            row_y=audio_y + 154,
            normalized=self.config.sfx_volume,
            label_x=right_column_x,
            control_x=right_column_x + 170,
            width=180,
        )

        self._draw_button(screen, "reset_button", pygame.Rect(action_rect.x, action_rect.y, 150, 34), "Сбросить")
        self._draw_button(screen, "play_button", pygame.Rect(action_rect.right - 50, action_rect.y, 150, 34), "Играть", primary=True)

        status_label = f"Status: {self.status_text}"
        screen.blit(self.font_small.render(status_label, True, self.MUTED_TEXT_COLOR), (status_rect.x + 4, status_rect.y))
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, screen.get_rect(), width=1)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered_control_id = self._get_control_id_at(event.pos)
            if self.active_slider_id is not None:
                self._update_slider_from_x(self.active_slider_id, event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.active_slider_id = None
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return True
        control_id = self._get_control_id_at(event.pos)
        if control_id is None:
            return True
        self.hovered_control_id = control_id
        if control_id in {"bot_turn_speed", "music_volume", "sfx_volume"}:
            self.active_slider_id = control_id
            self._update_slider_from_x(control_id, event.pos[0])
            return True
        return self._activate_control(control_id)

    def _activate_control(self, control_id):
        if control_id == "back_button":
            if callable(self.on_back):
                return self.on_back()
            return False
        if control_id == "close_button":
            return False
        if control_id == "player_count_decrement":
            self.config = replace(self.config, player_count=max(2, self.config.player_count - 1))
            return True
        if control_id == "player_count_increment":
            self.config = replace(self.config, player_count=min(4, self.config.player_count + 1))
            return True
        if control_id == "player_portrait_id":
            next_id = 1 if self.config.player_portrait_id >= 4 else self.config.player_portrait_id + 1
            self.config = replace(self.config, player_portrait_id=next_id)
            return True
        if control_id == "bot_difficulty":
            order = ("easy", "normal", "hard")
            index = (order.index(self.config.bot_difficulty) + 1) % len(order)
            self.config = replace(self.config, bot_difficulty=order[index])
            return True
        if control_id == "deck_skin":
            index = (self.DECK_SKINS.index(self.config.deck_skin) + 1) % len(self.DECK_SKINS)
            self.config = replace(self.config, deck_skin=self.DECK_SKINS[index])
            return True
        if control_id == "deck_animation_enabled":
            self.config = replace(self.config, deck_animation_enabled=not self.config.deck_animation_enabled)
            return True
        if control_id == "music_enabled":
            self.config = replace(self.config, music_enabled=not self.config.music_enabled)
            return True
        if control_id == "sfx_enabled":
            self.config = replace(self.config, sfx_enabled=not self.config.sfx_enabled)
            return True
        if control_id == "reset_button":
            self.config = AppConfig()
            self.settings_repository.save(self.config)
            self.saved_config = self.config
            return True
        if control_id == "play_button":
            self.settings_repository.save(self.config)
            self.saved_config = self.config
            if callable(self.on_play):
                return self.on_play(self.config)
        return True

    def _draw_section_title(self, screen, title, x, y):
        screen.blit(self.font_section.render(title, True, self.TEXT_COLOR), (x, y))
        pygame.draw.line(screen, self.PANEL_BORDER_COLOR, (x, y + 26), (x + 340, y + 26), width=1)

    def _draw_stepper_row(self, screen, label, value, dec_id, value_id, inc_id, row_y, label_x=80, control_x=318):
        screen.blit(self.font_text.render(label, True, self.TEXT_COLOR), (label_x, row_y + 4))
        self._draw_button(screen, dec_id, pygame.Rect(control_x, row_y, 34, 28), "-")
        value_rect = pygame.Rect(control_x + 44, row_y, 64, 28)
        self.control_rects[value_id] = value_rect
        pygame.draw.rect(screen, (246, 240, 225), value_rect, border_radius=4)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, value_rect, width=1, border_radius=4)
        self._blit_center(screen, self.font_text.render(value, True, self.TEXT_COLOR), value_rect)
        self._draw_button(screen, inc_id, pygame.Rect(control_x + 118, row_y, 34, 28), "+")

    def _draw_select_row(self, screen, label, value, control_id, row_y, label_x=80, control_x=318, width=152):
        screen.blit(self.font_text.render(label, True, self.TEXT_COLOR), (label_x, row_y + 4))
        rect = pygame.Rect(control_x, row_y, width, 28)
        self.control_rects[control_id] = rect
        fill = (252, 248, 236) if self.hovered_control_id == control_id else (246, 240, 225)
        pygame.draw.rect(screen, fill, rect, border_radius=4)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, rect, width=1, border_radius=4)
        screen.blit(self.font_text.render(f"{value} v", True, self.TEXT_COLOR), (rect.x + 10, rect.y + 4))

    def _draw_toggle_row(self, screen, label, control_id, row_y, enabled, label_x=80, control_x=318):
        screen.blit(self.font_text.render(label, True, self.TEXT_COLOR), (label_x, row_y + 4))
        rect = pygame.Rect(control_x, row_y, 28, 28)
        self.control_rects[control_id] = rect
        color = self.TOGGLE_ON_COLOR if enabled else self.TOGGLE_OFF_COLOR
        if self.hovered_control_id == control_id:
            color = tuple(min(255, channel + 10) for channel in color)
        pygame.draw.rect(screen, color, rect, border_radius=4)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, rect, width=1, border_radius=4)
        self._blit_center(screen, self.font_text.render("x" if enabled else "", True, (245, 241, 232)), rect)

    def _draw_slider_row(self, screen, label, control_id, row_y, normalized, label_x=80, control_x=318, width=210):
        screen.blit(self.font_text.render(label, True, self.TEXT_COLOR), (label_x, row_y + 4))
        track_rect = pygame.Rect(control_x, row_y + 11, width, 8)
        self.control_rects[control_id] = track_rect.inflate(8, 18)
        pygame.draw.rect(screen, self.SLIDER_TRACK_COLOR, track_rect, border_radius=4)
        fill_width = max(0, min(track_rect.width, int(round(track_rect.width * normalized))))
        if fill_width > 0:
            pygame.draw.rect(
                screen,
                self.SLIDER_FILL_COLOR,
                pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height),
                border_radius=4,
            )
        knob_center_x = track_rect.x + fill_width
        knob_color = self.ACCENT_HOVER_COLOR if self.hovered_control_id == control_id or self.active_slider_id == control_id else self.ACCENT_COLOR
        pygame.draw.circle(screen, knob_color, (knob_center_x, track_rect.centery), 8)
        pygame.draw.circle(screen, self.PANEL_BORDER_COLOR, (knob_center_x, track_rect.centery), 8, width=1)

    def _draw_button(self, screen, control_id, rect, label, primary=False):
        self.control_rects[control_id] = rect
        hovered = self.hovered_control_id == control_id
        fill = self.ACCENT_COLOR if primary else (239, 229, 207)
        if hovered:
            fill = self.ACCENT_HOVER_COLOR if primary else (247, 241, 229)
        text_color = (245, 241, 232) if primary else self.TEXT_COLOR
        pygame.draw.rect(screen, fill, rect, border_radius=4)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, rect, width=1, border_radius=4)
        self._blit_center(screen, self.font_text.render(label, True, text_color), rect)

    def _blit_center(self, screen, surface, rect):
        screen.blit(surface, surface.get_rect(center=rect.center))

    def _get_control_id_at(self, pos):
        for control_id, rect in reversed(tuple(self.control_rects.items())):
            if rect.collidepoint(pos):
                return control_id
        return None

    def _update_slider_from_x(self, control_id, pointer_x):
        rect = self.control_rects.get(control_id)
        if rect is None:
            return
        track_rect = pygame.Rect(rect.x + 4, rect.y + 5, rect.width - 8, 8)
        normalized = 0.0 if track_rect.width <= 0 else (pointer_x - track_rect.x) / track_rect.width
        normalized = max(0.0, min(1.0, normalized))
        if control_id == "bot_turn_speed":
            self.config = replace(self.config, bot_turn_delay_ms=self._normalized_to_delay(normalized))
        elif control_id == "music_volume":
            self.config = replace(self.config, music_volume=normalized)
        elif control_id == "sfx_volume":
            self.config = replace(self.config, sfx_volume=normalized)

    def _update_status(self):
        self.status_text = "настройки не изменены" if self.config == self.saved_config else "есть несохраненные изменения"

    def _build_fonts(self):
        if self.font_title is not None:
            return
        self.font_title = pygame.font.SysFont("arial", 26, bold=True)
        self.font_section = pygame.font.SysFont("arial", 22, bold=True)
        self.font_text = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 14)

    @staticmethod
    def _delay_to_normalized(delay_ms):
        return (max(100, min(3000, delay_ms)) - 100) / 2900.0

    @staticmethod
    def _normalized_to_delay(normalized):
        return int(round(100 + normalized * 2900))
