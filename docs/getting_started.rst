Getting Started
===============

.. contents:: Table of Contents
   :depth: 2
   :local:

Installation
------------

1. Create and activate a virtual environment (optional but recommended).
2. Install the project in editable mode with its dependencies::

      pip install -e .[dev]

3. Install the documentation extras::

      pip install sphinx sphinx-rtd-theme

Building the Docs
-----------------

Inside the ``docs`` directory run::

    make html

The generated site will be placed in ``_build/html``. Open ``index.html`` in a
browser to view the rendered documentation.

Next Steps
----------

* Review :doc:`api/index` for modules you can import and extend.
* Consult the README at the repository root for simulation usage examples.
