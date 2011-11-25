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
Compile regular expressions from a simple and more or less
concise language into non-deterministic finite automata (NFA).
"""

import re

from nfa import Nfa, nfa_token, nfa_tag, nfa_list
from text import TextError, TextRange

class Options(object):
	"""
	Options for the compiler.
	"""
	def __init__(self, tokenizer, treeify):
		self.escape = '$'
		self.tokenizer = tokenizer
		self.treeify = treeify

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
		if text[pos] == '{':
			# Matching a tagged token
			pos += 1
			end = text.find('}', pos)
			if end == -1:
				raise TextError(text, pos, "unclosed ${...}")

			nextstate = nfa.newstate()
			nfa.transition(startstate, nextstate, nfa_tag(text[pos:end]))
			currentstate = nextstate

			pos = end+1
		elif text[pos] == '(':
			# Matching a group
			pos += 1
			tree, end = do_compile_maketree(nfa, text, pos, ")", options)
			currentstate = do_compile_transitions(nfa, startstate, tree, options)
			pos = end
		else:
			raise TextError(text, pos, "unknown escape character '%s'" % (text[pos]))

		if text[pos] == '|':
			# Capturing information about matches
			pos += 1
			end = text.find('|', pos)
			if end == -1:
				raise TextError(text, pos, "unclosed escape matcher |...|")

			tag = text[pos:end]
			pos = end+1

			newstart = nfa.newstate()
			t = nfa.transition(newstart, startstate, match=None)
			t.nextcapture = (tag, 0)
			startstate = newstart

			nextstate = nfa.newstate()
			t = nfa.transition(currentstate, nextstate, match=None)
			t.prevcapture = (tag, 1)
			currentstate = nextstate

		return (startstate, currentstate), pos

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
			currentstate = nfa.transition(currentstate, match=nfa_list(nfa, startinner, endinner))
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
