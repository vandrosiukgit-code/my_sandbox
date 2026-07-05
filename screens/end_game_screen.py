import pygame

from game_screen.game_screen import GameScreen


class EndGameScreen(GameScreen):
    SCREEN_SIZE = (912, 513)
    BG_COLOR = (38, 29, 20)
    PANEL_COLOR = (225, 211, 182)
    PANEL_BORDER_COLOR = (92, 67, 46)
    TEXT_COLOR = (37, 26, 18)
    MUTED_TEXT_COLOR = (86, 71, 58)
    ACCENT_COLOR = (139, 89, 48)
    ACCENT_HOVER_COLOR = (162, 106, 58)

    def __init__(
        self,
        game_controller=None,
        moves_count=0,
        winner=None,
        loser=None,
        stats=None,
        on_new_game=None,
        on_exit=None,
    ):
        super().__init__(background_color=self.BG_COLOR)
        self.game_controller = game_controller
        stats = self._resolve_stats(stats)
        self.moves_count = self._get_first_stat(stats, ("moves_count", "moves", "turn_count", "turns"), moves_count)
        self.winner = self._get_first_stat(stats, ("winner", "winner_name"), winner) or "Unknown"
        self.loser = self._get_first_stat(stats, ("loser", "loser_name"), loser) or "Unknown"
        self.on_new_game = on_new_game
        self.on_exit = on_exit
        self.hovered_control_id = None
        self.font_title = None
        self.font_section = None
        self.font_text = None
        self.font_small = None
        self.control_rects = {}

    def start(self):
        super().start()
        self._build_fonts()

    def finish(self):
        super().finish()
        self.hovered_control_id = None

    def update(self, dt):
        super().update(dt)

    def draw(self, screen):
        self._build_fonts()
        screen.fill(self.BG_COLOR)
        self.control_rects = {}

        main_rect = pygame.Rect(24, 22, 864, 469)
        header_rect = pygame.Rect(main_rect.x, main_rect.y, main_rect.width, 54)
        content_rect = pygame.Rect(main_rect.x + 80, header_rect.bottom + 46, main_rect.width - 160, 230)
        action_rect = pygame.Rect(main_rect.x + 212, main_rect.bottom - 86, 440, 44)

        pygame.draw.rect(screen, self.PANEL_COLOR, main_rect, border_radius=8)
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, main_rect, width=2, border_radius=8)
        self._blit_center(screen, self.font_title.render("GAME OVER", True, self.TEXT_COLOR), header_rect)

        self._draw_section_title(screen, "Statistics", content_rect.x, content_rect.y)
        row_y = content_rect.y + 54
        self._draw_stat_row(screen, "Moves:", str(self.moves_count), content_rect.x + 24, row_y)
        self._draw_stat_row(screen, "Winner:", str(self.winner), content_rect.x + 24, row_y + 52)
        self._draw_stat_row(screen, "Loser:", str(self.loser), content_rect.x + 24, row_y + 104)

        self._draw_button(screen, "new_game_button", pygame.Rect(action_rect.x, action_rect.y, 190, 38), "New Game", primary=True)
        self._draw_button(screen, "exit_button", pygame.Rect(action_rect.right - 190, action_rect.y, 190, 38), "Exit")

        screen.blit(
            self.font_small.render("Match finished", True, self.MUTED_TEXT_COLOR),
            (main_rect.x + 24, main_rect.bottom - 28),
        )
        pygame.draw.rect(screen, self.PANEL_BORDER_COLOR, screen.get_rect(), width=1)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered_control_id = self._get_control_id_at(event.pos)
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return True
        control_id = self._get_control_id_at(event.pos)
        if control_id is None:
            return True
        self.hovered_control_id = control_id
        return self._activate_control(control_id)

    def _activate_control(self, control_id):
        if control_id == "new_game_button":
            if callable(self.on_new_game):
                return self.on_new_game()
            return True
        if control_id == "exit_button":
            if callable(self.on_exit):
                return self.on_exit()
            return False
        return True

    def _draw_section_title(self, screen, title, x, y):
        screen.blit(self.font_section.render(title, True, self.TEXT_COLOR), (x, y))
        pygame.draw.line(screen, self.PANEL_BORDER_COLOR, (x, y + 30), (x + 700, y + 30), width=1)

    def _draw_stat_row(self, screen, label, value, x, y):
        label_surface = self.font_text.render(label, True, self.MUTED_TEXT_COLOR)
        value_surface = self.font_section.render(value, True, self.TEXT_COLOR)
        screen.blit(label_surface, (x, y + 5))
        screen.blit(value_surface, (x + 190, y))

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

    def _build_fonts(self):
        if self.font_title is not None:
            return
        self.font_title = pygame.font.SysFont("arial", 30, bold=True)
        self.font_section = pygame.font.SysFont("arial", 24, bold=True)
        self.font_text = pygame.font.SysFont("arial", 18)
        self.font_small = pygame.font.SysFont("arial", 14)

    def _resolve_stats(self, stats):
        if stats is not None:
            return stats
        if self.game_controller is None:
            return None
        stats_getter = getattr(self.game_controller, "get_end_game_stats", None)
        if callable(stats_getter):
            return stats_getter()
        return None

    @staticmethod
    def _get_first_stat(stats, keys, default):
        if stats is None:
            return default
        for key in keys:
            if isinstance(stats, dict) and key in stats:
                return stats[key]
            if hasattr(stats, key):
                return getattr(stats, key)
        return default
