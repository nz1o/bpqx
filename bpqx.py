#!/usr/bin/env python3

import glob
import os
import re
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


def validate_io(io_obj, filepath, path):
    errors = []
    if not isinstance(io_obj, dict):
        errors.append(f"{filepath}: {path}.io must be a mapping")
        return errors
    if "command" not in io_obj:
        errors.append(f"{filepath}: {path}.io.command is required")
    inputs = io_obj.get("inputs")
    if inputs:
        if "prompt" not in io_obj:
            errors.append(f"{filepath}: {path}.io.prompt is required when inputs are specified")
        if not isinstance(inputs, list):
            errors.append(f"{filepath}: {path}.io.inputs must be a list")
        else:
            for inp in inputs:
                if "id" not in inp:
                    errors.append(f"{filepath}: {path}.io.inputs[].id is required")
                if "type" not in inp:
                    errors.append(f"{filepath}: {path}.io.inputs[].type is required")
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
        if key and key.lower() in RESERVED_KEYS:
            errors.append(f"{filepath}: {item_path}.key '{key}' is reserved")
        text = item.get("text")
        if text and text.lower() in RESERVED_TEXTS:
            errors.append(f"{filepath}: {item_path}.text '{text}' is reserved")
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
    user_lower = user_input.lower()
    for item in items:
        if item.get("key") and item["key"].lower() == user_lower:
            return item
        if item["text"].lower() == user_lower:
            return item
    return None


def find_item_by_text(items, text):
    text_lower = text.lower()
    for item in items:
        if item["text"].lower() == text_lower:
            return item
    return None


def run_io(io_obj):
    inputs_def = io_obj.get("inputs", []) or []
    while True:
        if io_obj.get("prompt"):
            user_input = input(f"{io_obj['prompt']}: ").strip()
        elif inputs_def:
            user_input = input(": ").strip()
        else:
            user_input = None

        if user_input is not None:
            if user_input.lower() in ("h", "help"):
                print(io_obj.get("help", "No help available."))
                continue

        if not inputs_def:
            command = io_obj["command"]
        else:
            values = user_input.split() if user_input else []
            if len(values) != len(inputs_def):
                print(f"Error: expected {len(inputs_def)} input(s), got {len(values)}")
                continue
            valid = True
            for inp, val in zip(sorted(inputs_def, key=lambda x: x["id"]), values):
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

            command = io_obj["command"]
            for inp, val in zip(sorted(inputs_def, key=lambda x: x["id"]), values):
                command = command.replace(f"{{{inp['id']}}}", val)
                if inp.get("name"):
                    command = command.replace(f"{{{inp['name']}}}", val)

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
        return


def display_menu(menu):
    items = sorted(menu["items"], key=lambda x: x["id"])
    parts = []
    for item in items:
        if item.get("key"):
            parts.append(f"[{item['key']}]{item['text']}")
        else:
            parts.append(item["text"])
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

        item = find_item_by_input(current_menu["items"], user_input)
        if not item:
            continue

        if "menu" in item:
            menu_stack.append(item["menu"])
        elif "io" in item:
            run_io(item["io"])


def main():
    appsettings = load_appsettings()
    extensions = load_extensions()

    if not extensions:
        print("No valid extensions found.")
        sys.exit(1)

    while True:
        ext_names = [ext["name"] for ext in extensions.values()]
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
            print(f"Unknown extension: {user_input}")


if __name__ == "__main__":
    main()
