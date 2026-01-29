# BPQX

BPQX is a command-line application that loads and runs user-defined extensions. Each extension is defined in a YAML file and provides a menu-driven interface that ultimately executes shell commands. It is designed to work over low-speed RF links using line-based text I/O.

## Requirements

- Python 3.6+
- [PyYAML](https://pypi.org/project/PyYAML/) (`pip install pyyaml`)

## Project Structure

```
bpqx/
  bpqx.py            # Main application
  appsettings.yml     # Application-wide settings
  extensions/         # Extension YAML files
    example.yml
```

## Usage

```
python3 bpqx.py
```

On startup, BPQX loads all `.yml` files from the `extensions/` directory, validates them, and presents the user with a list of available extensions. Invalid files are reported to stdout and skipped.

All user input is case-insensitive unless otherwise noted.

### Main Menu

```
Select Extension: RPBOOK, OTHEREXT
>
```

| Command | Action |
|---|---|
| `{extension name}` | Launch the named extension (supports prefix matching — e.g., `RPB` launches `RPBOOK`; if multiple extensions match, options are listed) |
| `H` or `Help` | Display application help text |
| `A` or `About` | Display application about text |
| `H {extension}` or `Help {extension}` | Display help for a specific extension |
| `A {extension}` or `About {extension}` | Display about for a specific extension |
| `X` or `Exit` | Exit the application |

### Extension Menus

Once inside an extension, menus are displayed as:

```
Select search type: [C]Call [T]History [V]Version
>
```

Items can be selected by typing the shortcut key (e.g., `C`) or the full text (e.g., `Call`).

| Command | Action |
|---|---|
| `{key}` or `{text}` | Select a menu item |
| `H` or `Help` | Display help for the current menu scope |
| `A` or `About` | Display about for the current menu scope |
| `H {item text}` or `Help {item text}` | Display help for a specific menu item |
| `A {item text}` or `About {item text}` | Display about for a specific menu item |
| `B` or `Back` | Go back one menu level (returns to main menu from root) |
| `X` or `Exit` | Exit the application |

### IO Prompts

When a menu item with an `io` block is selected, the user is prompted for input sequentially — one prompt at a time, ordered by `id`. Each prompt collects its own inputs before moving to the next.

```
Enter a call sign: W1AW
```

| Command | Action |
|---|---|
| `H` or `Help` | Display help for this IO prompt |
| Any other input | Validated against expected inputs, then used to execute the command |

Input values are space-separated. The number and types of values must match the prompt's `inputs` definition. If an input has `required: true`, a blank response is rejected. If all inputs for a prompt are optional, a blank response is accepted. Command stdout is printed to the user. Command stderr is suppressed.

## Application Settings

`appsettings.yml` contains application-wide configuration:

```yaml
help: "Help text displayed when user types H at the main menu"
about: "About text displayed when user types A at the main menu"
```

## Extension File Schema

Extension files are placed in the `extensions/` directory as `.yml` files. Each file defines one extension.

### Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Single-word name used to launch the extension. Must be unique across all extensions. |
| `description` | string | Yes | Short description of the extension. |
| `about` | string | No | About text displayed when user requests about info at the extension root. |
| `help` | string | No | Help text displayed when user requests help at the extension root. |
| `version` | string | No | Version string for the extension. |
| `program` | object | Yes | The extension's program definition. |

### Program Object

| Field | Type | Required | Description |
|---|---|---|---|
| `start_msg` | string | No | Message displayed when the extension is first launched. |
| `menu` | object | Yes | The root menu of the extension. |

### Menu Object

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | Yes | Text displayed before the menu item list. |
| `items` | list | Yes | List of menu item objects. |

### Menu Item Object

Each menu item must have exactly one of `io` or `menu` (not both).

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | int | Yes | Sort order for display. |
| `key` | char | No | Single-character shortcut key. Must not be a reserved key. |
| `text` | string | Yes | Display text for the menu item. Must not be a reserved text. |
| `help` | string | Yes | Help text for this menu item. |
| `about` | string | No | About text for this menu item. |
| `io` | object | No | IO block (terminal action). |
| `menu` | object | No | Submenu (nested menu object). |

**Reserved keys:** `A`, `B`, `H`, `X`
**Reserved texts:** `About`, `Back`, `Help`, `Exit`

### IO Object

| Field | Type | Required | Description |
|---|---|---|---|
| `prompts` | list | No | List of prompt objects presented to the user sequentially, ordered by `id`. If omitted, the command runs with no user input. |
| `help` | string | No | Help text shown when user types H at any IO prompt. |
| `command` | string | Yes | Shell command to execute. May contain `{id}` or `{name}` placeholders. |

### Prompt Object

Each entry in the `prompts` list defines a single prompt displayed to the user.

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | Yes | Text displayed to the user when requesting input. |
| `inputs` | list | No | List of expected input parameters for this prompt. |

### Input Object

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | int | Yes | Position of this input (starting at 1). Also used as `{id}` placeholder in command. |
| `type` | string | Yes | Expected type: `string`, `int`, or `bool`. |
| `required` | bool | No | If `true`, the user must provide a non-empty value. Defaults to `false`. |
| `name` | string | No | Named placeholder. If set, `{name}` can be used in the command string. |

### Placeholder Substitution

Commands can reference inputs by position or name:

- `{1}`, `{2}`, etc. are replaced by the input value at that position.
- `{_callsign}`, `{_frn}`, etc. are replaced by the input whose `name` matches.
- If any `{...}` placeholders remain after substitution, an error is displayed.

### Example Extension

```yaml
name: FCCDB
description: 'Query an offline copy of the FCC amateur radio license database'
about: >-
  This is an offline version of the FCC amateur radio license database.
help: >-
  Search the FCC DB by call sign and get license history by FRN and USI
program:
  start_msg: ''
  menu:
    prompt: Select search type
    items:
      - id: 1
        key: C
        text: Call
        help: Search by call sign
        io:
          prompts:
            - prompt: 'Enter a call sign'
              inputs:
                - id: 1
                  type: string
                  required: true
                  name: _callsign
          command: 'curl http://localhost:8010/api/query/callastext?call_sign={_callsign}'
          help: Enter a call sign to search for
      - id: 2
        key: V
        text: Version
        help: Get version info
        io:
          command: 'curl -s http://localhost:8010/api/version'
          help: Get date of the most recent data pull
version: 0.1.0
```
