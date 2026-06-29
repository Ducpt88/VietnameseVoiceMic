#!/usr/bin/env python3
"""Native draggable mic icon that types Vietnamese speech into the selected field."""

from __future__ import annotations

import ctypes
import audioop
import json
import math
import queue
import threading
import time
import tkinter as tk
import winsound
from ctypes import wintypes
from pathlib import Path

import os
import tempfile

import speech_recognition as sr

try:
    import whisper as _whisper
except Exception:
    _whisper = None

try:
    from pywinauto import Desktop
except Exception:
    Desktop = None


APP_DIR = Path(__file__).resolve().parent
STATE_FILE = APP_DIR / "mic-position.json"
TARGETS_FILE = APP_DIR / "voice-targets.json"
SETTINGS_FILE = APP_DIR / "voice-mic-settings.json"
LOG_FILE = APP_DIR / "voice-mic.log"
APP_TITLE = "Vietnamese Voice Mic"
APP_BUILD = "alt-click-locked-target-2026-06-29"
SIZE = 38
CORE = 26
HUD_WIDTH = 220
HUD_HEIGHT = 44
HUD_GAP = 8
HIDE_FLOATING_MIC_BUTTON = True
SHOW_FLOATING_MIC_ICON = False
STREAM_PHRASE_SECONDS = 7
MAX_SPEECH_CHUNK_SECONDS = 12.0
MIN_SPEECH_CHUNK_SECONDS = 0.45
SILENCE_END_SECONDS = 1.25
MAX_UNRECOGNIZED_BEFORE_STOP = 3
VOICE_START_FRAMES = 3
TRANSPARENT = "#ff00ff"
LISTEN_CHUNK_SECONDS = 8
LISTEN_TIMEOUT_SECONDS = 8.0
AUTO_LISTEN_TIMEOUT_SECONDS = 18.0
AUTO_AFTER_SPEECH_TIMEOUT_SECONDS = 5.0
AUTO_PHRASE_LIMIT_SECONDS = 180
INITIAL_NO_SPEECH_TIMEOUT_SECONDS = 8.0
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


def select_microphone_device(settings: dict[str, object]) -> tuple[int | None, str]:
    preferred = str(settings.get("preferred_microphone", "") or "").strip().lower()
    fallback_hints = settings.get("microphone_name_hints", ["UGREEN Camera 2K", "USB Audio Device", "BKD-11"])
    hints = [str(h).lower() for h in fallback_hints if str(h).strip()]
    names = sr.Microphone.list_microphone_names()

    if preferred:
        for index, name in enumerate(names):
            if preferred in name.lower():
                return index, name

    for hint in hints:
        for index, name in enumerate(names):
            if hint in name.lower():
                return index, name

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


def keybd(vk: int, flags: int = 0) -> None:
    user32.keybd_event(vk, 0, flags, 0)


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
    # Save clipboard before overwriting so we can restore it afterwards
    old_clipboard = ""
    try:
        old_clipboard = get_clipboard_text()
    except Exception:
        pass
    try:
        set_clipboard_text(text)
        time.sleep(0.08)
        log(f"clipboard set: {get_clipboard_text()[:80]}")
        root.withdraw()
        root.update_idletasks()
        time.sleep(0.12)
        if target_point:
            user32.SetCursorPos(target_point[0], target_point[1])
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.24)
        elif target_hwnd:
            user32.SetForegroundWindow(target_hwnd)
            time.sleep(0.24)
        keybd(VK_CONTROL)
        time.sleep(0.02)
        keybd(VK_V)
        time.sleep(0.03)
        keybd(VK_V, KEYEVENTF_KEYUP)
        time.sleep(0.02)
        keybd(VK_CONTROL, KEYEVENTF_KEYUP)
        log(f"paste sent | hwnd={target_hwnd} | point={target_point}")
    finally:
        # Restore previous clipboard content so user's data isn't lost
        time.sleep(0.12)
        try:
            set_clipboard_text(old_clipboard)
        except Exception:
            pass
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


