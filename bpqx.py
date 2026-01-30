#!/usr/bin/env python3

import glob
import os
import re
import shlex
import subprocess
import sys

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSIONS_DIR = os.path.join(SCRIPT_DIR, "extensions")
APPSETTINGS_PATH = os.path.join(SCRIPT_DIR, "appsettings.yml")

RESERVED_KEYS = {"a", "b", "h", "x"}
RESERVED_TEXTS = {"about", "back", "help", "exit"}


def load_appsettings():
    with open(APPSETTINGS_PATH, "r") as f:
        return yaml.safe_load(f)


def parse_inline_param(s):
    """Extract base and parameter name from strings like 'S {search}' -> ('s', 'search')."""
    m = re.match(r'^(\S+)\s+\{(\w+)\}$', s)
    if m:
        return m.group(1).lower(), m.group(2)
    return s.lower(), None


def strip_inline_param(s):
    """Remove '{param}' suffix from key/text for display."""
    return re.sub(r'\s*\{\w+\}$', '', s)


def validate_io(io_obj, filepath, path):
    errors = []
    if isinstance(io_obj, list):
        if len(io_obj) == 0:
            errors.append(f"{filepath}: {path}.io must not be empty")
            return errors
        io_obj = io_obj[0]
    if not isinstance(io_obj, dict):
        errors.append(f"{filepath}: {path}.io must be a mapping")
        return errors
    if "command" not in io_obj:
        errors.append(f"{filepath}: {path}.io.command is required")
    prompts = io_obj.get("prompts")
    if prompts:
        if not isinstance(prompts, list):
            errors.append(f"{filepath}: {path}.io.prompts must be a list")
        else:
            for j, p in enumerate(prompts):
                p_path = f"{path}.io.prompts[{j}]"
                if not isinstance(p, dict):
                    errors.append(f"{filepath}: {p_path} must be a mapping")
                    continue
                if "prompt" not in p:
                    errors.append(f"{filepath}: {p_path}.prompt is required")
                inputs = p.get("inputs")
                if inputs:
                    if not isinstance(inputs, list):
                        errors.append(f"{filepath}: {p_path}.inputs must be a list")
                    else:
                        for inp in inputs:
                            if "id" not in inp:
                                errors.append(f"{filepath}: {p_path}.inputs[].id is required")
                            if "type" not in inp:
                                errors.append(f"{filepath}: {p_path}.inputs[].type is required")
    return errors


def validate_menu(menu, filepath, path="program.menu"):
    errors = []
    if not isinstance(menu, dict):
        errors.append(f"{filepath}: {path} must be a mapping")
        return errors
    if "prompt" not in menu:
        errors.append(f"{filepath}: {path}.prompt is required")
    if "items" not in menu or not isinstance(menu.get("items"), list):
        errors.append(f"{filepath}: {path}.items is required and must be a list")
        return errors
    for i, item in enumerate(menu["items"]):
        item_path = f"{path}.items[{i}]"
        if "id" not in item:
            errors.append(f"{filepath}: {item_path}.id is required")
        if "text" not in item:
            errors.append(f"{filepath}: {item_path}.text is required")
        if "help" not in item:
            errors.append(f"{filepath}: {item_path}.help is required")
        key = item.get("key")
        key_base, key_param = parse_inline_param(key) if key else (None, None)
        if key_base and key_base in RESERVED_KEYS:
            errors.append(f"{filepath}: {item_path}.key '{key}' is reserved")
        text = item.get("text")
        _, text_param = parse_inline_param(text) if text else (None, None)
        if text and strip_inline_param(text).lower() in RESERVED_TEXTS:
            errors.append(f"{filepath}: {item_path}.text '{text}' is reserved")
        inline_param = key_param or text_param
        if inline_param:
            if "menu" in item:
                errors.append(f"{filepath}: {item_path} inline parameter '{inline_param}' is only valid with 'io', not 'menu'")
            if "io" in item:
                io = item["io"]
                if isinstance(io, list):
                    io = io[0] if io else {}
                all_inputs = []
                for p in (io.get("prompts") or []):
                    all_inputs.extend(p.get("inputs") or [])
                if len(all_inputs) != 1:
                    errors.append(f"{filepath}: {item_path} inline parameter requires exactly 1 input, found {len(all_inputs)}")
                elif not any(inp.get("name") == inline_param for inp in all_inputs):
                    errors.append(f"{filepath}: {item_path} inline parameter '{inline_param}' does not match input name '{all_inputs[0].get('name', '')}'")
        has_io = "io" in item
        has_menu = "menu" in item
        if has_io == has_menu:
            errors.append(f"{filepath}: {item_path} must have exactly one of 'io' or 'menu'")
        if has_io:
            errors.extend(validate_io(item["io"], filepath, item_path))
        if has_menu:
            errors.extend(validate_menu(item["menu"], filepath, f"{item_path}.menu"))
    return errors


