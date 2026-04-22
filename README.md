# growforme

A simple command-line plant-growth tracker.

---

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration format](#configuration-format)
- [Execution format](#execution-format)
- [Examples](#examples)

---

## Requirements

- Python 3.8 or newer
- `pyyaml` (optional – used to read `config.yaml`; falls back to built-in defaults when absent)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Normalnet/growforme.git
cd growforme

# 2. (Optional) install PyYAML so the app can read config.yaml
pip install pyyaml
```

---

## Configuration format

Configuration is stored in **`config.yaml`** (YAML format).  
Copy the provided file and edit the values that differ from the defaults:

```yaml
# config.yaml
app:
  name: growforme
  version: "1.0.0"
  log_level: info          # debug | info | warning | error

plants:
  data_dir: ./data/plants  # directory where plant records are stored
  reminder_days: 7         # days before next watering to send a reminder

notifications:
  enabled: false
  email: ""                # recipient address; required when enabled is true
  smtp_host: smtp.example.com
  smtp_port: 587

output:
  format: table            # table | json | csv
  date_format: "%Y-%m-%d"
```

All keys are optional; any omitted key falls back to the default value shown above.

### Overriding the config path

Pass `--config <path>` before the subcommand to load a different file:

```bash
python growforme.py --config /etc/growforme/prod.yaml list
```

---

## Execution format

```
python growforme.py [--config CONFIG] <command> [options]
```

| Command  | Description                        |
|----------|------------------------------------|
| `add`    | Add a new plant entry              |
| `list`   | List all tracked plants            |
| `water`  | Record a watering event            |
| `report` | Generate a growth report           |

### `add`

```
python growforme.py add --name <NAME> [--species <SPECIES>]
```

| Option      | Required | Description                        |
|-------------|----------|------------------------------------|
| `--name`    | yes      | Common name of the plant           |
| `--species` | no       | Scientific species name            |

### `list`

```
python growforme.py list
```

Output format is controlled by `output.format` in `config.yaml` (`table`, `json`, or `csv`).

### `water`

```
python growforme.py water --name <NAME>
```

| Option   | Required | Description                        |
|----------|----------|------------------------------------|
| `--name` | yes      | Name of the plant to water         |

### `report`

```
python growforme.py report [--format table|json|csv]
```

| Option     | Required | Description                                             |
|------------|----------|---------------------------------------------------------|
| `--format` | no       | Override the output format set in `config.yaml`        |

---

## Examples

```bash
# Add plants
python growforme.py add --name "Basil" --species "Ocimum basilicum"
python growforme.py add --name "Tomato" --species "Solanum lycopersicum"

# List all plants (table format by default)
python growforme.py list

# Record a watering event
python growforme.py water --name "Basil"

# Generate a JSON report
python growforme.py report --format json

# Use a custom config file
python growforme.py --config my-config.yaml list
```
