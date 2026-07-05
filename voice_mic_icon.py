#!/usr/bin/env python3
"""Native draggable mic icon that types Vietnamese speech into the selected field."""

from __future__ import annotations

import ctypes
import audioop
import concurrent.futures
import hashlib
import json
import math
import msvcrt
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import winsound
from ctypes import wintypes
from pathlib import Path

import os
import sys
import tempfile
import wave

import speech_recognition as sr

_whisper = None
try:
    import webrtcvad
except Exception:
    webrtcvad = None

try:
    from pywinauto import Desktop
except Exception:
    Desktop = None


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
STATE_FILE = APP_DIR / "mic-position.json"
TARGETS_FILE = APP_DIR / "voice-targets.json"
SETTINGS_FILE = APP_DIR / "voice-mic-settings.json"
CONTEXT_FILE = APP_DIR / "voice-context.json"
LOG_FILE = APP_DIR / "voice-mic.log"
LOCK_FILE = APP_DIR / "voice-mic.lock"
LAST_TRANSCRIPT_FILE = APP_DIR / "voice-last.txt"
TRANSCRIPT_HISTORY_FILE = APP_DIR / "voice-transcripts.jsonl"
LAST_AUDIO_FILE = APP_DIR / "voice-last.wav"
APP_TITLE = "Vietnamese Voice Mic"
APP_VERSION = "1.1.0"
APP_BUILD = "mic-recovery-clipboard-2026-07-05"
SIZE = 38
CORE = 26
HUD_WIDTH = 220
HUD_HEIGHT = 44
HUD_GAP = 8
PARTICLE_EFFECT_WIDTH = 300
PARTICLE_EFFECT_HEIGHT = 300
PARTICLE_EFFECT_DEFAULT_COUNT = 180
PARTICLE_EFFECT_GAP = 18
HIDE_FLOATING_MIC_BUTTON = True
SHOW_FLOATING_MIC_ICON = False
STREAM_PHRASE_SECONDS = 7
MAX_SPEECH_CHUNK_SECONDS = 18.0
MIN_SPEECH_CHUNK_SECONDS = 0.45
SILENCE_END_SECONDS = 2.0
MAX_UNRECOGNIZED_BEFORE_STOP = 3
VOICE_START_FRAMES = 1
VAD_MIN_THRESHOLD = 220
VAD_NOISE_MULTIPLIER = 1.35
VAD_NOISE_MARGIN = 160
VAD_P90_MARGIN = 60
VAD_MAX_THRESHOLD = 1800
VAD_ACTIVITY_MARGIN = 80
VAD_ACTIVITY_MULTIPLIER = 1.12
WEBRTC_RMS_MIN_GATE = 220
WEBRTC_RMS_NOISE_RATIO = 0.65
WEBRTC_VAD_AGGRESSIVENESS = 1
WEBRTC_VAD_SAMPLE_RATE = 16000
WEBRTC_SHORT_VOICE_END_SECONDS = 1.45
RMS_SHORT_VOICE_END_SECONDS = 1.65
LONG_VOICE_AFTER_SECONDS = 9.0
WEBRTC_VOICE_END_SECONDS = 2.05
RMS_VOICE_END_SECONDS = 2.3
MIN_CAPTURE_BEFORE_AUTO_STOP_SECONDS = 1.2
VAD_SOFT_ACTIVITY_MARGIN = 120
VAD_SOFT_ACTIVITY_MULTIPLIER = 1.08
GOOGLE_RECOGNITION_TIMEOUT_SECONDS = 20.0
GOOGLE_SINGLE_PASS_MAX_SECONDS = 28.0
GOOGLE_LONG_CHUNK_SECONDS = 24.0
GOOGLE_CHUNK_BOUNDARY_SEARCH_SECONDS = 2.5
GOOGLE_CHUNK_MIN_SECONDS = 8.0
GOOGLE_CHUNK_MIN_TAIL_SECONDS = 4.0
GOOGLE_MIN_RETRY_CHUNK_SECONDS = 4.0
GOOGLE_CHUNK_RETRY_ATTEMPTS = 2
TRANSPARENT = "#ff00ff"
LISTEN_CHUNK_SECONDS = 8
LISTEN_TIMEOUT_SECONDS = 8.0
AUTO_LISTEN_TIMEOUT_SECONDS = 18.0
AUTO_AFTER_SPEECH_TIMEOUT_SECONDS = 2.8
AUTO_PHRASE_LIMIT_SECONDS = 300
INITIAL_NO_SPEECH_TIMEOUT_SECONDS = 12.0
AUTO_CLICK_POLL_SECONDS = 0.035
AUTO_CLICK_COOLDOWN_SECONDS = 0.8
AUTO_START_FROM_CHAT_CLICK = False
ALT_CLICK_ONLY = True
CLICK_DETECT_RETRY_MS = (90, 220, 420, 700)
ARM_TARGET_SECONDS = 60.0
CHAT_BOTTOM_FRACTION = 0.14
CHAT_BOTTOM_MAX_HEIGHT = 110
CHAT_HINT_FRACTION = 0.25
STRICT_CHAT_BOTTOM_MAX_HEIGHT = 110
STRICT_CHAT_WIDTH_FRACTION = 0.65
CARET_CLICK_RADIUS = 60
LEARNED_TARGET_RADIUS = 80
ERROR_ALREADY_EXISTS = 183
SINGLE_INSTANCE_MUTEX_NAME = "Local\\VietnameseVoiceMicSingleInstance"
SINGLE_INSTANCE_MUTEX_HANDLE = None
SINGLE_INSTANCE_LOCK_FILE_HANDLE = None

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
UIA_DESKTOP = Desktop(backend="uia") if Desktop else None

HWND_TOPMOST = wintypes.HWND(-1)
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_M = 0x4D
VK_V = 0x56
VK_LBUTTON = 0x01
VK_BACK = 0x08
VK_1 = 0x31
VK_2 = 0x32
VK_F2 = 0x71
VK_ESCAPE = 0x1B
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
VOICE_HOTKEY_NAME = "Ctrl+Alt+M"

if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_longlong):
    user32.GetWindowLongPtrW.restype = ctypes.c_longlong
    user32.SetWindowLongPtrW.restype = ctypes.c_longlong
else:
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.restype = ctypes.c_long

kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.GetLastError.restype = wintypes.DWORD
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
user32.GetGUIThreadInfo.restype = wintypes.BOOL


try:
    user32.SetProcessDPIAware()
except Exception:
    pass


def load_position() -> tuple[int, int]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return int(data.get("x", 900)), int(data.get("y", 895))
    except Exception:
        return 900, 895


def save_position(x: int, y: int) -> None:
    try:
        STATE_FILE.write_text(json.dumps({"x": x, "y": y}), encoding="utf-8")
    except Exception:
        return


def load_voice_targets() -> dict[str, tuple[int, int]]:
    try:
        data = json.loads(TARGETS_FILE.read_text(encoding="utf-8"))
        targets: dict[str, tuple[int, int]] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                targets[str(key)] = (int(value["x"]), int(value["y"]))
        return targets
    except Exception:
        return {}


def save_voice_targets(targets: dict[str, tuple[int, int]]) -> None:
    try:
        data = {key: {"x": point[0], "y": point[1]} for key, point in targets.items()}
        TARGETS_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        return


def load_settings() -> dict[str, object]:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def microphone_name_score(name: str) -> int:
    lower = name.lower()
    score = 0
    if any(word in lower for word in ("microphone", "mic", "input", "capture")):
        score += 20
    if "headset" in lower and "hands-free" in lower:
        score += 10
    if any(word in lower for word in ("headphones", "speakers", "output", "nvidia", "stereo")):
        score -= 50
    return score


def first_matching_microphone(names: list[str], needle: str) -> tuple[int, str] | None:
    matches = [
        (microphone_name_score(name), index, name)
        for index, name in enumerate(names)
        if needle in name.lower()
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    _score, index, name = matches[0]
    return index, name


def select_microphone_device(settings: dict[str, object]) -> tuple[int | None, str]:
    preferred = str(settings.get("preferred_microphone", "") or "").strip().lower()
    fallback_hints = settings.get("microphone_name_hints", ["UGREEN Camera 2K", "USB Audio Device", "BKD-11"])
    hints = [str(h).lower() for h in fallback_hints if str(h).strip()]
    names = sr.Microphone.list_microphone_names()

    if preferred:
        match = first_matching_microphone(names, preferred)
        if match:
            return match

    for hint in hints:
        match = first_matching_microphone(names, hint)
        if match:
            return match

    return None, "system default"


def set_clipboard_text(text: str) -> None:
    data = text.encode("utf-16-le") + b"\x00\x00"
    hglob = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not hglob:
        raise OSError("GlobalAlloc failed")
    locked = kernel32.GlobalLock(hglob)
    if not locked:
        kernel32.GlobalFree(hglob)
        raise OSError("GlobalLock failed")
    ctypes.memmove(locked, data, len(data))
    kernel32.GlobalUnlock(hglob)
    if not user32.OpenClipboard(None):
        kernel32.GlobalFree(hglob)
        raise OSError("OpenClipboard failed")
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, hglob):
            kernel32.GlobalFree(hglob)
            raise OSError("SetClipboardData failed")
        hglob = None
    finally:
        user32.CloseClipboard()


def get_clipboard_text() -> str:
    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        locked = kernel32.GlobalLock(handle)
        if not locked:
            return ""
        try:
            return ctypes.wstring_at(locked)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text_retry(text: str, attempts: int = 8, delay: float = 0.08) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            set_clipboard_text(text)
            return True
        except OSError as exc:
            log(f"clipboard set retry | attempt={attempt} | {exc}")
            time.sleep(delay)
    return False


def keybd(vk: int, flags: int = 0) -> None:
    user32.keybd_event(vk, 0, flags, 0)


def send_ctrl_v() -> None:
    keybd(VK_CONTROL)
    time.sleep(0.02)
    keybd(VK_V)
    time.sleep(0.03)
    keybd(VK_V, KEYEVENTF_KEYUP)
    time.sleep(0.02)
    keybd(VK_CONTROL, KEYEVENTF_KEYUP)


def focus_locked_target(target_hwnd: int, target_point: tuple[int, int] | None, click_to_focus: bool = True) -> int:
    if target_hwnd:
        user32.SetForegroundWindow(target_hwnd)
        time.sleep(0.12)
    if click_to_focus and target_point:
        user32.SetCursorPos(target_point[0], target_point[1])
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.18)
    return foreground_window()


def beep_async(kind: str) -> None:
    patterns = {
        "start": ((1200, 60),),
        "chunk": ((980, 35),),
        "done": ((880, 70), (1180, 45)),
        "stop": ((620, 55),),
        "error": ((400, 80), (300, 80)),
    }

    def worker() -> None:
        for freq, duration in patterns.get(kind, patterns["chunk"]):
            winsound.Beep(freq, duration)
            time.sleep(0.025)

    threading.Thread(target=worker, daemon=True).start()


def log(message: str) -> None:
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(f"{stamp} {message}\n")
    except Exception:
        return


def save_last_transcript(text: str, metadata: dict[str, object] | None = None) -> None:
    text = text.strip()
    if not text:
        return
    metadata = metadata or {}
    record = {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "text": text,
        **metadata,
    }
    try:
        LAST_TRANSCRIPT_FILE.write_text(text, encoding="utf-8")
    except Exception as exc:
        log(f"last transcript save error: {type(exc).__name__}: {exc}")
    try:
        with TRANSCRIPT_HISTORY_FILE.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        log(f"transcript history save error: {type(exc).__name__}: {exc}")


