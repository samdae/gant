"""Keep one foreground research invocation and all its descendants inside a time budget."""

import ctypes
import os
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _windows_job(proc):
    """Close-on-exit job. The child waits for stdin until assignment is complete."""
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", Basic),
            ("IoInfo", ctypes.c_uint64 * 6),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = (
            0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not api.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not api.AssignProcessToJobObject(handle, int(proc._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        yield
    finally:
        api.CloseHandle(handle)


@contextmanager
def _posix_group(proc):
    try:
        yield
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def bounded_run(command, payload, timeout, label):
    env = dict(os.environ, PYTHONUTF8="1")
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (root, env.get("PYTHONPATH"))))
    windows = os.name == "nt"
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
        start_new_session=not windows,
        creationflags=subprocess.CREATE_NO_WINDOW if windows else 0,
    )
    try:
        with _windows_job(proc) if windows else _posix_group(proc):
            output, _ = proc.communicate(payload, timeout=timeout)
        if proc.returncode:
            raise RuntimeError(f"{label} subprocess failed")
        return output
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"{label} exceeded its time budget") from exc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate()