def clean_transcript(text: str) -> str:
    text = " ".join(text.replace("\n", " ").split())
    junk_phrases = (
        "cáº£m Æ¡n cÃ¡c báº¡n Ä‘Ã£ theo dÃµi",
        "hÃ£y subscribe cho kÃªnh",
        "hÃ£y Ä‘Äƒng kÃ½ kÃªnh",
    )
    normalized = text.strip(" .,!?:;").lower()
    if normalized in junk_phrases:
        return ""
    if normalized and all(phrase in normalized for phrase in ("tiếng việt có dấu", "ô chat")):
        return ""
    return text


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
        self.hud_message = ""
        self.hud_visible = False
        self.hud_hide_after_id: str | None = None
        self.hud_anchor_point: tuple[int, int] | None = None
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
        self.settings = load_settings()
        self.microphone_device_index, self.microphone_device_name = select_microphone_device(self.settings)
        self.voice_targets = load_voice_targets()
        self.escape_was_down = key_down(VK_ESCAPE)
        self.last_auto_started_at = 0.0
        self._auto_listen_triggered = False
        self._auto_click_token = 0
        self._alt_click_token = 0
        self._alt_click_triggered = False
        self.recognizer = sr.Recognizer()
        self.whisper_model = None
        threading.Thread(target=self._load_whisper_model, daemon=True).start()
        log(
            f"app started | build={APP_BUILD} | auto_start={AUTO_START_FROM_CHAT_CLICK} | "
            f"trigger=Alt+left-click | mic_index={self.microphone_device_index} | mic={self.microphone_device_name}"
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

        self.draw("idle")
        self.animate()
        self.root.update_idletasks()
        self.app_hwnd = int(self.root.winfo_id())
        self.hud_hwnd = int(self.hud.winfo_id())
        make_tool_window(self.app_hwnd)
        make_tool_window(self.hud_hwnd)
        if HIDE_FLOATING_MIC_BUTTON:
            self.root.withdraw()
        self.update_hud_position()
        self.monitor_target_window()
        self.monitor_global_clicks()
        self.monitor_voice_hotkeys()
        self.keep_topmost()

    def keep_topmost(self) -> None:
        try:
            hwnd = self.app_hwnd or int(self.root.winfo_id())
            make_tool_window(hwnd)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            hud_hwnd = int(self.hud.winfo_id())
            make_tool_window(hud_hwnd)
            user32.SetWindowPos(hud_hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass
        self.root.after(1200, self.keep_topmost)

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
        self.show_hud("armed", "Mic Ä‘Ã£ ghim vÃ o Ã´ chat", 1200)
        log(f"voice target pinned | hwnd={hwnd} | point={point}")

    def request_stop(self, reason: str) -> None:
        if not self.listening:
            return
        self.stop_reason = reason
        self.stop_requested = True
        self.draw("busy")
        self.show_hud("busy", "Äang dá»«ng...", None)
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
        self.show_hud("done", "DÃ¹ng bÃ n phÃ­m", 900)
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
            self.request_stop("alt-click")
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
        self.show_hud("armed", "Nháº¥n 1 Ä‘á»ƒ nÃ³i, 2 Ä‘á»ƒ nháº­p tay", 6000)
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
        self.show_hud("armed", "Nháº¥n 1 Ä‘á»ƒ nÃ³i, 2 Ä‘á»ƒ nháº­p tay", 6000)
        log(f"voice target armed: {reason} | hwnd={target_hwnd} | point={target_point} | caret={caret_rect}")

    def animate(self) -> None:
        if self.visual_state in {"armed", "listen", "busy", "error"}:
            self.anim_tick += 1
            self.draw()
        if self.hud_visible:
            self.draw_hud()
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
            "armed": "Nháº¥n 1 mic Â· 2 bÃ n phÃ­m",
            "listen": "Hãy nói đi Sếp ơi!",
            "busy": "Tèn tén tén ten....!",
            "done": self.hud_message or "Xong",
            "error": "Thá»­ láº¡i",
        }
        label = labels.get(state, self.hud_message or "")
        if len(label) > 32:
            label = label[:30] + "â€¦"
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
        if not SHOW_FLOATING_MIC_ICON:
            try:
                self.root.withdraw()
            except Exception:
                pass
            return
        try:
            screen_left, screen_top, screen_right, screen_bottom = virtual_screen_rect()
            if point:
                x = point[0] - SIZE // 2
                y = point[1] - SIZE - 10
                x = max(screen_left + 4, min(x, screen_right - SIZE - 4))
                y = max(screen_top + 4, min(y, screen_bottom - SIZE - 4))
                self.root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")
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
        self.show_hud("listen", "Hãy nói đi Sếp ơi!", None)
        beep_async("start")
        log(f"session start | id={self.active_session_id} | locked_hwnd={target_hwnd} | locked_point={target_point}")
        if self.capture_clicks:
            threading.Thread(target=self.capture_target_click_worker, daemon=True).start()
        threading.Thread(target=self.listen_worker, args=(auto_stop_after_phrase, self.active_session_id), daemon=True).start()

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
        if _whisper is None:
            log("whisper unavailable; google speech recognition only")
            return
        try:
            log("loading whisper medium model...")
            self.whisper_model = _whisper.load_model("medium")
            log("whisper medium model loaded")
        except Exception as exc:
            log(f"whisper load error: {exc}")

    def _transcribe_audio(self, audio: sr.AudioData) -> str:
        """Transcribe Vietnamese speech. Prefer Google for dictation accuracy, fallback to Whisper offline."""
        try:
            google_text = clean_transcript(self.recognizer.recognize_google(audio, language="vi-VN"))
            if google_text:
                log(f"transcribe engine=google | text={google_text[:80]}")
                return google_text
        except sr.UnknownValueError:
            log("google unrecognized; falling back to whisper")
        except Exception as exc:
            log(f"google transcribe error: {type(exc).__name__}: {exc}; falling back to whisper")

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
                initial_prompt="Lời nói tiếng Việt tự nhiên, chính tả tiếng Việt có dấu.",
            )
            # Bá» qua náº¿u Whisper khÃ´ng cháº¯c cÃ³ giá»ng nÃ³i (hallucination tá»« tiáº¿ng á»“n)
            segments = result.get("segments", [])
            if segments:
                avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
                log(f"whisper no_speech_prob={avg_no_speech:.2f}")
                if avg_no_speech > 0.75:
                    raise sr.UnknownValueError()
            elif not result["text"].strip():
                raise sr.UnknownValueError()
            return clean_transcript(result["text"])
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def listen_worker(self, auto_stop_after_phrase: bool = False, session_id: int = 0) -> None:
        pasted_count = 0
        target_hwnd = self.active_target_hwnd or self.last_target_hwnd
        target_point = self.active_target_point or self.last_click_point
        listen_started = time.monotonic()
        empty_chunks_after_paste = 0
        transcript_chunks: list[str] = []
        unrecognized_count = 0
        stop_reason = "completed"
        try:
            with sr.Microphone(device_index=self.microphone_device_index) as source:
                self.recognizer.energy_threshold = 120
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.pause_threshold = 1.2
                self.recognizer.non_speaking_duration = 0.55

                log(
                    f"mic open | session={session_id} | index={self.microphone_device_index} | "
                    f"name={self.microphone_device_name} | energy={self.recognizer.energy_threshold:.0f}"
                )

                # NgÆ°á»¡ng im láº·ng: láº§n Ä‘áº§u 2s, sau khi Ä‘Ã£ nÃ³i 2.5s
                noise_until = time.monotonic() + 0.8
                noise_samples: list[int] = []
                while time.monotonic() < noise_until and not self.stop_requested:
                    data = source.stream.read(source.CHUNK)
                    noise_samples.append(audioop.rms(data, source.SAMPLE_WIDTH))
                noise_floor = sorted(noise_samples)[len(noise_samples) // 2] if noise_samples else 50
                speech_threshold = max(180, int(noise_floor * 2.2), noise_floor + 250)
                log(f"rms vad ready | session={session_id} | noise={noise_floor} | threshold={speech_threshold}")

                while not self.stop_requested:
                    # Kiá»ƒm tra im láº·ng má»—i 200ms thay vÃ¬ block cáº£ 3s
                    now = time.monotonic()
                    if self.stop_requested:
                        stop_reason = self.stop_reason or "requested"
                        break
                    if not transcript_chunks and now - listen_started > INITIAL_NO_SPEECH_TIMEOUT_SECONDS:
                        stop_reason = "no-speech"
                        log(f"vad: initial no speech timeout | id={session_id}")
                        break
                    if auto_stop_after_phrase and now - listen_started > AUTO_PHRASE_LIMIT_SECONDS:
                        stop_reason = "max-time"
                        log(f"vad: max phrase time | pasted={pasted_count}")
                        break
                    frames: list[bytes] = []
                    speech_started = False
                    speech_started_at = 0.0
                    last_voice_at = 0.0
                    ended_by_silence = False
                    voice_frame_count = 0
                    chunk_started_at = time.monotonic()

                    while not self.stop_requested:
                        data = source.stream.read(source.CHUNK)
                        rms = audioop.rms(data, source.SAMPLE_WIDTH)
                        now = time.monotonic()

                        if rms >= speech_threshold:
                            voice_frame_count += 1
                            if not speech_started:
                                if voice_frame_count < VOICE_START_FRAMES:
                                    continue
                                speech_started = True
                                speech_started_at = now
                                self.root.after(0, lambda sid=session_id: self.show_hud("listen", f"Äang nghe #{sid}", None))
                                log(f"voice start | session={session_id} | rms={rms} | threshold={speech_threshold}")
                            last_voice_at = now
                        else:
                            voice_frame_count = 0

                        if speech_started:
                            frames.append(data)
                            if (
                                now - speech_started_at >= MIN_SPEECH_CHUNK_SECONDS
                                and now - last_voice_at >= SILENCE_END_SECONDS
                            ):
                                ended_by_silence = True
                                break
                            if now - speech_started_at >= MAX_SPEECH_CHUNK_SECONDS:
                                break
                        elif now - chunk_started_at > 0.25:
                            break

                    if self.stop_requested:
                        stop_reason = self.stop_reason or "requested"
                        break
                    if not frames:
                        continue
                    t_api = time.monotonic()
                    self.root.after(0, lambda sid=session_id: self.show_hud("listen", f"Äang nghe #{sid}", None))
                    audio = sr.AudioData(b"".join(frames), source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                    self.root.after(0, lambda sid=session_id: self.show_hud("busy", f"Äang xá»­ lÃ½ #{sid}", None))
                    try:
                        chunk = self._transcribe_audio(audio)
                    except sr.UnknownValueError:
                        if pasted_count > 0:
                            stop_reason = "silence"
                            log(f"auto stop after unrecognized silence | pasted={pasted_count}")
                            break
                        unrecognized_count += 1
                        if unrecognized_count >= MAX_UNRECOGNIZED_BEFORE_STOP:
                            stop_reason = "no-speech"
                            log(f"auto stop after no speech | unrecognized={unrecognized_count}")
                            break
                        log(f"unrecognized | mode=fixed-record | api={time.monotonic()-t_api:.2f}s")
                        continue
                    except Exception as exc:
                        log(f"transcribe error: {exc}")
                        continue
                    api_ms = int((time.monotonic() - t_api) * 1000)
                    if self.stop_requested:
                        stop_reason = self.stop_reason or "requested"
                        log("paste skipped: stop requested")
                        break
                    if not chunk:
                        continue
                    empty_chunks_after_paste = 0
                    transcript_chunks.append(chunk)
                    unrecognized_count = 0
                    beep_async("chunk")
                    log(f"session chunk | id={session_id} | text={chunk} | api={api_ms}ms | buffered")
                    self.root.after(0, lambda c=chunk, sid=session_id: self.show_hud("listen", f"#{sid}: {ellipsize(c, 28)}", None))
                    pasted_count += 1
                    if ended_by_silence:
                        stop_reason = "silence"
                        log(f"auto stop after speech silence | id={session_id} | chunks={pasted_count}")
                        break

            if pasted_count == 0:
                if stop_reason not in {"completed", "initial-timeout"}:
                    self.root.after(0, lambda: self.draw("idle"))
                    self.root.after(0, lambda r=stop_reason: self.show_hud("done", f"Dá»«ng: {r}", 900))
                    self.root.after(900, self.hide_hud)
                    self.root.after(900, self.root.withdraw)
                    log(f"session stopped | id={session_id} | chunks=0 | hwnd={target_hwnd} | reason={stop_reason}")
                    return
                raise sr.UnknownValueError()
            beep_async("done")
            final_text = " ".join(transcript_chunks).strip()
            if final_text:
                self.root.after(0, lambda t=final_text, hw=target_hwnd, pt=target_point:
                    self.paste_chunk(t, hw, pt, click_to_focus=True))
            self.remember_voice_target(target_hwnd, target_point)
            self.root.after(0, lambda: self.draw("idle"))
            self.root.after(0, lambda r=stop_reason, c=pasted_count: self.show_hud("done", f"Dá»«ng: {r} Â· {c} Ä‘oáº¡n", 1200))
            self.root.after(1200, self.hide_hud)
            self.root.after(1200, self.root.withdraw)
            log(f"session done | id={session_id} | chunks={pasted_count} | hwnd={target_hwnd} | reason={stop_reason}")
        except Exception as exc:
            log(f"session error | id={session_id} | {type(exc).__name__}: {exc}")
            beep_async("error")
            self.root.after(0, lambda: self.draw("error"))
            self.root.after(0, lambda: self.show_hud("error", "Thá»­ láº¡i gáº§n micro hÆ¡n", 1200))
            self.root.after(700, lambda: self.draw("idle"))
            self.root.after(1300, self.hide_hud)
            self.root.after(1300, self.root.withdraw)
        finally:
            self.capture_clicks = False
            self.stop_requested = False
            self.listening = False

    def listen_worker(self, auto_stop_after_phrase: bool = False, session_id: int = 0) -> None:
        target_hwnd = self.active_target_hwnd or self.last_target_hwnd
        target_point = self.active_target_point or self.last_click_point
        stop_reason = "completed"
        try:
            with sr.Microphone(device_index=self.microphone_device_index) as source:
                self.recognizer.energy_threshold = 420
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.pause_threshold = 1.0
                self.recognizer.non_speaking_duration = 0.45
                log(
                    f"mic open | session={session_id} | index={self.microphone_device_index} | "
                    f"name={self.microphone_device_name} | energy={self.recognizer.energy_threshold:.0f}"
                )
                self.root.after(0, lambda: self.show_hud("listen", "Hãy nói đi Sếp ơi!", None))
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=AUTO_LISTEN_TIMEOUT_SECONDS,
                        phrase_time_limit=AUTO_PHRASE_LIMIT_SECONDS,
                    )
                except sr.WaitTimeoutError:
                    stop_reason = "no-speech"
                    log(f"listen timeout | id={session_id}")
                    self.root.after(0, lambda: self.draw("idle"))
                    self.root.after(0, lambda: self.show_hud("done", "Không nghe thấy giọng", 900))
                    self.root.after(900, self.hide_hud)
                    self.root.after(900, self.root.withdraw)
                    return

            if self.stop_requested:
                stop_reason = self.stop_reason or "requested"
                log(f"session stopped before transcribe | id={session_id} | reason={stop_reason}")
                return

            t_api = time.monotonic()
            self.root.after(0, lambda: self.show_hud("busy", "Tèn tén tén ten....!", None))
            text = self._transcribe_audio(audio)
            api_ms = int((time.monotonic() - t_api) * 1000)
            if not text:
                stop_reason = "empty"
                raise sr.UnknownValueError()
            log(f"session transcript | id={session_id} | text={text} | api={api_ms}ms")

            if self.stop_requested:
                stop_reason = self.stop_reason or "requested"
                log("paste skipped: stop requested")
                return

            beep_async("done")
            self.root.after(0, lambda t=text, hw=target_hwnd, pt=target_point:
                self.paste_chunk(t, hw, pt, click_to_focus=True))
            self.remember_voice_target(target_hwnd, target_point)
            self.root.after(0, lambda: self.draw("idle"))
            self.root.after(0, lambda r=stop_reason: self.show_hud("done", f"Dừng: {r}", 1200))
            self.root.after(1200, self.hide_hud)
            self.root.after(1200, self.root.withdraw)
            log(f"session done | id={session_id} | hwnd={target_hwnd} | reason={stop_reason}")
        except Exception as exc:
            log(f"session error | id={session_id} | {type(exc).__name__}: {exc}")
            beep_async("error")
            self.root.after(0, lambda: self.draw("error"))
            self.root.after(0, lambda: self.show_hud("error", "Không nhận được giọng", 1200))
            self.root.after(700, lambda: self.draw("idle"))
            self.root.after(1300, self.hide_hud)
            self.root.after(1300, self.root.withdraw)
        finally:
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
            old_clip = get_clipboard_text()
            set_clipboard_text(text)
            time.sleep(0.05)
            current_hwnd = foreground_window()
            needs_refocus = click_to_focus or (target_hwnd and current_hwnd != target_hwnd)
            if needs_refocus:
                # Chunk Ä‘áº§u: click vÃ o input Ä‘á»ƒ focus
                if target_point:
                    user32.SetCursorPos(target_point[0], target_point[1])
                    time.sleep(0.04)
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    time.sleep(0.18)
                elif target_hwnd:
                    user32.SetForegroundWindow(target_hwnd)
                    time.sleep(0.18)
            else:
                # Chunk sau: chá»‰ SetForegroundWindow Ä‘á»ƒ khÃ´ng di chuyá»ƒn cursor/caret
                if target_hwnd:
                    user32.SetForegroundWindow(target_hwnd)
                    time.sleep(0.1)
            log(f"paste focus | target={target_hwnd} | current={current_hwnd} | refocus={needs_refocus} | point={target_point}")
            keybd(VK_CONTROL)
            time.sleep(0.02)
            keybd(VK_V)
            time.sleep(0.03)
            keybd(VK_V, KEYEVENTF_KEYUP)
            time.sleep(0.02)
            keybd(VK_CONTROL, KEYEVENTF_KEYUP)
            time.sleep(0.05)
            set_clipboard_text(old_clip)
            log(f"chunk pasted: {text[:60]}")
        except Exception as exc:
            log(f"chunk paste error: {type(exc).__name__}: {exc}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    MicIconApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
