Getting Started
===============

.. contents:: Table of Contents
   :depth: 2
   :local:

Prerequisites
-------------

* Python 3.12 or newer (``uv`` will create and manage the virtual environment).
* ``uv`` package manager installed (`installation guide <https://docs.astral.sh/uv/getting-started/installation/>`_).
* Optional: a modern GPU if you plan to extend the visualizer, though the
  simulator itself is CPU-bound.

Project Setup
-------------

1. Clone the repository (replace the URL if you work from a fork)::

      git clone https://github.com/WelshDragon/touchline.git
      cd football-simulator

2. Install dependencies with ``uv`` (creates ``.venv/`` automatically)::

      uv sync --group dev

   This installs the core simulator plus the development extras (tests, docs,
   linting). To inspect the managed environments run ``uv venv list``.

3. Activate the environment when you need manual shell access (optional)::

      source .venv/bin/activate

   On Windows use ``.venv\Scripts\activate``. Alternatively prefix commands
   with ``uv run`` to execute inside the environment without activation.

Running the Simulator
---------------------

The quickest way to see the engine in action is to run the default match demo::

      uv run python touchline/main.py

By default this renders debug output to the console and writes detailed logs to
``debug_logs/``. When the optional ``pygame`` dependency is present the
visualiser launches automatically; otherwise the engine falls back to the
console-only mode.

Testing
-------

Unit tests live in the ``tests/`` directory. Execute the suite with::

            uv run pytest

Some tests rely on deterministic data under ``data/players.json``; keep that
file checked in for consistent results.

Building Documentation
----------------------

For project documentation (including these pages) ensure the ``dev`` group is
installed (``uv sync --group dev``) and build the HTML site from ``docs``::

      uv run -- make -C docs html

Open ``docs/_build/html/index.html`` in a browser to browse the generated docs.

Where to Go Next
----------------

* :doc:`api/index` lists the Python modules available for import.
* ``README.md`` at the repository root outlines gameplay features and command
      line options.
* Explore ``touchline/engine/`` to understand how the match loop, physics, and
      AI roles interact.
