#!/usr/bin/env python
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
# @category  GTK
# @package   Preferences
# @author    Marco Antonio Islas Cruz <markuz@islascruz.org>
# @copyright 2006-2007 Christine Development Group
# @license   http://www.gnu.org/licenses/gpl.txt
#
# Module that holds all christine global vars.
#

import os
import sys

VERSION = '0.2.0_alpha1'
PROGRAMNAME = 'christine'
DATADIR = '/usr/share'
PREFIX = '/usr'
SYSCONFDIR = '/usr/etc'
USERDIR  = os.path.join(os.environ["HOME"],".christine")


DBFILE = os.path.join(USERDIR,'christine.db')
LOGFILE  = os.path.join(USERDIR,"log")

CHRISTINE_AUDIO_EXT = sound = ["mp3","ogg","wma"]
CHRISTINE_VIDEO_EXT = video = ["mpg","mpeg","mpe","avi"]


# global PATH to share files required
if "--devel" in sys.argv:
	SHARE_PATH = os.path.join("./")
	PLUGINSDIR = './libchristine/Plugins'
else:
	SHARE_PATH = os.path.join('/usr/share', 'christine')
	PLUGINSDIR = '/usr/lib/python2.5/site-packages/libchristine/Plugins'

GUI_PATH = os.path.join(SHARE_PATH,"gui")
LOCALE_DIR = "/usr/share/locale/"
BUGURL='https://sourceforge.net/tracker2/?atid=845044&group_id=167966&func=browse'