def validate_extension(data, filepath):
    errors = []
    for field in ("name", "description", "program"):
        if field not in data:
            errors.append(f"{filepath}: '{field}' is required")
    if "program" in data:
        prog = data["program"]
        if not isinstance(prog, dict):
            errors.append(f"{filepath}: 'program' must be a mapping")
        elif "menu" not in prog:
            errors.append(f"{filepath}: 'program.menu' is required")
        else:
            errors.extend(validate_menu(prog["menu"], filepath))
    return errors


def load_extensions():
    extensions = {}
    for filepath in sorted(glob.glob(os.path.join(EXTENSIONS_DIR, "*.yml"))):
        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}")
            continue
        if not isinstance(data, dict):
            print(f"Error in {filepath}: file must contain a YAML mapping")
            continue
        errors = validate_extension(data, filepath)
        if errors:
            for err in errors:
                print(err)
            continue
        name = data["name"]
        extensions[name.lower()] = data
    return extensions


def find_item_by_input(items, user_input):
    """Match user input to a menu item. Returns (item, inline_value) tuple."""
    user_lower = user_input.lower()
    parts = user_input.split(None, 1)
    base_lower = parts[0].lower() if parts else user_lower
    inline_value = None
    if len(parts) == 2:
        try:
            parsed = shlex.split(parts[1])
            inline_value = parsed[0] if len(parsed) == 1 else parts[1]
        except ValueError:
            inline_value = parts[1]

    for item in items:
        key = item.get("key", "")
        text = item.get("text", "")
        key_base, key_param = parse_inline_param(key) if key else (None, None)
        text_base, text_param = parse_inline_param(text)

        # Exact match on base key (with or without inline value)
        if key_base and key_base == base_lower:
            if key_param and inline_value:
                return item, (key_param, inline_value)
            if not inline_value:
                return item, None

        # Exact match on base text
        if text_base == base_lower:
            if text_param and inline_value:
                return item, (text_param, inline_value)
            if not inline_value:
                return item, None

        # Full exact match (no param pattern) - original behavior
        if key and key.lower() == user_lower:
            return item, None
        if text.lower() == user_lower:
            return item, None

    return None, None


def find_item_by_text(items, text):
    text_lower = text.lower()
    for item in items:
        if strip_inline_param(item["text"]).lower() == text_lower:
            return item
    return None


def run_io(io_obj, precollected=None):
    prompts = io_obj.get("prompts") or []
    collected = dict(precollected) if precollected else {}

    for prompt_def in sorted(prompts, key=lambda p: p.get("id", 0)):
        inputs_def = prompt_def.get("inputs", []) or []
        inputs_sorted = sorted(inputs_def, key=lambda x: x["id"]) if inputs_def else []

        if inputs_sorted and all(
            (inp.get("name") and inp["name"] in collected) or str(inp["id"]) in collected
            for inp in inputs_sorted
        ):
            continue

        while True:
            user_input = input(f"{prompt_def['prompt']}: ").strip()

            if user_input.lower() in ("h", "help"):
                print(io_obj.get("help", "No help available."))
                continue

            if not inputs_sorted:
                break

            try:
                values = shlex.split(user_input) if user_input else []
            except ValueError:
                values = user_input.split() if user_input else []
            if len(values) != len(inputs_sorted):
                if not values:
                    has_required = any(inp.get("required") for inp in inputs_sorted)
                    if not has_required:
                        for inp in inputs_sorted:
                            collected[inp["id"]] = ""
                            if inp.get("name"):
                                collected[inp["name"]] = ""
                        break
                    print("Error: input is required")
                else:
                    print(f"Error: expected {len(inputs_sorted)} input(s), got {len(values)}")
                continue

            valid = True
            for inp, val in zip(inputs_sorted, values):
                if inp.get("required") and not val:
                    print(f"Error: input {inp['id']} is required")
                    valid = False
                    continue
                t = inp["type"].lower()
                if t == "int":
                    try:
                        int(val)
                    except ValueError:
                        print(f"Error: input {inp['id']} must be an integer")
                        valid = False
                elif t == "bool":
                    if val.lower() not in ("true", "false"):
                        print(f"Error: input {inp['id']} must be true or false")
                        valid = False
            if not valid:
                continue

            for inp, val in zip(inputs_sorted, values):
                collected[inp["id"]] = val
                if inp.get("name"):
                    collected[inp["name"]] = val
            break

    command = io_obj["command"]
    for key, val in collected.items():
        command = command.replace(f"{{{key}}}", val)

    unknown = re.findall(r"\{[^}]+\}", command)
    if unknown:
        print(f"Error: unknown placeholder(s) in command: {', '.join(unknown)}")
        return

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
    except Exception as e:
        print(f"Error running command: {e}")


