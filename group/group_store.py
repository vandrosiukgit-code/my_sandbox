"""РљРѕРЅС‚РµР№РЅРµСЂ СЃРѕР·РґР°РЅРЅС‹С… Group-РѕРІ.

GroupStore - СЌС‚Рѕ РѕР±С‰РёР№ СЃРєР»Р°Рґ РІРёР·СѓР°Р»СЊРЅС‹С… РѕР±СЉРµРєС‚РѕРІ РёРіСЂС‹. РћРЅ РЅРµ СЏРІР»СЏРµС‚СЃСЏ
СЌРєСЂР°РЅРѕРј, РЅРµ Р·РЅР°РµС‚ РїСЂР°РІРёР» РёРіСЂС‹ Рё РЅРµ Р·Р°РїСѓСЃРєР°РµС‚ Activity. Р•РіРѕ Р·Р°РґР°С‡Р° РїСЂРѕС‰Рµ:
РґРµСЂР¶Р°С‚СЊ СѓР¶Рµ СЃРѕР·РґР°РЅРЅС‹Рµ Group РїРѕ СЃС‚Р°Р±РёР»СЊРЅС‹Рј ID Рё РѕС‚РґР°РІР°С‚СЊ РёС… Р°РєС‚РёРІРЅРѕРјСѓ
GameScreen РїРѕ Р·Р°РїСЂРѕСЃСѓ.
"""

import pkgutil
from importlib import import_module


