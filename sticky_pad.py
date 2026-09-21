#!/usr/bin/env python3
"""Yellow sticky-pad notebook — type straight onto a keep-on-top desktop pad."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

HOME = Path.home()
CFG_DIR = HOME / ".config" / "lee-stickypad"
CFG = CFG_DIR / "notes.json"
PID = HOME / ".cache" / "lee-stickypad.pid"
ICON = HOME / ".local" / "share" / "icons" / "hicolor" / "256x256" / "apps" / "lee-stickypad.png"
LOG = Path("/tmp/stickypad-widget.log")

APP_ID = "uk.lee.stickypad"
PRGNAME = "lee-stickypad-widget"
DEFAULT_W, DEFAULT_H = 380, 520
SAVE_MS = 400
LINE_ABOVE, LINE_BELOW = 5, 5

# Classic yellow legal pad
PAPER = (0.973, 0.890, 0.420)  # #F8E36B
INK = "#2A2314"
RULE = (0.50, 0.66, 0.82, 0.50)
MARGIN = (0.82, 0.30, 0.28)

CSS = b"""
window, window.background, window.stickypad, window.stickypad.background,
decoration, decoration:backdrop {
  background-color: #F8E36B;
  background-image: none;
  color: #2A2314;
}
headerbar, headerbar:backdrop, .titlebar, .titlebar:backdrop {
  background-image: none;
  background-color: #EED45A;
  color: #4A3D18;
  border: none;
  box-shadow: inset 0 -1px 0 rgba(0,0,0,0.08);
  min-height: 42px;
  padding: 2px 6px;
}
headerbar label, headerbar button, headerbar image, headerbar:backdrop label {
  color: #4A3D18;
}
headerbar button, headerbar button:backdrop {
  background-image: none;
  background-color: transparent;
  border: none;
  box-shadow: none;
  min-width: 28px;
  min-height: 28px;
  padding: 2px 6px;
  border-radius: 6px;
  color: #4A3D18;
}
headerbar button:hover {
  background-color: rgba(0,0,0,0.08);
}
headerbar button:active, headerbar button:checked {
  background-color: rgba(0,0,0,0.14);
}
headerbar entry, entry.title, headerbar entry:backdrop {
  background-image: none;
  background-color: rgba(255,255,255,0.35);
  color: #4A3D18;
  border: none;
  box-shadow: none;
  border-radius: 6px;
  padding: 4px 8px;
  font-weight: 600;
  font-size: 13px;
  min-width: 90px;
  caret-color: #2A2314;
}
headerbar entry:focus {
  background-color: rgba(255,255,255,0.62);
}
label.pager {
  color: #4A3D18;
  font-weight: 600;
  font-size: 12px;
  min-width: 42px;
}
scrolledwindow, scrolledwindow viewport, eventbox {
  background-color: #F8E36B;
  background-image: none;
  border: none;
  box-shadow: none;
}
textview, textview text, textview:selected, textview text:selected {
  background-color: transparent;
  color: #2A2314;
  caret-color: #2A2314;
  font-family: "Liberation Sans", "DejaVu Sans", sans-serif;
  font-size: 16px;
}
textview text selection {
  background-color: #C9A227;
  color: #1A150C;
}
scrollbar, scrollbar trough {
  background: transparent;
  border: none;
}
scrollbar slider {
  background-color: rgba(90,70,20,0.28);
  min-width: 8px;
  border-radius: 6px;
}
"""


def log(msg: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_note(title: str = "", text: str = "") -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "title": title,
        "text": text,
        "updated": now_iso(),
    }


def default_state() -> dict:
    return {
        "keep_above": True,
        "width": DEFAULT_W,
        "height": DEFAULT_H,
        "x": None,
        "y": None,
        "active": 0,
        "notes": [new_note()],
    }


def load_state() -> dict:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    state = default_state()
    if not CFG.exists():
        save_state(state)
        return state
    try:
        data = json.loads(CFG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return state
    if not isinstance(data, dict):
        return state
    notes = []
    for item in data.get("notes") or []:
        if not isinstance(item, dict):
            continue
        notes.append(
            {
                "id": str(item.get("id") or uuid.uuid4().hex[:10]),
                "title": str(item.get("title") or ""),
                "text": str(item.get("text") or ""),
                "updated": str(item.get("updated") or now_iso()),
            }
        )
    if not notes:
        notes = [new_note()]
    state["notes"] = notes
    try:
        state["active"] = max(0, min(int(data.get("active") or 0), len(notes) - 1))
    except (TypeError, ValueError):
        state["active"] = 0
    state["keep_above"] = bool(data.get("keep_above", True))
    for key in ("width", "height", "x", "y"):
        val = data.get(key)
        if val is None:
            state[key] = None
        else:
            try:
                state[key] = int(val)
            except (TypeError, ValueError):
                state[key] = None
    if not state["width"]:
        state["width"] = DEFAULT_W
    if not state["height"]:
        state["height"] = DEFAULT_H
    return state


def save_state(state: dict) -> None:
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CFG.with_suffix(".json.tmp")
    payload = {
        "keep_above": bool(state.get("keep_above", True)),
        "width": int(state.get("width") or DEFAULT_W),
        "height": int(state.get("height") or DEFAULT_H),
        "x": state.get("x"),
        "y": state.get("y"),
        "active": int(state.get("active") or 0),
        "notes": list(state.get("notes") or [new_note()]),
    }
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(CFG)


def write_icon(path: Path, size: int = 256) -> None:
    import cairo

    path.parent.mkdir(parents=True, exist_ok=True)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()

    pad = size * 0.10
    x, y = pad, pad * 0.85
    w, h = size - pad * 2, size - pad * 1.85
    radius = size * 0.04

    # drop shadow
    cr.set_source_rgba(0, 0, 0, 0.22)
    round_rect(cr, x + size * 0.03, y + size * 0.04, w, h, radius)
    cr.fill()

    # paper
    cr.set_source_rgb(*PAPER)
    round_rect(cr, x, y, w, h, radius)
    cr.fill()

    # glued top strip
    cr.save()
    round_rect(cr, x, y, w, h, radius)
    cr.clip()
    cr.set_source_rgb(0.93, 0.83, 0.35)
    cr.rectangle(x, y, w, h * 0.14)
    cr.fill()
    cr.restore()

    # ruled lines
    cr.set_source_rgba(*RULE)
    cr.set_line_width(max(1.0, size / 160))
    top = y + h * 0.22
    gap = h * 0.09
    yy = top
    while yy < y + h - gap * 0.4:
        cr.move_to(x + w * 0.08, yy)
        cr.line_to(x + w * 0.92, yy)
        cr.stroke()
        yy += gap

    # red margin
    cr.set_source_rgb(*MARGIN)
    cr.set_line_width(max(1.5, size / 90))
    mx = x + w * 0.22
    cr.move_to(mx, y + h * 0.16)
    cr.line_to(mx, y + h * 0.94)
    cr.stroke()

    # folded corner
    fold = size * 0.14
    cr.set_source_rgb(0.90, 0.78, 0.28)
    cr.move_to(x + w - fold, y + h)
    cr.line_to(x + w, y + h - fold)
    cr.line_to(x + w, y + h - radius)
    cr.arc_negative(x + w - radius, y + h - radius, radius, 0, 1.57)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(0, 0, 0, 0.12)
    cr.move_to(x + w - fold, y + h)
    cr.line_to(x + w - fold, y + h - fold)
    cr.line_to(x + w, y + h - fold)
    cr.stroke()

    surf.write_to_png(str(path))


def round_rect(cr, x, y, w, h, r) -> None:
    cr.new_path()
    cr.arc(x + w - r, y + r, r, -1.57, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.57)
    cr.arc(x + r, y + h - r, r, 1.57, 3.14)
    cr.arc(x + r, y + r, r, 3.14, 4.71)
    cr.close_path()


def paint_legal_pad(tv: Gtk.TextView, cr) -> None:
    """Yellow paper, blue rules under the text baseline, red margin."""
    alloc = tv.get_allocation()
    cr.set_source_rgb(*PAPER)
    cr.paint()
    try:
        _paint_legal_pad_marks(tv, cr, alloc)
    except Exception as exc:
        log(f"draw marks: {exc}")


def _paint_legal_pad_marks(tv: Gtk.TextView, cr, alloc) -> None:

    vis = tv.get_visible_rect()
    loc_res = tv.get_iter_at_location(0, max(int(vis.y), 0))
    it = loc_res[-1] if isinstance(loc_res, tuple) else loc_res
    loc = tv.get_iter_location(it)
    line_h = loc.height if loc.height else 26
    _wx, wy = tv.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, 0, loc.y)
    # Sit the rule just under the glyphs (legal-pad baseline).
    rule0 = wy + line_h - 3

    cr.set_source_rgba(*RULE)
    cr.set_line_width(1.0)
    y = rule0
    while y > -line_h:
        y -= line_h
    while y <= alloc.height + line_h:
        if -2 <= y <= alloc.height + 2:
            cr.move_to(0, y + 0.5)
            cr.line_to(alloc.width, y + 0.5)
            cr.stroke()
        y += line_h

    mx = tv.get_left_margin() - 12
    cr.set_source_rgb(*MARGIN)
    cr.set_line_width(1.4)
    cr.move_to(mx + 0.5, 0)
    cr.line_to(mx + 0.5, alloc.height)
    cr.stroke()
    cr.set_line_width(1.0)
    cr.set_source_rgba(MARGIN[0], MARGIN[1], MARGIN[2], 0.45)
    cr.move_to(mx + 4.5, 0)
    cr.line_to(mx + 4.5, alloc.height)
    cr.stroke()


def write_pid() -> None:
    PID.parent.mkdir(parents=True, exist_ok=True)
    PID.write_text(str(os.getpid()) + "\n", encoding="utf-8")


def clear_pid() -> None:
    try:
        if PID.exists() and PID.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID.unlink()
    except OSError:
        pass


class StickyPadWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Sticky Pad")
        self.get_style_context().add_class("stickypad")
        self.state = load_state()
        self._save_tid = 0
        self._geom_tid = 0
        self._loading = False
        self._line_h = 26

        self.set_default_size(
            int(self.state.get("width") or DEFAULT_W),
            int(self.state.get("height") or DEFAULT_H),
        )
        self.set_resizable(True)
        self.set_keep_above(bool(self.state.get("keep_above", True)))
        try:
            self.stick()
        except Exception:
            pass
        if ICON.exists():
            self.set_icon_from_file(str(ICON))

        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property("gtk-application-prefer-dark-theme", False)

        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        yellow = Gdk.RGBA()
        yellow.parse("#F8E36B")
        strip = Gdk.RGBA()
        strip.parse("#EED45A")
        ink = Gdk.RGBA()
        ink.parse("#2A2314")
        trans = Gdk.RGBA(red=0, green=0, blue=0, alpha=0)
        self.override_background_color(Gtk.StateFlags.NORMAL, yellow)

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title("")
        hb.override_background_color(Gtk.StateFlags.NORMAL, strip)
        hb.override_color(Gtk.StateFlags.NORMAL, ink)
        self.set_titlebar(hb)

        prev_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        prev_btn.set_tooltip_text("Previous page")
        prev_btn.connect("clicked", lambda *_: self._step(-1))
        hb.pack_start(prev_btn)

        self.pager = Gtk.Label(label="1 / 1")
        self.pager.get_style_context().add_class("pager")
        self.pager.set_xalign(0.5)
        hb.pack_start(self.pager)

        next_btn = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        next_btn.set_tooltip_text("Next page")
        next_btn.connect("clicked", lambda *_: self._step(1))
        hb.pack_start(next_btn)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_placeholder_text("Page title")
        self.title_entry.get_style_context().add_class("title")
        self.title_entry.set_hexpand(True)
        self.title_entry.connect("changed", self._on_title_changed)
        hb.set_custom_title(self.title_entry)

        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        add_btn.set_tooltip_text("New page")
        add_btn.connect("clicked", lambda *_: self._new_page())
        hb.pack_end(add_btn)

        del_btn = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
        del_btn.set_tooltip_text("Delete this page")
        del_btn.connect("clicked", lambda *_: self._delete_page())
        hb.pack_end(del_btn)

        self.pin = Gtk.ToggleButton(label="Pin")
        self.pin.set_tooltip_text("Keep on top of other windows")
        self.pin.set_active(bool(self.state.get("keep_above", True)))
        self.pin.connect("toggled", self._on_pin)
        hb.pack_end(self.pin)

        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(48)
        self.view.set_right_margin(18)
        self.view.set_top_margin(10)
        self.view.set_bottom_margin(24)
        self.view.set_pixels_above_lines(LINE_ABOVE)
        self.view.set_pixels_below_lines(LINE_BELOW)
        self.view.set_pixels_inside_wrap(0)
        self.view.set_accepts_tab(True)
        self.view.override_background_color(Gtk.StateFlags.NORMAL, trans)
        self.view.override_color(Gtk.StateFlags.NORMAL, ink)
        self.view.override_font(Pango.FontDescription("Liberation Sans 16"))
        try:
            self.view.set_input_hints(Gtk.InputHints.SPELLCHECK)
        except Exception:
            pass
        self.buf = self.view.get_buffer()
        self.buf.connect("changed", self._on_text_changed)
        self.view.connect("draw", self._on_draw)
        self.view.connect("button-press-event", self._on_view_press)
        self.view.connect("populate-popup", self._on_popup)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)
        scroll.override_background_color(Gtk.StateFlags.NORMAL, yellow)
        scroll.add(self.view)
        paper = Gtk.EventBox()
        paper.override_background_color(Gtk.StateFlags.NORMAL, yellow)
        paper.add(scroll)
        self.add(paper)

        self.connect("configure-event", self._on_configure)
        self.connect("delete-event", self._on_delete)
        self.connect("key-press-event", self._on_key)
        self.connect("map-event", self._on_map)

        self._load_active()
        GLib.idle_add(self._focus_pad)
        dump = os.environ.get("STICKYPAD_DUMP") or ""
        if dump:
            GLib.timeout_add(450, lambda: self._dump_png(dump))

    def notes(self) -> list[dict]:
        return self.state.setdefault("notes", [new_note()])

    def active_note(self) -> dict:
        notes = self.notes()
        i = int(self.state.get("active") or 0)
        if i < 0 or i >= len(notes):
            i = 0
            self.state["active"] = 0
        return notes[i]

    def _focus_pad(self) -> bool:
        self.view.grab_focus()
        return False

    def _on_map(self, *_args):
        x, y = self.state.get("x"), self.state.get("y")
        if isinstance(x, int) and isinstance(y, int) and x >= 0 and y >= 0:
            try:
                self.move(x, y)
            except Exception:
                pass
        GLib.idle_add(self._focus_pad)
        return False

    def _on_pin(self, btn: Gtk.ToggleButton) -> None:
        on = btn.get_active()
        self.set_keep_above(on)
        self.state["keep_above"] = on
        self._save_now()

    def _on_view_press(self, _w, _event):
        self.view.grab_focus()
        return False

    def _on_key(self, _w, event) -> bool:
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        key = Gdk.keyval_name(event.keyval) or ""
        if ctrl and key in ("n", "N"):
            self._new_page()
            return True
        if ctrl and key in ("s", "S"):
            self._flush_editor()
            self._save_now()
            return True
        if ctrl and key in ("Page_Down", "Tab"):
            if key == "Tab" and event.state & Gdk.ModifierType.SHIFT_MASK:
                self._step(-1)
            else:
                self._step(1)
            return True
        if ctrl and key == "Page_Up":
            self._step(-1)
            return True
        if ctrl and key in ("w", "W", "q", "Q"):
            self.close()
            return True
        return False

    def _on_popup(self, _view, menu: Gtk.Menu) -> None:
        menu.prepend(Gtk.SeparatorMenuItem())
        items = [
            ("New page", self._new_page),
            ("Delete this page", self._delete_page),
            ("Open notes folder", self._open_folder),
        ]
        for label, fn in reversed(items):
            it = Gtk.MenuItem(label=label)
            it.connect("activate", lambda _m, f=fn: f())
            menu.prepend(it)
        menu.show_all()

    def _on_title_changed(self, entry: Gtk.Entry) -> None:
        if self._loading:
            return
        self.active_note()["title"] = entry.get_text()
        self.active_note()["updated"] = now_iso()
        self._schedule_save()

    def _on_text_changed(self, _buf) -> None:
        if self._loading:
            return
        self._schedule_save()

    def _on_configure(self, _w, event) -> bool:
        self.state["width"] = int(event.width)
        self.state["height"] = int(event.height)
        if event.x or event.y:
            self.state["x"] = int(event.x)
            self.state["y"] = int(event.y)
        if self._geom_tid:
            GLib.source_remove(self._geom_tid)
        self._geom_tid = GLib.timeout_add(SAVE_MS, self._save_geom)
        return False

    def _save_geom(self) -> bool:
        self._geom_tid = 0
        self._save_now()
        return False

    def _on_delete(self, *_args) -> bool:
        self._flush_editor()
        self._save_now()
        clear_pid()
        return False

    def _line_height(self) -> int:
        ctx = self.view.get_pango_context()
        metrics = ctx.get_metrics(ctx.get_font_description())
        h = (metrics.get_ascent() + metrics.get_descent()) / Pango.SCALE
        h += LINE_ABOVE + LINE_BELOW
        return max(18, int(round(h)))

    def _on_draw(self, tv: Gtk.TextView, cr) -> bool:
        paint_legal_pad(tv, cr)
        return False

    def _flush_editor(self) -> None:
        note = self.active_note()
        start, end = self.buf.get_bounds()
        note["text"] = self.buf.get_text(start, end, True)
        note["title"] = self.title_entry.get_text()
        note["updated"] = now_iso()

    def _load_active(self) -> None:
        self._loading = True
        notes = self.notes()
        i = int(self.state.get("active") or 0)
        i = max(0, min(i, len(notes) - 1))
        self.state["active"] = i
        note = notes[i]
        self.buf.set_text(note.get("text") or "")
        self.title_entry.set_text(note.get("title") or "")
        self.pager.set_text(f"{i + 1} / {len(notes)}")
        self.set_title(note.get("title") or "Sticky Pad")
        self._loading = False
        GLib.idle_add(self._focus_pad)

    def _step(self, delta: int) -> None:
        notes = self.notes()
        if len(notes) < 2:
            return
        self._flush_editor()
        i = (int(self.state.get("active") or 0) + delta) % len(notes)
        self.state["active"] = i
        self._load_active()
        self._save_now()

    def _new_page(self) -> None:
        self._flush_editor()
        notes = self.notes()
        notes.append(new_note())
        self.state["active"] = len(notes) - 1
        self._load_active()
        self._save_now()

    def _delete_page(self) -> None:
        notes = self.notes()
        note = self.active_note()
        if (note.get("text") or "").strip() or (note.get("title") or "").strip():
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.OK_CANCEL,
                text="Delete this page?",
            )
            dlg.format_secondary_text("This page’s text will be gone.")
            resp = dlg.run()
            dlg.destroy()
            if resp != Gtk.ResponseType.OK:
                return
        i = int(self.state.get("active") or 0)
        if len(notes) == 1:
            notes[0] = new_note()
        else:
            notes.pop(i)
            if i >= len(notes):
                i = len(notes) - 1
            self.state["active"] = i
        self._load_active()
        self._save_now()

    def _open_folder(self) -> None:
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        Gio.AppInfo.launch_default_for_uri(CFG_DIR.as_uri(), None)

    def _schedule_save(self) -> None:
        if self._save_tid:
            GLib.source_remove(self._save_tid)
        self._save_tid = GLib.timeout_add(SAVE_MS, self._debounced_save)

    def _debounced_save(self) -> bool:
        self._save_tid = 0
        self._flush_editor()
        self._save_now()
        return False

    def _save_now(self) -> None:
        try:
            save_state(self.state)
        except OSError as exc:
            log(f"save failed: {exc}")

    def _dump_png(self, path: str) -> bool:
        try:
            import cairo

            self.queue_draw()
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            w, h = self.get_size()
            if w < 8 or h < 8:
                alloc = self.get_allocation()
                w, h = alloc.width, alloc.height
            pb = None
            gdk_win = self.get_window()
            if gdk_win is not None:
                pb = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, w, h)
            if pb is not None:
                pb.savev(path, "png", [], [])
                log(f"dump pixbuf {path}")
            else:
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(w, 1), max(h, 1))
                cr = cairo.Context(surf)
                self.draw(cr)
                surf.write_to_png(path)
                log(f"dump cairo {path}")
        except Exception as exc:
            log(f"dump failed: {exc}")
        if os.environ.get("STICKYPAD_DUMP_QUIT") == "1":
            self.close()
        return False


class StickyPadApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = StickyPadWindow(self)
            self.win.show_all()
        self.win.present()
        GLib.idle_add(self.win._focus_pad)


def dump_offscreen(path: str, sample_text: str = "Milk\nEggs\nBread\n") -> str:
    """Render the pad off-screen (no compositor screenshot needed)."""
    settings = Gtk.Settings.get_default()
    if settings is not None:
        settings.set_property("gtk-application-prefer-dark-theme", False)
    css = Gtk.CssProvider()
    css.load_from_data(CSS)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    yellow = Gdk.RGBA()
    yellow.parse("#F8E36B")
    ink = Gdk.RGBA()
    ink.parse("#2A2314")
    trans = Gdk.RGBA(red=0, green=0, blue=0, alpha=0)

    win = Gtk.OffscreenWindow()
    win.set_default_size(DEFAULT_W, DEFAULT_H)
    win.override_background_color(Gtk.StateFlags.NORMAL, yellow)

    tv = Gtk.TextView()
    tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    tv.set_left_margin(48)
    tv.set_right_margin(18)
    tv.set_top_margin(10)
    tv.set_bottom_margin(24)
    tv.set_pixels_above_lines(LINE_ABOVE)
    tv.set_pixels_below_lines(LINE_BELOW)
    tv.override_background_color(Gtk.StateFlags.NORMAL, trans)
    tv.override_color(Gtk.StateFlags.NORMAL, ink)
    tv.override_font(Pango.FontDescription("Liberation Sans 16"))
    tv.get_buffer().set_text(sample_text)

    def on_draw(widget, cr):
        paint_legal_pad(widget, cr)
        return False

    tv.connect("draw", on_draw)
    win.add(tv)
    win.show_all()
    for _ in range(40):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    pb = win.get_pixbuf()
    if pb is None:
        raise RuntimeError("offscreen pixbuf was empty")
    pb.savev(path, "png", [], [])
    win.destroy()
    return path


def self_test() -> int:
    global CFG, CFG_DIR
    import tempfile

    td = Path(tempfile.mkdtemp(prefix="stickypad-test-"))
    CFG_DIR = td
    CFG = td / "notes.json"
    st = default_state()
    st["notes"][0]["title"] = "Hello"
    st["notes"][0]["text"] = "typed on the pad"
    save_state(st)
    loaded = load_state()
    assert loaded["notes"][0]["title"] == "Hello", loaded
    assert loaded["notes"][0]["text"] == "typed on the pad", loaded
    assert loaded["keep_above"] is True
    icon = td / "icon.png"
    write_icon(icon, 128)
    assert icon.exists() and icon.stat().st_size > 200, icon
    if "--visual" in sys.argv or os.environ.get("DISPLAY"):
        png = "/tmp/stickypad-offscreen.png"
        dump_offscreen(png)
        assert Path(png).stat().st_size > 1000, png
        print("visual dump", png)
    print("stickypad self-test ok", CFG)
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    if "--dump-offscreen" in sys.argv:
        path = "/tmp/stickypad-offscreen.png"
        for i, arg in enumerate(sys.argv):
            if arg == "--dump-offscreen" and i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                path = sys.argv[i + 1]
                break
        dump_offscreen(path)
        print(path)
        return 0
    if not ICON.exists():
        try:
            write_icon(ICON, 256)
        except Exception as exc:
            log(f"icon: {exc}")
    GLib.set_prgname(PRGNAME)
    write_pid()
    try:
        app = StickyPadApp()
        return app.run([sys.argv[0]])
    finally:
        clear_pid()


if __name__ == "__main__":
    sys.exit(main())
