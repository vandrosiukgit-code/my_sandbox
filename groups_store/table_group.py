"""Build this group from group_config.json."""

from group import Group


GROUP_ID = 'table_group'


def create(resource_manager):
    return Group.from_config(GROUP_ID, resource_manager)
