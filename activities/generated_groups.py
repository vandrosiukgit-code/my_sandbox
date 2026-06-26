"""Small registries for visual-only groups owned by activities."""


class GeneratedGroupRegistry:
    """Track generated visual groups and monotonic generated group IDs."""

    def __init__(self, id_prefix=None):
        self.id_prefix = id_prefix
        self._groups = []
        self._next_index = 0

    def next_id(self):
        if not self.id_prefix:
            raise RuntimeError("GeneratedGroupRegistry requires id_prefix for next_id()")
        self._next_index += 1
        return f"{self.id_prefix}.{self._next_index}"

    def append(self, group):
        self._groups.append(group)
        return group

    def remove(self, group):
        self._groups = [item for item in self._groups if item is not group]

    def clear(self):
        self._groups = []

    def set_groups(self, groups):
        self._groups = list(groups or ())

    def iter_groups(self):
        return tuple(self._groups)
