# Touchline

A Python-based football management game simulation engine inspired by Football Manager. This project simulates football matches with realistic player and team behaviors, tactical AI, and match physics.

## Features

- Player and team modeling with realistic attributes
- Real-time match simulation engine with tactical AI
- Event-based gameplay mechanics
- Defensive principles of play (pressing, compactness, cover & balance)
- Attacking patterns (width, depth, penetration)
- Statistical analysis and match reports
- Optional pygame-based visualization

## Setup

1. Create and activate the virtual environment:
```bash
uv venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
uv pip install -e .
```

## Project Structure

```
touchline/
├── touchline/
│   ├── models/      # Player, team, and match classes
│   ├── engine/      # Simulation logic and physics
│   ├── utils/       # Helper functions and generators
│   └── visualizer/  # Optional pygame visualization
├── tests/           # Unit tests
├── tools/           # Development and debugging scripts
└── pyproject.toml   # Project configuration and dependencies
```

## Running

Run a match simulation:
```bash
python -m touchline.main
```

## Running Tests

```bash
uv run pytest
```
