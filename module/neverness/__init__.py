import os

_sys32 = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
_path_value = os.environ.get("PATH", "")
_path_entries = [p for p in _path_value.split(os.pathsep) if p]
_norm_sys32 = os.path.normcase(os.path.normpath(_sys32))
_has_sys32 = any(os.path.normcase(os.path.normpath(p)) == _norm_sys32 for p in _path_entries)
if os.path.isdir(_sys32) and not _has_sys32:
    os.environ["PATH"] = _path_value + (os.pathsep if _path_value else "") + _sys32

text_white_color = {"r": (244, 255), "g": (244, 255), "b": (244, 255)}
text_black_color = {"r": (0, 50), "g": (0, 50), "b": (0, 50)}