def save_last_audio(audio: sr.AudioData, metadata: dict[str, object] | None = None) -> None:
    metadata = metadata or {}
    try:
        with wave.open(str(LAST_AUDIO_FILE), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(audio.sample_width)
            wav.setframerate(audio.sample_rate)
            wav.writeframes(audio.frame_data)
        log(
            f"last audio saved | path={LAST_AUDIO_FILE.name} | "
            f"bytes={len(audio.frame_data)} | metadata={metadata}"
        )
    except Exception as exc:
        log(f"last audio save error: {type(exc).__name__}: {exc}")


def keep_transcript_on_clipboard(text: str, reason: str) -> bool:
    ok = set_clipboard_text_retry(text)
    if ok:
        log(f"recovery clipboard set | reason={reason} | text={text[:80]}")
    else:
        log(f"recovery clipboard failed | reason={reason} | text={text[:80]}")
    return ok


def acquire_single_instance_lock() -> bool:
    global SINGLE_INSTANCE_MUTEX_HANDLE, SINGLE_INSTANCE_LOCK_FILE_HANDLE
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_file = LOCK_FILE.open("a+b")
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(str(os.getpid()).encode("ascii"))
        lock_file.flush()
        SINGLE_INSTANCE_LOCK_FILE_HANDLE = lock_file
    except OSError:
        log("another Vietnamese Voice Mic instance is already running; exiting via file lock")
        return False

    handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
    if not handle:
        log("single instance lock failed; continuing without lock")
        return True
    SINGLE_INSTANCE_MUTEX_HANDLE = handle
    if int(kernel32.GetLastError()) == ERROR_ALREADY_EXISTS:
        log("another Vietnamese Voice Mic instance is already running; exiting")
        return False
    return True


def read_audio_chunk(stream: object, chunk_size: int) -> bytes:
    try:
        return stream.read(chunk_size, exception_on_overflow=False)
    except TypeError:
        return stream.read(chunk_size)


def create_voice_vad(sample_rate: int, sample_width: int) -> dict[str, object] | None:
    if webrtcvad is None or sample_width != 2:
        return None
    return {
        "vad": webrtcvad.Vad(WEBRTC_VAD_AGGRESSIVENESS),
        "source_rate": sample_rate,
        "target_rate": WEBRTC_VAD_SAMPLE_RATE,
        "resample_state": None,
        "pending": b"",
    }


def vad_detects_speech(vad_state: dict[str, object] | None, data: bytes, sample_width: int) -> bool | None:
    if vad_state is None:
        return None
    target_rate = int(vad_state["target_rate"])
    source_rate = int(vad_state["source_rate"])
    payload = data
    if source_rate != target_rate:
        try:
            payload, vad_state["resample_state"] = audioop.ratecv(
                data,
                sample_width,
                1,
                source_rate,
                target_rate,
                vad_state.get("resample_state"),
            )
        except Exception:
            return None
    pending = bytes(vad_state.get("pending", b"")) + payload
    frame_bytes = int(target_rate * 30 / 1000) * sample_width
    if frame_bytes <= 0 or len(pending) < frame_bytes:
        vad_state["pending"] = pending
        return None
    hits = 0
    total = 0
    consumed = 0
    vad = vad_state["vad"]
    for start in range(0, len(pending) - frame_bytes + 1, frame_bytes):
        frame = pending[start:start + frame_bytes]
        try:
            if vad.is_speech(frame, target_rate):
                hits += 1
            total += 1
            consumed = start + frame_bytes
        except Exception:
            return None
    vad_state["pending"] = pending[consumed:]
    if total == 0:
        return None
    return hits > 0


def calculate_vad_threshold(noise_samples: list[int]) -> tuple[int, int, int, int]:
    if not noise_samples:
        return VAD_MIN_THRESHOLD, 140, 50, 50
    samples = sorted(noise_samples)
    median = samples[len(samples) // 2]
    p90 = samples[min(len(samples) - 1, int(len(samples) * 0.9))]
    threshold = max(
        VAD_MIN_THRESHOLD,
        int(median * VAD_NOISE_MULTIPLIER),
        median + VAD_NOISE_MARGIN,
        p90 + VAD_P90_MARGIN,
    )
    threshold = min(threshold, VAD_MAX_THRESHOLD)
    activity_threshold = max(
        140,
        int(median * VAD_ACTIVITY_MULTIPLIER),
        median + VAD_ACTIVITY_MARGIN,
    )
    activity_threshold = min(activity_threshold, max(VAD_MIN_THRESHOLD, threshold - 80))
    return threshold, activity_threshold, median, p90


def calculate_webrtc_rms_gate(noise_floor: int, speech_threshold: int) -> int:
    noise_gate = int(max(0, noise_floor) * WEBRTC_RMS_NOISE_RATIO)
    return max(WEBRTC_RMS_MIN_GATE, min(speech_threshold, noise_gate))


def count_transcript_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def format_speech_stats(text: str, duration_seconds: float) -> tuple[int, int, int, float]:
    words = count_transcript_words(text)
    chars = len(text)
    duration = max(0.1, duration_seconds)
    words_per_minute = int(round(words * 60 / duration)) if words else 0
    return words_per_minute, words, chars, duration


def parse_version(version: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(version or ""))
    return tuple(int(part) for part in parts[:4]) or (0,)


def is_newer_version(remote: str, current: str) -> bool:
    left = parse_version(remote)
    right = parse_version(current)
    size = max(len(left), len(right))
    return left + (0,) * (size - len(left)) > right + (0,) * (size - len(right))


def read_update_manifest(manifest_url: str) -> dict[str, object]:
    manifest_url = manifest_url.strip()
    if not manifest_url:
        return {}
    if re.match(r"^https?://", manifest_url, flags=re.IGNORECASE):
        with urllib.request.urlopen(manifest_url, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    path = Path(manifest_url.replace("file:///", "")).expanduser()
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_update_url(manifest_url: str, zip_url: str) -> str:
    if re.match(r"^https?://", zip_url, flags=re.IGNORECASE):
        return zip_url
    if re.match(r"^https?://", manifest_url, flags=re.IGNORECASE):
        return urllib.parse.urljoin(manifest_url, zip_url)
    manifest_path = Path(manifest_url.replace("file:///", "")).expanduser()
    return str((manifest_path.parent / zip_url).resolve())


def download_update_zip(zip_url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if re.match(r"^https?://", zip_url, flags=re.IGNORECASE):
        with urllib.request.urlopen(zip_url, timeout=60) as response, destination.open("wb") as file:
            shutil.copyfileobj(response, file)
        return
    shutil.copy2(Path(zip_url).expanduser(), destination)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_window_long(hwnd: int, index: int) -> int:
    if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_longlong):
        return int(user32.GetWindowLongPtrW(hwnd, index))
    return int(user32.GetWindowLongW(hwnd, index))


def set_window_long(hwnd: int, index: int, value: int) -> None:
    if ctypes.sizeof(ctypes.c_void_p) == ctypes.sizeof(ctypes.c_longlong):
        user32.SetWindowLongPtrW(hwnd, index, value)
    else:
        user32.SetWindowLongW(hwnd, index, value)


def make_tool_window(hwnd: int) -> None:
    ex_style = get_window_long(hwnd, GWL_EXSTYLE)
    ex_style |= WS_EX_TOOLWINDOW
    ex_style &= ~WS_EX_APPWINDOW
    set_window_long(hwnd, GWL_EXSTYLE, ex_style)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def paste_to_focused_field(
    text: str,
    root: tk.Tk,
    target_hwnd: int = 0,
    target_point: tuple[int, int] | None = None,
    restore_root: bool = True,
) -> None:
    text = text.strip()
    if not text:
        return
    if target_hwnd and not window_exists(target_hwnd):
        keep_transcript_on_clipboard(text, "target-closed")
        log(f"paste skipped: target window closed | hwnd={target_hwnd} | text={text[:120]}")
        return
    try:
        set_clipboard_text(text)
        time.sleep(0.08)
        log(f"clipboard set: {get_clipboard_text()[:80]}")
        root.withdraw()
        root.update_idletasks()
        time.sleep(0.12)
        focused_hwnd = focus_locked_target(target_hwnd, target_point, click_to_focus=True)
        send_ctrl_v()
        log(f"paste sent | hwnd={target_hwnd} | focused={focused_hwnd} | point={target_point}")
    finally:
        time.sleep(0.12)
        keep_transcript_on_clipboard(text, "after-paste")
        if restore_root:
            root.deiconify()
            root.lift()
            root.attributes("-topmost", True)


def left_button_down() -> bool:
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def voice_hotkey_down() -> bool:
    return key_down(VK_CONTROL) and key_down(VK_MENU) and key_down(VK_M)


def foreground_window() -> int:
    return int(user32.GetForegroundWindow())


def window_exists(hwnd: int) -> bool:
    return bool(hwnd and user32.IsWindow(hwnd))


def window_class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def stable_target_key(hwnd: int, point: tuple[int, int]) -> str:
    """Key á»•n Ä‘á»‹nh qua restart: class cá»­a sá»• + vá»‹ trÃ­ snap 40px."""
    cls = window_class_name(hwnd)
    sx, sy = (point[0] // 40) * 40, (point[1] // 40) * 40
    return f"{cls}|{sx}|{sy}"


def cursor_position() -> tuple[int, int]:
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def virtual_screen_rect() -> tuple[int, int, int, int]:
    left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        return 0, 0, 1920, 1080
    return left, top, left + width, top + height


def get_caret_screen_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    thread_id = user32.GetWindowThreadProcessId(hwnd, None)
    if not thread_id:
        return None

    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)) or not info.hwndCaret:
        return None

    left_top = wintypes.POINT(info.rcCaret.left, info.rcCaret.top)
    right_bottom = wintypes.POINT(info.rcCaret.right, info.rcCaret.bottom)
    if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(left_top)):
        return None
    if not user32.ClientToScreen(info.hwndCaret, ctypes.byref(right_bottom)):
        return None

    left, top = int(left_top.x), int(left_top.y)
    right, bottom = int(right_bottom.x), int(right_bottom.y)
    if left == right and top == bottom:
        return None
    return left, top, right, bottom


def rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    left, top, right, bottom = rect
    return (left + right) // 2, (top + bottom) // 2


def point_near_rect(point: tuple[int, int], rect: tuple[int, int, int, int], radius: int) -> bool:
    x, y = point
    left, top, right, bottom = rect
    nearest_x = min(max(x, left), right)
    nearest_y = min(max(y, top), bottom)
    return math.hypot(x - nearest_x, y - nearest_y) <= radius


def point_in_bottom_chat_zone(point: tuple[int, int], hwnd: int) -> bool:
    rect = window_rect(hwnd)
    if not rect:
        return False
    x, y = point
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width < 260 or height < 180:
        return False
    zone_height = min(int(height * CHAT_BOTTOM_FRACTION), CHAT_BOTTOM_MAX_HEIGHT)
    zone_top = bottom - zone_height
    return left <= x <= right and zone_top <= y <= bottom


def point_in_chat_hint_zone(point: tuple[int, int], hwnd: int) -> bool:
    rect = window_rect(hwnd)
    if not rect:
        return False
    x, y = point
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width < 260 or height < 180:
        return False
    zone_top = bottom - int(height * CHAT_HINT_FRACTION)
    return left <= x <= right and zone_top <= y <= bottom


def point_in_strict_chat_zone(point: tuple[int, int], hwnd: int) -> bool:
    rect = window_rect(hwnd)
    if not rect:
        return False
    x, y = point
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width < 260 or height < 180:
        return False
    zone_top = bottom - min(int(height * CHAT_BOTTOM_FRACTION), STRICT_CHAT_BOTTOM_MAX_HEIGHT)
    center = (left + right) / 2
    half_width = width * STRICT_CHAT_WIDTH_FRACTION / 2
    return center - half_width <= x <= center + half_width and zone_top <= y <= bottom


def best_paste_point(
    clicked_point: tuple[int, int],
    caret_rect: tuple[int, int, int, int] | None,
) -> tuple[int, int]:
    if caret_rect and point_near_rect(clicked_point, caret_rect, CARET_CLICK_RADIUS):
        return rect_center(caret_rect)
    return clicked_point


_RICH_INPUT_CLASSES = frozenset({
    "prosemirror", "tiptap", "ql-editor", "codemirror", "cm-content",
    "monaco-editor", "ace_editor", "notranslate", "public-draftstyleditor",
    "draftstyleditorroot",
})

_RICH_INPUT_CONTROL_TYPES = frozenset({"edit"})

# Class cá»­a sá»• Chrome/Electron â€” Ã´ chat náº±m á»Ÿ Ä‘Ã¡y
_BROWSER_WIN_CLASSES = frozenset({"Chrome_WidgetWin_1", "Chrome_WidgetWin_0"})
# Tá»« khÃ³a trong tÃªn UIA element gá»£i Ã½ Ä‘Ã¢y lÃ  Ã´ nháº­p liá»‡u
_INPUT_NAME_HINTS = frozenset({
    "write", "message", "compose", "type here", "input", "send", "prompt",
    "nháº­p", "soáº¡n", "chat", "reply", "your message",
})


def is_browser_bottom_input(hwnd: int, point: tuple[int, int]) -> bool:
    """Heuristic: click á»Ÿ 22% Ä‘Ã¡y cá»­a sá»• Chrome/Electron â†’ kháº£ nÄƒng cao lÃ  Ã´ chat."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    if buf.value not in _BROWSER_WIN_CLASSES:
        return False
    rect = window_rect(hwnd)
    if not rect:
        return False
    left, top, right, bottom = rect
    h = bottom - top
    if h <= 0:
        return False
    zone_top = bottom - int(h * 0.22)
    return zone_top <= point[1] <= bottom and left <= point[0] <= right


def uia_is_likely_input(point: tuple[int, int]) -> tuple[bool, str]:
    """Stricter check: only trigger on edit/document control types or known rich-text classes."""
    if UIA_DESKTOP is None:
        return False, "uia=unavailable"
    try:
        wrapper = UIA_DESKTOP.from_point(point[0], point[1])
        chain: list[str] = []
        current = wrapper
        for _ in range(8):
            info = current.element_info
            control_type = str(getattr(info, "control_type", "") or "").lower()
            class_name = str(getattr(info, "class_name", "") or "")
            name = str(getattr(info, "name", "") or "")
            auto_id = str(getattr(info, "automation_id", "") or "")
            chain.append(f"{control_type}:{class_name}:{name[:28]}:{auto_id[:28]}")
            # Match known rich input class substrings (case-insensitive)
            class_lower = class_name.lower()
            name_lower = name.lower()
            if control_type in _RICH_INPUT_CONTROL_TYPES:
                return True, " > ".join(chain)
            if any(rc in class_lower for rc in _RICH_INPUT_CLASSES):
                return True, " > ".join(chain)
            if any(hint in name_lower for hint in _INPUT_NAME_HINTS):
                return True, " > ".join(chain)
            parent = current.parent()
            if parent is None:
                break
            current = parent
        return False, " > ".join(chain)
    except Exception as exc:
        return False, f"uia-error={type(exc).__name__}"


def uia_text_input_at_point(point: tuple[int, int]) -> tuple[bool, str]:
    """Legacy wrapper kept for compatibility; delegates to uia_is_likely_input."""
    return uia_is_likely_input(point)


def ellipsize(text: str, limit: int = 86) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


_MOJIBAKE_MARKERS = ("Ãƒ", "Ã„", "Ã‚", "Ã¡Âº", "Ã¡Â»", "Ã†")
_TECH_TERM_PATTERNS = (
    (r"\bclau(?:de|d)?\s+code\b", "Claude Code"),
    (r"\bcode(?:x|ex)\b", "Codex"),
    (r"\bchat\s*gpt\b", "ChatGPT"),
    (r"\bopen\s*ai\b", "OpenAI"),
    (r"\bapi\b", "API"),
    (r"\bhtml\b", "HTML"),
    (r"\bcss\b", "CSS"),
    (r"\bjavascript\b|\bjava script\b", "JavaScript"),
    (r"\bpython\b", "Python"),
    (r"\bfast\s*api\b", "FastAPI"),
    (r"\bwhisper\b", "Whisper"),
    (r"\bvad\b", "VAD"),
    (r"\bwebrtc\b|\bweb rtc\b", "WebRTC"),
    (r"\bgoogle\b", "Google"),
    (r"\bfrontend\b|\bfront end\b|\bphá» ron ten\b", "frontend"),
    (r"\bbackend\b|\bback end\b|\bbÃ¡ch ken\b", "backend"),
    (r"\bworkflow\b|\bwork flow\b|\buá»‘c flow\b|\buá»‘t flow\b", "workflow"),
    (r"\bprompt\b|\bprÃ´m\b|\bprÃ´m pá»\b", "prompt"),
    (r"\bagent\b|\bÃ¢y giáº§n\b|\bÃ¢y dáº§n\b", "agent"),
    (r"\btemplate\b|\btem pá» lÃ©t\b|\btem plate\b", "template"),
    (r"\bformat\b|\bpho mÃ¡t\b|\bpho mat\b", "format"),
    (r"\bvoice\s*mic\b", "Voice Mic"),
    (r"\bspeech\s*to\s*text\b", "speech-to-text"),
)
_CONTEXT_TERM_BLOCKLIST = {
    "again",
    "anh",
    "ban",
    "build",
    "cao",
    "check",
    "cho",
    "click",
    "copy",
    "data",
    "demo",
    "download",
    "face",
    "hay",
    "hoa",
    "icon",
    "key",
    "khi",
    "keyword",
    "lai",
    "lan",
    "lau",
    "like",
    "line",
    "link",
    "live",
    "mai",
    "map",
    "min",
    "nam",
    "nghe",
    "nhanh",
    "note",
    "open",
    "plan",
    "play",
    "sai",
    "sao",
    "sau",
    "sit",
    "tab",
    "text",
    "thanh",
    "thay",
    "thu",
    "translate",
    "view",
    "voice",
    "website",
    "win",
    "xem",
    "xong",
}


def repair_mojibake(text: str) -> str:
    if not any(marker in text for marker in _MOJIBAKE_MARKERS):
        return text
    try:
        fixed = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return text
    return fixed if fixed.count("ï¿½") <= text.count("ï¿½") else text


def normalize_technical_terms(text: str) -> str:
    for pattern, replacement in _TECH_TERM_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def load_speech_cleanup_replacements() -> list[dict[str, object]]:
    try:
        settings = load_settings()
        replacements = settings.get("speech_cleanup_replacements", [])
        if isinstance(replacements, list):
            return [item for item in replacements if isinstance(item, dict)]
    except Exception:
        pass
    return []


def apply_custom_replacements(text: str) -> str:
    for item in load_speech_cleanup_replacements():
        pattern = str(item.get("pattern", "") or "")
        replacement = str(item.get("replacement", "") or "")
        if not pattern:
            continue
        try:
            if bool(item.get("regex", False)):
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            else:
                text = text.replace(pattern, replacement)
        except re.error as exc:
            log(f"cleanup replacement ignored | pattern={pattern!r} | error={exc}")
    return text


def load_voice_context() -> dict[str, int]:
    try:
        data = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
        terms = data.get("terms", {}) if isinstance(data, dict) else {}
        if isinstance(terms, dict):
            return {str(k): int(v) for k, v in terms.items() if str(k).strip()}
    except Exception:
        pass
    return {}


def save_voice_context(terms: dict[str, int]) -> None:
    try:
        sorted_terms = dict(sorted(terms.items(), key=lambda item: (-item[1], item[0]))[:300])
        CONTEXT_FILE.write_text(
            json.dumps({"terms": sorted_terms}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        log(f"voice context save error: {type(exc).__name__}: {exc}")


def configured_context_terms() -> list[str]:
    settings = load_settings()
    if not bool(settings.get("enable_context_memory", True)):
        return []
    terms = settings.get("speech_context_terms", [])
    if isinstance(terms, list):
        return [str(term).strip() for term in terms if str(term).strip()]
    return []


def context_terms(limit: int = 80) -> list[str]:
    if not bool(load_settings().get("enable_context_memory", True)):
        return []
    learned = load_voice_context()
    ranked = [term for term, _count in sorted(learned.items(), key=lambda item: (-item[1], item[0]))]
    merged: list[str] = []
    seen: set[str] = set()
    for term in configured_context_terms() + ranked:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            merged.append(term)
        if len(merged) >= limit:
            break
    return merged


def apply_context_terms(text: str) -> str:
    for term in context_terms():
        if not context_term_allowed(term):
            continue
        if len(term) < 2:
            continue
        pattern = r"\b" + re.escape(term) + r"\b"
        text = re.sub(pattern, term, text, flags=re.IGNORECASE)
    return text


def context_term_allowed(term: str) -> bool:
    key = term.strip().lower()
    if not key or key in _CONTEXT_TERM_BLOCKLIST:
        return False
    if len(term.strip()) < 3:
        return False
    return True


def should_learn_context_word(term: str) -> bool:
    if not context_term_allowed(term):
        return False
    if re.search(r"[0-9+#.-]", term):
        return True
    if term.isupper() and len(term) >= 2:
        return True
    if any(ch.isupper() for ch in term[1:]):
        return True
    return False


def learn_context_terms(text: str) -> None:
    if not bool(load_settings().get("enable_context_memory", True)):
        return
    candidates: set[str] = set()
    configured = configured_context_terms()
    for term in configured:
        if re.search(r"\b" + re.escape(term) + r"\b", text, flags=re.IGNORECASE):
            candidates.add(term)
    for match in re.finditer(r"(?<!\w)[A-Za-z][A-Za-z0-9+#.-]*(?!\w)", text):
        term = match.group(0).strip(" .,!?;:")
        if should_learn_context_word(term):
            candidates.add(term)
    for term in re.findall(r"\b(?:API|HTML|CSS|JavaScript|Python|Whisper|Google|VAD|WebRTC|OpenAI|ChatGPT|Codex|Claude Code|FastAPI|workflow|prompt|agent|template|format|frontend|backend|Voice Mic|speech-to-text|Google Speech Recognition)\b", text, flags=re.IGNORECASE):
        candidates.add(normalize_technical_terms(term))
    if not candidates:
        return
    terms = load_voice_context()
    for term in candidates:
        clean = cleanup_pass(term)
        if 2 <= len(clean) <= 48 and context_term_allowed(clean):
            terms[clean] = terms.get(clean, 0) + 1
    save_voice_context(terms)


def whisper_initial_prompt() -> str:
    terms = ", ".join(context_terms(60))
    base = (
        "L\u1eddi n\u00f3i ti\u1ebfng Vi\u1ec7t t\u1ef1 nhi\u00ean, "
        "c\u00f3 th\u1ec3 xen k\u1ebd ti\u1ebfng Anh/k\u1ef9 thu\u1eadt. "
        "Gi\u1eef \u0111\u00fang thu\u1eadt ng\u1eef, t\u00ean c\u00f4ng c\u1ee5 "
        "v\u00e0 ch\u00ednh t\u1ea3 ti\u1ebfng Vi\u1ec7t."
    )
    if terms:
        return f"{base} T\u1eeb kh\u00f3a hay d\u00f9ng: {terms}."
    return base


def cleanup_pass(text: str) -> str:
    text = normalize_technical_terms(text)
    text = apply_custom_replacements(text)
    text = apply_context_terms(text)
    text = re.sub(r"\b(Ã |á»|á»«|á»«m|á»m)\b[ ,]*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(mÃ¡y|mÃ y)\s+(?=lÃ m|táº¡o|viáº¿t|kiá»ƒm|thá»­|chÃ¨n|gá»­i|phÃ¢n|xem|cho)\b", "hÃ£y ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\w{2,})(?:\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_transcript(text: str) -> str:
    text = repair_mojibake(text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])(?=\S)", r"\1 ", text)
    text = text.strip(" \t\r\n\"'")

    junk_phrases = (
        "cáº£m Æ¡n cÃ¡c báº¡n Ä‘Ã£ theo dÃµi",
        "hÃ£y subscribe cho kÃªnh",
        "hÃ£y Ä‘Äƒng kÃ½ kÃªnh",
        "lá»i nÃ³i tiáº¿ng viá»‡t cÃ³ dáº¥u",
        "lá»i nÃ³i tiáº¿ng viá»‡t tá»± nhiÃªn chÃ­nh táº£ tiáº¿ng viá»‡t cÃ³ dáº¥u",
    )
    normalized = text.strip(" .,!?:;").lower()
    if normalized in junk_phrases:
        return ""
    if normalized and all(phrase in normalized for phrase in ("tiáº¿ng viá»‡t cÃ³ dáº¥u", "Ã´ chat")):
        return ""

    return cleanup_pass(text)


def audio_byte_rate(audio: sr.AudioData) -> int:
    return max(1, audio.sample_rate * audio.sample_width)


def align_audio_byte(position: int, sample_width: int) -> int:
    width = max(1, sample_width)
    return max(0, position - (position % width))


def quiet_chunk_boundary(
    frame_data: bytes,
    sample_rate: int,
    sample_width: int,
    target: int,
    lower: int,
    upper: int,
) -> int:
    byte_rate = max(1, sample_rate * sample_width)
    window = align_audio_byte(int(byte_rate * 0.16), sample_width)
    step = align_audio_byte(int(byte_rate * 0.06), sample_width)
    if window <= 0 or step <= 0:
        return align_audio_byte(target, sample_width)

    start = align_audio_byte(max(lower, target - int(byte_rate * GOOGLE_CHUNK_BOUNDARY_SEARCH_SECONDS)), sample_width)
    end = align_audio_byte(min(upper - window, target + int(byte_rate * GOOGLE_CHUNK_BOUNDARY_SEARCH_SECONDS)), sample_width)
    if end <= start:
        return align_audio_byte(target, sample_width)

    best_pos = start
    best_score = float("inf")
    for pos in range(start, end + 1, step):
        sample = frame_data[pos:pos + window]
        if len(sample) < window:
            continue
        rms = audioop.rms(sample, sample_width)
        distance_penalty = abs(pos - target) / byte_rate * 12.0
        score = rms + distance_penalty
        if score < best_score:
            best_score = score
            best_pos = pos
    return align_audio_byte(best_pos, sample_width)


def google_audio_chunks(audio: sr.AudioData) -> list[tuple[int, sr.AudioData, float, float]]:
    byte_rate = audio_byte_rate(audio)
    max_bytes = align_audio_byte(int(byte_rate * GOOGLE_LONG_CHUNK_SECONDS), audio.sample_width)
    min_bytes = align_audio_byte(int(byte_rate * GOOGLE_CHUNK_MIN_SECONDS), audio.sample_width)
    min_tail_bytes = align_audio_byte(int(byte_rate * GOOGLE_CHUNK_MIN_TAIL_SECONDS), audio.sample_width)
    if max_bytes <= 0:
        return []

    ranges: list[tuple[int, int]] = []
    start = 0
    total_bytes = len(audio.frame_data)
    while total_bytes - start > max_bytes:
        target = start + max_bytes
        lower = min(total_bytes, start + min_bytes)
        upper = total_bytes - min_tail_bytes
        boundary = quiet_chunk_boundary(audio.frame_data, audio.sample_rate, audio.sample_width, target, lower, upper)
        if boundary <= start + min_bytes or boundary >= total_bytes:
            boundary = align_audio_byte(target, audio.sample_width)
        ranges.append((start, boundary))
        start = boundary

    if start < total_bytes:
        ranges.append((start, total_bytes))

    if len(ranges) > 1:
        last_start, last_end = ranges[-1]
        if last_end - last_start < min_tail_bytes:
            prev_start, _prev_end = ranges[-2]
            ranges[-2] = (prev_start, last_end)
            ranges.pop()

    chunks: list[tuple[int, sr.AudioData, float, float]] = []
    for index, (start_byte, end_byte) in enumerate(ranges, start=1):
        frame_data = audio.frame_data[start_byte:end_byte]
        if not frame_data:
            continue
        chunks.append(
            (
                index,
                sr.AudioData(frame_data, audio.sample_rate, audio.sample_width),
                start_byte / byte_rate,
                end_byte / byte_rate,
            )
        )
    return chunks


def normalized_merge_token(token: str) -> str:
    return re.sub(r"[^\w]+", "", token.lower(), flags=re.UNICODE)


def merge_transcript_parts(parts: list[str]) -> str:
    merged_words: list[str] = []
    for part in parts:
        words = clean_transcript(part).split()
        if not words:
            continue
        if not merged_words:
            merged_words.extend(words)
            continue
        normalized_merged = [normalized_merge_token(word) for word in merged_words]
        normalized_words = [normalized_merge_token(word) for word in words]
        max_overlap = min(10, len(normalized_merged), len(normalized_words))
        overlap = 0
        for size in range(max_overlap, 0, -1):
            if normalized_merged[-size:] == normalized_words[:size]:
                overlap = size
                break
        merged_words.extend(words[overlap:])
    return clean_transcript(" ".join(merged_words))


def google_response_alternatives(response: object) -> list[tuple[str, float | None]]:
    if not isinstance(response, dict):
        return []
    alternatives = response.get("alternative", [])
    if not isinstance(alternatives, list):
        return []
    results: list[tuple[str, float | None]] = []
    for item in alternatives:
        if not isinstance(item, dict):
            continue
        transcript = str(item.get("transcript", "") or "").strip()
        if not transcript:
            continue
        confidence_raw = item.get("confidence")
        confidence: float | None = None
        if isinstance(confidence_raw, (int, float)):
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        results.append((transcript, confidence))
    return results


def choose_google_alternative(response: object) -> tuple[str, float | None, int]:
    alternatives = google_response_alternatives(response)
    if not alternatives:
        return "", None, 0
    best_raw = ""
    best_clean = ""
    best_confidence: float | None = None
    best_score = -1.0
    for raw, confidence in alternatives:
        clean = clean_transcript(raw)
        if not clean:
            continue
        confidence_score = confidence if confidence is not None else 0.55
        length_score = min(0.08, count_transcript_words(clean) * 0.002)
        score = confidence_score + length_score
        if score > best_score:
            best_raw = raw
            best_clean = clean
            best_confidence = confidence
            best_score = score
    return best_clean or clean_transcript(best_raw), best_confidence, len(alternatives)


def format_confidence_percent(confidence: float | None) -> str:
    if confidence is None:
        return "n/a"
    return f"{confidence * 100:.0f}%"


class MicIconApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT)
        self.root.resizable(False, False)

        x, y = load_position()
        self.root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root,
            width=SIZE,
            height=SIZE,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        self.drag_start: tuple[int, int, int, int] | None = None
        self.dragged = False
        self.listening = False
        self.visual_state = "idle"
        self.hud_state = "idle"
        self.settings = load_settings()
        self.hud_message = ""
        self.hud_visible = False
        self.hud_hide_after_id: str | None = None
        self.hud_anchor_point: tuple[int, int] | None = None
        self.particle_effect_enabled = bool(self.settings_value("enable_particle_effect", True))
        self.particle_effect_visible = False
        self.particle_anchor_point: tuple[int, int] | None = None
        self.particle_count = max(40, min(360, int(self.settings_value("particle_effect_count", PARTICLE_EFFECT_DEFAULT_COUNT))))
        self.particles = self.build_particles(self.particle_count)
        self.audio_level = 0.0
        self.audio_level_target = 0.0
        self.particle_result_text = ""
        self.particle_result_stats = ""
        self.particle_result_visible = False
        self.anim_tick = 0
        self.app_hwnd = 0
        self.hud_hwnd = 0
        self.last_target_hwnd = 0
        self.last_click_point: tuple[int, int] | None = None
        self.active_target_hwnd = 0
        self.active_target_point: tuple[int, int] | None = None
        self.pinned_target_hwnd = 0
        self.pinned_target_point: tuple[int, int] | None = None
        self.capture_clicks = False
        self.stop_requested = False
        self.stop_reason = ""
        self.session_counter = 0
        self.active_session_id = 0
        self.auto_was_down = False
        self.mouse_down_had_alt = False
        self.armed_target_hwnd = 0
        self.armed_target_point: tuple[int, int] | None = None
        self.armed_at = 0.0
        self.microphone_device_index, self.microphone_device_name = select_microphone_device(self.settings)
        self.voice_targets = load_voice_targets()
        self.escape_was_down = key_down(VK_ESCAPE)
        self.last_auto_started_at = 0.0
        self._auto_listen_triggered = False
        self._auto_click_token = 0
        self._alt_click_token = 0
        self._alt_click_triggered = False
        self.recognizer = sr.Recognizer()
        self.recognizer.operation_timeout = GOOGLE_RECOGNITION_TIMEOUT_SECONDS
        self.google_confidence_scores: list[float] = []
        self.whisper_model = None
        self.enable_whisper_fallback = bool(self.settings.get("enable_whisper_fallback", False))
        self.whisper_model_name = str(self.settings.get("whisper_model", "base") or "base")
        if self.enable_whisper_fallback:
            threading.Thread(target=self._load_whisper_model, daemon=True).start()
        else:
            log("whisper disabled by settings; google speech recognition only")
        log(
            f"app started | build={APP_BUILD} | auto_start={AUTO_START_FROM_CHAT_CLICK} | "
            f"trigger=Alt+left-click | mic_index={self.microphone_device_index} | mic={self.microphone_device_name} | "
            f"whisper={self.enable_whisper_fallback}:{self.whisper_model_name}"
        )

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda _event: self.request_stop("escape") if self.listening else self.root.destroy())

        self.hud = tk.Toplevel(self.root)
        self.hud.title(f"{APP_TITLE} Status")
        self.hud.overrideredirect(True)
        self.hud.attributes("-topmost", True)
        self.hud.attributes("-alpha", 0.93)
        self.hud.configure(bg=TRANSPARENT)
        self.hud.wm_attributes("-transparentcolor", TRANSPARENT)
        self.hud.resizable(False, False)
        self.hud.withdraw()
        self.hud_canvas = tk.Canvas(
            self.hud,
            width=HUD_WIDTH,
            height=HUD_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT,
            cursor="arrow",
        )
        self.hud_canvas.pack(fill="both", expand=True)

        self.particle = tk.Toplevel(self.root)
        self.particle.title(f"{APP_TITLE} AI Aura")
        self.particle.overrideredirect(True)
        self.particle.attributes("-topmost", True)
        self.particle.attributes("-alpha", 0.9)
        self.particle.configure(bg=TRANSPARENT)
        self.particle.wm_attributes("-transparentcolor", TRANSPARENT)
        self.particle.resizable(False, False)
        self.particle.withdraw()
        self.particle_canvas = tk.Canvas(
            self.particle,
            width=PARTICLE_EFFECT_WIDTH,
            height=PARTICLE_EFFECT_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=TRANSPARENT,
            cursor="arrow",
        )
        self.particle_canvas.pack(fill="both", expand=True)

        self.draw("idle")
        self.animate()
        self.root.update_idletasks()
        self.app_hwnd = int(self.root.winfo_id())
        self.hud_hwnd = int(self.hud.winfo_id())
        self.particle_hwnd = int(self.particle.winfo_id())
        make_tool_window(self.app_hwnd)
        make_tool_window(self.hud_hwnd)
        make_tool_window(self.particle_hwnd)
        if HIDE_FLOATING_MIC_BUTTON:
            self.root.withdraw()
        self.update_hud_position()
        self.monitor_target_window()
        self.monitor_global_clicks()
        self.monitor_voice_hotkeys()
        self.keep_topmost()
        self.check_for_updates_on_start()

    def settings_value(self, key: str, default: object) -> object:
        try:
            return self.settings.get(key, default)
        except Exception:
            return default

    def build_particles(self, count: int) -> list[tuple[float, float, float, float, float]]:
        particles: list[tuple[float, float, float, float, float]] = []
        golden_angle = math.pi * (3 - math.sqrt(5))
        for i in range(count):
            t = (i + 0.5) / count
            radius = math.sqrt(t)
            phase = i * golden_angle
            speed = 0.012 + ((i % 11) * 0.0028)
            wobble = 0.45 + ((i * 7) % 13) / 18
            depth = 0.35 + ((i * 17) % 100) / 100
            particles.append((phase, radius, speed, wobble, depth))
        return particles

    def keep_topmost(self) -> None:
        try:
            hwnd = self.app_hwnd or int(self.root.winfo_id())
            make_tool_window(hwnd)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            hud_hwnd = int(self.hud.winfo_id())
            make_tool_window(hud_hwnd)
            user32.SetWindowPos(hud_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            particle_hwnd = int(self.particle.winfo_id())
            make_tool_window(particle_hwnd)
            user32.SetWindowPos(particle_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass
        self.root.after(1200, self.keep_topmost)

    def check_for_updates_on_start(self) -> None:
        if not bool(self.settings.get("auto_update_enabled", False)):
            return
        if not getattr(sys, "frozen", False):
            log("auto update skipped: source mode")
            return
        manifest_url = str(self.settings.get("update_manifest_url", "") or "").strip()
        if not manifest_url:
            log("auto update skipped: update_manifest_url is empty")
            return
        threading.Thread(target=self.update_worker, args=(manifest_url,), daemon=True).start()

    def update_worker(self, manifest_url: str) -> None:
        try:
            manifest = read_update_manifest(manifest_url)
            remote_version = str(manifest.get("version", "") or "")
            if not is_newer_version(remote_version, APP_VERSION):
                log(f"auto update: current version ok | current={APP_VERSION} | remote={remote_version}")
                return
            zip_url_value = str(manifest.get("zip_url", "") or "")
            if not zip_url_value:
                log("auto update skipped: manifest missing zip_url")
                return
            zip_url = resolve_update_url(manifest_url, zip_url_value)
            update_dir = Path(tempfile.gettempdir()) / "VietnameseVoiceMic-update"
            zip_path = update_dir / "VietnameseVoiceMic-windows.zip"
            log(f"auto update downloading | version={remote_version} | url={zip_url}")
            download_update_zip(zip_url, zip_path)
            expected_sha = str(manifest.get("sha256", "") or "").strip().lower()
            if expected_sha:
                actual_sha = sha256_file(zip_path)
                if actual_sha.lower() != expected_sha:
                    log(f"auto update hash mismatch | expected={expected_sha} | actual={actual_sha}")
                    return
            self.root.after(0, lambda: self.show_hud("busy", f"C\u1eadp nh\u1eadt {remote_version}", None))
            self.launch_updater(zip_path)
        except Exception as exc:
            log(f"auto update error: {type(exc).__name__}: {exc}")

    def launch_updater(self, zip_path: Path) -> None:
        updater = APP_DIR / "updater.ps1"
        if not updater.exists():
            log(f"auto update skipped: updater missing | path={updater}")
            return
        exe_name = Path(sys.executable).name
        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(updater),
            "-AppPid",
            str(os.getpid()),
            "-ZipPath",
            str(zip_path),
            "-AppDir",
            str(APP_DIR),
            "-ExeName",
            exe_name,
        ]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(args, creationflags=flags)
        log(f"auto update launched updater | zip={zip_path}")
        self.root.after(700, self.root.destroy)

    def monitor_target_window(self) -> None:
        try:
            if not self.listening:
                hwnd = foreground_window()
                if hwnd and hwnd not in {self.app_hwnd, self.hud_hwnd}:
                    self.last_target_hwnd = hwnd
        except Exception:
            pass
        self.root.after(200, self.monitor_target_window)

    def monitor_global_clicks(self) -> None:
        try:
            down = left_button_down()
            if down and not self.auto_was_down:
                self.mouse_down_had_alt = key_down(VK_MENU)
            if self.auto_was_down and not down:
                point = cursor_position()
                alt_click = self.mouse_down_had_alt and key_down(VK_MENU)
                self.mouse_down_had_alt = False
                if alt_click:
                    self.try_alt_click_listen_from_click(point)
            self.auto_was_down = down
        except Exception as exc:
            log(f"auto click monitor error: {type(exc).__name__}: {exc}")
        self.root.after(int(AUTO_CLICK_POLL_SECONDS * 1000), self.monitor_global_clicks)

    def monitor_voice_hotkeys(self) -> None:
        try:
            escape_down = key_down(VK_ESCAPE)
            if escape_down and not self.escape_was_down and self.listening:
                self.request_stop("escape")
            self.escape_was_down = escape_down

        except Exception as exc:
            log(f"hotkey monitor error: {type(exc).__name__}: {exc}")
        self.root.after(35, self.monitor_voice_hotkeys)

    def current_text_target(self) -> tuple[int, tuple[int, int]] | None:
        hwnd = foreground_window()
        if not hwnd or hwnd in {self.app_hwnd, self.hud_hwnd}:
            return None
        caret_rect = get_caret_screen_rect(hwnd)
        if caret_rect:
            return hwnd, rect_center(caret_rect)

        point = cursor_position()
        has_uia_text_input, uia_details = uia_is_likely_input(point)
        browser_bottom = is_browser_bottom_input(hwnd, point) and point_in_strict_chat_zone(point, hwnd)
        if has_uia_text_input or browser_bottom:
            log(
                f"hotkey target from cursor | hwnd={hwnd} | point={point} | "
                f"browser_bottom={browser_bottom} | uia={uia_details}"
            )
            return hwnd, point
        return None

    def current_armed_target(self) -> tuple[int, tuple[int, int]] | None:
        if not self.armed_target_hwnd or not self.armed_target_point:
            return None
        if time.monotonic() - self.armed_at > ARM_TARGET_SECONDS:
            self.armed_target_hwnd = 0
            self.armed_target_point = None
            self.armed_at = 0.0
            return None
        return self.armed_target_hwnd, self.armed_target_point

    def is_near_learned_target(self, hwnd: int, point: tuple[int, int]) -> bool:
        key = stable_target_key(hwnd, point)
        if key in self.voice_targets:
            return True
        cls = window_class_name(hwnd)
        for saved_key, saved_point in self.voice_targets.items():
            if not saved_key.startswith(f"{cls}|"):
                continue
            if math.hypot(point[0] - saved_point[0], point[1] - saved_point[1]) <= LEARNED_TARGET_RADIUS:
                return True
        return False

    def remember_voice_target(self, hwnd: int, point: tuple[int, int] | None) -> None:
        if not hwnd or not point:
            return
        key = stable_target_key(hwnd, point)
        self.voice_targets[key] = (point[0], point[1])
        save_voice_targets(self.voice_targets)
        log(f"voice target learned | key={key} | point={point}")

    def pin_voice_target(self, hwnd: int, point: tuple[int, int] | None) -> None:
        if not hwnd or not point:
            return
        self.pinned_target_hwnd = hwnd
        self.pinned_target_point = point
        self.last_target_hwnd = hwnd
        self.last_click_point = point
        self.show_icon_near(point)
        self.draw("armed")
        self.show_hud("armed", "Mic \u0111\u00e3 ghim", 1200)
        log(f"voice target pinned | hwnd={hwnd} | point={point}")

    def request_stop(self, reason: str) -> None:
        if not self.listening:
            return
        self.stop_reason = reason
        self.stop_requested = True
        self.draw("busy")
        self.show_hud("busy", "\u0110ang d\u1eebng...", None)
        beep_async("stop")
        log(f"stop requested | reason={reason} | session={self.active_session_id}")

    def try_voice_hotkey(self) -> None:
        if self.listening:
            self.request_stop("hotkey")
            return
        self.try_hotkey_listen()

    def try_hotkey_listen(self) -> None:
        if self.listening:
            return
        now = time.monotonic()
        armed_target = self.current_armed_target()
        if not armed_target and now - self.last_auto_started_at < AUTO_CLICK_COOLDOWN_SECONDS:
            log(f"hotkey ignored: cooldown without armed target | hotkey={VOICE_HOTKEY_NAME}")
            return
        target = armed_target or self.current_text_target()
        if not target:
            log(f"hotkey ignored: no focused text target | hotkey={VOICE_HOTKEY_NAME}")
            return
        target_hwnd, target_point = target
        self.last_auto_started_at = now
        self.start_listening(auto_stop_after_phrase=True, target_hwnd=target_hwnd, target_point=target_point)
        self.armed_target_hwnd = 0
        self.armed_target_point = None
        self.armed_at = 0.0
        log(f"hotkey listen armed | hotkey={VOICE_HOTKEY_NAME} | hwnd={target_hwnd} | point={target_point}")

    def choose_keyboard_mode(self, vk: int) -> None:
        target = self.current_armed_target()
        if target:
            target_hwnd, target_point = target
            self.erase_activation_key(target_hwnd, target_point)
        self.armed_target_hwnd = 0
        self.armed_target_point = None
        self.armed_at = 0.0
        self.show_hud("done", "Nh\u1eadp b\u00e0n ph\u00edm", 900)
        log(f"keyboard mode selected | vk={vk}")

    def erase_activation_key(self, target_hwnd: int, target_point: tuple[int, int]) -> None:
        try:
            user32.SetCursorPos(target_point[0], target_point[1])
            time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.04)
            keybd(VK_BACK)
            time.sleep(0.02)
            keybd(VK_BACK, KEYEVENTF_KEYUP)
        except Exception as exc:
            log(f"activation key erase error: {type(exc).__name__}: {exc}")

    def try_alt_click_listen_from_click(self, point: tuple[int, int]) -> None:
        if self.listening:
            log(f"alt-click ignored while listening | session={self.active_session_id} | point={point}")
            return
        if not HIDE_FLOATING_MIC_BUTTON and self.point_inside_icon(*point):
            return

        hwnd = foreground_window()
        if not hwnd or hwnd in {self.app_hwnd, self.hud_hwnd}:
            return

        self.last_target_hwnd = hwnd
        self._alt_click_triggered = False
        self._alt_click_token += 1
        token = self._alt_click_token
        for delay in CLICK_DETECT_RETRY_MS:
            self.root.after(
                delay,
                lambda original_hwnd=hwnd, original_point=point, click_token=token:
                    self.maybe_start_alt_click_listen(original_hwnd, original_point, click_token),
            )

    def maybe_start_alt_click_listen(self, hwnd: int, point: tuple[int, int], token: int) -> None:
        if token != self._alt_click_token:
            return
        if self.listening or getattr(self, "_alt_click_triggered", False):
            return

        focused_hwnd = foreground_window()
        target_hwnd = focused_hwnd if focused_hwnd and focused_hwnd not in {self.app_hwnd, self.hud_hwnd} else hwnd
        caret_rect = get_caret_screen_rect(target_hwnd)
        has_uia_text_input, uia_details = uia_is_likely_input(point)
        has_text_caret = bool(caret_rect and point_near_rect(point, caret_rect, CARET_CLICK_RADIUS))
        near_learned_target = self.is_near_learned_target(target_hwnd, point)
        strict_chat = point_in_strict_chat_zone(point, target_hwnd)
        browser_bottom = is_browser_bottom_input(target_hwnd, point) and strict_chat

        if not has_uia_text_input and not has_text_caret and not near_learned_target and not browser_bottom:
            log(
                f"alt-click ignored | hwnd={target_hwnd} | point={point} | "
                f"strict={strict_chat} | caret={caret_rect} | uia={uia_details}"
            )
            return

        target_point = point
        reason = (
            "uia-edit" if has_uia_text_input
            else "caret" if has_text_caret
            else "learned-zone" if near_learned_target
            else "browser-bottom"
        )
        self._alt_click_triggered = True
        self.armed_target_hwnd = 0
        self.armed_target_point = None
        self.armed_at = 0.0
        self.last_auto_started_at = time.monotonic()
        self.pin_voice_target(target_hwnd, target_point)
        self.start_listening(auto_stop_after_phrase=True, target_hwnd=target_hwnd, target_point=target_point)
        log(
            f"alt-click listen started: {reason} | hwnd={target_hwnd} | "
            f"point={point} | paste_point={target_point} | uia={uia_details} | caret={caret_rect}"
        )

    def try_auto_listen_from_click(self, point: tuple[int, int]) -> None:
        if ALT_CLICK_ONLY:
            return
        if self.listening:
            return
        if not HIDE_FLOATING_MIC_BUTTON and self.point_inside_icon(*point):
            return
        now = time.monotonic()
        if now - self.last_auto_started_at < AUTO_CLICK_COOLDOWN_SECONDS:
            return

        hwnd = foreground_window()
        if not hwnd or hwnd in {self.app_hwnd, self.hud_hwnd}:
            return

        self.last_target_hwnd = hwnd
        self._auto_listen_triggered = False
        self._auto_click_token += 1
        token = self._auto_click_token
        for delay in CLICK_DETECT_RETRY_MS:
            self.root.after(
                delay,
                lambda original_hwnd=hwnd, original_point=point, click_token=token:
                    self.maybe_start_auto_listen(original_hwnd, original_point, click_token),
            )

    def maybe_start_auto_listen(self, hwnd: int, point: tuple[int, int], token: int) -> None:
        if token != self._auto_click_token:
            return
        if self.listening or self.armed_target_point == point:
            return
        # Early-exit: if a previous retry already triggered for this click, skip
        if getattr(self, "_auto_listen_triggered", False):
            return
        focused_hwnd = foreground_window()
        target_hwnd = focused_hwnd if focused_hwnd and focused_hwnd != self.app_hwnd else hwnd

        caret_rect = get_caret_screen_rect(target_hwnd)
        has_uia_text_input, uia_details = uia_is_likely_input(point)
        has_text_caret = bool(caret_rect and point_near_rect(point, caret_rect, CARET_CLICK_RADIUS))
        near_learned_target = self.is_near_learned_target(target_hwnd, point)
        looks_like_bottom_chat = point_in_bottom_chat_zone(point, target_hwnd)
        looks_like_chat_hint = point_in_chat_hint_zone(point, target_hwnd)
        looks_like_strict_chat = point_in_strict_chat_zone(point, target_hwnd)
        # Fallback: click Ä‘Ã¡y Chrome/Electron â†’ kháº£ nÄƒng cao lÃ  Ã´ chat
        browser_bottom = is_browser_bottom_input(target_hwnd, point) and looks_like_strict_chat
        if not has_uia_text_input and not has_text_caret and not near_learned_target and not browser_bottom:
            log(
                f"auto listen ignored | hwnd={target_hwnd} | point={point} | "
                f"caret={caret_rect} | uia={uia_details}"
            )
            return

        self.last_auto_started_at = time.monotonic()
        reason = (
            "uia-edit" if has_uia_text_input
            else "caret" if has_text_caret
            else "learned-zone" if near_learned_target
            else "browser-bottom"
        )
        if AUTO_START_FROM_CHAT_CLICK:
            self._auto_listen_triggered = True
            self.armed_target_hwnd = 0
            self.armed_target_point = None
            self.armed_at = 0.0
            target_point = best_paste_point(point, caret_rect)
            self.start_listening(auto_stop_after_phrase=True, target_hwnd=target_hwnd, target_point=target_point)
            log(
                f"voice target auto-started: {reason} | hwnd={target_hwnd} | point={point} | paste_point={target_point} | "
                f"bottom={looks_like_bottom_chat} | strict={looks_like_strict_chat} | "
                f"hint={looks_like_chat_hint} | uia={uia_details} | caret={caret_rect}"
            )
            return

        self.arm_voice_target(target_hwnd, best_paste_point(point, caret_rect), reason, caret_rect)
        self.show_hud("armed", "Nh\u1ea5n 1 \u0111\u1ec3 n\u00f3i, 2 \u0111\u1ec3 nh\u1eadp tay", 6000)
        log(
            f"voice target waiting for choice | hwnd={target_hwnd} | point={point} | "
            f"strict={looks_like_strict_chat} | uia={uia_details}"
        )

    def start_armed_voice_target(self) -> None:
        target = self.current_armed_target()
        if not target or self.listening:
            return
        target_hwnd, target_point = target
        self.armed_target_hwnd = 0
        self.armed_target_point = None
        self.armed_at = 0.0
        self.start_listening(auto_stop_after_phrase=True, target_hwnd=target_hwnd, target_point=target_point)

    def arm_voice_target(
        self,
        target_hwnd: int,
        target_point: tuple[int, int],
        reason: str,
        caret_rect: tuple[int, int, int, int] | None,
    ) -> None:
        self.armed_target_hwnd = target_hwnd
        self.armed_target_point = target_point
        self.armed_at = time.monotonic()
        self.draw("armed")
        self.show_hud("armed", "Nh\u1ea5n 1 \u0111\u1ec3 n\u00f3i, 2 \u0111\u1ec3 nh\u1eadp tay", 6000)
        log(f"voice target armed: {reason} | hwnd={target_hwnd} | point={target_point} | caret={caret_rect}")

    def animate(self) -> None:
        if self.visual_state in {"armed", "listen", "busy", "error"}:
            self.anim_tick += 1
            self.draw()
        if self.hud_visible:
            self.draw_hud()
        if self.particle_effect_visible:
            self.draw_particle_effect()
        self.root.after(80, self.animate)

    def draw(self, state: str | None = None) -> None:
        if state is not None:
            self.visual_state = state
        state = self.visual_state
        self.canvas.delete("all")
        palette = {
            "idle": ("#070a10", "#121826", "#29e6b8"),
            "armed": ("#07182b", "#123d69", "#45c7ff"),
            "listen": ("#05251f", "#087b6f", "#5ff4d3"),
            "busy": ("#111322", "#4637c8", "#c4b5fd"),
            "done": ("#07170d", "#15803d", "#86efac"),
            "error": ("#2a0707", "#9f1f1f", "#fecaca"),
        }
        base, mid, accent = palette.get(state, palette["idle"])
        cx = cy = SIZE // 2
        pulse = (math.sin(self.anim_tick / 2.7) + 1) / 2

        if state in {"armed", "listen"}:
            for i, alpha_color in enumerate(("#134e7a", "#0f766e")):
                offset = 2 + i * 5 + int(pulse * 4)
                self.canvas.create_oval(
                    offset,
                    offset,
                    SIZE - offset,
                    SIZE - offset,
                    outline=alpha_color if state == "armed" else "#0f766e",
                    width=1,
                )

        if state == "busy":
            for i in range(6):
                angle = (self.anim_tick * 0.32) + (i * math.tau / 6)
                r = 31
                x = cx + math.cos(angle) * r
                y = cy + math.sin(angle) * r
                dot = 2 + (i % 2)
                self.canvas.create_oval(x - dot, y - dot, x + dot, y + dot, fill="#c4b5fd", outline="")

        if state == "error":
            self.canvas.create_oval(3, 3, SIZE - 3, SIZE - 3, outline="#ef4444", width=2)

        left = (SIZE - CORE) // 2
        top = (SIZE - CORE) // 2
        right = left + CORE
        bottom = top + CORE

        # Scale mic body to CORE size
        self.canvas.create_oval(left + 2, top + 3, right, bottom + 1, fill="#020617", outline="")
        self.canvas.create_oval(left, top, right, bottom, fill=base, outline="#020617", width=1)
        self.canvas.create_oval(left + 2, top + 2, right - 2, bottom - 2, fill=mid, outline=accent, width=1)

        # Mic shape scaled for small icon
        mw = max(3, CORE // 7)
        mh_top = cy - CORE // 2 + 2
        mh_bot = cy - 1
        self.canvas.create_oval(cx - mw, mh_top, cx + mw, mh_top + mw * 2, fill="#f8fafc", outline="")
        self.canvas.create_rectangle(cx - mw, mh_top + mw, cx + mw, mh_bot, fill="#f8fafc", outline="")
        self.canvas.create_oval(cx - mw, mh_bot - mw, cx + mw, mh_bot + mw, fill="#f8fafc", outline="")
        arc_r = CORE // 4
        self.canvas.create_arc(cx - arc_r, cy - arc_r // 2, cx + arc_r, cy + arc_r, start=200, extent=140, style="arc", outline="#f8fafc", width=2)
        self.canvas.create_line(cx, cy + arc_r // 2, cx, cy + arc_r + 2, fill="#f8fafc", width=2, capstyle="round")
        self.canvas.create_line(cx - mw, cy + arc_r + 2, cx + mw, cy + arc_r + 2, fill="#f8fafc", width=2, capstyle="round")

        if state in {"armed", "listen", "busy"}:
            dot_r = max(3, CORE // 8)
            self.canvas.create_oval(cx + CORE // 4, top, cx + CORE // 4 + dot_r * 2, top + dot_r * 2, fill=accent, outline="")

        if state == "listen":
            bar_y = bottom + 3
            heights = [3, 5, 7, 5, 3]
            for i, h in enumerate(heights):
                live = h + int(math.sin((self.anim_tick / 1.5) + i) * 2)
                x = cx - 8 + i * 4
                self.canvas.create_line(x, bar_y - live, x, bar_y + live, fill=accent, width=2, capstyle="round")

    def update_hud_position(self) -> None:
        try:
            screen_left, screen_top, screen_right, screen_bottom = virtual_screen_rect()
            if self.hud_anchor_point:
                anchor_x, anchor_y = self.hud_anchor_point
                x = anchor_x + HUD_GAP
                if x + HUD_WIDTH > screen_right - 8:
                    x = anchor_x - HUD_WIDTH - HUD_GAP
                y = anchor_y - HUD_HEIGHT - HUD_GAP
                if y < screen_top + 8:
                    y = anchor_y + HUD_GAP
            else:
                icon_x = self.root.winfo_x()
                icon_y = self.root.winfo_y()
                x = icon_x + SIZE + HUD_GAP
                if x + HUD_WIDTH > screen_right - 8:
                    x = icon_x - HUD_WIDTH - HUD_GAP
                y = icon_y + (SIZE - HUD_HEIGHT) // 2
            x = max(screen_left + 8, min(x, screen_right - HUD_WIDTH - 8))
            y = max(screen_top + 8, min(y, screen_bottom - HUD_HEIGHT - 8))
            self.hud.geometry(f"{HUD_WIDTH}x{HUD_HEIGHT}+{x}+{y}")
        except Exception:
            pass

    def show_hud(self, state: str, message: str, auto_hide_ms: int | None = None) -> None:
        # HUD Ä‘Ã£ bá»‹ áº©n â€” tráº¡ng thÃ¡i biá»ƒu thá»‹ qua mÃ u sáº¯c icon mic
        self.hud_state = state
        self.hud_message = ellipsize(message)
        try:
            if self.hud_hide_after_id:
                self.root.after_cancel(self.hud_hide_after_id)
                self.hud_hide_after_id = None
            if state in {"listen", "busy"} and self.particle_effect_enabled:
                self.hide_hud()
                self.show_particle_effect(self.active_target_point)
                return
            if state == "done" and self.particle_effect_enabled and self.particle_result_visible:
                self.hide_hud()
                return
            self.update_hud_position()
            self.hud_visible = True
            self.hud.deiconify()
            self.hud.lift()
            self.draw_hud()
            if auto_hide_ms:
                self.hud_hide_after_id = self.root.after(auto_hide_ms, self.hide_hud)
        except Exception:
            pass

    def hide_hud(self) -> None:
        try:
            self.hud_visible = False
            self.hud.withdraw()
            self.hud_hide_after_id = None
        except Exception:
            pass

    def show_particle_effect(self, point: tuple[int, int] | None) -> None:
        if not self.particle_effect_enabled:
            return
        if point is None:
            self.hide_particle_effect()
            return
        try:
            self.particle_anchor_point = point
            self.audio_level = 0.12
            self.audio_level_target = 0.18
            self.particle_result_text = ""
            self.particle_result_stats = ""
            self.particle_result_visible = False
            self.update_particle_position()
            self.particle_effect_visible = True
            self.particle.deiconify()
            self.particle.lift()
            self.draw_particle_effect()
        except Exception as exc:
            log(f"particle effect show error: {type(exc).__name__}: {exc}")

    def hide_particle_effect(self) -> None:
        try:
            self.particle_effect_visible = False
            self.audio_level = 0.0
            self.audio_level_target = 0.0
            self.particle_result_visible = False
            self.particle.withdraw()
            self.particle_canvas.delete("all")
        except Exception:
            pass

    def show_particle_result(self, text: str, stats: str, point: tuple[int, int] | None, auto_hide_ms: int = 2600) -> None:
        if not self.particle_effect_enabled:
            return
        if point is None:
            return
        try:
            self.visual_state = "done"
            self.particle_anchor_point = point
            self.particle_result_text = ellipsize(text, 58)
            self.particle_result_stats = stats
            self.particle_result_visible = True
            self.audio_level_target = 0.0
            self.update_particle_position()
            self.particle_effect_visible = True
            self.particle.deiconify()
            self.particle.lift()
            self.draw_particle_effect()
            self.root.after(auto_hide_ms, self.hide_particle_effect)
        except Exception as exc:
            log(f"particle result show error: {type(exc).__name__}: {exc}")

    def update_particle_position(self) -> None:
        try:
            screen_left, screen_top, screen_right, screen_bottom = virtual_screen_rect()
            point = self.particle_anchor_point
            if point is None:
                self.hide_particle_effect()
                return
            x = point[0] - PARTICLE_EFFECT_WIDTH // 2
            y = point[1] - PARTICLE_EFFECT_HEIGHT - PARTICLE_EFFECT_GAP
            if y < screen_top + 8:
                y = point[1] + PARTICLE_EFFECT_GAP
            x = max(screen_left + 8, min(x, screen_right - PARTICLE_EFFECT_WIDTH - 8))
            y = max(screen_top + 8, min(y, screen_bottom - PARTICLE_EFFECT_HEIGHT - 8))
            self.particle.geometry(f"{PARTICLE_EFFECT_WIDTH}x{PARTICLE_EFFECT_HEIGHT}+{x}+{y}")
        except Exception:
            pass

    def draw_particle_effect(self) -> None:
        if not self.particle_effect_enabled:
            return
        canvas = self.particle_canvas
        canvas.delete("all")
        state = self.visual_state
        if state not in {"listen", "busy", "done"}:
            return
        W, H = PARTICLE_EFFECT_WIDTH, PARTICLE_EFFECT_HEIGHT
        cx, cy = W // 2, H // 2
        state_colors = {
            "listen": ("#12314f", "#1e6f95", "#67e8f9", "#5eead4", "#ecfeff", "DANG NGHE"),
            "busy": ("#34205f", "#6d28d9", "#c4b5fd", "#ddd6fe", "#f5f3ff", "DANG NHAN DIEN"),
            "done": ("#14532d", "#16a34a", "#86efac", "#bbf7d0", "#f0fdf4", "DA CO TEXT"),
        }
        outer_color, mid_color, accent_color, bar_color, text_color, status_label = state_colors.get(
            state, state_colors["listen"]
        )
        base_radius = 92 if state == "listen" else 88
        self.audio_level += (self.audio_level_target - self.audio_level) * 0.28
        if state == "busy":
            self.audio_level = max(self.audio_level * 0.9, 0.28 + math.sin(self.anim_tick / 3.0) * 0.08)
        if state == "done":
            self.audio_level *= 0.72
        level = max(0.0, min(1.0, self.audio_level))
        pulse = 1.0 + level * 0.14 + math.sin(self.anim_tick / 5.0) * 0.025
        radius = base_radius * pulse

        # Soft circular field, no rectangular/pill frame.
        canvas.create_oval(cx - radius - 18, cy - radius - 18, cx + radius + 18, cy + radius + 18, outline=outer_color, width=1)
        canvas.create_oval(cx - radius - 7, cy - radius - 7, cx + radius + 7, cy + radius + 7, outline=mid_color, width=2)
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=accent_color, width=3)

        ring_points = 44
        spin = self.anim_tick * (0.055 if state == "listen" else 0.11)
        for i in range(ring_points):
            angle = spin + i * math.tau / ring_points
            wave = math.sin(self.anim_tick / 2.4 + i * 0.7)
            outer = radius + 9 + level * 16 + wave * (3 + level * 8)
            inner = radius - 2
            x1 = cx + math.cos(angle) * inner
            y1 = cy + math.sin(angle) * inner
            x2 = cx + math.cos(angle) * outer
            y2 = cy + math.sin(angle) * outer
            color = "#f8fafc" if i % 7 == 0 else bar_color
            canvas.create_line(x1, y1, x2, y2, fill=color, width=2, capstyle="round")

        # Audio recognition wave inside the circle.
        bars = 17
        wave_y = cy - 22 if state == "done" else cy
        for i in range(bars):
            offset = i - (bars - 1) / 2
            x = cx + offset * 6
            envelope = 1 - min(1, abs(offset) / (bars / 2))
            live = math.sin(self.anim_tick / 1.7 + i * 0.85) * 0.5 + 0.5
            height = 8 + envelope * 26 * (0.25 + level) + live * 10
            if state == "busy":
                height = 10 + envelope * 22 + live * 7
            if state == "done":
                height = 8 + envelope * 16 + live * 6
            top = wave_y - height / 2
            bottom = wave_y + height / 2
            color = "#f8fafc" if abs(offset) < 2 else bar_color
            canvas.create_line(x, top, x, bottom, fill=color, width=3, capstyle="round")

        for i, (phase, _spread, speed, wobble, depth) in enumerate(self.particles[:90]):
            angle = phase + self.anim_tick * speed * (2.0 if state == "busy" else 1.0)
            sparkle_radius = radius + 2 + math.sin(self.anim_tick * 0.07 + phase) * 10 * wobble
            x = cx + math.cos(angle) * sparkle_radius
            y = cy + math.sin(angle) * sparkle_radius
            dot = 0.8 + depth * 1.4
            color = "#ffffff" if depth > 0.88 else bar_color
            canvas.create_oval(x - dot, y - dot, x + dot, y + dot, fill=color, outline="")

        canvas.create_text(cx, cy + 42, text=status_label, fill=text_color, font=("Segoe UI", 9, "bold"))

        if state == "done" and self.particle_result_visible:
            stats = self.particle_result_stats
            preview = self.particle_result_text
            panel_x1, panel_y1 = cx - 104, cy + 58
            panel_x2, panel_y2 = cx + 104, cy + 112
            panel_r = 12
            panel_fill = "#052e16"
            canvas.create_rectangle(panel_x1 + panel_r, panel_y1, panel_x2 - panel_r, panel_y2, fill=panel_fill, outline="")
            canvas.create_rectangle(panel_x1, panel_y1 + panel_r, panel_x2, panel_y2 - panel_r, fill=panel_fill, outline="")
            canvas.create_oval(panel_x1, panel_y1, panel_x1 + panel_r * 2, panel_y1 + panel_r * 2, fill=panel_fill, outline="")
            canvas.create_oval(panel_x2 - panel_r * 2, panel_y1, panel_x2, panel_y1 + panel_r * 2, fill=panel_fill, outline="")
            canvas.create_oval(panel_x1, panel_y2 - panel_r * 2, panel_x1 + panel_r * 2, panel_y2, fill=panel_fill, outline="")
            canvas.create_oval(panel_x2 - panel_r * 2, panel_y2 - panel_r * 2, panel_x2, panel_y2, fill=panel_fill, outline="")
            canvas.create_rectangle(panel_x1 + 10, panel_y1, panel_x2 - 10, panel_y1 + 1, fill="#86efac", outline="")
            canvas.create_text(cx, panel_y1 + 16, text=preview, fill="#f0fdf4", font=("Segoe UI", 9, "bold"), width=190, justify="center")
            canvas.create_text(cx, panel_y1 + 40, text=stats, fill="#bbf7d0", font=("Segoe UI", 8, "bold"), width=190, justify="center")

    def draw_hud(self) -> None:
        canvas = self.hud_canvas
        canvas.delete("all")
        state = self.hud_state
        palettes = {
            "armed": ("#08111f", "#102a43", "#38bdf8", "#f8fafc"),
            "listen": ("#061512", "#0f766e", "#5eead4", "#ecfeff"),
            "busy": ("#10101f", "#4338ca", "#c4b5fd", "#f5f3ff"),
            "done": ("#07170d", "#15803d", "#86efac", "#f0fdf4"),
            "error": ("#210909", "#991b1b", "#fecaca", "#fff1f2"),
        }
        bg, mid, accent, text_color = palettes.get(state, palettes["listen"])
        pulse = (math.sin(self.anim_tick / 2.2) + 1) / 2
        W, H = HUD_WIDTH, HUD_HEIGHT
        r = H // 2 - 2

        # Pill background
        canvas.create_rectangle(r + 2, 2, W - r - 2, H - 2, fill=bg, outline="")
        canvas.create_oval(2, 2, H - 2, H - 2, fill=bg, outline="")
        canvas.create_oval(W - H + 2, 2, W - 2, H - 2, fill=bg, outline="")
        canvas.create_rectangle(r + 2, 2, W - r - 2, H - 2, fill=bg, outline="", width=0)
        # Border
        canvas.create_rectangle(r + 2, 2, W - r - 2, 3, fill=accent, outline="")
        canvas.create_rectangle(r + 2, H - 3, W - r - 2, H - 2, fill=accent, outline="")
        canvas.create_arc(2, 2, H - 2, H - 2, start=90, extent=180, outline=accent, width=1, style="arc")
        canvas.create_arc(W - H + 2, 2, W - 2, H - 2, start=270, extent=180, outline=accent, width=1, style="arc")

        # Small mic dot indicator on left
        dot_x, dot_y = r + 2, H // 2
        if state in {"listen", "armed"}:
            ring_r = 9 + int(pulse * 4)
            canvas.create_oval(dot_x - ring_r, dot_y - ring_r, dot_x + ring_r, dot_y + ring_r, outline=accent, width=1)
        canvas.create_oval(dot_x - 9, dot_y - 9, dot_x + 9, dot_y + 9, fill=mid, outline=accent, width=1)
        # mini mic shape
        canvas.create_oval(dot_x - 3, dot_y - 7, dot_x + 3, dot_y - 1, fill="#f8fafc", outline="")
        canvas.create_rectangle(dot_x - 3, dot_y - 4, dot_x + 3, dot_y + 1, fill="#f8fafc", outline="")
        canvas.create_arc(dot_x - 6, dot_y - 1, dot_x + 6, dot_y + 7, start=200, extent=140, style="arc", outline="#f8fafc", width=2)
        canvas.create_line(dot_x, dot_y + 6, dot_x, dot_y + 9, fill="#f8fafc", width=2, capstyle="round")

        # Status icon on right side
        icon_x = W - r - 2
        if state == "listen":
            bars = 5
            for i in range(bars):
                live = 5 + int((math.sin(self.anim_tick / 1.5 + i * 0.8) + 1) * 7)
                x = icon_x - 20 + i * 8
                canvas.create_line(x, dot_y - live // 2, x, dot_y + live // 2, fill=accent, width=3, capstyle="round")
        elif state == "busy":
            for i in range(5):
                angle = self.anim_tick * 0.35 + i * math.tau / 5
                x = icon_x - 12 + math.cos(angle) * 9
                y = dot_y + math.sin(angle) * 7
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=accent, outline="")
        elif state == "done":
            canvas.create_line(icon_x - 16, dot_y + 2, icon_x - 8, dot_y + 10, fill=accent, width=3, capstyle="round")
            canvas.create_line(icon_x - 8, dot_y + 10, icon_x + 6, dot_y - 8, fill=accent, width=3, capstyle="round")
        elif state == "error":
            canvas.create_line(icon_x - 12, dot_y - 8, icon_x + 4, dot_y + 8, fill=accent, width=3, capstyle="round")
            canvas.create_line(icon_x + 4, dot_y - 8, icon_x - 12, dot_y + 8, fill=accent, width=3, capstyle="round")
        elif state == "armed":
            canvas.create_text(icon_x - 6, dot_y, text="1/2", fill=accent, font=("Segoe UI", 8, "bold"))

        # Label text
        labels = {
            "armed": "Nh\u1ea5n 1 mic / 2 b\u00e0n ph\u00edm",
            "listen": "\u0110ang nghe...",
            "busy": "\u0110ang x\u1eed l\u00fd...",
            "done": self.hud_message or "Xong",
            "error": "Th\u1eed l\u1ea1i",
        }
        label = labels.get(state, self.hud_message or "")
        if len(label) > 32:
            label = label[:30] + "..."
        tx = dot_x + 14
        max_text_w = icon_x - tx - 30
        canvas.create_text(tx, dot_y, anchor="w", text=label, fill=text_color, font=("Segoe UI", 9, "bold"), width=max_text_w)

    def on_press(self, event: tk.Event) -> None:
        self.drag_start = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y())
        self.dragged = False

    def on_drag(self, event: tk.Event) -> None:
        if not self.drag_start:
            return
        start_x, start_y, win_x, win_y = self.drag_start
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        if abs(dx) + abs(dy) > 3:
            self.dragged = True
        if self.dragged:
            x = win_x + dx
            y = win_y + dy
            self.root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")
            self.update_hud_position()

    def on_release(self, _event: tk.Event) -> None:
        save_position(self.root.winfo_x(), self.root.winfo_y())
        self.drag_start = None
        if not self.dragged:
            self.listen_now()

    def listen_now(self) -> None:
        if self.listening:
            self.request_stop("mic-button")
            return
        if self.pinned_target_hwnd and self.pinned_target_point:
            self.start_listening(
                auto_stop_after_phrase=True,
                target_hwnd=self.pinned_target_hwnd,
                target_point=self.pinned_target_point,
            )
            return
        self.start_listening(auto_stop_after_phrase=False)

    def show_icon_near(self, point: tuple[int, int] | None) -> None:
        try:
            screen_left, screen_top, screen_right, screen_bottom = virtual_screen_rect()
            if point:
                self.hud_anchor_point = point
                x = point[0] - SIZE // 2
                y = point[1] - SIZE - 10
                x = max(screen_left + 4, min(x, screen_right - SIZE - 4))
                y = max(screen_top + 4, min(y, screen_bottom - SIZE - 4))
                self.root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")
            self.update_hud_position()
            if not SHOW_FLOATING_MIC_ICON:
                self.root.withdraw()
                return
            self.root.deiconify()
            self.root.lift()
            make_tool_window(self.app_hwnd)
        except Exception:
            pass

    def start_listening(
        self,
        auto_stop_after_phrase: bool,
        target_hwnd: int = 0,
        target_point: tuple[int, int] | None = None,
    ) -> None:
        if self.listening:
            return
        self.listening = True
        self.capture_clicks = not auto_stop_after_phrase
        self.stop_requested = False
        self.stop_reason = ""
        self.session_counter += 1
        self.active_session_id = self.session_counter
        self.last_click_point = target_point
        self.active_target_hwnd = target_hwnd
        self.active_target_point = target_point
        if target_hwnd:
            self.last_target_hwnd = target_hwnd
        self.draw("listen")
        self.show_icon_near(target_point)
        self.show_particle_effect(target_point)
        self.show_hud("listen", "\u0110ang nghe...", None)
        beep_async("start")
        log(f"session start | id={self.active_session_id} | locked_hwnd={target_hwnd} | locked_point={target_point}")
        if self.capture_clicks:
            threading.Thread(target=self.capture_target_click_worker, daemon=True).start()
        threading.Thread(target=self.listen_worker, args=(auto_stop_after_phrase, self.active_session_id), daemon=True).start()

    def refresh_microphone_device(self, session_id: int = 0) -> tuple[int | None, str]:
        index, name = select_microphone_device(self.settings)
        if index != self.microphone_device_index or name != self.microphone_device_name:
            log(
                f"mic reselected | session={session_id} | "
                f"old_index={self.microphone_device_index} | old_name={self.microphone_device_name} | "
                f"new_index={index} | new_name={name}"
            )
            self.microphone_device_index = index
            self.microphone_device_name = name
        return index, name

    def capture_target_click_worker(self) -> None:
        was_down = left_button_down()
        while self.capture_clicks:
            down = left_button_down()
            if down and not was_down:
                x, y = cursor_position()
                if not self.point_inside_icon(x, y):
                    self.last_click_point = (x, y)
            was_down = down
            time.sleep(0.02)

    def point_inside_icon(self, x: int, y: int) -> bool:
        left = self.root.winfo_x()
        top = self.root.winfo_y()
        return left <= x <= left + SIZE and top <= y <= top + SIZE

    def _load_whisper_model(self) -> None:
        global _whisper
        if _whisper is None:
            try:
                import whisper as whisper_module
                _whisper = whisper_module
            except Exception:
                log("whisper unavailable; google speech recognition only")
                return
        if _whisper is None:
            log("whisper unavailable; google speech recognition only")
            return
        try:
            log(f"loading whisper {self.whisper_model_name} model...")
            self.whisper_model = _whisper.load_model(self.whisper_model_name)
            log(f"whisper {self.whisper_model_name} model loaded")
        except Exception as exc:
            log(f"whisper load error: {exc}")

    def _audio_duration_seconds(self, audio: sr.AudioData) -> float:
        bytes_per_second = max(1, audio.sample_rate * audio.sample_width)
        return len(audio.frame_data) / bytes_per_second

    def _transcribe_google_once(self, audio: sr.AudioData) -> str:
        recognizer = sr.Recognizer()
        recognizer.operation_timeout = GOOGLE_RECOGNITION_TIMEOUT_SECONDS
        response = recognizer.recognize_google(audio, language="vi-VN", show_all=True)
        google_text, confidence, alternative_count = choose_google_alternative(response)
        if not google_text:
            raise sr.UnknownValueError()
        if confidence is not None:
            self.google_confidence_scores.append(confidence)
        log(
            f"google confidence={format_confidence_percent(confidence)} | "
            f"alternatives={alternative_count} | text={google_text[:80]}"
        )
        return google_text

    def _slice_audio(self, audio: sr.AudioData, start_byte: int, end_byte: int) -> sr.AudioData:
        width = max(1, audio.sample_width)
        start_byte -= start_byte % width
        end_byte -= end_byte % width
        return sr.AudioData(audio.frame_data[start_byte:end_byte], audio.sample_rate, audio.sample_width)

    def _transcribe_google_resilient(self, audio: sr.AudioData, label: str, depth: int = 0) -> str:
        duration = self._audio_duration_seconds(audio)
        last_error: Exception | None = None
        for attempt in range(1, GOOGLE_CHUNK_RETRY_ATTEMPTS + 1):
            try:
                text = self._transcribe_google_once(audio).strip()
                if text:
                    return text
                log(f"google {label} empty | attempt={attempt} | duration={duration:.1f}s")
                return ""
            except sr.UnknownValueError as exc:
                last_error = exc
                log(f"google {label} unrecognized | attempt={attempt} | duration={duration:.1f}s")
                return ""
            except Exception as exc:
                last_error = exc
                log(f"google {label} error | attempt={attempt} | duration={duration:.1f}s | {type(exc).__name__}: {exc}")
                time.sleep(0.25 * attempt)

        if duration <= GOOGLE_MIN_RETRY_CHUNK_SECONDS or depth >= 2:
            if last_error:
                raise last_error
            return ""

        midpoint = len(audio.frame_data) // 2
        midpoint -= midpoint % max(1, audio.sample_width)
        if midpoint <= 0 or midpoint >= len(audio.frame_data):
            if last_error:
                raise last_error
            return ""

        log(f"google {label} splitting after failure | duration={duration:.1f}s")
        left = self._slice_audio(audio, 0, midpoint)
        right = self._slice_audio(audio, midpoint, len(audio.frame_data))
        parts = [
            self._transcribe_google_resilient(left, f"{label}a", depth + 1),
            self._transcribe_google_resilient(right, f"{label}b", depth + 1),
        ]
        return clean_transcript(" ".join(part for part in parts if part.strip()))

    def _transcribe_google_chunked(self, audio: sr.AudioData) -> str:
        chunks = google_audio_chunks(audio)
        if not chunks:
            raise sr.UnknownValueError()

        total = len(chunks)
        for index, chunk_audio, start_sec, end_sec in chunks:
            log(
                f"google smart chunk {index}/{total} | "
                f"range={start_sec:.1f}-{end_sec:.1f}s | duration={self._audio_duration_seconds(chunk_audio):.1f}s"
            )

        def transcribe_chunk(item: tuple[int, sr.AudioData, float, float]) -> tuple[int, str, str]:
            index, chunk_audio, _start_sec, _end_sec = item
            try:
                chunk_text = self._transcribe_google_resilient(chunk_audio, f"chunk {index}/{total}").strip()
                if chunk_text:
                    return index, chunk_text, "ok"
                return index, "", "empty"
            except sr.UnknownValueError:
                return index, "", "unrecognized"
            except Exception as exc:
                return index, "", f"error:{type(exc).__name__}: {exc}"

        parts: list[str] = []
        errors = 0
        workers = min(3, max(1, len(chunks)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(transcribe_chunk, chunks))

        for index, chunk_text, status in sorted(results, key=lambda item: item[0]):
            if chunk_text:
                parts.append(chunk_text)
                log(f"google chunk {index}/{total} ok | chars={len(chunk_text)} | text={chunk_text[:80]}")
            else:
                errors += 1
                log(f"google chunk {index}/{total} {status}")

        text = merge_transcript_parts(parts)
        if text:
            log(
                f"transcribe engine=google-chunked | chunks={len(parts)}/{total} | "
                f"errors={errors} | workers={workers} | text={text[:80]}"
            )
            return text
        raise sr.UnknownValueError()

    def _transcribe_audio(self, audio: sr.AudioData) -> str:
        """Transcribe Vietnamese speech. Prefer Google for dictation accuracy, fallback to Whisper offline."""
        duration = self._audio_duration_seconds(audio)
        self.google_confidence_scores.clear()
        try:
            if duration > GOOGLE_SINGLE_PASS_MAX_SECONDS:
                log(f"long audio detected; using google chunks | duration={duration:.1f}s")
                google_text = self._transcribe_google_chunked(audio)
            else:
                google_text = self._transcribe_google_once(audio)
            if google_text:
                avg_confidence = (
                    sum(self.google_confidence_scores) / len(self.google_confidence_scores)
                    if self.google_confidence_scores
                    else None
                )
                log(
                    f"transcribe engine=google | confidence_avg={format_confidence_percent(avg_confidence)} | "
                    f"text={google_text[:80]}"
                )
                return google_text
        except sr.UnknownValueError:
            log("google unrecognized; falling back to whisper")
        except Exception as exc:
            log(f"google transcribe error: {type(exc).__name__}: {exc}")
            if duration > GOOGLE_MIN_RETRY_CHUNK_SECONDS:
                try:
                    log(f"retrying google with chunks after error | duration={duration:.1f}s")
                    google_text = self._transcribe_google_chunked(audio)
                    if google_text:
                        return google_text
                except Exception as retry_exc:
                    log(f"google chunk retry failed: {type(retry_exc).__name__}: {retry_exc}")
            log("falling back to whisper")

        if self.whisper_model is None:
            raise sr.UnknownValueError()

        wav_data = audio.get_wav_data()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp.write(wav_data)
            tmp.close()
            result = self.whisper_model.transcribe(
                tmp.name,
                language="vi",
                task="transcribe",
                fp16=False,
                condition_on_previous_text=False,
                temperature=0,
                beam_size=5,
                best_of=5,
                no_speech_threshold=0.75,
                logprob_threshold=-1.0,
                compression_ratio_threshold=2.4,
                initial_prompt=whisper_initial_prompt(),
            )
            # BÃ¡Â»Â qua nÃ¡ÂºÂ¿u Whisper khÃƒÂ´ng chÃ¡ÂºÂ¯c cÃƒÂ³ giÃ¡Â»Âng nÃƒÂ³i (hallucination tÃ¡Â»Â« tiÃ¡ÂºÂ¿ng Ã¡Â»â€œn)
            segments = result.get("segments", [])
            if segments:
                avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
                log(f"whisper no_speech_prob={avg_no_speech:.2f}")
                if avg_no_speech > 0.75:
                    raise sr.UnknownValueError()
            elif not result["text"].strip():
                raise sr.UnknownValueError()
            whisper_raw = str(result["text"])
            whisper_text = clean_transcript(whisper_raw)
            if whisper_text and whisper_text != whisper_raw.strip():
                log(f"cleanup | raw={whisper_raw[:100]} | clean={whisper_text[:100]}")
            return whisper_text
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def listen_worker(self, auto_stop_after_phrase: bool = False, session_id: int = 0) -> None:
        target_hwnd = self.active_target_hwnd or self.last_target_hwnd
        target_point = self.active_target_point or self.last_click_point
        listen_started = time.monotonic()
        last_activity_at = listen_started
        stop_reason = "completed"
        audio_frames: list[bytes] = []
        pre_roll: list[bytes] = []
        speech_started = False
        speech_started_at = 0.0
        capture_finished_at = listen_started
        voice_frame_count = 0
        sample_rate = 16000
        sample_width = 2
        particle_result_scheduled = False
        try:
            mic_index, mic_name = self.refresh_microphone_device(session_id)
            with sr.Microphone(device_index=mic_index) as source:
                self.recognizer.energy_threshold = 120
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.pause_threshold = 1.2
                self.recognizer.non_speaking_duration = 0.55
                sample_rate = source.SAMPLE_RATE
                sample_width = source.SAMPLE_WIDTH
                voice_vad = create_voice_vad(sample_rate, sample_width)

                log(
                    f"mic open | session={session_id} | index={mic_index} | "
                    f"name={mic_name} | energy={self.recognizer.energy_threshold:.0f} | "
                    f"sample_rate={sample_rate} | vad={'webrtc@16000' if voice_vad else 'rms'}"
                )

                # Measure noise briefly so speech right after activation is not treated as background.
                noise_until = time.monotonic() + 0.35
                noise_samples: list[int] = []
                while time.monotonic() < noise_until and not self.stop_requested:
                    data = read_audio_chunk(source.stream, source.CHUNK)
                    noise_samples.append(audioop.rms(data, source.SAMPLE_WIDTH))
                speech_threshold, activity_threshold, noise_floor, noise_p90 = calculate_vad_threshold(noise_samples)
                webrtc_rms_gate = calculate_webrtc_rms_gate(noise_floor, speech_threshold)
                log(
                    f"rms vad ready | session={session_id} | noise={noise_floor} | "
                    f"p90={noise_p90} | speech_threshold={speech_threshold} | "
                    f"activity_threshold={activity_threshold} | webrtc_rms_gate={webrtc_rms_gate}"
                )

                while not self.stop_requested:
                    data = read_audio_chunk(source.stream, source.CHUNK)
                    rms = audioop.rms(data, source.SAMPLE_WIDTH)
                    vad_voice = vad_detects_speech(voice_vad, data, sample_width)
                    now = time.monotonic()
                    level_floor = max(1, noise_floor)
                    level_span = max(250, speech_threshold * 2)
                    self.audio_level_target = max(0.04, min(1.0, (rms - level_floor) / level_span))
                    if vad_voice is not None:
                        rms_voice = rms >= activity_threshold
                        strong_rms_voice = rms >= speech_threshold
                        start_voice = (bool(vad_voice) and rms >= webrtc_rms_gate) or strong_rms_voice
                        active_voice = (bool(vad_voice) and rms >= webrtc_rms_gate) or rms_voice
                    else:
                        start_voice = rms >= speech_threshold
                        active_voice = rms >= activity_threshold
                    soft_activity_threshold = max(
                        int(noise_floor * VAD_SOFT_ACTIVITY_MULTIPLIER),
                        noise_floor + VAD_SOFT_ACTIVITY_MARGIN,
                    )
                    soft_voice = speech_started and rms >= soft_activity_threshold

                    if start_voice:
                        voice_frame_count += 1
                        if not speech_started and voice_frame_count >= VOICE_START_FRAMES:
                            speech_started = True
                            speech_started_at = now
                            audio_frames.extend(pre_roll)
                            pre_roll.clear()
                            last_activity_at = now
                            self.root.after(0, lambda sid=session_id: self.show_hud("listen", f"\u0110ang nghe #{sid}", None))
                            log(
                                f"voice start | session={session_id} | rms={rms} | "
                                f"speech_threshold={speech_threshold} | webrtc_rms_gate={webrtc_rms_gate} | vad={vad_voice}"
                            )
                        if speech_started:
                            audio_frames.append(data)
                            last_activity_at = now
                    else:
                        voice_frame_count = 0
                        if speech_started:
                            audio_frames.append(data)
                            if active_voice or soft_voice:
                                last_activity_at = now
                        else:
                            pre_roll.append(data)
                            if len(pre_roll) > 6:
                                pre_roll.pop(0)

                    if not speech_started and now - listen_started > INITIAL_NO_SPEECH_TIMEOUT_SECONDS:
                        stop_reason = "no-speech"
                        log(f"vad: initial no speech timeout | id={session_id}")
                        break
                    capture_age = now - speech_started_at
                    if capture_age >= LONG_VOICE_AFTER_SECONDS:
                        trailing_timeout = WEBRTC_VOICE_END_SECONDS if voice_vad else RMS_VOICE_END_SECONDS
                    else:
                        trailing_timeout = WEBRTC_SHORT_VOICE_END_SECONDS if voice_vad else RMS_SHORT_VOICE_END_SECONDS
                    can_auto_stop = now - speech_started_at >= MIN_CAPTURE_BEFORE_AUTO_STOP_SECONDS
                    if speech_started and can_auto_stop and now - last_activity_at > trailing_timeout:
                        stop_reason = "silence"
                        log(
                            f"auto stop after trailing silence | id={session_id} | "
                            f"timeout={trailing_timeout:.1f}s | age={capture_age:.1f}s | "
                            f"last_rms={rms} | soft_threshold={soft_activity_threshold} | "
                            f"frames={len(audio_frames)}"
                        )
                        break
                    if auto_stop_after_phrase and now - listen_started > AUTO_PHRASE_LIMIT_SECONDS:
                        stop_reason = "max-time"
                        log(f"vad: max phrase time | frames={len(audio_frames)}")
                        break
                capture_finished_at = time.monotonic()
                self.audio_level_target = 0.0

            if self.stop_requested and audio_frames:
                stop_reason = self.stop_reason or "requested"
                capture_finished_at = time.monotonic()
                log(f"finish requested; transcribing captured audio | id={session_id} | frames={len(audio_frames)}")

            if not audio_frames:
                self.root.after(0, lambda: self.draw("idle"))
                self.root.after(0, lambda r=stop_reason: self.show_hud("done", f"D\u1eebng: {r}", 900))
                self.root.after(900, self.hide_hud)
                self.root.after(900, self.root.withdraw)
                log(f"session stopped | id={session_id} | frames=0 | hwnd={target_hwnd} | reason={stop_reason}")
                return

            t_api = time.monotonic()
            self.root.after(0, lambda: self.draw("busy"))
            self.root.after(0, lambda sid=session_id: self.show_hud("busy", f"\u0110ang nh\u1eadn di\u1ec7n #{sid}", None))
            audio = sr.AudioData(b"".join(audio_frames), sample_rate, sample_width)
            save_last_audio(
                audio,
                {
                    "session_id": session_id,
                    "hwnd": target_hwnd,
                    "reason": stop_reason,
                    "frames": len(audio_frames),
                },
            )
            final_text = self._transcribe_audio(audio).strip()
            api_ms = int((time.monotonic() - t_api) * 1000)
            if not final_text:
                raise sr.UnknownValueError()

            beep_async("done")
            communication_seconds = max(0.1, capture_finished_at - (speech_started_at or listen_started))
            wpm, word_count, char_count, measured_seconds = format_speech_stats(final_text, communication_seconds)
            avg_confidence = (
                sum(self.google_confidence_scores) / len(self.google_confidence_scores)
                if self.google_confidence_scores
                else None
            )
            confidence_text = format_confidence_percent(avg_confidence)
            stats_text = f"{wpm} t\u1eeb/ph\u00fat | {char_count} k\u00fd t\u1ef1 | tin c\u1eady {confidence_text}"
            log(
                f"session transcript | id={session_id} | text={final_text} | api={api_ms}ms | "
                f"frames={len(audio_frames)} | wpm={wpm} | words={word_count} | chars={char_count} | "
                f"duration={measured_seconds:.1f}s | confidence_avg={format_confidence_percent(avg_confidence)}"
            )
            save_last_transcript(
                final_text,
                {
                    "session_id": session_id,
                    "hwnd": target_hwnd,
                    "point": target_point,
                    "reason": stop_reason,
                    "confidence": confidence_text,
                    "duration_seconds": round(measured_seconds, 2),
                    "chars": char_count,
                },
            )
            keep_transcript_on_clipboard(final_text, "recognized")
            learn_context_terms(final_text)
            self.root.after(0, lambda t=final_text, hw=target_hwnd, pt=target_point:
                self.paste_chunk(t, hw, pt, click_to_focus=True))
            self.remember_voice_target(target_hwnd, target_point)
            particle_result_scheduled = True
            self.root.after(0, lambda t=final_text, s=stats_text, pt=target_point: self.show_particle_result(t, s, pt, 2800))
            self.root.after(2800, lambda: self.draw("idle"))
            self.root.after(2800, self.hide_hud)
            self.root.after(2800, self.root.withdraw)
            log(
                f"session done | id={session_id} | frames={len(audio_frames)} | hwnd={target_hwnd} | "
                f"reason={stop_reason} | stats={stats_text}"
            )
        except Exception as exc:
            log(f"session error | id={session_id} | {type(exc).__name__}: {exc}")
            beep_async("error")
            self.root.after(0, lambda: self.draw("error"))
            self.root.after(0, lambda: self.show_hud("error", "Th\u1eed l\u1ea1i g\u1ea7n micro h\u01a1n", 1200))
            self.root.after(700, lambda: self.draw("idle"))
            self.root.after(1300, self.hide_hud)
            self.root.after(1300, self.root.withdraw)
        finally:
            if not particle_result_scheduled:
                self.root.after(0, self.hide_particle_effect)
            self.capture_clicks = False
            self.stop_requested = False
            self.listening = False
            self.active_target_hwnd = 0
            self.active_target_point = None

    def paste_result(self, text: str, target_hwnd: int, target_point: tuple[int, int] | None) -> None:
        try:
            paste_to_focused_field(text, self.root, target_hwnd, target_point, restore_root=False)
        except Exception as exc:
            log(f"paste error: {type(exc).__name__}: {exc}")
            self.draw("error")
            self.root.after(900, lambda: self.draw("idle"))

    def paste_chunk(self, text: str, target_hwnd: int, target_point: tuple[int, int] | None, click_to_focus: bool = True) -> None:
        """Paste má»™t chunk ngay láº­p tá»©c, giá»¯ icon hiá»ƒn thá»‹ Ä‘á»ƒ tiáº¿p tá»¥c nghe."""
        try:
            if target_hwnd and not window_exists(target_hwnd):
                keep_transcript_on_clipboard(text, "target-closed")
                log(f"chunk paste skipped: target window closed | hwnd={target_hwnd} | text={text[:120]}")
                return
            if not set_clipboard_text_retry(text):
                log(f"chunk paste skipped: clipboard busy; text={text[:120]}")
                return
            time.sleep(0.05)
            current_hwnd = foreground_window()
            needs_refocus = click_to_focus or (target_hwnd and current_hwnd != target_hwnd)
            if needs_refocus:
                focused_hwnd = focus_locked_target(target_hwnd, target_point, click_to_focus=True)
            else:
                focused_hwnd = focus_locked_target(target_hwnd, None, click_to_focus=False)
            log(
                f"paste focus | target={target_hwnd} | before={current_hwnd} | "
                f"focused={focused_hwnd} | refocus={needs_refocus} | point={target_point}"
            )
            send_ctrl_v()
            time.sleep(0.05)
            keep_transcript_on_clipboard(text, "after-paste")
            log(f"chunk pasted; transcript kept on clipboard: {text[:60]}")
        except Exception as exc:
            keep_transcript_on_clipboard(text, "paste-error")
            log(f"chunk paste error: {type(exc).__name__}: {exc}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    if not acquire_single_instance_lock():
        return 0
    MicIconApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
