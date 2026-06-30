"""Isolated domain model for Durak rules.

This package is intentionally independent from pygame, Group, Frame, Activity,
and the current fixture-oriented ``core.game_controller`` module.
"""

from core.durak.actions import AttackAction, DefendAction, TakeCardsAction, ThrowInAction
from core.durak.cards import Card, Rank, Suit
from core.durak.contracts import DomainResult, GameSnapshot, PlayerSnapshot, TablePairSnapshot
from core.durak.controller import DurakGameController
from core.durak.participants import BaseBotPlayer, BaseHumanPlayer, BaseParticipant, RuleBasedBotPlayer
from core.durak.state import BattlePair, BattleTable, DurakGameState, GamePhase

__all__ = [
    "AttackAction",
    "BaseBotPlayer",
    "BaseHumanPlayer",
    "BaseParticipant",
    "BattlePair",
    "BattleTable",
    "Card",
    "DefendAction",
    "DomainResult",
    "DurakGameController",
    "DurakGameState",
    "GamePhase",
    "GameSnapshot",
    "PlayerSnapshot",
    "Rank",
    "RuleBasedBotPlayer",
    "Suit",
    "TablePairSnapshot",
    "TakeCardsAction",
    "ThrowInAction",
]
