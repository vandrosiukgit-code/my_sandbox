"""Shared normalization helpers for visual activities."""


def normalize_int_pair(value, error_type=TypeError):
    if isinstance(value, dict):
        value = (value.get("x", 0), value.get("y", 0))
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        raise error_type(f"Expected coordinate pair: {value!r}")
    return int(round(float(value[0]))), int(round(float(value[1])))


def normalize_float_pair(value):
    if isinstance(value, dict):
        return float(value.get("x", 0)), float(value.get("y", 0))
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return 0.0, 0.0


def normalize_optional_pair(value, pair_normalizer=normalize_int_pair):
    if value is None:
        return None
    return pair_normalizer(value)


def normalize_offsets(offsets, pair_normalizer=normalize_int_pair):
    if offsets is None:
        return None
    if not isinstance(offsets, (tuple, list)):
        raise ValueError(f"slot_offsets must be a list or tuple of pairs: {offsets!r}")
    return tuple(pair_normalizer(offset) for offset in offsets)


def normalize_scale_factor(value):
    if value is None:
        return None
    scale = float(value)
    if scale <= 0:
        raise ValueError(f"scale_factor must be positive: {value!r}")
    return scale


def normalize_cards(cards):
    if cards is None:
        return tuple()
    if isinstance(cards, str):
        return (cards,)
    return tuple(str(card) for card in cards)


def normalize_visible_cards(cards):
    normalized = []
    for card in cards or ():
        if isinstance(card, str):
            normalized.append(card)
        elif isinstance(card, dict):
            resource_key = card.get("resource_key") or card.get("key")
            if not resource_key:
                raise TypeError(f"Card descriptor requires resource_key or key: {card!r}")
            normalized.append(str(resource_key))
        else:
            raise TypeError(f"Unsupported card descriptor: {card!r}")
    return tuple(normalized)


def limit_cards(cards, max_cards):
    if max_cards is None:
        return tuple(cards)
    return tuple(cards[:max_cards])


def normalize_max_cards(max_cards):
    if max_cards is None:
        return None
    return max(0, int(max_cards))


def normalize_strict_max_cards(max_cards):
    if max_cards is None:
        return None
    value = int(max_cards)
    if value < 0:
        raise ValueError(f"max_cards must be non-negative: {max_cards!r}")
    return value


def get_fixture_cards(fixture):
    for key in ("cards", "card_resource_keys", "resource_keys"):
        if key in fixture:
            return fixture[key]
    return None
