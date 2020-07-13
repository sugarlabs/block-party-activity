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

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk

from BlockParty import BlockParty

from sugar3.activity import activity
from sugar3.graphics.style import FONT_FACE, FONT_SIZE


class BlockPartyActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        canvas = Gtk.DrawingArea()
        self.block_party = BlockParty(
            self, canvas, font_face=FONT_FACE, font_size=FONT_SIZE * 2)
        self.set_canvas(canvas)
        canvas.show()

    def close(self, **kwargs):
        self.block_party.close()
        activity.Activity.close(self, **kwargs)
