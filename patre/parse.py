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
Tokenize text and build a token tree based on matching parentheses.
"""

from text import TextError, TextRange, where_from_pos

def tok_whitespace(white):
	"""
	Generate a function for use in Tokenizer.addfn that will discard all characters in white.
	"""
	def inner(text, pos):
		if not text[pos] in white:
			return None, None

		pos += 1
		while pos < len(text) and text[pos] in white:
			pos += 1
		return None, pos
	return inner

def tok_fallback():
	"""
	Generate a function for use in Tokenizer.addfn that will turn any single character
	into a TextRange
	"""
	def inner(text, pos):
		return TextRange(text, pos, pos + 1), pos + 1
	return inner

def tok_regex(regex, tag=None):
	"""
	Generate a function for use in Tokenizer.addfn that will match the text against the
	given regular expression and returns the match (if any) as a TextRange with the
	given tag.
	"""
	def inner(text, pos):
		m = regex.match(text, pos)
		if m:
			if m.end() == pos:
				raise TextError(text, pos, "regular expression (tag=%s) has 0-length match" % (tag))
			return TextRange(text, pos, m.end(), tag), m.end()
		else:
			return None, None
	return inner

class Tokenizer(object):
	"""
	This simplistic tokenizer class maintains a list of functions that greedily
	attempt to produce tokens from the input string.

	Each function is given a stage number that controls at which point the function
	is tried.
	"""
	def __init__(self):
		self.fns = []

	def addfn(self, fn, stage=0):
		"""
		fn will be called as fn(text, pos) and should attempt to produce a token
		from the text at the given position. It should return a pair out, end,
		where end is None if no token is matched, or the next position; and out
		is the token returned by tokenize (or None if the token should be discarded
		silently).
		"""
		self.fns.append((stage, fn))
		self.fns.sort(key=lambda x: x[0])

	def __call__(self, text, pos=0, override=None):
		class Instance(object):
			def __init__(self, tok, text, pos, override):
				self.tok = tok
				self.text = text
				self.pos = pos
				self.override = override

			def __call__(self):
				while self.pos < len(self.text):
					if override != None:
						out, end = override(self.text, self.pos)
						if end != None:
							self.pos = end
							if out != None:
								yield out
							continue

					for stage, fn in self.tok.fns:
						out, end = fn(self.text, self.pos)
						if end != None:
							self.pos = end
							if out != None:
								yield out
							break
					else:
						raise TextError(text, pos, "failed to tokenize")
		return Instance(self, text, pos, override)

class Treeify(object):
	"""
	Tokenize and parse text into a tree of tokens.
	"""
	def __init__(self):
		self.parens = []

	def addparens(self, open, close):
		self.parens.append((open, close))

	def maketree(self, tokens, close=None):
		liststack = [[]]
		closestack = [close]

		for tok in tokens:
			s = str(tok)

			for open,close in self.parens:
				if s == open:
					liststack[-1].append(tok)
					liststack.append([])
					closestack.append(close)
					break
				elif s == close:
					if closestack[-1] != s:
						raise TextError(tok.text, tok.start, "unexpected closing '%s'" % (s))

					if len(liststack) == 1:
						return liststack[0]

					liststack[-2].append(liststack[-1])
					liststack.pop()
					liststack[-1].append(tok)
					closestack.pop()
					break
			else:
				liststack[-1].append(tok)

		if len(liststack) > 1:
			open = liststack[-2][-1]
			raise TextError(open.text, open.start, "unclosed '%s'" % (str(open)))

		return liststack[0]
