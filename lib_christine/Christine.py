#! /usr/bin/env python
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
# @category  Multimedia
# @package   Christine
# @author    Marco Antonio Islas Cruz <markuz@islascruz.org>
# @author    Miguel Vazquez Gocobachi <demrit@gnu.org>
# @copyright 2006-2007 Christine Development Group
# @license   http://www.gnu.org/licenses/gpl.txt
# @version   $Id$
import sys
import random
import thread
import time
import gtk
import gtk.gdk
import pygst; pygst.require('0.10')
import gst.interfaces
from lib_christine.Trans import *
from lib_christine.ChristineLibrary import *
from lib_christine.GtkMisc import *
from lib_christine.Library import *
from lib_christine.Queue import *
from lib_christine.Preferences import *
from lib_christine.About import *
from lib_christine.Player import *
from lib_christine.Display import *
from lib_christine.Plugins import *
from lib_christine.Share import *

try:
	import pynotify
	pynotify.Urgency(pynotify.URGENCY_NORMAL)
	pynotify.init('christine')
	version = pynotify.get_server_info()['version'].split('.')
	
	if (version < [0, 3, 6]):
		raise ImportError("server version is %d.%d.%d, 0.3.6 or major required" % version)

	PYNOTIFY = True
except ImportError:
	print 'no pynotify available'
	PYNOTIFY = False

if (gtk.gtk_version < (2, 10, 0)):
	print translate('Gtk+ 2.10 or better is required')
	sys.exit()