def display_menu(menu):
    items = sorted(menu["items"], key=lambda x: x["id"])
    parts = []
    for item in items:
        raw_key = item.get("key", "")
        raw_text = item.get("text", "")
        key_base = strip_inline_param(raw_key) if raw_key else None
        text_base = strip_inline_param(raw_text)
        _, key_param = parse_inline_param(raw_key) if raw_key else (None, None)
        _, text_param = parse_inline_param(raw_text)
        param = key_param or text_param
        suffix = f" ({param})" if param else ""
        if key_base:
            parts.append(f"[{key_base}]{text_base}{suffix}")
        else:
            parts.append(f"{text_base}{suffix}")
    print(f"\n{menu['prompt']}: {' '.join(parts)}")


def run_extension(ext):
    start_msg = ext["program"].get("start_msg", "")
    if start_msg:
        print(start_msg)

    menu_stack = [ext["program"]["menu"]]

    while True:
        current_menu = menu_stack[-1]
        display_menu(current_menu)

        user_input = input("> ").strip()
        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("x", "exit"):
            sys.exit(0)

        if lower in ("b", "back"):
            if len(menu_stack) > 1:
                menu_stack.pop()
            else:
                return
            continue

        if lower in ("h", "help"):
            if len(menu_stack) == 1:
                print(ext.get("help", "No help available."))
            else:
                print(current_menu.get("help", ext.get("help", "No help available.")))
            continue

        if lower in ("a", "about"):
            if len(menu_stack) == 1:
                print(ext.get("about", "No about information available."))
            else:
                print(current_menu.get("about", ext.get("about", "No about information available.")))
            continue

        parts = lower.split(None, 1)
        if len(parts) == 2 and parts[0] in ("h", "help"):
            item = find_item_by_text(current_menu["items"], parts[1])
            if item:
                print(item.get("help", "No help available."))
            else:
                print(f"Unknown item: {parts[1]}")
            continue

        if len(parts) == 2 and parts[0] in ("a", "about"):
            item = find_item_by_text(current_menu["items"], parts[1])
            if item:
                print(item.get("about", "No about information available."))
            else:
                print(f"Unknown item: {parts[1]}")
            continue

        item, inline = find_item_by_input(current_menu["items"], user_input)
        if not item:
            continue

        if "menu" in item:
            menu_stack.append(item["menu"])
        elif "io" in item:
            io_obj = item["io"]
            if isinstance(io_obj, list):
                io_obj = io_obj[0]
            precollected = None
            if inline:
                param_name, param_value = inline
                precollected = {param_name: param_value}
            run_io(io_obj, precollected=precollected)


def main():
    appsettings = load_appsettings()
    extensions = load_extensions()

    if not extensions:
        print("No valid extensions found.")
        sys.exit(1)

    while True:
        ext_names = [ext["name"] for ext in extensions.values()]
        print("\n- BPQX -")
        print("[A]About [H]Help [B]Back [X]Exit")
        print(f"\nSelect Extension: {', '.join(ext_names)}")
        user_input = input("> ").strip()
        if not user_input:
            continue

        lower = user_input.lower()

        if lower in ("x", "exit"):
            sys.exit(0)

        if lower in ("h", "help"):
            print(appsettings.get("help", "No help available."))
            continue

        if lower in ("a", "about"):
            print(appsettings.get("about", "No about information available."))
            continue

        parts = lower.split(None, 1)
        if len(parts) == 2 and parts[0] in ("h", "help"):
            ext = extensions.get(parts[1])
            if ext:
                print(ext.get("help", "No help available."))
            else:
                print(f"Unknown extension: {parts[1]}")
            continue

        if len(parts) == 2 and parts[0] in ("a", "about"):
            ext = extensions.get(parts[1])
            if ext:
                print(ext.get("about", "No about information available."))
            else:
                print(f"Unknown extension: {parts[1]}")
            continue

        ext = extensions.get(lower)
        if ext:
            run_extension(ext)
        else:
            matches = [k for k in extensions if k.startswith(lower)]
            if len(matches) == 1:
                run_extension(extensions[matches[0]])
            elif len(matches) > 1:
                names = ", ".join(extensions[k]["name"] for k in matches)
                print(f"Options: {names}")
            else:
                print(f"\nSelect Extension: {', '.join(ext['name'] for ext in extensions.values())}")


if __name__ == "__main__":
    main()
