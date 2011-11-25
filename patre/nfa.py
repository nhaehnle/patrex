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
Non-deterministic finite automaton (NFA) for tokenized trees.
"""

from text import TextRange

def nfa_token(token):
	"""
	Return a transition matching function that matches exactly the given token.
	"""
	assert isinstance(token, (str, TextRange))
	def inner(prev, cur, next):
		if isinstance(cur, TextRange) and str(cur) == str(token):
			return {}
		return None
	inner.func_name = "token(%s)" % (token)
	return inner

def nfa_tag(tag):
	"""
	Return a transition matching function that matches a token if it has the given tag.
	"""
	def inner(prev, cur, next):
		if hasattr(cur, "tag") and cur.tag == tag:
			return {}
		return None
	inner.func_name = "tag(%s)" % (tag)
	return inner

def nfa_list(nfa, startstate, endstate):
	"""
	Return a transition matching function that matches a tree which matches
	the given NFA, starting at startstate and ending at endstate
	"""
	def inner(prev, cur, next):
		if type(cur) == list:
			endstates = nfa(cur, startstate, prev, next)
			if endstate in endstates:
				return endstates[endstate]
		return None
	inner.func_name = "list(%d, %d)" % (startstate, endstate)
	inner.write = nfa.write
	return inner

def nfa_any():
	"""
	Return a transition matching function that matches any token
	"""
	def inner(prev, cur, next):
		return {}
	inner.func_name = "any"
	return inner

class Nfa(object):
	class State(object):
		def __init__(self):
			self.transitions = []
			self.epsilons = []

	class Transition(object):
		def __init__(self, start, end, match):
			self.start = start
			self.end = end
			self.match = match
			self.callback = None
			self.prevcapture = None
			self.nextcapture = None

	def __init__(self):
		self.states = []
		self.debug = False
		self.writing = False

	def newstate(self):
		self.states.append(Nfa.State())
		return len(self.states) - 1

	def transition(self, start, end, match):
		assert 0 <= start and start < len(self.states)
		assert 0 <= end and end < len(self.states)
		t = Nfa.Transition(start, end, match)
		if match != None:
			self.states[start].transitions.append(t)
		else:
			self.states[start].epsilons.append(t)
		return t

	def insert(self, subnfa):
		"""
		Copy all of the sub-NFA's states into this one, returning a state mapping dictionary
		"""
		statemap = dict([(i, len(self.states)+i) for i in range(len(subnfa.states))])
		for state in subnfa.states:
			self.newstate()

		for oldidx in range(len(subnfa.states)):
			oldstate = subnfa.states[oldidx]
			newstate = self.states[statemap[oldidx]]
			for t in oldstate.transitions:
				self.transition(statemap[t.start], statemap[t.end], match=t.match)
			for t in oldstate.epsilons:
				newt = self.transition(statemap[t.start], statemap[t.end], match=None)
				newt.callback = t.callback
				newt.prevcapture = t.prevcapture
				newt.nextcapture = t.nextcapture

		return statemap

	def expand_epsilons(self, states, prev, next):
		while type(prev) == list:
			prev = prev[-1]
		while type(next) == list:
			next = next[0]

		queue = states.items()
		while queue:
			state,kv = queue.pop()
			for transition in self.states[state].epsilons:
				if transition.end in states:
					continue

				if transition.prevcapture or transition.nextcapture:
					newkv = kv.copy()
					if transition.prevcapture and prev:
						newkv[transition.prevcapture] = prev.end
					if transition.nextcapture and next:
						newkv[transition.nextcapture] = next.start
				else:
					newkv = kv
				states[transition.end] = newkv
				queue.append((transition.end, newkv))

				if transition.callback:
					transition.callback(newkv)

	def __call__(self, tree, startstate, beforetoken=None, aftertoken=None):
		states = { startstate: {} }

		if not tree:
			self.expand_epsilons(state, beforetoken, aftertoken)
			return states

		token = beforetoken
		nexttoken = tree[0]

		for idx in range(len(tree)):
			prevtoken, token = token, nexttoken
			if idx+1 == len(tree):
				nexttoken = aftertoken
			else:
				nexttoken = tree[idx+1]

			self.expand_epsilons(states, prevtoken, token)
			if self.debug:
				print "%d = %s" % (idx, token), states.keys()

			newstates = {}
			for state,kv in states.iteritems():
				for transition in self.states[state].transitions:
					if transition.end in newstates:
						continue

					matchkv = transition.match(prevtoken, token, nexttoken)
					if matchkv == None:
						continue

					if matchkv:
						newkv = kv.copy()
						newkv.update(matchkv)
					else:
						newkv = kv
					newstates[transition.end] = newkv
			states = newstates

		self.expand_epsilons(states, token, nexttoken)
		return states

	def write(self):
		"""
		Output the states and transitions (for debugging)
		"""
		if self.writing:
			return
		self.writing = True
		for state in range(len(self.states)):
			print "%3d:" % (state),
			first = True
			for transition in self.states[state].transitions:
				if first:
					first = False
				else:
					print "    ",
				print "->", transition.end, transition.match
				if hasattr(transition.match, "write"):
					transition.match.write()

			for transition in self.states[state].epsilons:
				if first:
					first = False
				else:
					print "    ",
				print "->", transition.end, "<eps>",
				if transition.callback:
					print "callback", transition.callback,
				if transition.prevcapture:
					print "prevcapture", transition.prevcapture,
				if transition.nextcapture:
					print "nextcapture", transition.nextcapture,
				print
			if first:
				print
		self.writing = False
