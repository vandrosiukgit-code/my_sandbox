"""Build this group from group_config.json."""

from group import Group


GROUP_ID = 'top_player'


def create(resource_manager):
    return Group.from_config(GROUP_ID, resource_manager)
