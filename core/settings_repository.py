import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


BotDifficulty = Literal["easy", "normal", "hard"]


@dataclass(frozen=True)
class AppConfig:
    player_count: int = 4
    bot_difficulty: BotDifficulty = "normal"
    player_portrait_id: int = 1
    deck_skin: str = "classic"
    deck_animation_enabled: bool = True
    bot_turn_delay_ms: int = 700
    music_enabled: bool = True
    sfx_enabled: bool = True
    music_volume: float = 0.7
    sfx_volume: float = 0.8


class SettingsRepository:
    def __init__(self, config_path):
        self.config_path = Path(config_path)

    def load(self) -> AppConfig:
        if not self.config_path.exists():
            return AppConfig()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppConfig()
        return self._normalize(payload)

    def save(self, config: AppConfig) -> None:
        normalized = self._normalize(asdict(config))
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(asdict(normalized), indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _normalize(payload) -> AppConfig:
        data = dict(payload or {})
        player_count = max(2, min(4, int(data.get("player_count", 4))))
        difficulty = str(data.get("bot_difficulty", "normal")).lower()
        if difficulty not in ("easy", "normal", "hard"):
            difficulty = "normal"
        player_portrait_id = max(1, min(4, int(data.get("player_portrait_id", 1))))
        deck_skin = str(data.get("deck_skin", "classic")).lower()
        if deck_skin not in ("classic", "red", "blue"):
            deck_skin = "classic"
        deck_animation_enabled = bool(data.get("deck_animation_enabled", True))
        bot_turn_delay_ms = max(100, min(3000, int(data.get("bot_turn_delay_ms", 700))))
        music_enabled = bool(data.get("music_enabled", True))
        sfx_enabled = bool(data.get("sfx_enabled", True))
        music_volume = SettingsRepository._clamp01(data.get("music_volume", 0.7))
        sfx_volume = SettingsRepository._clamp01(data.get("sfx_volume", 0.8))
        return AppConfig(
            player_count=player_count,
            bot_difficulty=difficulty,
            player_portrait_id=player_portrait_id,
            deck_skin=deck_skin,
            deck_animation_enabled=deck_animation_enabled,
            bot_turn_delay_ms=bot_turn_delay_ms,
            music_enabled=music_enabled,
            sfx_enabled=sfx_enabled,
            music_volume=music_volume,
            sfx_volume=sfx_volume,
        )

    @staticmethod
    def _clamp01(value) -> float:
        return max(0.0, min(1.0, float(value)))
