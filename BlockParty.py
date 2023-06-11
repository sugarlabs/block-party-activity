#
# Copyright (c) 2007 Vadim Gerasimov <vadim@media.mit.edu>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

#  Block Party Activity for OLPC
#  by Vadim Gerasimov
#  updated 23 Feb 2007

import time
import sys
import random
import copy
import os

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Pango
from gi.repository import PangoCairo

from aplay import Aplay


def color_parse(color):
    rgba = Gdk.RGBA()
    rgba.parse(color)
    return rgba


class VanishingCursor:

    def __init__(self, win, hide_time=3):
        self.win = win
        self._blank_cursor = Gdk.Cursor.new(Gdk.CursorType.BLANK_CURSOR)
        self._old_cursor = self.win.get_window().get_cursor()
        self.hide_time = hide_time
        self.last_touched = time.time()
        self.win.connect("motion-notify-event", self.move_event)
        self.win.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

    def move_event(self, win, event):
        self._set_cursor(self._old_cursor)
        self.last_touched = time.time()
        return True

    def time_event(self):
        if time.time() - self.last_touched > self.hide_time:
            self._set_cursor(self._blank_cursor)
        return True

    def _set_cursor(self, cursor):
        self.win.get_window().set_cursor(cursor)
        Gdk.flush()


