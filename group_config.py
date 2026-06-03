"""Project-wide source of truth API for GUI Group metadata and layers."""

from __future__ import annotations

import copy
import json
import os


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
GROUP_CONFIG_FILE = os.path.join(PROJECT_DIR, "group_config.json")


def load_group_config():
    """Load group metadata from group_config.json."""
    if not os.path.exists(GROUP_CONFIG_FILE):
        return {"groups": {}}
    with open(GROUP_CONFIG_FILE, "r", encoding="utf-8") as file:
        payload = json.load(file)
    payload.setdefault("groups", {})
    return payload


def save_group_config(payload=None):
    """Save group metadata to group_config.json."""
    payload = payload if payload is not None else GROUP_CONFIG
    with open(GROUP_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


GROUP_CONFIG = load_group_config()


def reload_group_config():
    """Reload config from disk and return it."""
    global GROUP_CONFIG
    GROUP_CONFIG = load_group_config()
    return GROUP_CONFIG


def get_group_config(group_id):
    """Return metadata for one group."""
    try:
        return GROUP_CONFIG["groups"][group_id]
    except KeyError as error:
        raise KeyError(f"Group config not found: {group_id}") from error


def iter_group_ids():
    """Return configured group ids in stable order."""
    return tuple(sorted(GROUP_CONFIG.get("groups", {})))


def ensure_group(group_id):
    """Create group metadata if it does not exist yet."""
    groups = GROUP_CONFIG.setdefault("groups", {})
    return groups.setdefault(
        group_id,
        {
            "role": "",
            "tags": [],
            "rect": [0, 0, 0, 0],
            "hit_rect": [0, 0, 0, 0],
            "scale_factor": 1.0,
            "hide_rect": True,
            "manifest_targets": {},
            "layers": [],
        },
    )


def delete_group(group_id):
    """Delete one group from group_config.json."""
    groups = GROUP_CONFIG.setdefault("groups", {})
    if group_id not in groups:
        raise KeyError(f"Group config not found: {group_id}")
    removed = groups.pop(group_id)
    save_group_config()
    return removed


def upsert_group(group_id, group_metadata, source_group_id=None):
    """Create or update one group metadata block while preserving layers by default."""
    groups = GROUP_CONFIG.setdefault("groups", {})
    if source_group_id and source_group_id != group_id:
        source = groups.get(source_group_id)
        if source is not None and group_id not in groups:
            groups[group_id] = copy.deepcopy(source)
    group = ensure_group(group_id)
    for key, value in (group_metadata or {}).items():
        if value is None:
            group.pop(key, None)
        else:
            group[key] = value
    save_group_config()
    return group


def delete_layer(group_id, layer_name):
    """Delete one layer from a group_config group."""
    group = get_group_config(group_id)
    layers = group.setdefault("layers", [])
    for index, layer_config in enumerate(layers):
        if layer_config.get("name") == layer_name:
            removed = layers.pop(index)
            save_group_config()
            return removed
    raise KeyError(f"Layer config not found: {group_id}.{layer_name}")


def get_layer_config(group_id, layer_name):
    """Return metadata for one layer inside one group."""
    for layer_config in get_group_config(group_id).get("layers", ()):
        if layer_config.get("name") == layer_name:
            return layer_config
    raise KeyError(f"Layer config not found: {group_id}.{layer_name}")


def upsert_layer(group_id, layer_config):
    """Insert or replace one layer in a group."""
    group = ensure_group(group_id)
    layers = group.setdefault("layers", [])
    layer_name = layer_config["name"]
    for index, existing_layer in enumerate(layers):
        if existing_layer.get("name") == layer_name:
            layers[index] = copy.deepcopy(layer_config)
            save_group_config()
            return layers[index]
    layers.append(copy.deepcopy(layer_config))
    save_group_config()
    return layers[-1]


def set_layer_resource(group_id, layer_name, resource_key):
    """Change the configured PNG resource for one image layer."""
    layer_config = get_layer_config(group_id, layer_name)
    layer_config["type"] = "image"
    layer_config["resource_key"] = resource_key
    save_group_config()
    return layer_config


def set_layer_text(group_id, layer_name, text):
    """Change the configured text for one text layer."""
    layer_config = get_layer_config(group_id, layer_name)
    layer_config["type"] = "text"
    layer_config["text"] = str(text)
    save_group_config()
    return layer_config


def set_text_layer_config(group_id, layer_name, layer_updates):
    """Change configured text, size, fit mode, and font style for one text layer."""
    try:
        layer_config = get_layer_config(group_id, layer_name)
    except KeyError:
        layer_config = upsert_layer(group_id, {"name": layer_name, "type": "text"})
    layer_config["type"] = "text"
    for key, value in layer_updates.items():
        if key == "style":
            style = layer_config.setdefault("style", {})
            for style_key, style_value in value.items():
                if style_value is None:
                    style.pop(style_key, None)
                else:
                    style[style_key] = style_value
        elif value is None:
            layer_config.pop(key, None)
        else:
            layer_config[key] = value
    save_group_config()
    return layer_config


def set_layer_position(group_id, layer_name, position):
    """Change the configured layer position relative to the group rect."""
    layer_config = get_layer_config(group_id, layer_name)
    layer_config["position"] = [int(position[0]), int(position[1])]
    save_group_config()
    return layer_config


def upsert_image_layer(group_id, layer_name, resource_key, position=(0, 0), group_metadata=None):
    """Create or update an image layer in group_config.json."""
    group = ensure_group(group_id)
    for key, value in (group_metadata or {}).items():
        if value not in (None, ""):
            group[key] = value
    return upsert_layer(
        group_id,
        {
            "name": layer_name,
            "type": "image",
            "resource_key": resource_key,
            "position": [int(position[0]), int(position[1])],
        },
    )


def upsert_manifest_target(group_id, target_id, target_type, layer_name, description=""):
    """Create or update a public manifest target for one group layer."""
    group = ensure_group(group_id)
    targets = group.setdefault("manifest_targets", {})
    targets[target_id] = {
        "type": target_type,
        "layer": layer_name,
    }
    if description:
        targets[target_id]["description"] = description
    save_group_config()
    return targets[target_id]
