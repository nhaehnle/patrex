# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 Nicolai Hähnle <nhaehnle@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

"""
Represent multi-line text with the capability of returning line number and
column information, and allow editing of such strings.
"""

def line_from_pos(text, pos):
	"""
	Compute the line number of the given position in the text.
	"""
	return text.count('\n', 0, pos) + 1

def col_from_pos(text, pos):
	"""
	Compute the column number of the given position in the text.
	"""
	prev = text.rfind('\n', 0, pos)
	# turns out, the return value of -1 on failure is exactly what we need
	return pos - prev

def where_from_pos(text, pos):
	"""
	Format a textual representation of the given position in the text.
	"""
	return "%d:%d" % (line_from_pos(text, pos), col_from_pos(text, pos))

class TextRange(object):
	"""
	Range of text within a larger multi-line text. Used as token representation.
	"""
	def __init__(self, text, start, end, tag=None):
		self.text = text
		self.start = start
		self.end = end
		self.tag = tag

	def __str__(self):
		return self.text[self.start:self.end]

	def __repr__(self):
		if self.tag != None:
			return "<%s:%s>" % (str(self), repr(self.tag))
		else:
			return "<%s>" % (str(self))


class TextError(ValueError):
	def __init__(self, text, pos, msg):
		super(TextError, self).__init__("%s: %s" % (where_from_pos(text, pos), msg))

class Editor(object):
	"""
	Remember a number of insert and erase operations on text,
	all indexed to start (and end) at some character position.
	The operations are then to be applied to a text all at once.
	"""
	def __init__(self):
		self.erases = []
		self.inserts = []

	def insert(self, where, what):
		self.inserts.append((where, what))

	def erase(self, start, end):
		self.erases.append((start, end))

	def apply(self, text):
		self.inserts.sort(key=lambda x: x[0])
		self.erases.sort(key=lambda x: x[0])

		gen = []
		idxinsert = 0
		idxerase = 0
		where = 0
		while True:
			while idxerase < len(self.erases) and self.erases[idxerase][0] < where:
				idxerase += 1
			while idxinsert < len(self.inserts) and self.inserts[idxinsert][0] < where:
				idxinsert += 1

			nexterase = None
			if idxerase < len(self.erases):
				nexterase = self.erases[idxerase][0]
			nextinsert = None
			if idxinsert < len(self.inserts):
				nextinsert = self.inserts[idxinsert][0]

			if nextinsert == None and nexterase == None:
				gen.append(text[where:])
				break

			if nexterase != None and (nextinsert == None or nexterase < nextinsert):
				gen.append(text[where:nexterase])
				where = self.erases[idxerase][1]
				idxerase += 1
			else:
				ins = self.inserts[idxinsert]
				gen.append(text[where:ins[0]])
				where = ins[0]
				gen.append(ins[1])
				idxinsert += 1

		return ''.join(gen)

