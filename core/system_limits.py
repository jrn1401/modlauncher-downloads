"""Ressourcen-Begrenzung des Launchers selbst (CPU-Priorität, Kerne, Arbeitsspeicher).

Das betrifft nur diesen Prozess, nicht den ganzen PC und nicht andere Programme.
Eine GPU-Begrenzung gibt es nicht: Das Programm nutzt die Grafikkarte nicht.
Alles ist best effort: Was das Betriebssystem nicht erlaubt, wird als Hinweis zurückgegeben.
"""
import ctypes
import os
import sys

IS_WIN = sys.platform.startswith("win")
MIN_RAM_MB = 512
_job = None


def cpu_count() -> int:
    return os.cpu_count() or 1


def total_ram_mb() -> int | None:
    try:
        if IS_WIN:
            from ctypes import wintypes  # noqa: F401

            class MEMSTATUS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MEMSTATUS()
            st.dwLength = ctypes.sizeof(MEMSTATUS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullTotalPhys // (1024 * 1024))
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) // 1024
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)
    except Exception:
        return None


def process_ram_mb() -> int | None:
    try:
        if IS_WIN:
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return int(pmc.WorkingSetSize // (1024 * 1024))
        if sys.platform.startswith("linux"):
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) // 1024
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(rss // (1024 * 1024)) if sys.platform == "darwin" else int(rss // 1024)
    except Exception:
        return None


def _win_priority(low: bool) -> None:
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    if not k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000 if low else 0x20):  # BELOW_NORMAL / NORMAL
        raise OSError("SetPriorityClass fehlgeschlagen")


def _win_affinity(mask: int) -> None:
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    if not k32.SetProcessAffinityMask(k32.GetCurrentProcess(), mask):
        raise OSError("SetProcessAffinityMask fehlgeschlagen")


def _win_memory_limit(mb: int) -> None:
    """Begrenzt den (reservierten) Arbeitsspeicher dieses Prozesses über ein Job-Objekt. 0 = aufheben."""
    global _job
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    if _job is None:
        _job = k32.CreateJobObjectW(None, None)
        if not _job:
            raise OSError("Job-Objekt konnte nicht erstellt werden")
        if not k32.AssignProcessToJobObject(_job, k32.GetCurrentProcess()):
            _job = None
            raise OSError("Prozess konnte dem Job-Objekt nicht zugewiesen werden")
    info = EXTENDED()
    if mb > 0:
        info.BasicLimitInformation.LimitFlags = 0x100          # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = mb * 1024 * 1024
    if not k32.SetInformationJobObject(_job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # ExtendedLimitInformation
        raise OSError("Speicherlimit konnte nicht gesetzt werden")


def apply(priority: str = "normal", cores: int = 0, ram_mb: int = 0) -> list[str]:
    """Wendet die Limits an. Gibt eine Liste von Hinweisen zurück (leer = alles geklappt)."""
    notes: list[str] = []
    low = priority == "low"
    try:
        if IS_WIN:
            _win_priority(low)
        else:
            os.setpriority(os.PRIO_PROCESS, 0, 10 if low else 0)
    except Exception:
        notes.append("Normale Priorität kann erst nach einem Neustart wiederhergestellt werden." if not low
                     else "Die Priorität konnte nicht geändert werden.")

    total = cpu_count()
    n = cores if 0 < cores < total else total
    try:
        if IS_WIN:
            _win_affinity((1 << n) - 1)
        elif hasattr(os, "sched_setaffinity"):
            os.sched_setaffinity(0, set(range(n)))
        elif cores:
            notes.append("Die Kernbegrenzung wird auf diesem System nicht unterstützt (z. B. macOS).")
    except Exception:
        notes.append("Die Kernbegrenzung konnte nicht gesetzt werden.")

    if ram_mb:
        if not IS_WIN:
            notes.append("Das RAM-Limit gibt es nur unter Windows.")
        elif ram_mb < MIN_RAM_MB:
            notes.append(f"RAM-Limit nicht gesetzt: mindestens {MIN_RAM_MB} MB nötig, sonst stürzt das Programm ab.")
        else:
            try:
                _win_memory_limit(ram_mb)
            except Exception as exc:
                notes.append(f"RAM-Limit konnte nicht gesetzt werden: {exc}")
    elif IS_WIN and _job is not None:
        try:
            _win_memory_limit(0)
        except Exception:
            notes.append("Das RAM-Limit konnte nicht aufgehoben werden (Neustart nötig).")
    return notes
