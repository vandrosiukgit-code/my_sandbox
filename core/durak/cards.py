"""Card primitives for the Durak domain model."""

from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    CLUBS = "clubs"
    DIAMONDS = "diamonds"
    HEARTS = "hearts"
    SPADES = "spades"


class Rank(str, Enum):
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "j"
    QUEEN = "q"
    KING = "k"
    ACE = "a"


RANK_ORDER = {
    Rank.SIX: 0,
    Rank.SEVEN: 1,
    Rank.EIGHT: 2,
    Rank.NINE: 3,
    Rank.TEN: 4,
    Rank.JACK: 5,
    Rank.QUEEN: 6,
    Rank.KING: 7,
    Rank.ACE: 8,
}


@dataclass(frozen=True)
class Card:
    """A logical game card.

    ``card_id`` is the stable bridge to the visual layer, but this class has no
    dependency on visual objects.
    """

    card_id: str
    rank: Rank
    suit: Suit
