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
# @category  Pattern
# @package   Singleton
# @author    Miguel Vazquez Gocobachi <demrit@gnu.org>
# @copyright 2007 Christine Development Group
# @license   http://www.gnu.org/licenses/gpl.txt
# @version   $Id$

#
# Singleton implements
#
class Singleton:
	#
	# Manage instance
	#
	# @var object
	__Instance = None
	
	#
	# Constructor
	#
	def __init__(self, name):
		if (Singleton.__Instance is not None):
			raise Singleton.__Instance
		Singleton.__Instance = self
		self.__Name = name

	#
	# Returns name of the class
	#
	# @return string
	def getName(self):
		return self.__Name

	#
	# Returns Id of the object
	#
	# @return integer
	def getId(self):
		"""
		Test method, return singleton Id
		"""
		return id(self)