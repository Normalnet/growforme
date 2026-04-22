#!/usr/bin/env python3
"""growforme – a simple plant-growth tracker.

Usage
-----
    python growforme.py [--config CONFIG] <command> [options]

Commands
--------
    add      Add a new plant entry
    list     List all tracked plants
    water    Record a watering event
    report   Generate a growth report

Examples
--------
    python growforme.py add --name "Basil" --species "Ocimum basilicum"
    python growforme.py list
    python growforme.py water --name "Basil"
    python growforme.py report --format json
"""

import argparse
import json
import os
import sys
from datetime import date

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_DATA_DIR = os.path.join("data", "plants")


# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML configuration, falling back to defaults on error."""
    defaults = {
        "app": {"name": "growforme", "version": "1.0.0", "log_level": "info"},
        "plants": {"data_dir": DEFAULT_DATA_DIR, "reminder_days": 7},
        "notifications": {"enabled": False},
        "output": {"format": "table", "date_format": "%Y-%m-%d"},
    }
    if not _YAML_AVAILABLE:
        return defaults
    try:
        with open(path, "r") as fh:
            user_cfg = yaml.safe_load(fh) or {}
        for section, values in user_cfg.items():
            if isinstance(values, dict):
                defaults.setdefault(section, {}).update(values)
            else:
                defaults[section] = values
        return defaults
    except FileNotFoundError:
        return defaults


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _data_path(cfg: dict) -> str:
    return cfg["plants"]["data_dir"]


def _index_path(cfg: dict) -> str:
    return os.path.join(_data_path(cfg), "index.json")


def _load_index(cfg: dict) -> list:
    path = _index_path(cfg)
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return json.load(fh)


def _save_index(cfg: dict, index: list) -> None:
    os.makedirs(_data_path(cfg), exist_ok=True)
    with open(_index_path(cfg), "w") as fh:
        json.dump(index, fh, indent=2)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_add(cfg: dict, args: argparse.Namespace) -> int:
    index = _load_index(cfg)
    if any(p["name"] == args.name for p in index):
        print(f"Error: plant '{args.name}' already exists.", file=sys.stderr)
        return 1
    entry = {
        "name": args.name,
        "species": args.species or "",
        "added": date.today().isoformat(),
        "last_watered": None,
        "waterings": [],
    }
    index.append(entry)
    _save_index(cfg, index)
    print(f"Added plant: {args.name}")
    return 0


def cmd_list(cfg: dict, _args: argparse.Namespace) -> int:
    index = _load_index(cfg)
    if not index:
        print("No plants tracked yet. Use 'add' to get started.")
        return 0
    fmt = cfg["output"]["format"]
    if fmt == "json":
        print(json.dumps(index, indent=2))
    elif fmt == "csv":
        print("name,species,added,last_watered")
        for p in index:
            print(f"{p['name']},{p['species']},{p['added']},{p.get('last_watered', '')}")
    else:
        width = max(len(p["name"]) for p in index)
        header = f"{'Name':<{width}}  {'Species':<30}  Added       Last watered"
        print(header)
        print("-" * len(header))
        for p in index:
            lw = p.get("last_watered") or "-"
            print(f"{p['name']:<{width}}  {p['species']:<30}  {p['added']}  {lw}")
    return 0


def cmd_water(cfg: dict, args: argparse.Namespace) -> int:
    index = _load_index(cfg)
    for plant in index:
        if plant["name"] == args.name:
            today = date.today().isoformat()
            plant["last_watered"] = today
            plant.setdefault("waterings", []).append(today)
            _save_index(cfg, index)
            print(f"Recorded watering for '{args.name}' on {today}.")
            return 0
    print(f"Error: plant '{args.name}' not found.", file=sys.stderr)
    return 1


def cmd_report(cfg: dict, args: argparse.Namespace) -> int:
    index = _load_index(cfg)
    fmt = args.format or cfg["output"]["format"]
    report = {
        "generated": date.today().isoformat(),
        "total_plants": len(index),
        "plants": [
            {
                "name": p["name"],
                "species": p["species"],
                "total_waterings": len(p.get("waterings", [])),
                "last_watered": p.get("last_watered"),
            }
            for p in index
        ],
    }
    if fmt == "json":
        print(json.dumps(report, indent=2))
    elif fmt == "csv":
        print("name,species,total_waterings,last_watered")
        for p in report["plants"]:
            print(f"{p['name']},{p['species']},{p['total_waterings']},{p['last_watered'] or ''}")
    else:
        print(f"Growth report – {report['generated']}")
        print(f"Total plants tracked: {report['total_plants']}\n")
        for p in report["plants"]:
            print(f"  {p['name']} ({p['species']})")
            print(f"    Waterings: {p['total_waterings']}, last on {p['last_watered'] or 'never'}")
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="growforme",
        description="Track and manage your plant growth.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        metavar="FILE",
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )

    sub = parser.add_subparsers(dest="command", metavar="command")

    # add
    p_add = sub.add_parser("add", help="Add a new plant")
    p_add.add_argument("--name", required=True, help="Common name for the plant")
    p_add.add_argument("--species", default="", help="Scientific species name")

    # list
    sub.add_parser("list", help="List all tracked plants")

    # water
    p_water = sub.add_parser("water", help="Record a watering event")
    p_water.add_argument("--name", required=True, help="Name of the plant to water")

    # report
    p_report = sub.add_parser("report", help="Generate a growth report")
    p_report.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default=None,
        help="Output format (overrides config setting)",
    )

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    cfg = load_config(args.config)

    dispatch = {
        "add": cmd_add,
        "list": cmd_list,
        "water": cmd_water,
        "report": cmd_report,
    }
    return dispatch[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
