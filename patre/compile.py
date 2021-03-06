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
Compile regular expressions from a simple and more or less
concise language into non-deterministic finite automata (NFA).
"""

import re

from nfa import Nfa, nfa_token, nfa_tag, nfa_list, nfa_any, nfa_not
from text import TextError, TextRange

class Options(object):
	"""
	Options for the compiler.
	"""
	def __init__(self, tokenizer, treeify):
		self.escape = '$'
		self.tokenizer = tokenizer
		self.treeify = treeify
		self.tags = {}

def readuntil(text, pos, delim):
	end = text.find(delim, pos)
	if end == -1:
		raise TextError(text, pos, "no delimiting '%s' found" % (delim))
	out = text[pos:end]
	return out, end+len(delim)

def do_subexpr(nfa, startstate, text, pos, options):
	"""
	Handle an escape {...} or (...) sub-expression.
	Returns endstate and new position in text
	"""
	if text[pos] == '{':
		# Matching a tagged token
		tag, pos = readuntil(text, pos+1, '}')

		if tag in options.tags:
			subnfa, substart, subend = options.tags[tag]
			assert nfa != subnfa

			statemap = nfa.insert(subnfa)
			substart = statemap[substart]
			subend = statemap[subend]

			nfa.transition(startstate, substart, match=None)
			endstate = subend
		else:
			endstate = nfa.newstate()
			nfa.transition(startstate, endstate, nfa_tag(tag))
	elif text[pos] == '(':
		# Matching a group
		tree, pos = do_compile_maketree(nfa, text, pos+1, ")", options)
		endstate = do_compile_transitions(nfa, startstate, tree, options)
	return endstate, pos

def do_compile_maketree(nfa, expr, pos, close, options):
	escaped = [False]
	def escape(text, pos):
		if text[pos] != options.escape or escaped[0]:
			escaped[0] = False
			return None, None

		pos += 1
		if text[pos] == options.escape:
			escaped[0] = True
			return None, pos

		startstate = nfa.newstate()

		if text[pos] in [ '<', '>' ]:
			# Remember the position of previous or next token
			prev = text[pos] == '<'
			if text[pos+1] != '|':
				raise TextError(text, pos, "expected |")

			tag, pos = readuntil(text, pos+2, '|')
			endstate = nfa.newstate()
			t = nfa.transition(startstate, endstate, match=None)
			if prev:
				t.prevcapture = tag
			else:
				t.nextcapture = tag

			return (startstate, endstate), pos

		negate = False
		if text[pos] == '!':
			negate = True
			pos += 1

		if text[pos] in [ '{', '(' ]:
			endstate, pos = do_subexpr(nfa, startstate, text, pos, options)
		elif text[pos] == '.':
			# Match anything
			endstate = nfa.newstate()
			nfa.transition(startstate, endstate, nfa_any())
			pos += 1
		elif text[pos] == '|':
			pos += 1
			endstate = nfa.newstate()
			prio = 0
			while pos < len(text) and text[pos] in [ '{', '(' ]:
				subend, pos = do_subexpr(nfa, startstate, text, pos, options)
				t = nfa.transition(subend, endstate, match=None)
				t.priority = prio
				prio += 1
		else:
			raise TextError(text, pos, "unknown escape character '%s'" % (text[pos]))

		if negate:
			# Match any token, so long as the prefix does not match what we described previously
			newstart = nfa.newstate()
			newend = nfa.newstate()
			nfa.transition(newstart, newend, match=nfa_not(nfa, startstate, endstate))

			startstate = newstart
			endstate = newend

		if pos < len(text) and text[pos] in [ '*', '+' ]:
			# Star operations
			star = text[pos] == '*'
			pos += 1

			if pos < len(text) and text[pos] in [ '{', '(' ]:
				# Support separator expressions
				sepend, pos = do_subexpr(nfa, endstate, text, pos, options)
				repeattransition = nfa.transition(sepend, startstate, match=None)
			else:
				repeattransition = nfa.transition(endstate, startstate, match=None)

			if star:
				nfa.transition(startstate, endstate, match=None)

			if pos < len(text) and text[pos] == '[':
				# Capture into a list
				key, pos = readuntil(text, pos+1, ']')

				newstart = nfa.newstate()
				newend = nfa.newstate()
				push = nfa.transition(newstart, startstate, match=None)
				push.stack = (Nfa.PUSH, key)
				pop = nfa.transition(endstate, newend, match=None)
				pop.stack = (Nfa.POP, key)
				repeattransition.stack = (Nfa.STORE, key)
				startstate = newstart
				endstate = newend

		if pos < len(text) and text[pos] == '|':
			# Capturing text range of a match
			key, pos = readuntil(text, pos+1, '|')

			newstart = nfa.newstate()
			t = nfa.transition(newstart, startstate, match=None)
			t.nextcapture = (key, 0)
			startstate = newstart

			newend = nfa.newstate()
			t = nfa.transition(endstate, newend, match=None)
			t.prevcapture = (key, 1)
			endstate = newend

		return (startstate, endstate), pos

	tok = options.tokenizer(expr, pos, override=escape)
	tree = options.treeify.maketree(tok(), close)
	return tree, tok.pos

def do_compile_transitions(nfa, startstate, tree, options):
	currentstate = startstate
	for token in tree:
		if isinstance(token, TextRange):
			nextstate = nfa.newstate()
			nfa.transition(currentstate, nextstate, match=nfa_token(token))
			currentstate = nextstate
		elif isinstance(token, list):
			startinner = nfa.newstate()
			endinner = do_compile_transitions(nfa, startinner, token, options)

			nextstate = nfa.newstate()
			nfa.transition(currentstate, nextstate, match=nfa_list(nfa, startinner, endinner))
			currentstate = nextstate
		elif isinstance(token, tuple):
			nfa.transition(currentstate, token[0], None)
			currentstate = token[1]
		else:
			raise ValueError("compile: unexpected token '%s'" % (token))
	return currentstate

def compile(nfa, expr, options):
	"""
	Turn the given regular expression into an Nfa
	"""
	startstate = nfa.newstate()
	tree, end = do_compile_maketree(nfa, expr, 0, None, options)
	endstate = do_compile_transitions(nfa, startstate, tree, options)
	return startstate, endstate
