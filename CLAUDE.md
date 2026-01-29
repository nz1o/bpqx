# CLAUDE.md

## Project Overview

BPQX is a Python CLI application that loads YAML-defined extensions from the `extensions/` directory and presents them as interactive menu-driven tools. Each extension defines a tree of menus that terminate in shell commands. Designed for use over low-speed RF links.

## Architecture

- **Single-file application:** `bpqx.py` contains all logic (loading, validation, menu navigation, IO execution).
- **No external dependencies** beyond PyYAML.
- **Line-based I/O:** Uses `print()` and `input()` exclusively. No curses, no ANSI codes. All output is line-buffered text suitable for serial/RF links.

## Key Files

- `bpqx.py` - Main application entry point. Run with `python3 bpqx.py`.
- `appsettings.yml` - Application-wide settings (help, about text).
- `extensions/*.yml` - Extension definitions. Schema is documented in `README.md` and heavily commented in `extensions/example.yml`.

## Important Conventions

- All string comparisons are case-insensitive unless specifically noted.
- Reserved keys (`A`, `B`, `H`, `X`) and texts (`About`, `Back`, `Help`, `Exit`) must not be used by extension menu items.
- Each menu item must have exactly one of `io` (terminal command) or `menu` (submenu), never both.
- Command stderr is suppressed; only stdout is returned to the user.
- Extension names are stored and matched in lowercase internally.

## Running

```
python3 bpqx.py
```

For unbuffered output (e.g., over a pipe or RF link):
```
python3 -u bpqx.py
```

## Testing

No test framework is configured. To verify manually:
1. Run `python3 bpqx.py` with extensions in `extensions/`.
2. Test H, A, X commands at the main menu.
3. Navigate into an extension, traverse submenus with keys/text, use B to go back.
4. Test IO prompts with valid and invalid input.
5. Place an invalid YAML file in `extensions/` and confirm it is reported and skipped.
