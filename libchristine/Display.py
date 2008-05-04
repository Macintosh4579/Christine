# -*- coding: utf-8 -*-
#
# This file is part of the Christine project
#
# Copyright (c) 2006-2007 Marco Antonio Islas Cruz
#
# Christine is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Christine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# @category  libchristine
# @package   Display
# @author    Marco Antonio Islas Cruz <markuz@islascruz.org>
# @author    Miguel Vazquez Gocobachi <demrit@gnu.org>
# @copyright 2006-2007 Christine Development Group
# @license   http://www.gnu.org/licenses/gpl.txt

import gtk
import cairo
import pango
import gobject
import math
from libchristine.Validator import *
from libchristine.GtkMisc import CairoMisc, GtkMisc

BORDER_WIDTH  = 3
POS_INCREMENT = 3
LINE_WIDTH    = 2

class Display(gtk.DrawingArea, CairoMisc, GtkMisc,object):
	"""
	Display the track progress in christine
	"""


	def __init__(self, text= ''):
		"""
		Constructor
		"""
		# since this class inherits methods and properties
		# from gtk.Drawind_area we need to initialize it too
		gtk.DrawingArea.__init__(self)
		CairoMisc.__init__(self)
		GtkMisc.__init__(self)

		# This flag is supposed to be used to check if the
		# display y being drawed
		self.__HPos = 0

		self.__color1 = gtk.gdk.color_parse('#FFFFFF')
		self.__color2 = gtk.gdk.color_parse('#3D3D3D')


		# Adding some events
		self.set_property('events', gtk.gdk.EXPOSURE_MASK |
								    gtk.gdk.POINTER_MOTION_MASK |
								    gtk.gdk.BUTTON_PRESS_MASK)

		self.connect('button-press-event', self.__buttonPressEvent)
		self.connect('expose-event',       self.__doExpose)

		gobject.signal_new('value-changed', self,
				           gobject.SIGNAL_RUN_LAST,
				           gobject.TYPE_NONE,
				           (gobject.TYPE_PYOBJECT,))

		self.__Song           = ""
		self.__Text           = ""
		self.__WindowPosition = 0
		self.__Value          = 0
		self.setText(text)
		self.set_size_request(300, 42)

	def __emit(self):
		'''
		Emits an expose event
		'''

		self.emit('expose-event', gtk.gdk.Event(gtk.gdk.EXPOSE))
		#self.emit("expose-event",self)
		return True

	def __buttonPressEvent(self, widget, event):
		"""
		Called when a button is pressed in the display
		"""
		(w, h)   = (self.allocation.width,self.allocation.height)
		(x, y)       = self.get_pointer()
		(minx, miny) = self.__Layout.get_pixel_size()
		minx         = miny
		width        = (w - miny - (BORDER_WIDTH * 3))
		miny         = (miny + (BORDER_WIDTH * 2))
		maxx         = (minx + width)
		maxy         = (miny + BORDER_WIDTH)

		if ((x >= minx) and (x <= maxx) and (y >= miny) and (y <= maxy)):
			value = (((x - minx) * 1.0) / width)
			self.setScale(value)
			self.emit("value-changed",self)

	def setText(self, text):
		"""
		Sets text
		"""
		self.__Text = text.encode('latin-1')

	def setSong(self, song):
		"""
		Sets song
		"""
		if (not isString(song)):
			raise TypeError('Paramether must be text')
		try:
			self.__Song = u'%s'%song.encode('latin-1')
		except:
			self.__Song = song

	def getValue(self):
		"""
		Gets value
		"""
		return self.__Value

	def setValue(self, value):
		self.__Value = value

	def setScale(self, value):
		"""
		Sets scale value
		"""
		try:
			value = float(value)
		except ValueError, a:
			raise ValueError(a)
		if ((value > 1.0) or (value < 0.0)):
			raise ValueError('value > 1.0 or value < 0.0')
		self.__Value = value
		self.__emit()

	def __doExpose(self,widget,event):
		if getattr(self,'window', None) == None:
			return True
		context = self.window.cairo_create()
		#clear the bitmap
		self.__drawDisplay(context)


	def __drawDisplay(self, context, allocation=0):
		"""
		This function is used to draw the display
		"""
		style = self.get_style()
		tcolor = style.fg[0]
		wcolor = style.bg[0]
		fontdesc = style.font_desc

		br,bg,bb = (self.getCairoColor(wcolor.red),
				self.getCairoColor(wcolor.green),
				self.getCairoColor(wcolor.blue))

		fr,fg,fb = (self.getCairoColor(tcolor.red),
				self.getCairoColor(tcolor.green),
				self.getCairoColor(tcolor.blue))

		(x, y, w, h)   = self.allocation


		context.move_to( 0, 0 )
		context.set_operator(cairo.OPERATOR_OVER)

		context.set_line_width( 1 )
		context.set_antialias(cairo.ANTIALIAS_DEFAULT)

		self.render_rect(context, 0, 0, w, h, 1)
		context.rectangle(x,y,w,h)
		context.set_source_rgb(br,bg,bb)
		context.fill()

		# Write text
		self.__Layout  = self.create_pango_layout(self.__Song)

		self.__Layout.set_font_description(fontdesc)

		(fontw, fonth) = self.__Layout.get_pixel_size()

		if self.__HPos == 0 or fontw < w:
			self.__HPos = (w - fontw) / 2
		elif self.__HPos > (fontw-(fontw*2)):
			self.__HPos = self.__HPos - 3
		else:
			self.__HPos = w + 1
		context.move_to(self.__HPos, (fonth)/2)
		context.set_source_rgb(fr,fg,fb)
		context.update_layout(self.__Layout)
		context.show_layout(self.__Layout)

		(fw, fh) = self.__Layout.get_pixel_size()
		width    = ((w - fh) - (BORDER_WIDTH * 3))

		# Drawing the progress bar
		context.set_antialias(cairo.ANTIALIAS_NONE)
		context.rectangle(fh,
				((BORDER_WIDTH * 2) + fh) +1 , width, BORDER_WIDTH)
		context.set_line_width(1)
		context.set_line_cap(cairo.LINE_CAP_BUTT)
		context.stroke()

		width = (self.__Value * width)

		context.rectangle(fh,
				((BORDER_WIDTH * 2) + fh)+1, width, BORDER_WIDTH)
		context.fill()

		context.set_antialias(cairo.ANTIALIAS_DEFAULT)
		context.arc(int (fh + width),
				(BORDER_WIDTH * 2) + fh + (BORDER_WIDTH/2) +2, 4, 0, 2 * math.pi)
		context.fill()

		context.arc(int (fh + width),
				(BORDER_WIDTH * 2) + fh + (BORDER_WIDTH/2) +2, 2, 0, 2 * math.pi)
		context.set_source_rgb(1,1,1)
		context.fill()

		context.set_antialias(cairo.ANTIALIAS_DEFAULT)

		layout         = self.create_pango_layout(self.__Text)
		(fontw, fonth) = layout.get_pixel_size()

		context.move_to(((w - fontw) / 2), ((fonth + 33) / 2) + 3)
		layout.set_font_description(fontdesc)
		context.set_source_rgb(fr,fg,fb)
		context.update_layout(layout)
		context.show_layout(layout)
		#
		width  =  int(300)
		height =  int(fonth * 2 + BORDER_WIDTH +10)
		#self.set_size_request(width, height)


	value = property(getValue, setScale)
