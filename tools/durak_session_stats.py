"""Compute isolated Durak session statistics across many autonomous games."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from core.durak import Card, DurakGameController, Rank, RuleBasedBotPlayer, Suit
from core.durak.state import GamePhase


def standard_36_deck():
    return [
        Card(f"cards.{rank.value}_of_{suit.value}", rank, suit)
        for rank in Rank
        for suit in Suit
    ]


def shuffled_standard_36_deck(seed):
    cards = standard_36_deck()
    random.Random(seed).shuffle(cards)
    return cards


def build_controller(seed):
    participants = [
        RuleBasedBotPlayer("p1", "Bot 1", 0),
        RuleBasedBotPlayer("p2", "Bot 2", 1),
        RuleBasedBotPlayer("p3", "Bot 3", 2),
        RuleBasedBotPlayer("p4", "Bot 4", 3),
    ]
    return DurakGameController(participants, shuffled_standard_36_deck(seed))


def collect_stats(games):
    stats = {
        "games": int(games),
        "max_table_cards": 0,
        "max_table_pairs": 0,
        "max_hand_size": 0,
        "table_cards_seed": None,
        "table_pairs_seed": None,
        "hand_size_seed": None,
    }
    for seed in range(int(games)):
        controller = build_controller(seed)
        while controller.state.phase != GamePhase.FINISHED:
            controller.play_automatic_step()
            table_pairs = len(controller.state.table.pairs)
            table_cards = len(controller.state.table.all_card_ids())
            hand_size = max(
                participant.hand_size()
                for participant in controller.state.participants.values()
            )
            if table_cards > stats["max_table_cards"]:
                stats["max_table_cards"] = table_cards
                stats["table_cards_seed"] = seed
            if table_pairs > stats["max_table_pairs"]:
                stats["max_table_pairs"] = table_pairs
                stats["table_pairs_seed"] = seed
            if hand_size > stats["max_hand_size"]:
                stats["max_hand_size"] = hand_size
                stats["hand_size_seed"] = seed
    return stats


def build_parser():
    parser = argparse.ArgumentParser(
        prog="durak_session_stats.py",
        description="Collect isolated Durak statistics across many autonomous games.",
    )
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    stats = collect_stats(args.games)
    if args.json:
        print(json.dumps(stats, ensure_ascii=True, indent=2))
        return 0
    print(f"Games: {stats['games']}")
    print(f"Max table cards: {stats['max_table_cards']} (seed={stats['table_cards_seed']})")
    print(f"Max table pairs: {stats['max_table_pairs']} (seed={stats['table_pairs_seed']})")
    print(f"Max hand size: {stats['max_hand_size']} (seed={stats['hand_size_seed']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
