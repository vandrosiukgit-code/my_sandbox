"""Visual actions owned by ActiveZone.

Actions describe visible screen scenarios, such as playing a card or dealing
cards. They compose lower-level animations and do not decide game rules.
"""

from actions.base_action import Action

__all__ = ["Action"]
