# Durak Rules And Opening Attack

## Purpose

This note documents the gameplay rules that matter for the domain
implementation in `core/durak/*`, with special focus on opening attacker
selection and the `take` action.

It also records the result of a code check against the current implementation.

## Baseline rules

These are the rules the current domain is expected to follow.

### Opening attacker

- At the start of a deal, each player receives `6` cards.
- One trump card is revealed.
- The first attacker is the player who holds the lowest trump card.
- If nobody has a trump card, fallback behavior must be defined by the
  implementation. The current domain falls back to the first player in
  `turn_order`.

### Defender

- The defender is the next active player after the attacker in turn order.

### Attack

- Only the current attacker may start the attack.
- An attacking card must come from the attacker hand.

### Defense

- Only the current defender may defend.
- A defense card must come from the defender hand.
- A higher card of the same suit beats an attack card.
- Any trump beats any non-trump.
- Against a trump attack, only a higher trump can defend.

### Throw-in

- Throw-in is allowed only after all current attack cards are defended.
- The defender cannot throw in.
- Throw-in cards must match a rank already present on the table.
- The total number of attack cards on the table cannot exceed the defender hand
  size at the start of the battle.

### Take cards

- Only the defender may take cards.
- Taking is legal only during defending.
- When the defender takes:
  - all table cards move to the defender hand;
  - the table is cleared;
  - the next attacker becomes the next active player after the defender;
  - the next defender becomes the next active player after that attacker.

### Successful defense

- When all attack cards are defended and no more legal throw-ins are made:
  - all table cards go to discard;
  - the previous defender becomes the next attacker;
  - the next defender becomes the next active player after that attacker.

### Refill order

- After take or successful defense, players draw back up to hand size in draw
  order defined by the rules.
- In the current domain, draw order is delegated to
  `DurakRules.get_draw_order(...)`.

## Code check result

### Domain logic: matches the rules

The opening-attacker rule is implemented in:

- [core/durak/controller.py](C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\core\durak\controller.py)
  `_select_first_attacker()`

The current code:

- scans every player hand;
- filters trump cards using `self.state.trump_suit`;
- picks the lowest trump by `RANK_ORDER`;
- assigns that player to `self.state.attacker_id`.

This matches the standard Durak rule for the opening attacker.

The start sequence also correctly sets:

- `attacker_id` first;
- `defender_id` as `next_active_player_id(attacker_id)`;
- `phase = ATTACKING`.

This is implemented in:

- [core/durak/controller.py](C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\core\durak\controller.py)
  `start_game()`

The existing domain test already encodes that rule:

- [tests/test_durak_game_controller.py](C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\tests\test_durak_game_controller.py)
  `test_start_game_deals_six_cards_and_lowest_trump_attacks_first`

### App startup deck policy

The adapter startup deck used by `GameController` must not bias the opening
attacker toward the human player.

Current policy:

- [core/game_controller.py](C:\Users\Zver\Documents\Codex\2026-04-26\Sandbox\core\game_controller.py)
  `create_default_deck()`
- delegates to `create_shuffled_deck()`;
- therefore the opening attacker is determined by the shuffled deal and the
  domain rule "lowest trump attacks first", not by a hardcoded human-favoring
  arrangement.

## Conclusion

### Correct

- `core/durak` opening-attacker logic follows the Durak rule "lowest trump
  attacks first".
- `take` legality belongs to the defender flow and is not supposed to be
  available at arbitrary startup states.

### Important project note

- The current app startup deck in `core/game_controller.py` is a shuffled
  adapter start and does not guarantee that the human attacks or defends first.
- If the goal is to test the `take` button deterministically, the startup
  scenario must place the human into a defending state explicitly.

## Recommended next step

If the desired runtime behavior is "bot attacks human at startup for button
testing", add a dedicated startup scenario for that purpose. Do not alter the
domain opening-attacker rule.
