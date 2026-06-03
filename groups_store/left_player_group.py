"""Build the left player group from group_config."""

from group import Group


GROUP_ID = "left_player"


def create(resource_manager):
    return Group.from_config(GROUP_ID, resource_manager)
