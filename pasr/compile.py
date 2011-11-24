# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 Nicolai Hähnle
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
Compile context-free grammar productions from a simple and more or less
concise language.
"""

import re

from cyk import Production, Tag
from text import TextError, TextRange

class Options(object):
	"""
	Options for the compiler.
	"""
	def __init__(self):
		self.escape = '$'

class MatchTextRange(Production.Element):
	def __init__(self, tok):
		self.unitlength = True
		self.token = tok

	def match(self, node, start, end):
		if end != start + 1:
			return None

		tok = node.token[start]
		if isinstance(tok, TextRange) and str(tok) == str(self.token) and tok.tag == self.token.tag:
			return {}
		return None

class MatchNonTerminal(Production.Element):
	def __init__(self, tag):
		self.unitlength = False
		self.tag = tag

	def match(self, node, start, end):
		for tag,kv in node.matches(start, end):
			if tag == self.tag:
				return kv
		return None

class MatchAnyStar(Production.Element):
	def __init__(self):
		self.unitlength = False

	def match(self, node, start, end):
		return {}

class MatchStore(Production.Element):
	def __init__(self, child, tag):
		self.child = child
		self.unitlength = child.unitlength
		self.tag = tag

	def match(self, node, start, end):
		kv = self.child.match(node, start, end)
		if kv != None:
			kv = kv.copy()
			kv[self.tag] = node.textrange(start, end)
		return kv

def make_production(productions, tag, elements, atstart=False, atend=False):
	"""
	Take the given set of flat matcher elements (no parenthesis nesting)
	and translate them into productions.
	"""
	# productions only support two non-unit-length elements
	nonunit = [i for i in range(len(elements)) if not elements[i].unitlength]
	if len(nonunit) <= 2:
		prod = Production(tag, elements)
		prod.atstart = atstart
		prod.atend = atend
		productions.append(prod)
		return

	prev = []
	prevend = nonunit[0]
	nr = 1
	while nr+1 < len(nonunit):
		subtag = Tag(str(tag) + ":split:" + str(nr))
		prod = Production(subtag, prev + elements[prevend:nonunit[nr]+1])
		prod.atstart = atstart and nonunit[0] == 0
		# never atend
		productions.append(prod)

		prev = [MatchNonTerminal(subtag)]
		prevend = nonunit[nr]+1
		nr += 1

	prod = Production(tag, elements[:nonunit[0]] + prev + elements[prevend:])
	prod.atstart = atstart
	prod.atend = atend
	productions.append(prod)

def compile(tag, expr, tokenizer, treeify, options=Options()):
	"""
	Return a list of productions needed to represent the given expression
	"""
	productions = []
	nestcounter = [0]

	# This sub-routine handles parsing $ escapes
	escaped = [False]
	def escape(text, pos):
		if text[pos] != options.escape or escaped[0]:
			escaped[0] = False
			return None, None

		pos += 1
		if text[pos] == options.escape:
			escaped[0] = True
			return None, pos

		if text[pos] == '(':
			pos += 1
			if text[pos] == '=' or text[pos] == '(':
				# recursive match
				m = re.compile("=*\\(").match(text, pos)
				if not m:
					raise TextError(text, pos, "bad recursive match opening")

				nrequals = m.end() - pos - 1
				pos = m.end()
				end = text.find(')' + '=' * nrequals + ')', pos)
				if end == -1:
					raise TextError(text, pos, "recursive match not closed")

				nestcounter[0] += 1
				subtag = Tag(str(tag) + ":rec" + str(nestcounter[0]))
				productions.extend(compile(subtag, text[pos:end], tokenizer, treeify, options))

				match = MatchNonTerminal(subtag)
				pos = end + nrequals + 2
			else:
				# simple non-terminal match
				end = text.find(')', pos)
				if end == -1:
					raise TextError(text, pos, "unclosed $(...)")

				match = MatchNonTerminal(text[pos:end])
				pos = end+1
		elif text[pos] == '*':
			pos += 1
			match = MatchAnyStar()
		else:
			raise TextError(text, pos, "unknown escape sequence '%s'" % (text[pos]))

		if pos < len(text) and text[pos] == '|':
			pos += 1
			end = text.find('|', pos)
			if end == -1:
				raise TextError(text, pos, "unclosed escape matcher |...|")

			match = MatchStore(match, text[pos:end])
			pos = end+1

		return match, pos

	tree = treeify.maketree(tokenizer.tokenize(expr, escape))
	eltstack = [[]]
	pos = [0]
	blocks = [tree]

	while pos:
		if pos[-1] >= len(blocks[-1]):
			if len(pos) == 1:
				break

			nestcounter[0] += 1
			subtag = Tag(str(tag) + ":nest" + str(nestcounter[0]))
			make_production(productions, subtag, eltstack[-1], atstart=True, atend=True)

			eltstack.pop()
			pos.pop()
			blocks.pop()
			pos[-1] += 1

			match = MatchNonTerminal(subtag)
			match.unitlength = True
			eltstack[-1].append(match)
			continue

		tok = blocks[-1][pos[-1]]
		if type(tok) == list:
			eltstack.append([])
			pos.append(0)
			blocks.append(tok)
			continue

		if isinstance(tok, TextRange):
			tok = MatchTextRange(tok)

		if not isinstance(tok, Production.Element):
			raise ValueError("compile: unexpected token %s (type %s)" % (tok, type(tok)))

		eltstack[-1].append(tok)
		pos[-1] += 1

	assert len(eltstack) == 1
	make_production(productions, tag, eltstack[0])
	return productions
