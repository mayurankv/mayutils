"""Visualisation utilities for plots, charts, and notebook rendering.

This package gathers the visual output layer of ``mayutils``, bringing
together helpers for constructing graphs, rendering rich output to the
console, and configuring Jupyter notebook display. It provides a common
surface for producing interactive and static figures from data structures
used elsewhere in the library while keeping optional dependencies behind
clearly scoped extras.

Submodules
----------
console
    Console rendering utilities backed by ``rich`` and ``unicodeit`` for
    formatted text, tables, and mathematical notation in terminals.
graphs
    Chart builders for plotly and matplotlib, gated behind the
    ``plotting`` extra.
notebook
    Jupyter notebook display configuration and helpers, gated behind the
    ``notebook`` extra.
"""
