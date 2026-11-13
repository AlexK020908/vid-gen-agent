"""render/limits.py: the ceiling on what a render may take of the computer, and render/film_parts.py's frame check."""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from render import film_parts, limits


def cfg(**limit):
    return SimpleNamespace(render={"limits": limit})


def test_cores_are_what_was_asked_and_never_more_than_the_machine_has():
    have = os.cpu_count()
    assert limits.cores(cfg(cores=1)) == 1
    assert limits.cores(cfg(cores=10_000)) == have
    assert limits.cores(cfg()) == have                       # unset: all of them
    assert limits.cores(SimpleNamespace(render={})) == have


def test_processes_side_by_side_share_the_cores():
    assert limits.processes(cfg(processes=2)) == 2
    assert limits.processes(cfg()) == 1
    assert limits.threads(cfg(cores=1), 2) == 1               # never none
    if os.cpu_count() >= 4:
        assert limits.threads(cfg(cores=4), 2) == 2


def test_the_mask_is_the_last_cores_so_the_first_stay_free():
    assert limits.mask(12, 24) == 0xFFF000
    assert limits.mask(24, 24) == 0xFFFFFF
    assert limits.mask(1, 4) == 0b1000
    assert limits.mask(9, 4) == 0b1111                        # more than there are: all


@pytest.mark.skipif(sys.platform != "win32" or (os.cpu_count() or 1) < 2, reason="Windows priorities and affinity")
def test_a_started_process_is_below_normal_and_held_to_its_cores():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.GetPriorityClass.argtypes = [wintypes.HANDLE]
    k32.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    proc = limits.start(cfg(cores=1), [sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        own, whole = ctypes.c_size_t(), ctypes.c_size_t()
        assert k32.GetProcessAffinityMask(int(proc._handle), ctypes.byref(own), ctypes.byref(whole))
        assert own.value == limits.mask(1, os.cpu_count())
        assert k32.GetPriorityClass(int(proc._handle)) == subprocess.BELOW_NORMAL_PRIORITY_CLASS
    finally:
        proc.kill()
        proc.wait()
    proc = limits.start(cfg(priority="normal"), [sys.executable, "-c", "import time; time.sleep(20)"])
    try:
        assert k32.GetPriorityClass(int(proc._handle)) == subprocess.NORMAL_PRIORITY_CLASS
    finally:
        proc.kill()
        proc.wait()


def test_a_frame_that_wont_open_is_made_again(tmp_path):
    Image.new("RGB", (8, 8), "red").save(tmp_path / "f_0001.png")
    whole = (tmp_path / "f_0001.png").read_bytes()
    (tmp_path / "f_0002.png").write_bytes(whole[: len(whole) // 2])          # a render killed while writing it
    assert film_parts.missing(tmp_path, [1, 2, 3]) == [2, 3]
    assert not (tmp_path / "f_0002.png").exists()
    assert (tmp_path / "f_0001.png").exists()
