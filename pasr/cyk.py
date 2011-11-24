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
Match context-free grammar productions on a token tree, using a variant of the
Cocke–Younger–Kasami (CYK) algorithm.
"""

from text import TextRange, where_from_pos

class Tag(object):
	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "Tag(%s)" % (self.name)

class Production(object):
	"""
	Productions can have at most two variable sized elements in the middle
	"""
	class Element(object):
		def __init__(self):
			self.unitlength = False

		def match(self, node, start, end):
			raise

	def __init__(self, tag, elements):
		self.tag = tag
		self.elements = elements
		self.atstart = False
		self.atend = False
		self.nonunitlength = [i for i in range(len(self.elements)) if not self.elements[i].unitlength]
		if len(self.nonunitlength) > 2:
			raise ValueError("productions can have at most two non-unitlength elements")
		if len(self.nonunitlength) == 2:
			self.spanlengths = [
				self.nonunitlength[0],
				self.nonunitlength[1] - self.nonunitlength[0] - 1,
				len(self.elements) - self.nonunitlength[1] - 1
			]
		elif len(self.nonunitlength) == 1:
			self.spanlengths = [
				self.nonunitlength[0],
				len(self.elements) - self.nonunitlength[0] - 1
			]
		else:
			self.spanlengths = [len(self.elements)]

	def cache_unitlengths(self, node):
		cache = []

		for span in range(len(self.nonunitlength) + 1):
			cache.append([])
			if span == 0:
				left = 0
			else:
				left = self.nonunitlength[span-1]+1
			if span == len(self.nonunitlength):
				right = len(self.elements)
			else:
				right = self.nonunitlength[span]

			for start in range(left, len(node.annotations) - (len(self.elements) - left) + 1):
				if self.atstart and span == 0 and start != 0:
					continue
				if self.atend and span == len(self.nonunitlength) and start + (right - left) != len(node.token):
					continue

				kv = {}
				for idx in range(right - left):
					subkv = self.elements[left + idx].match(node, start + idx, start + idx + 1)
					if subkv == None:
						break
					kv.update(subkv)
				else:
					cache[-1].append((start, kv))

#		print "on", str(node.textrange(0, len(node.token)))
#		print "cache", cache

		return cache

	def produce(self, node, length, cache):
		if length < len(self.elements):
			return

		if len(self.nonunitlength) == 0:
			if length == len(self.elements):
				for start,kv in cache[0]:
					node.addmatch(start, start + length, self.tag, kv)
			return

		# Filter potential positions based on left and right unitlength segments
		starts = []
		leftcache = cache[0]
		rightcache = cache[-1]
		rightoffset = self.spanlengths[-1] - length
		i = 0
		j = 0
		while i < len(leftcache) and j < len(rightcache):
			leftstart = leftcache[i][0]
			rightstart = rightcache[j][0] + rightoffset
			if leftstart < rightstart:
				i += 1
			elif leftstart > rightstart:
				j += 1
			else:
				kv = {}
				kv.update(leftcache[i][1])
				kv.update(rightcache[j][1])
				starts.append((leftstart, kv))
				i += 1
				j += 1

#		print "on", str(node.textrange(0, len(node.token)))
#		print "produce(%d)" % (length), "starts", starts

		if len(self.nonunitlength) == 1:
			for start,kv in starts:
				nu = self.nonunitlength[0]
				subkv = self.elements[nu].match(node, start + nu, start + length - self.spanlengths[-1])
				if subkv == None:
					continue
				kv = kv.copy()
				kv.update(subkv)
				node.addmatch(start, start + length, self.tag, kv)
		else:
			for start,kv in starts:
				for mid,midkv in cache[1]:
					left = self.nonunitlength[0]
					right = self.nonunitlength[1]
					if mid <= start + left:
						continue
					if mid + self.spanlengths[1] + 1 + self.spanlengths[2] > start + length:
						continue

					leftkv = self.elements[left].match(node, start + left, mid)
					if leftkv == None:
						continue
					rightkv = self.elements[right].match(node, mid + self.spanlengths[1], start + length - self.spanlengths[2])
					if rightkv == None:
						continue
					kv = kv.copy()
					kv.update(midkv)
					kv.update(leftkv)
					kv.update(rightkv)
					node.addmatch(start, start + length, self.tag, kv)
					break

class Match(object):
	"""
	Find production matches on a token tree using dynamic programming.
	"""
	class AnnotatedNode(object):
		def __init__(self, tok):
			self.token = tok
			if type(tok) == list:
				self.annotations = [Match.AnnotatedNode(elt) for elt in tok]
				self.thematches = [[] for i in range((len(tok) * (len(tok)+1)) / 2)]
			else:
				self.annotations = None
				self.thematches = None

		def visitlists(self, fn):
			"""
			Call fn on every list-node in the tree.
			"""
			if self.annotations:
				for elt in self.annotations:
					if elt.annotations:
						elt.visitlists(fn)
				fn(self)

		def islist(self):
			return self.annotations != None

		def matches(self, start, end):
			assert self.thematches != None
			assert 0 <= start and start < end and end <= len(self.annotations)
			return self.thematches[(end * (end-1))/2 + start]

		def addmatch(self, start, end, tag, kv):
			assert self.annotations

			tr = self.textrange(start, end)
			print "addmatch(%s = %s) from %s to %s" % (tag, str(tr), where_from_pos(tr.text, tr.start), where_from_pos(tr.text, tr.end))
			self.matches(start, end).append((tag, kv))

		def textstart(self, elt):
			assert self.annotations

			tok = self.token[elt]
			if type(tok) == list:
				return self.token[elt-1].end
			return tok.start

		def textend(self, elt):
			assert self.annotations

			tok = self.token[elt]
			if type(tok) == list:
				return self.token[elt+1].start
			return tok.end

		def textrange(self, start, end):
			startpos = self.textstart(start)
			endpos = self.textend(end-1)
			if type(self.token[start]) == list:
				text = self.token[start+1].text
			else:
				text = self.token[start].text
			return TextRange(text, startpos, endpos)

	def __init__(self, tree, productions):
		self.tree = Match.AnnotatedNode(tree)
		self.productions = productions
		self.tree.visitlists(self.produce)

	def produce(self, node):
		# First of all, mark tokens and sublists with already known matches
		for idx in range(len(node.token)):
			elt = node.annotations[idx]
			if not elt.islist():
				if elt.token.tag != None:
					node.addmatch(idx, idx+1, elt.token.tag, {})
			else:
				if len(elt.annotations) > 0:
					for tag,kv in elt.matches(0, len(elt.annotations)):
						node.addmatch(idx, idx+1, tag, kv)

		# Allow all productions to mark their potential unitlength entrypoints
		unitlengthcaches = []
		for prod in self.productions:
			unitlengthcaches.append(prod.cache_unitlengths(node))

		# Now apply productions
		for length in range(1, len(node.annotations) + 1):
			for idx in range(len(self.productions)):
				self.productions[idx].produce(node, length, unitlengthcaches[idx])

	def forgreedymax(self, tag, fn):
		"""
		Call the given function with the key-value mappings for a greedy selection
		of inclusion-wise maximal occurences of the given tag.
		"""
		def visit(node):
			start = 0
			while start < len(node.token):
				for end in range(len(node.token), start, -1):
					matches = node.matches(start, end)
					for t, kv in matches:
						if t == tag:
							fn(kv)
							break
					else:
						continue
					start = end
					break
				else:
					if type(node.token[start]) == list:
						visit(node.annotations[start])
					start += 1

		visit(self.tree)