class Christine(GtkMisc):
	def __init__(self):
		"""
		Constructor, this method will init the gtk_misc parent class,
		initialize the gnome ui client, create the XML interface descriptor,
		initialize class variables and create some timeouts calls
		"""
		GtkMisc.__init__(self)

		self.__Share   = Share()
		self.__GConf   = ChristineGconf()
		self.__Plugins = ChristinePlugins(self)

		self.__XML = self.__Share.getTemplate('WindowCore')
		self.__XML.signal_autoconnect(self)

		self.__MenuItemSmallView = self.__XML['ViewSmallMenuItem']
		self.__VBoxCore          = self.__XML['VBoxCore']

		# Class variables
		self.__TextToSearch     = ""
		self.__ErrorStreamCount = 0
		self.__TimeTotal        = 0     # Nanosecs for audio/video file
		self.__LocationCount    = 0     # Count ns and jump if the file is not good
		self.__LastPlayed       = []
		self.__IterNatural      = None
		self.__ScaleMoving      = False
		self.__StatePlaying     = False
		self.__IsFullScreen     = False
		self.__ShowButtons      = False
		self.__IsImporting      = False
		self.__IsHidden         = False

		# Creating the player and build the GUI interface
		self.__initPlayer()
		self.__buildInterface()

		if (self.__GConf.get_bool('ui/show_in_notification_area')):
			self.__buildTrayIcon()

		self.__GConf.notify_add('/apps/christine/ui/show_in_notification_area',
				lambda cl,cnx,entry,widget: self.__TrayIcon.set_visible(entry.get_value().get_bool()))

		gobject.timeout_add(500, self.checkTimeOnMedia)
	
	#
	# Initialize the player
	#
	# @access private
	# @return void
	def __initPlayer(self):
		"""
		Initialize the player and packs it into the HBoxPlayer
		"""
		self.__Player = player()
		self.__HBoxPlayer = self.__XML['HBoxPlayer']
		self.__HBoxPlayer.pack_start(self.__Player, True, True, 0)
		self.__Player.bus.add_watch(self.__handlerMessage)

	#
	# Interface descriptors (widgets)
	#
	# @access private
	# @return void
	def __buildInterface(self):
		"""
		This method calls most of the common used 
		interface descriptors (widgets) from self.__XML.
		Connects them to a callback (if needed) and 
		call some other methods to show/hide them.
		"""
		# Calling some widget descriptors with no callback connected "by hand"
		self.__VBoxTemporal   = self.__XML['VBoxTemporal']
		self.__MenuBar        = self.__XML['MenuBar']
		self.__HBoxSearch     = self.__XML['HBoxSearch']
		self.__EntrySearch    = self.__XML['EntrySearch']
		self.__HPanedListsBox = self.__XML['HPanedListsBox']
		self.__VBoxList       = self.__XML['VBoxList']
		# Ends the call to widgets descriptors not connected by hadn

		# Gets window widget from glade template
		self.__Window = self.__XML['WindowCore']
		self.__Window.set_icon(self.__Share.getImage('logo'))

		# Gets play button and menu play item from glade template
		self.__PlayButton   = self.__XML['ToggleButtonPlay']
		self.__MenuItemPlay = self.__XML['MenuItemPlay']

		self.__Menus = {}

		for (i in ['media', 'edit', 'control', 'help']):
			self.__Menus["%s" % i] = self.__XML["%s_menu" % i].get_submenu()
		
		# cdisplaybox is the display gtk-Box
		self.__HBoxCairoDisplay = self.__XML['HBoxCairoDisplay']
		
		# Create the display and attach it to the main window
		self.__Display = display()
		self.__Display.connect('value-changed', self.onScaleChanged)
		self.__HBoxCairoDisplay.pack_start(self.__Display, True, True, 0)
		self.__Display.show_all()

		# Create the library by calling to libs_christine.library class
		self.__Library  = library()
		self.__TreeView = self.__Library.tv

		# FIXME: check method if exist and change to standarization
		self.__TreeView.connect('button-press-event', self.pop_menu)
		self.__TreeView.connect('key-press-event',    self.handlerKeyPress)
		self.__TreeView.connect('row-activated',      self.itemActivated)
		self.__TreeView.show()

		# Models in the library are assigned to class variables
		self.__LibraryModel       = self.__Library.tv.get_model()
		self.__LibraryFilterModel = self.__LibraryModel.get_model()
		self.__LibraryFilterModel.set_visible_func(self.filter)
		
		self.__LibraryNaturalModel = self.__LibraryFilterModel.get_model()
		self.__LibraryCurrentInter = self.__LibraryModel.get_iter_first()
		
		self.__ScrolledMusic = self.__XML['ScrolledMusic']
		self.__VBoxVideo = self.__XML['VBoxVideo']

		self.__ScrolledMusic.add(self.__Library.tv)
		self.__VBoxCore.show_all()

		self.__Queue         = queue()
		self.__ScrolledQueue = self.__XML['ScrolledQueue']

		self.__Queue.treeview.connect('key-press-event', self.__queueHandlerKey)
		self.__Queue.treeview.connect('row-activated',   self.itemActivated)

		self.__ScrolledQueue.add(self.__Queue.treeview)
		gobject.timeout_add(500, self.checkQueue)

		self.__ControlButton = self.__XML['control_button']

		self.__MenuItemShuffle = self.__XML['MenuItemShuffle']
		self.__MenuItemShuffle.set_active(self.__GConf.get_bool('control/shuffle'))

		self.__MenuItemShuffle.connect('toggled', 
			lambda widget: self.__GConf.set_value('control/shuffle', 
			widget.get_active()))

		self.__GConf.notify_add('/apps/christine/control/shuffle', 
			self.__GConf.toggle_widget, 
			self.__MenuItemShuffle)

		self.__ControlRepeat = self.__XML['repeat']
		self.__ControlRepeat.set_active(self.__GConf.get_bool('control/repeat'))
		
		self.__ControlRepeat.connect('toggled', 
			lambda widget: self.__GConf.set_value('control/repeat', 
			widget.get_active()))

		self.__GConf.notify_add('/apps/christine/control/repeat', 
			self.__GConf.toggle_widget, 
			self.__ControlRepeat)

		self.__BothSr = self.__XML['both_sr']
		self.__NoneSr = self.__XML['none_sr']
		
		self.__MenuItemVisualMode = self.__XML['MenuItemVisualMode']
		self.__MenuItemVisualMode.set_active(self.__GConf.get_bool('ui/visualization'))

		self.visualMode()

		self.__MenuItemSmallView.set_active(self.__GConf.get_bool('ui/small_view'))
		self.toggleViewSmall(self.__MenuItemSmallView)

		self.__VBoxToolBox          = self.__XML['VBoxToolBox']
		self.__HBoxToolBoxContainer = self.__XML['HBoxToolBoxContainer']
		self.__HScaleVolume         = self.__XML['HScaleVolume']
		
		volume = self.__GConf.get_float('control/volume')

		self.__GConf.notify_add('/apps/christine/control/volume', self.changeGConfVolume)

		if (volume):
			self.__HScaleVolume.set_value(volume)
		else:
			self.__HScaleVolume.set_value(0.8)

		self.__HBoxToolBoxContainerMini = self.__HBoxToolBoxContainer
		self.jumpToPlaying(path = self.__GConf.get_string('backend/last_played'))

		if ('-q' in sys.argv):
			sys.exit()

	#
	# Makes TrayIcon
	#
	# @access private
	# @see __TrayIcon_handlerEvent()
	# @see __TrayIcon_activated()
	# @return void
	def __buildTrayIcon(self):
		"""
		Show the TrayIcon 
		"""
		self.__TrayIcon = gtk.StatusIcon()
		self.__TrayIcon.set_from_file(self.__Share.getImage('trayicon'))

		self.__TrayIcon.connect('popup-menu', self.__trayIconHandlerEvent)
		self.__TrayIcon.connect('activate',   self.__trayIconActivated)

		self.__TrayIcon.set_visible(self.__GConf.get_bool('ui/show_in_notification_area'))
	
	#
	# Catch TrayIcon events
	#
	# @access private
	# @param  widget  widget The widget that will be used
	# @param  event   event  The event requested by the widget
	# @param  integer time   The time requested by the widget
	# @return void
	def __trayIconHandlerEvent(self, widget, event, time):
		"""
		TrayIcon handler events
		"""
		# If the event is a button press event and it was 
		# the third button then show a popup menu
		if (event == 3):
			XML = self.__Share.getTemplate('MenuTrayIcon')
			XML.signal_autoconnect(self)
			
			popup = XML['menu']
			popup.popup(None, None, None, 3, gtk.get_current_event_time())
			popup.show_all()

	#
	# TrayIcon hide/show
	#
	# @access private
	# @param  boolean status The status of the trayicon true/false
	# @return void
	def __trayIconActivated(self, status):
		"""
		This hide and then show the window, 
		intended when you want to show the window
		in your current workspace
		"""
		if (self.IsHidden == True):
			self.__Window.show()
		else:
			self.__Window.hide()

		self.IsHidden = not self.IsHidden

	#
	# Queue list key-press-event manager
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @param  event  event  The event requested by the widget 
	# @return void
	def queueHandlerKey(self, widget, event):
		"""
		Handler the key-press-event in the queue list
		"""
		if (event.keyval == 65535):
			selection     = self.__Queue.treeview.get_selection()
			(model, iter) = selection.get_selected()

			if (iter is not None):
				name = model.get_value(iter, NAME)
				self.__Queue.remove(iter)
				self.__Queue.save()
	
	#
	# Catch popupMenu events
	#
	# @access public
	# @param  widget  widget The widget that will be used
	# @param  event   event  The event requested by the widget
	# @return void
	def popupMenuHandlerEvent(self, widget, event):
		"""
		handle the button-press-event in the library
		"""
		if (event.button == 3):
			XML = self.__Share.getTemplate('PopupMenu')
			XML.signal_autoconnect(self)

			popup = XML['menu']
			popup.popup(None, None, None, 3, gtk.get_current_event_time())
			popup.show_all()

	#
	# Delete file from disk
	#
	# @see    deleteFileFromDisk.glade
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def deleteFileFromDisk(self, widget):
		"""
		Delete file from disk
		"""
		selection     = self.__TreeView.get_selection()
		(model, iter) = selection.get_selected()
		iter          = self.getIterNatural(iter)

		self.__Library.delete_from_disk(iter)

	#
	# Add the selected item to the queue
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def popupAddToQueue(self, widget):
		"""
		Add the selected item to the queue
		"""
		selection       = self.__TreeView.get_selection()
		(model, iter,)  = selection.get_selected()
		file            = model.get_value(iter, PATH)

		self.__Queue.add(file)
	
	#
	# Handle the key-press-event in the library. 
	# Current keys: Enter to activate the row
	# and 'q' to send the selected song to the 
	# queue
	#
	# @access public
	# @param  widget treeview
	# @param  event  event
	# @return void
	def handlerKeyPress(self, treeview, event):
		"""
		Handle the key-press-event in the 
		library. 
		Current keys: Enter to activate the row
		and 'q' to send the selected song to the 
		queue
		"""
		if (event.keyval == 65535):
			self.removeFromLibrary()
		elif (event.keyval == 113):
			selection     = treeview.get_selection()
			(model, iter) = selection.get_selected()
			name          = model.get_value(iter, PATH)

			self.__Queue.add(name)

	#
	# Remove file from library
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def removeFromLibrary(self, widget = None):
		"""
		Remove file from library
		"""
		selection     = self.__TreeView.get_selection()
		(model, iter) = selection.get_selected()
		name          = model.get_value(iter, NAME)
		niter         = self.getIterNatural(iter)

		self.__LibraryNaturalModel.remove(niter)
		self.__Library.remove(niter)
		self.__Library.save()

	#
	# Add the selected item to the queue
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @param  string path
	# @param  ?      iter
	# @return void
	def itemActivated(self,widget, path, iter):
		model    = widget.get_model()
		iter     = model.get_iter(path)
		filename = model.get_value(iter, PATH)
		self.__FileName = filename

		self.setLocation(filename)

		self.__PlayButton.set_active(False)
		self.__PlayButton.set_active(True)

	#
	# Set the location in the player and
	# perform some other required actions
	#
	# @access public
	# @param  string filename
	# @return void
	def setLocation(self, filename):
		"""
		Set the location in the player and
		perform some other required actions
		"""
		self.__StatePlaying = False
		self.__IterNatural  = None
		# current iter is a temporal variable
		# that will hold a gtk.TreeIter
		# should be setted to None 
		# before using it
		self.__LibraryCurrentInter = None
		
		self.__Player.stop()
		self.__LibraryNaturalModel.foreach(self.__SearchByPath, self.__Player.get_location())

		if (self.__LibraryCurrentInter != None):
			pix = self.__Share.getImage('blank')
			pix = pix.scale_simple(20, 20, gtk.gdk.INTERP_BILINEAR)
			self.__LibraryNaturalModel.set(self.__LibraryCurrentInter, pix, pix)
		
		# Search for the item in the library.
		# if it exists then set it in the "backend/last_played"
		# entry in gconf to be able to select it in the next
		# christine start-up (and other functions) and
		self.__LibraryCurrentInter = None
		self.__LibraryNaturalModel.foreach(self.__SearchByPath, filename)

		if (self.__LibraryCurrentInter != None):
			self.__IterNatural = self.__LibraryCurrentInter.copy()

			count = self.__LibraryNaturalModel.get_value(self.__LibraryCurrentInter, PLAY_COUNT)
			self.__LibraryNaturalModel.set(self.__LibraryCurrentInter, PLAY_COUNT, count + 1)

			self.__Library.save()
			self.__LastPlayed.append(filename)
			self.__GConf.set_value('backend/last_played', filename)

		self.__Player.setLocation(filename)
		# enable the stream-length for the current song.
		# this will be stopped when we get the length
		gobject.timeout_add(300,self.__streamLength)
		# if we can't get the length, in more than 20
		# times in the same song, then, jump to the
		# next song
		if (self.__LocationCount > 20):
			self.goNext()
		else:
			self.__LocationCount +=1
	
	#
	# Stop the player
	#
	# @access public
	# @param  widget
	# @return void
	def stop(self, widget):
		"""
		Stop the player
		"""
		self.__Player.stop()
			
	#
	# Callback for the volume scale widget
	#
	# @access public
	# @param  widget
	# @return void
	def changeVolume(self, widget):
		"""
		Callback for the volume scale widget
		"""
		value = widget.get_value()

		self.__Player.set_volume(value)
		self.__GConf.set_value('control/volume', value)
	
	#
	# Change volume with GConf
	#
	# @access public
	# @return void
	def changeGConfVolume(self, client, cnx_id, entry, widget):
		self.__HScaleVolume.set_value(entry.get_value().get_float())
	
	#
	# Toggle between the small and the large view
	#
	# @access public
	# @param  widget
	# @return void
	def toggleViewSmall(self, widget):
		"""
		Toggle between the small and the large view
		"""
		#
		# The need to use the "self.__Window.get_size()" will be
		# erased in the future, window size will be saved in
		# gconf.
		#
		active = widget.get_active()
		self.__GConf.set_value('ui/small_view', active)

		if (active):
			self.__HPanedListsBox.hide()
			self.__HBoxSearch.hide()

			self.__WindowSize = self.__Window.get_size()
			self.__Window.unmaximize()
			self.__Window.resize(10, 10)
		else:
			try:
				(w, h) = self.__WindowSize
			except:
				(w, h) = (800, 480)

			self.__HPanedListsBox.show()
			self.__HBoxSearch.show()
			self.__Window.resize(w, h)

	#
	# This show/hide the visualization
	#
	# @access public
	# @param  widget
	# @return void
	def toggleVisualization(self, widget):
		"""
		This show/hide the visualization
		"""
		self.__Player.set_visualization_visible(widget.get_active())
		self.__GConf.set_value('ui/visualization', widget.get_active())
		self.visualMode()

		# Be shure that we are not in small view mode.
		if ((self.__MenuItemSmallView.get_active()) and (not widget.get_active())):
			self.toggleViewSmall(self.__MenuItemSmallView)

		if ((not widget.get_active()) and ((self.__IsFullScreen)):
			print 'self.__HPanedListsBox.show()'
			self.__VBoxVideo.show()
			self.__VBoxTemp.hide()

		if (self.__IsFullScreen):
			self.__IsFullScreen = False
			self.toggleFullScreen()
			self.__Window.fullscreen()
			self.__IsFullScreen = True
	
	#
	# Set the fullscreen mode
	#
	# @access public
	# @param  widget
	# @return void
	def toggleFullScreen(self, widget = None):
		"""
		Set the full Screen mode
		"""
		# Only if we are not in FullScreen and we are playing a video.
		# FIXME: We must enable the full screen if christine has
		#        visualization enabled
		if (not self.__IsFullScreen):
			if ((self.__Player.isVideo()) or (self.__GConf.get_bool('ui/visualization'))):
				self.__VBoxVideo.hide()
				self.__VBoxCore.remove(self.__Player)
				self.__VBoxTemp.pack_start(self.__Player, True, True, 2)
				self.__VBoxTemp.show_all()
				self.__Window.fullscreen()
				self.__IsFullScreen = True
			else:
				print 'WARNING: Full screen with no visualization'
				self.__Window.fullscreen()
				self.__IsFullScreen = True
		else: 
		# Non-full screen mode.
		# hide if we are not playing a video nor
		# visualization.
			if ((not self.__Player.isVideo()) and (not self.__GConf.get_bool('ui/visualization'))):
				self.__Player.hide()

			self.__Window.unfullscreen()
			self.__VBoxTemp.hide()
			self.__VBoxTemp.remove(self.__Player)
			self.__VBoxCore.pack_start(self.__Player, True, True, 0)
			self.__HBoxToolBoxContainerMini.show()
			self.__MenuBar.show()
			self.__VBoxVideo.show()
			self.__IsFullScreen = False
	
	#
	# Handler for the events in the window
	#
	# @access public
	# @param  widget
	# @return void
	def onWindowCoreEvent(self, player, event):
		"""
		Handler for the events in the window
		"""
		if (event.type == gtk.gdk.KEY_PRESS):
			if (event.keyval == 103):
				self.viewPlayButtons()
			elif (event.keyval == 65366):
				if (self.__IsFullScreen):
					self.goNext()
			elif (event.keyval == 65365):
				if (self.__IsFullScreen):
					self.goPreview()
					return True
			elif (event.keyval == 102):
				if (self.__IsFullScreen):
					self.toggleFullScreen()
	
	#
	# This show/hide the player buttons. Suppossed 
	# to work only on fullscreen mode
	#
	# @access public
	# @param  widget
	# @return void
	def viewPlayButtons(self, widget = None):
		"""
		This show/hide the player buttons. Suppossed to work only on 
		fullscreen mode
		"""
		if (not self.__IsFullScreen):
			return True

		if (self.__ShowButtons):
			self.__HBoxToolBoxContainerMini.show()
			self.__MenuBar.show()
			self.__ShowButtons = False
		else:
			self.__HBoxToolBoxContainerMini.hide()
			self.__MenuBar.hide()
			self.__ShowButtons = True

	###########################################
	#           search stuff begins           #
	###########################################
	
	#
	# Set the focus on the search entry
	#
	# @access public
	# @param  widget
	# @return void
	def onEntrySearchActivate(self, widget):
		"""
		Set the focus on the Search entry
		"""
		self.__EntrySearch.grab_focus()

	#
	# Perform the actions to make a search
	#
	# @access public
	# @param  widget
	# @return void
	def search(self, widget = None):
		"""
		Perform the actions to make a search
		"""
		self.__Library.tv.freeze_child_notify()

		# Store the text that is in search box into 
		# the self.__TextToSearch variable
		self.__TextToSearch = self.__EntrySearch.get_text().lower()

		if (self.__Search == ''):
			self.jumpToPlaying()

		# Since we are using a filter model (in the library) we can use
		# the refilter method in the filter model to show only
		# the rows that we need.
		#gobject.timeout_add(10,self.__LibraryFilterModel.refilter)
		self.__LibraryFilterModel.refilter()
		self.__Library.tv.thaw_child_notify()
	
	#
	# Entry search cleaning
	#
	# @access public
	# @param  widget
	# @return void
	def clearEntrySearch(self, widget):
		"""
		Entry search cleaning
		"""
		self.__EntrySearch.set_text('')

	#
	# This method is called by the library.refilter filtered model method.
	# This code should be as simple as we can, we must do everythin
	# as fast as we can
	#
	# @access public
	# @param  widget
	# @param  ?       iter
	# @return void
	def filter(self, model, iter):
		"""
		This method is called by the library.refilter filtered model method.
		This code should be as simple as we can, we must do everythin
		as fast as we can
		"""
		if (self.__IsImporting):
			return True

		if (self.__TextToSearch == ''):
			return True

		value = model.get(iter, SEARCH)[0]

		try:
			value = value.lower()
		except:
			value = ""
			
		if (value.find(self.__TextToSearch) >= 0):
			return True
		else: 
			return False

	###################################################
	#                  Play stuff                     #
	###################################################
	
	#
	# Entry search cleaning
	#
	# @access public
	# @param  widget
	# @return void
	def switchPlay(self, widget):
		"""
		This metod enable/disable the playing. Works for the 
		menuitem and for the play button.
		"""
		#
		# is really needed two controls? 
		#
		active = widget.get_active()

		if (not active):
			self.__Player.pause()
			self.__StatePlaying = False
		else:
			self.play()
			self.__StatePlaying = True
			self.jumpToPlaying()

		# Sync the two controls
		self.__MenuItemPlay.set_active(active)
		self.__PlayButton.set_active(active)
			
	#
	# PLay method
	#
	# @access public
	# @param  widget
	# @return void
	def play(self, widget = None):
		"""
		Play!!, but only if the state is not already playing
		"""
		if not self.__StatePlaying:
			location = self.__Player.get_location()

			# and only if location is not None, if it is the case then
			# go for one file to play
			if (location == None):
				self.goNext()
			self.__Player.playit()
			
			# is it used?
			# path = self.__Player.get_location()
	
	#
	# PLay from TrayIcon menu
	#
	# @access public
	# @param  widget
	# @return void
	def trayIconPlay(self,widget = None):
		"""
		Play from trayicon menu
		"""
		self.__PlayButton.set_active(True)

	#
	# Pause method
	#
	# @access public
	# @param  widget
	# @return void
	def pause(self, widget = None):
		"""
		Pause method
		"""
		self.__PlayButton.set_active(False)
		
	#
	# Gets Iter natural
	#
	# @access public
	# @return void
	def getIterNatural(self, iter):
		"""
		This returns a natural iter, the iter in the 
		low level model gtk.ListStore in library
		"""
		fiter = self.__LibraryModel.convert_iter_to_child_iter(None, iter)

		return self.__LibraryFilterModel.convert_iter_to_child_iter(fiter)

	#
	# Go to preview song
	#
	# @access public
	# @param  widget
	# @return void	
	def goPreview(self, widget = None):
		"""
		Go to play the previous song. If no previous song was played in the 
		current session, then plays the previous song in the library
		"""
		if (len(self.__LastPlayed) > 1):
			self.setLocation(self.__LastPlayed.pop())
			self.__PlayButton.set_active(False)
			self.__PlayButton.set_active(True)
		else:
			self.__LibraryCurrentInter = None
			self.__LibraryModel.foreach(self.__SearchByPath, 
				self.__GConf.get_string('backend/last_played'))

			if self.__LibraryCurrentInter != None:
				path = self.__LibraryModel.get_path(self.__LibraryCurrentInter)
				
				if (path > 0):
					path = (path[0] -1,)

				if (path[0] > -1):
					iter     = self.__LibraryModel.get_iter(path)
					location = self.__LibraryModel.get_value(iter, PATH)
					self.setLocation(location)

					# This avoid the return to the last played song
					# wich is the next in the list.
					self.__LastPlayed.pop()
					self.__PlayButton.set_active(False)
					self.__PlayButton.set_active(True)
	
	#
	# Next toggle_control_* functions where suppossed to be the controls
	# for the behavior in christine. I'm thinking about simplifying it
	# just to "shuffle/no-shuffle" mode and asume that shuffle mode is
	# with "repeat".
	#
	# So, I'm not gonna comment this methods XD
	#
	# @access public
	# @param  widget
	# @return void
	def toggleControlNone(self, widget):
		if (widget.get_active()):
			print 'toggleControlName: none'
			self.__ControlStat=CONTROL_NONE
			self.changeControl()

	#
	# Control shuffle
	#
	# @access public
	# @param  widget
	# @return void
	def toggleControlShuffle(self, widget):
		"""
		Control shuffle
		"""
		if (widget.get_active()):
			print 'toggleControlShuffle: shuffle'
			self.__ControlStat = CONTROL_SHUFFLE
			self.changeControl()

	#
	# Control repeat
	#
	# @access public
	# @param  widget
	# @return void
	def toggle_control_repeat(self, widget):
		"""
		 Control repeat
		"""
		if (widget.get_active()):
			print 'toggleControlRepeat: repeat'
			self.__ControlStat = CONTROL_REPEAT
			self.changeControl()

	#
	# Go to the next song
	#
	# @access public
	# @param  widget
	# @return void
	def goNext(self, widget = None):
		"""
		Find a new file to play. in some cases relay on self.getNextInList
		"""
		# resetting the self.__LocationCount to 0 as we have a new file :-)
		self.__LocationCount = 0

		# Look for a file in the queue. Iter should not be None in the case
		# there where something in the queue
		model = self.__Queue.treeview.get_model()
		iter  = model.get_iter_first()

		if (type(iter) == gtk.TreeIter):
			self.setLocation(model.get_value(iter, PATH))
			self.__LibraryCurrentInter == None
			self.jumpToPlaying()
			self.__Queue.remove(iter)
			self.__Queue.save()
			self.__PlayButton.set_active(False)
			self.__PlayButton.set_active(True)
		else:
			# FIXME: I got to fix this when I know what to do with the 
			# play behavior.
			if (self.__MenuItemShuffle.get_active()):
				self.__Elements = 0
				self.__Elements = len (self.__LibraryModel) - 1
	
				iter     = self.__LibraryModel.get_iter(((self.__Elements * random.random()),))
				filename = self.__LibraryModel.get_value(iter, PATH)

				if ((not filename in self.__LastPlayed) or (self.__GConf.get_bool('control/repeat'))):
						self.setLocation(filename)
						self.__PlayButton.set_active(False)
						self.__PlayButton.set_active(True)
				else:
					self.getNextInList()
					self.__PlayButton.set_active(False)
					self.__PlayButton.set_active(True)
			else:
				self.getNextInList()

	#
	# Check queue
	#
	# @access public
	# @param  widget
	# @return boolean
	def	checkQueue(self):
		model = self.__Queue.treeview.get_model()

		if (model != None):
			b = model.get_iter_first()

			if (type(b) != gtk.TreeIter):
				self.__ScrolledQueue.hide()
			else:
				self.__ScrolledQueue.show()

		return True
			
	#
	# Get next song in the list
	#
	# @access public
	# @return void
	def getNextInList(self):
		"""
		Gets the next item in list
		"""
		path = self.__GConf.get_string('backend/last_played')

		if (path == None):
			filename = self.__GConf.get_string('backend/last_played')
			self.__LibraryCurrentInter = None
			self.__LibraryModel.foreach(self.__SearchByPath, filename)

			if (self.__LibraryCurrentInter == None):
				iter     = self.__LibraryModel.get_iter_first()
				filename = self.__LibraryModel.get_value(iter, PATH)

			self.setLocation(filename)
		else:
			self.__LibraryCurrentInter = None
			self.__LibraryModel.foreach(self.__SearchByPath, path)

			if (self.__LibraryCurrentInter != None):
				iter = self.__LibraryModel.iter_next(self.__LibraryCurrentInter)
			else:
				iter = self.__LibraryModel.get_iter_first()

			try:
				self.setLocation(self.__LibraryModel.get_value(iter, PATH))
				self.__PlayButton.set_active(False)
				self.__PlayButton.set_active(True)
			except:
				self.setScale('', '', b = 0)
				self.setLocation(path)
				self.__PlayButton.set_active(False)
	
	#
	# Search location in the model
	#
	# @access public
	# @return boolean
	def searchByPath(self, model, path, iter, location):
		"""
		search location in the model, if it found it then it will
		store the iter where it was found in self.__LibraryCurrentInter
		"""
		iter      = model.get_iter(path)
		mlocation = model.get_value(iter, PATH)

		if (mlocation == location):
			self.__LibraryCurrentInter = iter
			return True
	
	#
	# Callback scale value
	#
	# @access public
	# @return void
	def onScaleChanged(self, scale, a, value = None):
		"""
		Callback on the value changed signal on position scale
		"""
		value = (int(self.__Display.value * self.__TimeTotal) / gst.SECOND)
		total = self.__TimeTotal*gst.SECOND

		print 'Nanos: ',         value
		print 'Rotal: ',         self.__TimeTotal
		print 'Display_value: ', self.__Display.value

		self.__ScaleMoving = False

		if (value < 0):
			value = 0

		self.__Player.seek_to(value)
	
	#
	# Sets scale value
	#
	# @access public
	# @return void
	def setScale(self, scale, a, b):
		"""
		This method changes the scale value
		"""
		self.__ScaleMoving = True
		self.__ScaleValue  = b
		self.__ScaleMoving = False
	
	#
	# Jump to playing
	#
	# @access public
	# @return void
	def jumpToPlaying(self, widget = None, path = None):
		"""
		This method jumps and select the file
		specified in the path.
		If path is not specified then try to
		select the playing one
		"""
		if (path == None):
			location = self.__Player.get_location()
		else:
			location = path

		self.__LibraryCurrentInter = None
		self.__LibraryModel.foreach(self.__SearchByPath, location)

		if (self.__LibraryCurrentInter != None):
			state = self.__StatePlaying

			if (self.__StatePlaying):
				iter = self.getIterNatural(self.__LibraryCurrentInter)
				pix  = self.__Share.getImage('sound')
				pix  = pix.scale_simple(20, 20, gtk.gdk.INTERP_BILINEAR)
				self.__LibraryNaturalModel.set(iter, pix, pix)

			path = self.__LibraryModel.get_path(self.__LibraryCurrentInter)

			if (path != None):
				self.__TreeView.scroll_to_cell(path, None, True, 0.5, 0.5)
				self.__TreeView.set_cursor(path)

	#
	# Jump to creates dialog
	#
	# @access public
	# @param  widget
	# @return boolean
	def jumpTo(self, widget):
		"""
		Creates a gtk.Dialog box where
		the user specify the minute and second
		where to the song/video should be.
		"""
		# if self.__TimeTotal is not defined then
		# there is no media in player, so
		# there is no way to "jump to" any place.
		if (self.__TimeTotal == 0):
			return False

		XML    = self.__Share.getTemplate('jumpTo')
		dialog = XML['dialog']
		dialog.set_icon(self.__Share.getImage('logo'))

		(mins, seconds) = divmod((self.__TimeTotal / gst.SECOND), 60)

		#Current minute and current second
		(cmins, cseconds) = divmod(self.__Display.get_value(), 60)
		(cmins, cseconds) = (int(cmins), int(cseconds))

		mins_adj = gtk.Adjustment(value = 0, lower = 0, upper = mins, step_incr = 1)
		secs_adj = gtk.Adjustment(value = 0, lower = 0, upper = 59, step_incr = 1)

		ok_button = XML['okbutton']

		mins_scale = XML['mins']
		secs_scale = XML['secs']

		mins_scale.connect('key-press-event', self.jumpToOkClicked, ok_button)
		secs_scale.connect('key-press-event', self.jumpToOkClicked, ok_button)

		mins_scale.set_adjustment(mins_adj)
		mins_scale.set_value(cmins)

		secs_scale.set_adjustment(secs_adj)
		secs_scale.set_value(cseconds)

		response = dialog.run()
		dialog.destroy()

		if (response == gtk.RESPONSE_OK):
			time = ((mins_scale.get_value() * 60) + secs_scale.get_value())

			if (time > self.__TimeTotal):
				time = self.__TimeTotal

			self.__Player.seek_to(time)

	#
	# Jump to accept button
	#
	# @access public
	# @param  widget
	# @param  event
	# @param  widget
	# @return void			
	def jumpToOkClicked(self, widget, event, button):
		"""
		Jumpo to Accept button
		"""
		if (event.keyval == 65293):
			button.emit('clicked')

	#
	# Decrease volume
	#
	# @access public
	# @param  widget
	# @return void
	def decreaseVolume(self, widget = None):
		"""
		Decrease the volume
		"""
		volume = (self.__HScaleVolume.get_value() - 0.1)

		if (volume < 0):
			volume = 0

		self.__HScaleVolume.set_value(volume)
	
	#
	# Increase volume
	#
	# @access public
	# @param  widget
	# @return void
	def increaseVolume(self, widget = None):
		"""
		Increase the volume
		"""
		volume = (self.__HScaleVolume.get_value() + 0.1)

		if (volume > 1.0):
			volume = 1.0

		self.__HScaleVolume.set_value(volume)
	
	#
	# Mute volume
	#
	# @access public
	# @param  widget
	# @return void
	def mute(self, widget):
		"""
		Set mute
		"""
		if (widget.get_active()):
			self.__Volume = self.__HScaleVolume.get_value()
			self.__HScaleVolume.set_value(0.0)
		else:
			self.__HScaleVolume.set_value(self.__Volume)

	####################################################
	#               libraty stuff begins               #
	####################################################
	
	#
	# Import a file or files
	#
	# @access public
	# @param  widget
	# @return void
	def importFile(self, widget, queue = False):
		"""
		Import a file or files
		first argument is a widget, second argument
		is an optional  boolean value that defines
		if the files are going to queue or not
		"""
		XML = self.__Share.getImage('FileSelector')
		fs  = XML['fs']
		fs.set_icon(self.__Share.getImage('logo'))

		response = fs.run()
		files    = fs.get_filenames()

		fs.destroy()

		if (response == gtk.RESPONSE_OK):
			self.addFiles(files = files, queue = queue)

			# What I told, if queue is true
			# send it to queue
			if (queue):
				self.__Queue.save()
			else:
				self.__Library.save()
	
	#
	# Import folder
	#
	# @access public
	# @param  widget
	# @return void
	def import_folder(self, widget):
		"""
		This is the 'simple' way to import folders
		Creates and rund a filechooser dialog to 
		select the dir. 
		A Checkbox let you set if the import will be
		recursive.
		"""
		XML  = self.__Share.getTemplate('directorySelector')
		ds   = XML['ds']
		walk = XML['walk']

		ds.set_icon(self.__Share.getImage('logo'))

		response  = ds.run()
		filenames = ds.get_filenames()

		ds.destroy()

		if (response == gtk.RESPONSE_OK):
			for (i in filenames):
				if (walk.get_active()):
					self.addDirectories(i)
				else:
					files = [os.path.join(i, k) \
					for (k in os.listdir(i)) if os.path.isfile(os.path.join(i, k))]

					if (len(files) > 0):
						self.addFiles(files = files)

			self.__Library.save()

	#
	# This add a single directory, is simplier that addDirectories
	# because there is no need to dig
	#
	# @access public
	# @param  string dir
	# @return void
	def addDirectory(self, dir):
		"""
		This add a single directory, is simplier that addDirectories
		because there is no need to dig
		"""
		files = os.listdir(dir)
		f     = []

		for (i in files):
			ext = i.split('.').pop()
			# Again, only files with the right
			# extension will be imported
			if (ext in [sound, video]):
				f.append(i)

		files = f
		self.addFiles(files)
	
	#
	# Recursive import, first and only argument
	# is the dir where to digg
	#
	# @access public
	# @param  string dir
	# @return void
	def addDirectories(self, dir):
		"""
		Recursive import, first and only argument
		is the dir where to digg
		"""
		# dig looking for files
		a         = os.walk(dir)
		b         = True
		f         = []
		filenames = []

		while (b):
			try: 
				(dirpath, dirnames, files) = a.next()
				filenames.append([dirpath, files])
			except:
				b = False

		self.f = []

		# create a temporal list with the path of
		# the files already stored in the library
		# to avoid duplicates
		#self.__LibraryModel.foreach(lambda model,path,iter: self.f.append(model.get_value(iter,PATH)))
		for (i in filenames):
			for (path in i[1]):
				ext    = path.split('.').pop().lower()
				exists = False

				if (os.path.join(i[0], path) in self.f):
					exists = True

				# FIXME: at the moment only files with the right
				# extension will be imported, 
				# this extensions are defined in 
				# libs_christine/libs_christine.py
				# We need to know what files are supported by 
				# gstreamer
				if ((ext in self.__GConf.get_string('backend/allowed_files').split(','))) and (not exists)):
					f.append(os.path.join(i[0],path))
				#else:
				#	print "skipping:",os.path.join(i[0],path)
		# Once we have the files to add, then use the addFiles
		# wrapper method to add them.
		if (len(f) > 0):
			self.addFiles(files = f)
		else:
			#print f
			pass
	
	#
	# Add a single file, to the library or queue.
	# the files are taken from the self.__FilesToAdd
	# list. the only one argument is queue, wich defines
	# if the importing is to the queue
	#
	# @access private
	# @return boolean
	def __addFile(self, queue = False, data = None):
		"""
		Add a single file, to the library or queue.
		the files are taken from the self.__FilesToAdd
		list. the only one argument is queue, wich defines
		if the importing is to the queue
		"""
		if (type(queue) != type(True)):
			queue = False

		# This method is the "hard" one in the importing files
		# (or directories) We must be carefull in the code
		# and everything must run as fast as we can
		if (self.__IsImporting) and (len(self.__FilesToAdd) > 0):
			new_file = self.__FilesToAdd.pop()

			if (not queue):
				length     = len(self.__FilesToAdd)
				(div, mod) = divmod(length, 50)
				# Add file to our Library
				self.__Library.add(new_file)

				if ((mod == 1) or (mod == 0)):
					print 'library.save()'
					self.__Library.save()
			else:
				self.__Queue.add(new_file)

				if (len(self.__FilesToAdd) > 0):
					self.__Queue.add(self.__FilesToAdd.pop())

			length = len(self.__FilesToAdd)

			if (length > 0):
				self.__Percentage = (1 - (length / float(self.__TimeTotalNFiles)))
			else:
				self.__Percentage = 1

			if (self.__Percentage >= 1.0):
				self.__Percentage = 0.99

			# Setting the value and text in the progressbar
			self.__AddProgress.set_fraction(self.__Percentage)

			rest = (self.__TimeTotalNFiles - length)
			text = "%02d/%02d" % (rest, self.__TimeTotalNFiles)

			self.__AddProgress.set_text(text)
			self.__AddFileLabel.set_text(os.path.split(new_file)[1])
		else:
			if (not queue):
				self.__Library.save()
			self.__IsImporting = False

		return self.__IsImporting

	#
	# Add files to the library or to the queue
	#
	# @access public
	# @return void
	def addFiles(self, widget = None, files = None, queue = False):
		"""
		Add files to the library or to the queue
		"""
		XML = self.__Share.getTemplate('addFiles')
		XML.signal_autoconnect(self)
		
		self.__IsImporting     = True
		self.__AddWindow       = XML['WindowCore']
		self.__AddProgress     = XML['progressbar']
		self.__AddCloseButton  = XML['close']
		self.__AddFileLabel    = XML['file_label']
		self.__AddFileLabel.set_text('None')

		# Be sure that we are working with a list of files
		if (type(files) != type([])):
			raise TypeError, "files must be List, got %s" % type(files)

		files.reverse()

		# Global variable to save temporal files and paths
		self.__FilesToAdd = []
		self.__Paths      = []

		self.__LibraryNaturalModel.foreach(self.getPaths)

		for (i in files):
			if (not i in self.__Paths):
				self.__FilesToAdd.append(i)
			else:
				print 'skipping: ', i

		self.__Percentage      = 0
		self.__TimeTotalNFiles = len(self.__FilesToAdd)

		self.__addFile(queue)
		self.__Library.connect('tags-found', self.__addFile)
		self.__AddWindow.run()

	#
	# Gets path from
	#
	# @access public
	# @return void
	def getPaths(self, model, path, iter):
		"""
		Gets path from
		"""
		self.__Paths.append(model.get_value(iter, PATH))

	#
	# Cancel de import stuff
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def importCancel(self, widget):
		"""
		Cancel de import stuff
		"""
		# Setting self.__IsImporting to false
		# we break the import file timeout
		# then destroy the add dialog.
		self.__IsImporting = False
		self.__AddWindow.destroy()

	#
	# Import file to queue
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def importToQueue(self, widget):
		"""
		Import file to queue
		"""
		self.importFile('', True)
	
	########################################
	#          PLayer section              #
	########################################

	#
	# Handle the messages from self.__Player
	#
	# @access public
	# @params ?        a
	# @params ?        b
	# @params ?        c
	# @params ?        d
	# @return boolean
	def __handlerMessage(self, a, b, c = None, d = None):
		"""
		Handle the messages from self.__Player
		"""
		type_file = b.type

		if (type_file == gst.MESSAGE_ERROR):
			error(b.parse_error()[1])

		if (type_file == gst.MESSAGE_EOS):
			self.goNext()
		elif (type_file == gst.MESSAGE_TAG):
			self.__Player.found_tag_cb(b.parse_tag())
			self.setTags()
		elif (type_file == gst.MESSAGE_BUFFERING):
			percent = 0
			percent = b.structure['buffer-percent']
			self.__Display.set_text("%d" % percent)
			self.__Display.value = (percent / 100)

		return True

	#
	# Update the time showed in the player 
	# it in the  player
	#
	# @access public
	# @return boolean
	def checkTimeOnMedia(self):
		"""
		Update the time showed in the player
		"""
		try:
			nanos      = self.__Player.query_position(gst.FORMAT_TIME)[0]
			ts         = (nanos / gst.SECOND)
			time       = "%02d:%02d" % divmod(ts, 60)
			time_total = "%02d:%02d" % divmod((self.__TimeTotal / gst.SECOND), 60)

			if (ts < 0):
				ts = long(0)

			if ((nanos > 0) and (self.__TimeTotal > 0)):
				currenttime = (nanos / float(self.__TimeTotal))
				self.__Display.set_text("%s/%s" % (time, time_total))

				if ((currenttime >= 0) and (currenttime <= 1)):
					self.__Display.value = currenttime
		# Taking care only in gst.QueryError
		# other errors are raised
		except gst.QueryError:
			pass

		return True
	
	#
	# Catches the lenght of the media and update 
	# it in the  player
	#
	# @access private
	# @return boolean
	def __streamLength(self):
		"""
		Catches the lenght of the media and update it in the 
		player
		"""
		if (self.__Player.get_location().split(':')[0] == 'http'):
			return True

		try:
			self.__TimeTotal = self.__Player.query_duration(gst.FORMAT_TIME)[0]
			ts               = (self.__TimeTotal / gst.SECOND)
			text             = "%02d:%02d" % divmod(ts, 60)

			self.__ErrorStreamCount = 0

			if (self.__IterNatural is not None):
				(time, path) = self.__LibraryNaturalModel.get(self.__IterNatural, TIME, PATH)

				if (time != text):
					self.__LibraryNaturalModel.set(self.__IterNatural, TIME, text)
					self.__Library.save()

			return False
		except gst.QueryError:
			self.__ErrorStreamCount += 1

			if (self.__ErrorStreamCount > 10):
				self.setLocation(self.__Player.get_location())
				self.__PlayButton.set_active(False)
				self.__PlayButton.set_active(True)

			return True
	
	#
	# Update the current media tags in the library
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @param  ?      b      ?
	# @return void
	def setTags(self, widget = "", b = ""):
		"""
		Update the current media tags in the library
		"""
		title     = self.__Player.get_tag('title').replace('_', ' ')
		artist    = self.__Player.get_tag('artist')
		album     = self.__Player.get_tag('album')
		genre     = self.__Player.get_tag('genre')
		type_file = self.__Player.type

		if (type(genre) == type([])):
			genre = ','.join(genre)

		track_number = self.__Player.get_tag('track-number')

		if (title == ''):
			title = os.path.split(self.__Player.get_location())[1]
			title = '.'.join(title.split('.')[:-1])

		# stript_XML_entities is a method inherited from gtk_misc
		tooltext = title
		title    = self.strip_XML_entities(title)

		# Sets window title, which it will be our current song :-)
		self.__Window.set_title("%s - Christine" % title)
		
		notify_text = "<big>%s</big>" % title

		# Show or hide deppending if there are something
		# to show or hide
		if (artist != ''):
			notify_text += " by <big>%s</big>" % artist
			tooltext    += "\nby %s" % artist

		if (album != ''):
			notify_text += " from <big>%s</big>" % album
			tooltext    += "\nfrom %s" % album

		# Updating the info in library, only if it is avaylable.
		if (self.__IterNatural is not None):
			if (title != ''):
				self.__LibraryNaturalModel.set(self.__IterNatural,
						NAME,   title,
						ALBUM,  album,
						ARTIST, artist,
						TN,     track_number,
						SEARCH, '.'.join([title, artist, album, genre, type_file]),
						GENRE,  genre)

			(title1, artist1, album1, tc) = self.__LibraryNaturalModel.get(self.__IterNatural, 
			NAME, ARTIST, ALBUM, TN)

			if ((title != title1) \
				or (artist != artist1) \
				or (album != album) \
				or (track_number != tc):
				gobject.timeout_add(500, self.__Library.save)

		if ((PYNOTIFY) and (self.__GConf.get_bool('ui/show_pynotify'))):
			try:
				self.__Notify.close()
			except:
				pass

			self.__Notify = pynotify.Notification('christine', '', self.__Share.getImage('logo'))

			if (self.__GConf.get_bool('ui/show_in_notification_area')):
				self.__Notify.attach_to_status_icon(self.__TrayIcon)
				self.__TrayIcon.set_tooltip(tooltext)

			self.__Notify.set_timeout(3000)

			# FIXME: where am I used?
			#pixbuf = self.__Share.getImage('logo')

			self.__Notify.set_property('body', notify_text)
			self.__Notify.show()

		self.__Display.set_song(tooltext.replace('\n', ' '))
		self.visualModePlayer()
	
	########################################
	#             Gtk modes                #
	########################################
	
	#
	# Simple or complete visualization
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def visualModePlayer(self, widget = None):
		"""
		Simple or complete visualization
		"""
		if (self.__Player.isVideo()):
			self.__VBoxCore.show_all()
		elif (self.__Player.isSound()):
			if (self.__GConf.getBool('ui/visualization')):
				self.__VBoxCore.show_all()
			else:
				self.__VBoxCore.hide_all()
		else:
			self.__VBoxCore.hide_all()
	
	#
	# Open a dialog to select a remote location
	#
	# @see    openRemote.glade
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def openRemote(self, widget):
		"""
		Open a dialog to select a remote location
		"""
		# Need be hacked to use mp3u playlist and radio features
		XML    = self.__Share.getTemplate('openRemote')
		entry  = XML['entry']
		dialog = XML['dialog']

		dialog.set_icon(self.__Share.getImage('logo'))

		response = dialog.run()

		if (response == gtk.RESPONSE_OK):
			self.setLocation(entry.get_text())
			self.play()

		dialog.destroy()
	
	#
	# Show the about dialog
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def showGtkAbout(self, widget):
		"""
		Show the about dialog
		"""
		guiAbout()
	
	#
	# Show the preferences dialog
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def showGtkPreferences(self, widget):
		"""
		Show the preferences dialog
		"""
		guiPreferences()
	
	#
	# GTK application exit
	#
	# @access public
	# @param  widget widget The widget that will be used
	# @return void
	def quitGtk(self, widget = None):
		self.__Player.stop()
		gtk.main_quit()
	
	#
	# GTK application run
	#
	# @access public
	# @return void
	def runGtk(self):
		"""
		GTK application running
		"""
		gtk.main()

#
# Initialize christine application and translation
#
if __name__ == '__main__':
	t         = trans()
	translate = t.trans
	chris     = christine()

	if (len(sys.argv) > 1):
		for (i in sys.argv[1:]):
			if (os.path.isfile(i)):
				chris.queue.add(i, prepend = True)
	chris.runGtk()