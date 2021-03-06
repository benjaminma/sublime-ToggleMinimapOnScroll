import sublime
import sublime_plugin
from threading import Thread, Lock
from time import sleep

default_settings = {
    "toggle_minimap_on_scroll_enabled_by_default": True,
    "toggle_minimap_on_scroll_duration_in_seconds": 2.5,
    "toggle_minimap_on_scroll_samples_per_second": 7.5,
    "toggle_minimap_on_cursor_line_changed": False,
    "toggle_minimap_on_view_changed": False
}
def get_setting(name):
    settings = sublime.load_settings("ToggleMinimapOnScroll.sublime-settings")
    return settings.get(name, default_settings[name])

toggle_minimap_on_scroll_is_enabled = get_setting("toggle_minimap_on_scroll_enabled_by_default")
def plugin_loaded():
    global toggle_minimap_on_scroll_is_enabled
    toggle_minimap_on_scroll_is_enabled = get_setting("toggle_minimap_on_scroll_enabled_by_default")

lock = Lock()
ignore_events = False
ignore_count = 0
prev_wrap_width = None

def unset_fixed_wrap_width(view=None):
    if not view:
        settings = sublime.active_window().active_view().settings()
    else:
        settings = view.settings()
    settings.set("wrap_width", prev_wrap_width)

def set_fixed_wrap_width():
    global prev_wrap_width
    settings = sublime.active_window().active_view().settings()
    prev_wrap_width = settings.get("wrap_width", 0)
    if not prev_wrap_width:
        settings.set("wrap_width", sublime.active_window().active_view().viewport_extent()[0] / sublime.active_window().active_view().em_width())

def untoggle_minimap(view):
    with lock:
        global ignore_events, ignore_count
        if ignore_events:
            view.window().run_command("toggle_minimap")
            unset_fixed_wrap_width(view)
            ignore_events = False
            ignore_count += 1

def untoggle_minimap_on_timeout():
    with lock:
        global ignore_events, ignore_count
        if ignore_count:
            ignore_count -= 1
            return
        sublime.active_window().run_command("toggle_minimap")
        unset_fixed_wrap_width()
        ignore_events = False

def toggle_minimap():
    with lock:
        global ignore_events, ignore_count
        if not ignore_events:
            set_fixed_wrap_width()
            sublime.active_window().run_command("toggle_minimap")
            ignore_events = True
        else:
            ignore_count += 1
        sublime.set_timeout(untoggle_minimap_on_timeout, int(float(get_setting("toggle_minimap_on_scroll_duration_in_seconds")) * 1000))

prev_view_id = None
prev_viewport_position = None
prev_viewport_extent = None
def viewport_scrolled():
    global prev_view_id, prev_viewport_position, prev_viewport_extent
    viewport_scrolled = False
    curr_view_id = sublime.active_window().active_view().id()
    curr_viewport_position = sublime.active_window().active_view().viewport_position()
    curr_viewport_extent = sublime.active_window().active_view().viewport_extent()
    if prev_view_id == curr_view_id and curr_viewport_position != prev_viewport_position and curr_viewport_extent == prev_viewport_extent:
        viewport_scrolled = True
    prev_view_id = curr_view_id
    prev_viewport_position = curr_viewport_position
    prev_viewport_extent = curr_viewport_extent
    return viewport_scrolled

def sample_viewport():
    try:
        if viewport_scrolled():
            toggle_minimap()
    except AttributeError:
        pass  # suppress ignorable error message (window and/or view does not exist)

class ViewportMonitor(Thread):
    sample_period = 1 / default_settings["toggle_minimap_on_scroll_samples_per_second"]

    def run(self):
        while True:
            if toggle_minimap_on_scroll_is_enabled:
                sublime.set_timeout(sample_viewport, 0)
            sublime.set_timeout(self.update_sample_period, 0)
            sleep(self.sample_period)

    def update_sample_period(self):
        self.sample_period = 1 / float(get_setting("toggle_minimap_on_scroll_samples_per_second"))
if not "viewport_monitor" in globals():
    viewport_monitor = ViewportMonitor()
    viewport_monitor.start()

class EventListener(sublime_plugin.EventListener):
    startup_events_triggered = False  # ignore startup events (Sublime Text 2)
    prev_sel_begin_row = None
    prev_sel_end_row = None
    prev_num_sel = None

    def cursor_line_changed(self, view):
        cursor_line_changed = False
        curr_sel_begin_row = view.rowcol(view.sel()[0].begin())[0]
        curr_sel_end_row = view.rowcol(view.sel()[0].end())[0]
        curr_num_sel = len(view.sel())
        if curr_sel_begin_row != self.prev_sel_begin_row or curr_sel_end_row != self.prev_sel_end_row or curr_num_sel != self.prev_num_sel:
            cursor_line_changed = True
        self.prev_sel_begin_row = curr_sel_begin_row
        self.prev_sel_end_row = curr_sel_end_row
        self.prev_num_sel = curr_num_sel
        return cursor_line_changed

    def on_selection_modified(self, view):
        if not view.window():  # ignore startup events (Sublime Text 2)
            return
        if not self.startup_events_triggered:  # ignore startup events (Sublime Text 2)
            self.startup_events_triggered = True
            return
        if toggle_minimap_on_scroll_is_enabled and get_setting("toggle_minimap_on_cursor_line_changed") and self.cursor_line_changed(view):
            toggle_minimap()

    def on_activated(self, view):
        if not self.startup_events_triggered:  # ignore startup events (Sublime Text 2)
            return
        if toggle_minimap_on_scroll_is_enabled and get_setting("toggle_minimap_on_view_changed"):
            toggle_minimap()

    def on_deactivated(self, view):
        untoggle_minimap(view)

    def on_close(self, view):
        try:
            untoggle_minimap(view)
        except AttributeError:
            pass  # suppress ignorable error message (window does not exist)

class DisableToggleMinimapOnScroll(sublime_plugin.WindowCommand):
    def run(self):
        global toggle_minimap_on_scroll_is_enabled
        toggle_minimap_on_scroll_is_enabled = False

    def is_enabled(self):
        return toggle_minimap_on_scroll_is_enabled

class EnableToggleMinimapOnScroll(sublime_plugin.WindowCommand):
    def run(self):
        global toggle_minimap_on_scroll_is_enabled
        toggle_minimap_on_scroll_is_enabled = True

    def is_enabled(self):
        return not toggle_minimap_on_scroll_is_enabled
