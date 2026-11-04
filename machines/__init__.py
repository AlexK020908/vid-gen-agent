"""Machines for the machine shorts (SHORTS.md): each a JSON spec of named parts that blender/kit.py builds.

`spec.check()` is the authority on the format and runs before Blender is ever started, so a bad spec comes back
as a list of problems rather than a broken render. The specs in machines/specs/ are ours to commit: generic
machines, not any one video's shots.
"""
