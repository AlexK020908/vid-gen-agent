"""The most a render may take of this computer (stickfleet.yaml, render.limits), so a long render never crowds out
whatever else the owner is doing. Their ask, Nov 12, 2026, of a film rendering in three Blender processes on every
core: "its taking a lot of my compute and memory. set a max to how much ur render can take".

Three things are capped: which processor cores a render's processes may run on, how many Blender processes run side by
side (each holds about 3 GB of memory with a film's scene loaded), and their priority, so anything else open is served
first. A capped render is slower, and nothing else about it changes: the same frames come out.
"""
from __future__ import annotations

import os
import subprocess
import sys


def settings(config=None) -> dict:
    """`config`'s render.limits, or the ones on disk when the caller has no config to hand (Remotion's runner)."""
    if config is None:
        from core import config as cfg
        config = cfg.load()
    return (getattr(config, "render", None) or {}).get("limits") or {}


def cores(config) -> int:
    """How many of this machine's logical processors a render may use (render.limits.cores; unset = all of them)."""
    have = os.cpu_count() or 1
    asked = settings(config).get("cores")
    return max(1, min(have, int(asked))) if asked else have


def processes(config) -> int:
    """How many Blender processes a film rendered in parts may run at once (render.limits.processes; unset = 1)."""
    return max(1, int(settings(config).get("processes") or 1))


def threads(config, share: int = 1) -> int:
    """Blender's `-t` for one of `share` processes running side by side: the allowed cores, split between them."""
    return max(1, cores(config) // max(1, share))


def mask(count: int, have: int) -> int:
    """The last `count` of `have` logical processors, as an affinity mask: the first ones stay free for everything else."""
    count = max(1, min(count, have))
    return ((1 << count) - 1) << (have - count)


def start(config, cmd, **kwargs) -> subprocess.Popen:
    """subprocess.Popen(cmd, **kwargs) under the limits: below normal priority (unless render.limits.priority is
    `normal`) and held to the allowed cores. Whatever the process starts itself inherits both."""
    low = settings(config).get("priority", "below_normal") != "normal"
    have, allowed = os.cpu_count() or 1, cores(config)
    if sys.platform == "win32":
        if low:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        proc = subprocess.Popen(cmd, **kwargs)
        if allowed < have:
            try:
                import ctypes
                from ctypes import wintypes
                hold = ctypes.windll.kernel32.SetProcessAffinityMask
                hold.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
                hold(int(proc._handle), mask(allowed, have))
            except Exception:          # a render that can't be held to its cores still renders
                pass
        return proc
    proc = subprocess.Popen(cmd, **kwargs)
    try:
        if allowed < have and hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(proc.pid, set(range(have - allowed, have)))
        if low and hasattr(os, "setpriority"):
            os.setpriority(os.PRIO_PROCESS, proc.pid, 10)
    except OSError:
        pass
    return proc