class GroupStore:
    """Р•РґРёРЅС‹Р№ РєРѕРЅС‚РµР№РЅРµСЂ Group-РѕРІ, РґРѕСЃС‚СѓРїРЅС‹С… РїРѕ group ID."""

    DEFAULT_BUILDER_PACKAGE = "groups_store"
    DEFAULT_BUILDER_MODULES = ()

    def __init__(self, resource_manager=None, builders=None, builder_modules=None):
        """РЎРѕР·РґР°С‚СЊ РїСѓСЃС‚РѕР№ СЃРєР»Р°Рґ РіСЂР°С„РёС‡РµСЃРєРёС… РѕР±СЉРµРєС‚РѕРІ.

        РљР»СЋС‡ СЃР»РѕРІР°СЂСЏ - СЃС‚Р°Р±РёР»СЊРЅС‹Р№ group_id. Р—РЅР°С‡РµРЅРёРµ - РѕР±СЉРµРєС‚ Group.
        РќР°РїСЂРёРјРµСЂ:

        - "card_17" -> Group РєР°СЂС‚С‹;
        - "main_menu.play_button" -> Group РєРЅРѕРїРєРё;
        - "table.background" -> Group С„РѕРЅР° СЃС‚РѕР»Р°.

        Args:
            resource_manager: РћР±С‰РёР№ ResourceManager, РёР· РєРѕС‚РѕСЂРѕРіРѕ builder-С‹
                РїРѕР»СѓС‡Р°СЋС‚ РєР°РґСЂС‹ РґР»СЏ СЃР»РѕРµРІ Group.
            builders: РќРµРѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ РЅР°Р±РѕСЂ С„СѓРЅРєС†РёР№-СЃР±РѕСЂС‰РёРєРѕРІ. РљР°Р¶РґР°СЏ С„СѓРЅРєС†РёСЏ
                РїРѕР»СѓС‡Р°РµС‚ resource_manager Рё РІРѕР·РІСЂР°С‰Р°РµС‚ РѕРґРёРЅ Group РёР»Рё СЃРїРёСЃРѕРє
                Group-РѕРІ.
            builder_modules: РќРµРѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ РЅР°Р±РѕСЂ РїСѓС‚РµР№ Рє РјРѕРґСѓР»СЏРј-СЃР±РѕСЂС‰РёРєР°Рј.
                РњРѕРґСѓР»СЊ РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ С„СѓРЅРєС†РёСЋ create(resource_manager).
        """
        self._groups = {}
        self.resource_manager = resource_manager
        self.builders = tuple(builders or ())
        self.builder_modules = (
            tuple(builder_modules)
            if builder_modules is not None
            else self.discover_builder_modules()
        )

    def build(self):
        """РЎРѕР±СЂР°С‚СЊ РІСЃРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅРЅС‹Рµ Group-С‹.

        Р­С‚Рѕ С‚РѕС‡РєР° РјР°СЃСЃРѕРІРѕР№ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё РіСЂР°С„РёС‡РµСЃРєРёС… РѕР±СЉРµРєС‚РѕРІ РёРіСЂС‹. Main.py РЅРµ
        РґРѕР»Р¶РµРЅ РІСЂСѓС‡РЅСѓСЋ Р·РЅР°С‚СЊ, РєР°Рє СѓСЃС‚СЂРѕРµРЅ table_group, card_group РёР»Рё Р±СѓРґСѓС‰РёРµ
        group-С‹ РјРµРЅСЋ. РћРЅ СЃРѕР·РґР°РµС‚ РѕРґРёРЅ РѕР±С‰РёР№ GroupStore, Р° store РІС‹Р·С‹РІР°РµС‚
        РєРѕРјРїР°РєС‚РЅС‹Рµ builder-С„СѓРЅРєС†РёРё РєРѕРЅРєСЂРµС‚РЅС‹С… group-РјРѕРґСѓР»РµР№.

        Р’Р°Р¶РЅРѕ: builder-С‹ РёСЃРїРѕР»СЊР·СѓСЋС‚ ResourceManager.get_frames(), РїРѕСЌС‚РѕРјСѓ
        runtime-РєСЌС€ СЂРµСЃСѓСЂСЃРѕРІ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃРѕР±СЂР°РЅ Р·Р°СЂР°РЅРµРµ, РїРѕСЃР»Рµ СЃРѕР·РґР°РЅРёСЏ pygame
        display.
        """
        if self.resource_manager is None:
            raise RuntimeError("GroupStore.build() С‚СЂРµР±СѓРµС‚ РїРѕРґРєР»СЋС‡РµРЅРЅС‹Р№ resource_manager")

        for builder in self.iter_builders():
            self.add_many(builder(self.resource_manager))
        return self

    def iter_builders(self):
        """Р’РµСЂРЅСѓС‚СЊ РІСЃРµ builder-С„СѓРЅРєС†РёРё РєРѕРЅРєСЂРµС‚РЅС‹С… Group-РјРѕРґСѓР»РµР№.

        РџСѓС‚Рё Рє РјРѕРґСѓР»СЏРј РёРјРїРѕСЂС‚РёСЂСѓСЋС‚СЃСЏ Р»РµРЅРёРІРѕ, С‚РѕР»СЊРєРѕ РІРѕ РІСЂРµРјСЏ build(). РўР°Рє
        Р±Р°Р·РѕРІС‹Р№ РїР°РєРµС‚ group РЅРµ С‚СЏРЅРµС‚ РєРѕРЅРєСЂРµС‚РЅС‹Рµ group-С‹ РїСЂРё РѕР±С‹С‡РЅРѕРј РёРјРїРѕСЂС‚Рµ
        Рё РЅРµ СЃРѕР·РґР°РµС‚ РєСЂСѓРіРѕРІС‹Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё.
        """
        for builder in self.builders:
            yield builder

        for module_path in self.builder_modules:
            module = import_module(module_path)
            builder = getattr(module, "create", None)
            if builder is not None:
                yield builder

    @classmethod
    def discover_builder_modules(cls, package_name=None):
        """Find group builder modules inside groups_store automatically."""
        package_name = package_name or cls.DEFAULT_BUILDER_PACKAGE
        package = import_module(package_name)
        return tuple(
            sorted(
                module_info.name
                for module_info in pkgutil.iter_modules(
                    package.__path__,
                    f"{package.__name__}.",
                )
                if not module_info.ispkg
                and not module_info.name.rsplit(".", 1)[-1].startswith("_")
            )
        )

    def add_many(self, groups):
        """Р”РѕР±Р°РІРёС‚СЊ РѕРґРёРЅ Group РёР»Рё РєРѕР»Р»РµРєС†РёСЋ Group-РѕРІ.

        Builder РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ РјРѕРґСѓР»СЏ РјРѕР¶РµС‚ РІРµСЂРЅСѓС‚СЊ РѕРґРёРЅ group РёР»Рё РЅРµСЃРєРѕР»СЊРєРѕ. Store
        РЅРѕСЂРјР°Р»РёР·СѓРµС‚ РѕР±Р° РІР°СЂРёР°РЅС‚Р°, С‡С‚РѕР±С‹ РјРѕРґСѓР»Рё group-РѕРІ РѕСЃС‚Р°РІР°Р»РёСЃСЊ РїСЂРѕСЃС‚С‹РјРё.
        """
        if groups is None:
            return ()

        if isinstance(groups, (list, tuple, set)):
            added = tuple(self.add(group) for group in groups)
        else:
            added = (self.add(groups),)
        return added

    def add(self, group):
        """Р”РѕР±Р°РІРёС‚СЊ Group РІ store.

        Group РѕР±СЏР·Р°РЅ РёРјРµС‚СЊ РЅРµРїСѓСЃС‚РѕР№ `id`. Р­С‚Рѕ РіР»Р°РІРЅС‹Р№ РјРѕСЃС‚ РјРµР¶РґСѓ Р»РѕРіРёС‡РµСЃРєРёРј
        РјРёСЂРѕРј GameController Рё РІРёР·СѓР°Р»СЊРЅС‹Рј РјРёСЂРѕРј GameScreen.

        Returns:
            Р”РѕР±Р°РІР»РµРЅРЅС‹Р№ group, С‡С‚РѕР±С‹ РІС‹Р·РѕРІ РјРѕР¶РЅРѕ Р±С‹Р»Рѕ РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ С†РµРїРѕС‡РєРѕР№.
        """
        group_id = self.get_group_id(group)
        if group_id in self._groups:
            raise ValueError(f"Group СЃ ID СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚: {group_id}")

        self._groups[group_id] = group
        return group

    def get(self, group_id):
        """Р’РµСЂРЅСѓС‚СЊ Group РїРѕ ID.

        Р•СЃР»Рё group РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РІС‹Р±СЂР°СЃС‹РІР°РµС‚СЃСЏ KeyError. Р­С‚Рѕ Р»СѓС‡С€Рµ, С‡РµРј С‚РёС…Рѕ
        РІРµСЂРЅСѓС‚СЊ None: РѕС€РёР±РєР° СЃСЂР°Р·Сѓ РїРѕРєР°Р¶РµС‚, С‡С‚Рѕ СЌРєСЂР°РЅ Р·Р°РїСЂРѕСЃРёР» РѕР±СЉРµРєС‚, РєРѕС‚РѕСЂС‹Р№
        РЅРµ Р±С‹Р» СЃРѕР·РґР°РЅ РїСЂРё СЃР±РѕСЂРєРµ РіСЂР°С„РёРєРё.
        """
        try:
            return self._groups[group_id]
        except KeyError as error:
            raise KeyError(f"Group РЅРµ РЅР°Р№РґРµРЅ РІ GroupStore: {group_id}") from error

    def has(self, group_id):
        """РџСЂРѕРІРµСЂРёС‚СЊ, РµСЃС‚СЊ Р»Рё Group СЃ С‚Р°РєРёРј ID."""
        return group_id in self._groups

    def remove(self, group_id):
        """РЈРґР°Р»РёС‚СЊ Group РёР· store Рё РІРµСЂРЅСѓС‚СЊ СѓРґР°Р»РµРЅРЅС‹Р№ РѕР±СЉРµРєС‚.

        РћР±С‹С‡РЅРѕ СЌРєСЂР°РЅ РґРѕР»Р¶РµРЅ С‚РѕР»СЊРєРѕ Р°РєС‚РёРІРёСЂРѕРІР°С‚СЊ РёР»Рё РґРµР°РєС‚РёРІРёСЂРѕРІР°С‚СЊ group ID.
        РЈРґР°Р»РµРЅРёРµ РёР· store РЅСѓР¶РЅРѕ РґР»СЏ СЂРµРґРєРёС… СЃР»СѓС‡Р°РµРІ, РєРѕРіРґР° РіСЂР°С„РёС‡РµСЃРєРёР№ РѕР±СЉРµРєС‚
        РґРµР№СЃС‚РІРёС‚РµР»СЊРЅРѕ Р±РѕР»СЊС€Рµ РЅРµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ РІ СЂР°РјРєР°С… РІСЃРµР№ РёРіСЂС‹.
        """
        try:
            return self._groups.pop(group_id)
        except KeyError as error:
            raise KeyError(f"РќРµР»СЊР·СЏ СѓРґР°Р»РёС‚СЊ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‰РёР№ Group: {group_id}") from error

    def all_ids(self):
        """Р’РµСЂРЅСѓС‚СЊ РІСЃРµ group ID РІ СЃС‚Р°Р±РёР»СЊРЅРѕРј РѕС‚СЃРѕСЂС‚РёСЂРѕРІР°РЅРЅРѕРј РїРѕСЂСЏРґРєРµ."""
        return tuple(sorted(self._groups))

    def clear(self):
        """РћС‡РёСЃС‚РёС‚СЊ store.

        РњРµС‚РѕРґ РїРѕР»РµР·РµРЅ РґР»СЏ С‚РµСЃС‚РѕРІ, РїРµСЂРµР·Р°РїСѓСЃРєР° РїРµСЃРѕС‡РЅРёС†С‹ РёР»Рё РїРѕР»РЅРѕР№ РїРµСЂРµСЃР±РѕСЂРєРё
        РіСЂР°С„РёС‡РµСЃРєРёС… РѕР±СЉРµРєС‚РѕРІ РїСЂРё СЃРјРµРЅРµ РїСЂРѕРµРєС‚Р°/РЅР°Р±РѕСЂР° СЂРµСЃСѓСЂСЃРѕРІ.
        """
        self._groups.clear()

    def __len__(self):
        """Р’РµСЂРЅСѓС‚СЊ РєРѕР»РёС‡РµСЃС‚РІРѕ group-РѕРІ РІ store."""
        return len(self._groups)

    def __contains__(self, group_id):
        """РџРѕРґРґРµСЂР¶Р°С‚СЊ РІС‹СЂР°Р¶РµРЅРёРµ `group_id in group_store`."""
        return self.has(group_id)

    @staticmethod
    def get_group_id(group):
        """Р”РѕСЃС‚Р°С‚СЊ ID РёР· Group Рё РїСЂРѕРІРµСЂРёС‚СЊ РµРіРѕ РєРѕСЂСЂРµРєС‚РЅРѕСЃС‚СЊ."""
        group_id = getattr(group, "id", None)
        if not group_id:
            raise ValueError("GroupStore.add() С‚СЂРµР±СѓРµС‚ group СЃ РЅРµРїСѓСЃС‚С‹Рј id")
        return group_id


