"""The most a render may take of this computer (stickfleet.yaml, render.limits), so a long render never crowds out
whatever else the owner is doing. Their ask, Nov 12, 2026, of a film rendering in three Blender processes on every
core: "its taking a lot of my compute and memory. set a max to how much ur render can take".

Four things are capped: which processor cores a render's processes may run on, how many Blender processes run side by
side, their priority, so anything else open is served first, and the memory they may take together
(render.limits.memory_gb, split evenly between the processes running; Windows: a job object's limit on each process's
committed memory, inherited by whatever it starts). A heavy film runs fewer processes (film_parts --processes 1) and so
gets a bigger share, rather than failing: the cap protects the machine, it doesn't stop a film that fits. A capped render is
slower, and nothing else about it changes: the same frames come out; a film too big for its share fails in its own
process, with an out-of-memory error in its log, instead of taking the machine.

The memory cap came of the owner's question on Nov 19, 2026 ("whast using so much ram, i thought we capped blender ram
usage?"): the poop jet's real houses brought hundreds of large textures, and its two processes held about 8 GB of RAM
each with 38 GB committed, on a 31 GB machine, while the cap covered only cores, processes and priority.
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


def memory_gb(config, share: int = 1) -> float | None:
    """How much memory one of `share` render processes running side by side may commit, in GB: render.limits.memory_gb
    (all of them together) split evenly; unset = no cap."""
    asked = settings(config).get("memory_gb")
    return float(asked) / max(1, share) if asked else None


def _cap_memory(proc, gb: float) -> None:
    """Windows: puts the process in a job object whose limit on each process's committed memory is `gb`. Whatever it
    starts joins the job too. The job's handle is kept on the process object, so the cap lasts as long as it does."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class Io(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("Basic", Basic), ("Io", Io), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.windll.kernel32
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = k32.CreateJobObjectW(None, None)
    info = Extended()
    info.Basic.LimitFlags = 0x100                    # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    info.ProcessMemoryLimit = int(gb * 1024 ** 3)
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):      # 9: extended limits
        raise OSError("SetInformationJobObject failed")
    if not k32.AssignProcessToJobObject(job, int(proc._handle)):
        raise OSError("AssignProcessToJobObject failed")
    proc._memory_job = job


def start(config, cmd, share: int = 1, **kwargs) -> subprocess.Popen:
    """subprocess.Popen(cmd, **kwargs) under the limits: below normal priority (unless render.limits.priority is
    `normal`), held to the allowed cores and, on Windows, to its share of render.limits.memory_gb of committed memory, as one
    of `share` processes side by side. Whatever the process starts itself inherits all three."""
    low = settings(config).get("priority", "below_normal") != "normal"
    have, allowed = os.cpu_count() or 1, cores(config)
    cap = memory_gb(config, share)
    if sys.platform == "win32":
        if low:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.BELOW_NORMAL_PRIORITY_CLASS
        proc = subprocess.Popen(cmd, **kwargs)
        if cap:
            try:
                _cap_memory(proc, cap)
            except Exception as e:     # say so: an uncapped render is what the owner asked never to happen
                print(f"render limits: couldn't cap this process's memory at {cap} GB ({e})", flush=True)
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