class BlockParty:

    bw, bh, gridwidth = 11, 20, 1

    colors = [color_parse(i) for i in [
        '#101944', 'blue', 'green', 'cyan',
        'red', 'magenta', 'YellowGreen', 'white'
    ]]
    figures = [
        [[0, 0, 0, 0],
         [0, 1, 1, 0],
         [0, 1, 1, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [0, 2, 2, 0],
         [2, 2, 0, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [3, 3, 0, 0],
         [0, 3, 3, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [4, 4, 4, 4],
         [0, 0, 0, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [0, 5, 5, 5],
         [0, 5, 0, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [6, 6, 6, 0],
         [0, 6, 0, 0],
         [0, 0, 0, 0]],
        [[0, 0, 0, 0],
         [0, 7, 0, 0],
         [0, 7, 7, 7],
         [0, 0, 0, 0]]]

    left_key = ['Left', 'KP_Left']
    right_key = ['Right', 'KP_Right']
    speed_key = ['Down', 'KP_Down']
    drop_key = ['space']
    rotate_key = ['Up', 'KP_Up']
    exit_key = ['Escape']
    sound_toggle_key = ['s', 'S']
    enter_key = ['Return']

    next_figure = None
    level = 0
    figure_score = 0
    scorex, scorey = 20, 100

    IDLE, SELECT_LEVEL, PLAY, GAME_OVER = 0, 1, 2, 3

    def __init__(self, toplevel_window, da, font_face='Sans', font_size=14,
                 gcs=0, score_path=None):

        ghost_colors = []
        for clr in self.colors :
            ghost_color = clr.copy()
            ghost_color.alpha = 0.3
            ghost_colors.append(ghost_color)

        self.colors = self.colors + ghost_colors[1:]

        self.glass = [[0] * self.bw for i in range(self.bh)]
        self.window = toplevel_window
        self.da = da
        self.game_mode = self.IDLE
        self.sound = True

        self.window_w = self.window.get_screen().get_width()
        self.window_h = self.window.get_screen().get_height() - gcs
        self.window.set_title("Block Party")
        self.window.connect("destroy", lambda w: Gtk.main_quit())
        da.set_size_request(self.window_w, self.window_h)
        da.connect("draw", self.draw_cb)
        self.window.connect("key-press-event", self.keypress_cb)
        self.window.connect("key-release-event", self.keyrelease_cb)

        self.color_back = color_parse("#343e76")
        self.color_glass = color_parse("#6e82e6")
        self.color_glass_back = color_parse("#4960d4")
        self.color_score = color_parse("white")
        self.color_ui_text = color_parse("#eeeeee")

        self.bwpx = int(self.window_w / (self.bw + self.bw / 2 + 2))
        self.bhpx = int(self.window_h / (self.bh + 2))
        if self.bwpx < self.bhpx:
            self.bhpx = self.bwpx
        else:
            self.bwpx = self.bhpx
        self.xshift = int((self.window_w - (self.bw + 1) * self.bwpx) / 2)
        self.yshift = int((self.window_h - (self.bh + 1) * self.bhpx) / 2)
        self.xnext = self.window_w - self.xshift / \
            2 - min(self.xshift / 2, 100)
        self.ynext = self.window_h / 2 - min(self.window_h / 2, 200)

        self.scorex = self.xshift / 2 - min(self.xshift / 2, 150)
        self.scorey = self.window_h / 2 - min(self.window_h / 2, 100)

        self.score_path = score_path

        self.font = Pango.FontDescription(font_face)
        self.font.set_size(self.window_w * font_size * Pango.SCALE / 900)
        self.audioplayer = Aplay()

        self.init_game()

        def realize_cb(da):
            self.vanishing_cursor = VanishingCursor(da, 5)
            self.timer_id = GLib.timeout_add(20, self.timer_cb)
        self.da.connect("realize", realize_cb)

    def init_game(self):
        self.clear_glass()
        self.can_speed_up = True
        self.linecount = 0
        if self.score_path is not None:
            self.hscore = self.read_highscore()
        self.score = 0
        self.new_figure()
        self.set_level(5)

        self.queue_draw_complete()
        self.game_mode = self.SELECT_LEVEL

    def set_time_step(self):
        self.time_step = 0.1 + (9 - self.level) * 0.1

    def draw_glass(self, cairo_ctx):
        draw_glass = copy.deepcopy(self.glass)

        ghost_figure = copy.deepcopy(self.figure)
        ghost_py = self.generate_ghost_py(ghost_figure)

        for i in range(4):
            for j in range(4):
                if self.py + i < self.bh and self.figure[i][j] != 0:
                    draw_glass[self.py + i][self.px + j] = self.figure[i][j]
                    draw_glass[ghost_py + i][self.px + j] = ghost_figure[i][j] + len(self.figures)

        for i in range(self.bh):
            for j in range(self.bw):
                if self.view_glass is None or \
                   draw_glass[i][j] != self.view_glass[i][j]:

                    color = self.colors[draw_glass[i][j]]
                    cairo_ctx.set_source_rgba(color.red,
                                              color.green,
                                              color.blue,
                                              color.alpha)
                    cairo_ctx.rectangle(
                        self.xshift + j * self.bwpx,
                        self.yshift + (self.bh - i - 1) * self.bhpx,
                        self.bwpx - self.gridwidth, self.bhpx - self.gridwidth)

                    cairo_ctx.fill()

        self.view_glass = draw_glass

    def quit_game(self):
        self.audioplayer.close()
        sys.exit()

    def key_action(self, key):
        if key in self.exit_key:
            self.quit_game()
        if key in self.sound_toggle_key:
            self.sound = not self.sound
            return
        if self.game_mode == self.SELECT_LEVEL:
            if key in self.left_key:
                self.set_level(self.level - 1)
                self.queue_draw_glass(True)
            else:
                if key in self.right_key:
                    self.set_level(self.level + 1)
                    self.queue_draw_glass(True)
                else:  # if key in enter_key:
                    self.queue_draw_complete()
                    self.next_tick = time.time() + self.time_step
                    self.game_mode = self.PLAY
            return
        if self.game_mode == self.IDLE:
            return
        if self.game_mode == self.GAME_OVER:
            if key in self.enter_key:
                self.init_game()
                return

        changed = False
        if key in self.left_key:
            self.px -= 1
            if not self.figure_fits():
                self.px += 1
            else:
                changed = True
        if key in self.right_key:
            self.px += 1
            if not self.figure_fits():
                self.px -= 1
            else:
                changed = True
        if key in self.speed_key and self.can_speed_up:
            self.time_step = (9 - self.level) * 0.005
        if key in self.drop_key:
            changed = self.drop_figure()
        if key in self.rotate_key:
            changed = self.rotate_figure_ccw(True)
        if changed:
            self.queue_draw_glass(False)

    def tick(self):
        self.py -= 1
        self.queue_draw_glass(False)
        if self.figure_score > 0:
            self.figure_score -= 1
        if not self.figure_fits():
            self.py += 1
            self.can_speed_up = False
            self.set_time_step()
            self.put_figure()
            self.make_sound('heart.wav')
            self.new_figure()
            if not self.figure_fits():
                i = random.randint(0, 2)
                if i == 0:
                    self.make_sound('ouch.wav')
                if i == 1:
                    self.make_sound('wah.au')
                if i == 2:
                    self.make_sound('lost.wav')
                self.game_mode = self.GAME_OVER

                self.queue_draw_complete()
                return
        self.chk_glass()
        new_level = int(self.linecount / 5)
        if new_level > self.level:
            self.set_level(new_level)

    def new_figure(self):
        self.figure_score = self.bh + self.level
        self.figure = copy.deepcopy(
            self.figures[random.randint(0, len(self.figures) - 1)])
        for i in range(random.randint(0, 3)):
            self.rotate_figure_ccw(False)
        self.figure, self.next_figure = self.next_figure, self.figure
        self.px = self.bw // 2 - 2
        self.py = self.bh - 3
        if self.figure is None:
            self.new_figure()
        else:
            self.queue_draw_next()

    def rotate_figure_cw(self, check_fit):
        oldfigure = copy.deepcopy(self.figure)
        for i in range(4):
            for j in range(4):
                self.figure[i][j] = oldfigure[j][3 - i]
        if not check_fit or self.figure_fits():
            return True
        else:
            self.figure = oldfigure
            return False

    def rotate_figure_ccw(self, check_fit):
        oldfigure = copy.deepcopy(self.figure)
        for i in range(4):
            for j in range(4):
                self.figure[i][j] = oldfigure[3 - j][i]
        if not check_fit or self.figure_fits():
            return True
        else:
            self.figure = oldfigure
            return False

    def drop_figure(self):
        oldy = self.py
        self.py -= 1
        while self.figure_fits():
            self.py -= 1
        self.py += 1
        return oldy != self.py

    # Takes Argument py to calculate for ghost_peice
    def figure_fits(self, py=None, figure=None):
        if not py and not figure:
            py = self.py
            figure = self.figure
        for i in range(4):
            for j in range(4):
                if self.figure[i][j] != 0:
                    if i + py < 0 or \
                       j + self.px < 0 or j + self.px >= self.bw:
                        return False
                    if i + py < self.bh:
                        if self.glass[i + py][j + self.px] != 0:
                            return False
        return True

    def put_figure(self):
        self.score += self.figure_score
        if self.score_path is not None:
            if self.score > self.hscore:
                self.hscore = self.score
        self.queue_draw_score()
        for i in range(4):
            for j in range(4):
                if i + self.py < self.bh and self.figure[i][j] != 0:
                    self.glass[i + self.py][j + self.px] = self.figure[i][j]

    def generate_ghost_py(self, figure):
        ghost_py = self.py - 1
        while self.figure_fits(ghost_py, figure):
            ghost_py -= 1
        return ghost_py + 1

    def chk_glass(self):
        clearlines = []
        for i in range(self.bh - 1, -1, -1):
            j = 0
            while j < self.bw and self.glass[i][j] != 0:
                j += 1
            if j >= self.bw:
                clearlines.append(i)
                self.linecount += 1
                for j in range(self.bw):
                    self.glass[i][j] = -self.glass[i][j]
        if len(clearlines) > 0:
            self.make_sound('boom.au')
            for i in clearlines:
                for j in range(self.bw):
                    self.glass[i][j] = 0
            self.queue_draw_glass(True)
            time.sleep(self.time_step)
            self.next_tick += self.time_step * 2
        for i in clearlines:
            tmp = self.glass[i]
            for ii in range(i, self.bh - 1):
                self.glass[ii] = self.glass[ii + 1]
            self.glass[self.bh - 1] = tmp

    def draw_background(self, cairo_ctx):
        cairo_ctx.set_source_rgb(self.color_back.red,
                                 self.color_back.green,
                                 self.color_back.blue)
        cairo_ctx.rectangle(0, 0, self.window_w, self.window_h)
        cairo_ctx.fill()
        cairo_ctx.set_source_rgb(self.color_glass.red,
                                 self.color_glass.green,
                                 self.color_glass.blue)
        cairo_ctx.rectangle(
            self.xshift - self.bwpx / 2, self.yshift,
            self.bwpx * (self.bw + 1) - self.gridwidth, self.bhpx * self.bh + self.bhpx / 2 - self.gridwidth)
        cairo_ctx.fill()
        cairo_ctx.set_source_rgb(self.color_glass_back.red,
                                 self.color_glass_back.green,
                                 self.color_glass_back.blue)
        cairo_ctx.rectangle(
            self.xshift, self.yshift,
            self.bwpx * self.bw - self.gridwidth, self.bhpx * self.bh - self.gridwidth)
        cairo_ctx.fill()

    def draw_cb(self, widget, cr):
        self.update_picture(cr)

    def queue_draw_complete(self):
        self.queue_draw_score()
        self.queue_draw_next()
        self.queue_draw_glass(True)
        self.da.queue_draw()

    def queue_draw_score(self):
        self.da.queue_draw_area(
            0, 0, self.xshift - self.bw * 2, self.window_h)

    def queue_draw_next(self):
        self.da.queue_draw_area(
            self.xnext, self.ynext, self.bwpx * 5, self.bhpx * 5 + 50)

    def queue_draw_glass(self, redraw):
        if redraw:
            self.da.queue_draw_area(
                self.xshift - self.bwpx / 2, self.yshift,
                self.bwpx * (self.bw + 1), self.bhpx * self.bh + self.bhpx / 2)
        else:
            # TODO: Only update the block since nothing else changed
            self.da.queue_draw_area(
                self.xshift - self.bwpx / 2, self.yshift,
                self.bwpx * (self.bw + 1), self.bhpx * self.bh + self.bhpx / 2)

    def update_picture(self, cairo_ctx):
        self.view_glass = None
        self.draw_background(cairo_ctx)
        self.draw_score(cairo_ctx)
        self.draw_escape(cairo_ctx)

        self.draw_glass(cairo_ctx)
        if self.game_mode is self.GAME_OVER:
            self.draw_game_end_poster(cairo_ctx)
        if self.game_mode is self.SELECT_LEVEL:
            self.draw_select_level_poster(cairo_ctx)

        self.draw_next(cairo_ctx)

    def keypress_cb(self, widget, event):
        self.key_action(Gdk.keyval_name(event.keyval))

    def keyrelease_cb(self, widget, event):
        key = Gdk.keyval_name(event.keyval)
        if key in self.speed_key:
            self.set_time_step()
            self.can_speed_up = True

    def timer_cb(self):
        self.vanishing_cursor.time_event()
        while self.game_mode == self.PLAY and time.time() >= self.next_tick:
            self.next_tick += self.time_step
            self.tick()
        if self.game_mode != self.PLAY:
            self.next_tick = time.time() + 100
        return True

    def draw_string(self, cairo_ctx, string, x, y, is_center):
        pl = PangoCairo.create_layout(cairo_ctx)
        pl.set_text(string, -1)
        pl.set_font_description(self.font)
        width = pl.get_size()[0] / Pango.SCALE

        if is_center:
            x = x - width / 2

        cairo_ctx.move_to(int(x), int(y))
        PangoCairo.layout_path(cairo_ctx, pl)

    def draw_game_end_poster(self, cairo_ctx):
        self.save_highscore()
        cairo_ctx.set_source_rgb(self.colors[0].red,
                                 self.colors[0].green,
                                 self.colors[0].blue)
        cairo_ctx.rectangle(
            self.xshift, self.yshift + (self.bh / 2 - 3) * self.bhpx,
            self.bw * self.bwpx, self.bhpx * 6)
        cairo_ctx.fill()
        cairo_ctx.set_source_rgb(self.color_score.red,
                                 self.colors[0].green,
                                 self.color_score.blue)
        self.draw_string(
            cairo_ctx, 'GAME OVER',
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2 - 1) * self.bhpx, True)
        self.draw_string(
            cairo_ctx, 'Enter to play again',
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2 + 1) * self.bhpx, True)
        cairo_ctx.fill()

    def draw_score(self, cairo_ctx):
        if self.score_path is not None:
            displaystr = 'HighScore: ' + str(self.hscore)
        else:
            displaystr = ''
        displaystr += '\nScore: ' + str(self.score)
        displaystr += '\nLevel: ' + str(self.level)
        displaystr += '\nLines: ' + str(self.linecount)

        cairo_ctx.set_source_rgb(self.color_ui_text.red,
                                 self.color_ui_text.green,
                                 self.color_ui_text.blue)
        self.draw_string(
            cairo_ctx, displaystr, self.scorex, self.scorey, False)
        cairo_ctx.fill()

    def set_level(self, new_level):
        self.level = new_level
        if self.level < 0:
            self.level = 0
        if self.level > 9:
            self.level = 9
        self.set_time_step()
        self.next_tick = time.time() + self.time_step

    def draw_select_level_poster(self, cairo_ctx):

        cairo_ctx.set_source_rgb(self.color_score.red,
                                 self.colors[0].green,
                                 self.color_score.blue)

        self.draw_string(
            cairo_ctx, 'Select Level',
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2 - 4) * self.bhpx, True)
        self.draw_string(
            cairo_ctx, 'Use arrow keys',
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2 - 2) * self.bhpx, True)
        self.draw_string(
            cairo_ctx, 'LEVEL: ' + str(self.level),
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2) * self.bhpx, True)
        self.draw_string(
            cairo_ctx, 'Enter to start',
            self.xshift + (self.bwpx * self.bw) / 2,
            self.yshift + (self.bh / 2 + 2) * self.bhpx, True)
        cairo_ctx.fill()

    def clear_glass(self):
        for i in range(self.bh):
            for j in range(self.bw):
                self.glass[i][j] = 0

    def draw_next(self, cairo_ctx):
        cairo_ctx.set_line_width(1)
        cairo_ctx.set_source_rgb(self.color_ui_text.red,
                                 self.color_ui_text.green,
                                 self.color_ui_text.blue)
        self.draw_string(
            cairo_ctx, 'NEXT', self.xnext + self.bwpx * 2.5, self.ynext, True)
        cairo_ctx.fill()
        cairo_ctx.set_source_rgb(self.color_glass.red,
                                 self.color_glass.green,
                                 self.color_glass.blue)
        cairo_ctx.rectangle(
            self.xnext, self.ynext + 50, self.bwpx * 5, self.bhpx * 5)
        cairo_ctx.fill()
        cairo_ctx.set_source_rgb(self.colors[0].red,
                                 self.colors[0].green,
                                 self.colors[0].blue)
        cairo_ctx.rectangle(
            self.xnext + self.bwpx / 4, self.ynext + 50 + self.bhpx / 4, self.bwpx * 4.5, self.bhpx * 4.5)
        cairo_ctx.fill()
        for i in range(4):
            for j in range(4):
                if self.next_figure[i][j] != 0:
                    color = self.colors[self.next_figure[i][j]]
                    cairo_ctx.set_source_rgb(
                        color.red, color.green, color.blue)
                    cairo_ctx.rectangle(
                        self.xnext + j * self.bwpx + self.bwpx / 2,
                        self.ynext + 50 + (3 - i) * self.bhpx + self.bhpx / 2,
                        self.bwpx - self.gridwidth, self.bhpx - self.gridwidth)
        cairo_ctx.fill()

    def draw_escape(self, cairo_ctx):
        cairo_ctx.set_line_width(1)
        cairo_ctx.set_source_rgb(self.color_ui_text.red,
                                 self.color_ui_text.green,
                                 self.color_ui_text.blue)

        self.draw_string(
            cairo_ctx, 'Press ESC to exit',
            self.xnext + self.bwpx * 2.5, self.window_h - 4 * self.bhpx, True)
        cairo_ctx.fill()

    def make_sound(self, filename):
        filename = os.path.abspath(os.path.join('sounds', filename))
        if self.sound:
            self.audioplayer.play(filename)

    def close(self):
        if self.timer_id != None:
            GLib.source_remove(self.timer_id)
        self.audioplayer.close()

    def read_highscore(self):
        try:
            with open(self.score_path, "r") as fp:
                return int(fp.readline())
        except (FileNotFoundError, ValueError, IndexError):
            return 0

    def save_highscore(self):
        if self.score > self.read_highscore():
            try:
                with open(self.score_path, "w") as fp:
                    fp.writelines([str(self.score)])
            except PermissionError:
                pass


def main():
    win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    da = Gtk.DrawingArea()
    BlockParty(win, da)
    win.add(da)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
