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
Provide Tokenizer and Treeify that are appropriate for working with C++
source files (and sources from many other languages, particularly those
with similar comment syntax).
"""

from text import where_from_pos, TextRange
from parse import Tokenizer, Treeify, tok_whitespace, tok_fallback, tok_regex
import re

def cppcomment(text, pos):
	if text.startswith('//', pos):
		end = text.find('\n', pos + 2)
		if end == -1:
			return None, len(text)
		else:
			return None, end + 1
	elif text.startswith('/*', pos):
		end = text.find('*/', pos + 2)
		if end == -1:
			raise ValueError("%s: unterminated /* */ style comment" % (where_from_pos(text, pos)))
		return None, end + 2
	return None, None

def cppliteral(text, pos):
	if text[pos] in [ '"', "'" ]:
		end = pos + 1
		while end < len(text):
			if text[end] == text[pos]:
				break
			if text[end] == '\\':
				end += 1
			end += 1
		else:
			raise ValueError("unterminated string literal")
		end += 1
		return TextRange(text, pos, end, "literal"), end
	return None, None

tokenizer = Tokenizer()
tokenizer.addfn(tok_regex(re.compile("[a-zA-z_][a-zA-Z_0-9]*", re.VERBOSE), "id"))
tokenizer.addfn(cppcomment)
tokenizer.addfn(cppliteral)
tokenizer.addfn(tok_whitespace([' ', '\t', '\n']), -100)
tokenizer.addfn(tok_fallback(), 100)

treeify = Treeify()
treeify.addparens("(", ")")
treeify.addparens("[", "]")
treeify.addparens("{", "}")
