Parenthesis-Aware Tokenized Regular EXpressions
===============================================

Patrex allows you to automatically and conveniently refactor source-code based
on relatively simple pattern matching.

At its core, you can think of Patrex as a more powerful `sed`. It matches regular
expressions on a tokenized stream in which parenthesis (and brackets and curly
braces) are treated specially to simplify dealing with nested expressions, and
allows you to perform actions based on matches. This is explained later in a
bit more detail.

All this generality aside, Patrex was created to help with maintaining a large
codebase in C++, so that is how to best understand where it can come in useful.


Examples
--------

Suppose we have a lot of code that uses [boost::bind](http://www.boost.org/doc/libs/1_48_0/libs/bind/bind.html)
to bind member function pointers using

    boost::bind(&Foo::bar, boost::ref( *this ), ...)

As you may know, `boost::bind` can take both references and pointers with
member functions, so all such calls can be simplified to

    boost::bind(&Foo::bar, this, ...)

We do not want to blindly search and replace `boost::ref( *this )` by `this`,
because there are places where such a replacement would be incorrect. Patrex
can help. Create a script called `bind.patrex` with contents

    match boost::bind(& ${id} $( :: ${id} )+, $( boost::ref( *this ) )|ref| $.* )
        replace ref "this"

and run Patrex as follows:

    patrex bind.patrex sourcefile.cc

So how does this work? The first line of the script file tells Patrex to
search for the given regular expression. Observe how whitespace within the
regular expression is not important.

Whenever a match is found, it then runs the "mini-program" given below.
Indentation is relevant here, similar to Python, and the `replace` command
should be self-explanatory.

Pretty much everything inside a Patrex regular expression is interpreted
literally. The only exception is the $ (dollar) sign, which introduces
*escape sequences*. For example, `${id}` matches any token that is *tagged*
`id` -- that is, it matches things that look like identifiers. `$.*` matches
any number of zero or more tokens, `$(...)` is used for grouping, and the
pipes in `$( ... )|ref|` cause the contents of the previous group to be
*captured* into the variable called `ref`. This is later used to tell the
`replace` command where to do the replacing.

Let us look at a more complicated example. Suppose you want to refactor a
method `setfoo` such that its third parameter is removed, and setting that
parameter is delegated to a new method `setbar`. That is, code like this:

    a.setfoo(get(x, y), (w + h) / 2, tmp, 0);

must be changed to:

    a.setfoo(get(x, y), (w + h) / 2, 0);
    a.setbar(tmp);

Note how problematic it would be to try to achieve this transformation using
normal regular expressions: the comma inside the call to `get` is sure to
throw off a naive approach. We ill use the following Patrex script:

    define arg $!(,)*

    match $( ${id} $|( . )( -> ) )|var| foo ( ${arg}, ${arg}|second|, ${arg}|third|, ${arg} ); $<|pos|
        erase second.end third.end
        insert pos "\n\t{var}bar({third});"

This script shows off a number of additional features of regular expressions
in Patrex. It is possible to `define` regular expression snippets. Every
occurence of `${arg}` behaves as if the definition of `arg` were pasted
literally. The expression `$!(,)*` matches an arbitrary length sequence of
tokens that are not commas. The expression `$<|pos|` causes the end of the
previous token to be stored in the variable `pos`. Note the mnemonic `$<`:
the corresponding `$>` exists as well.

Note that the `insert` and `replace` commands use the [Python formatting
syntax](http://docs.python.org/library/string.html#formatspec).

Patrex also has some support for lists and loops. The script

    match $( dolist( $!(,)*|obj|, $( $!(,)*|param| )+(,)[params] ); )|call|
        erase call
        forall params
            insert call.start "do({obj}, {param});\n"

will transform

    dolist(obj, a, b, c);

into

    do(obj, a);
    do(obj, b);
    do(obj, c);

You can find more examples in the `tests/` subdirectory.


Background and some Internals
-----------------------------

Typical implementations of regular expressions like `sed` and `grep` operate
on character streams. However, the theory of regular expressions can be just
as well applied on streams of tokens, and this is done by Patrex.

One key weakness of regular expressions is dealing with nested expressions.
Since nesting is typically always done by balanced pairs of parentheses,
brackets, or curly braces, the power of regular expressions can be greatly
enhanced simply by nesting those explicitly.

Therefore, the first processing step of Patrex is to tokenize the input stream
and transform it into a tree. The internal representation is via lists,
i.e. the input stream is translated into a list that contains tokens and
nested lists. For example,

    x * (end - begin)

is represented as

    [ 'x', '*', '(', [ 'end', '-', 'begin' ], ')' ]

Regular expressions are parsed similarly and compiled into a non-determinstic
finite automaton (NFA). Transitions between states are labelled with matching
functions, and transitions are taken when the corresponding matching function
succeeds. The NFA implementation also supports *epsilon* transitions, which
are always taken immediately. The latter transitions can be labelled by
*capturing instructions* to capture the position of parts of the input, and
by *stack operations*, to support capturing lists.

Despite this, the NFA implementation does not really understanding about the
nesting of trees. Sublists are considered almost like any other token. It is
up to the matching functions to use a secondary NFA computation to test
whether a sublist matches the desired regular expression. That is, a regular
expression like

    boost::ref( *this )

is in fact implemented by two separate NFAs. The top-level NFA recognizes
`boost::ref(`, followed by a transition that matches any sublist that is
recognized by a second NFA, followed by `)`. The second NFA recognizes the
list `[ '*', 'this' ]`.


Escape sequences
----------------

All escape sequences begin with a dollar sign. The dollar sign itself can be
represented as `$$`.

The special escape sequences `$<|name|` and `$>|name|` store the end of the
previous and the start of the next token, respectively, in the field of the
given name.

Other escape sequences have the following general form:

    '$' ['!'] (brace | parens | '.' | '|' (brace | parens)* )
        [ '*' | '+' [ brace | parens ] [ '[' capturename ']' ] ]
        [ '|' capture '|' ]

Note that no whitespace is allowed between elements of escape sequences.
The sole exception are sub-expressions inside parenthesis, which may contain
arbitrary whitespace.

Braces take the form `{tag}`; they match a previously defined regular
expression snippet or (if not defined) a single token of the given tag.

Parens take the form `( ... )` and simply contain a free-form  sub-expression
to be matched.

The dot '.' matches any token.

The pipe '|' can be followed by any number of braces and parens, and matches
any of them. If several of the options match, latter ones are preferred.

If the bang '!' is present, then instead of matching what has been described
so far, a single token is matched *as long as the previously described
expression does not match at the current point*.

The star '*' and plus '+' match any number and at least one of the previously
described expressions as usual. They can be optionally followed by a brace or
parens to require matching of separators. That is, `$(X)*(Y)` matches token
streams such as `X Y X Y X`. The optional square bracket can be used to store
matches inside the star into a list that can later be read out by `forall`.

Finally, the pipes '|', when present, capture the entire previously matched
string into the given key.

For example, the escape sequence

    $( ${id}|name| )+(,)[list]|all|

will match the input

    foo, bar, baz

and will assign

    all: "foo, bar, baz"
    list: [ {name: "foo"}, {name: "bar"}, {name: "baz"} ]


Limitations
-----------

Patrex does not actually understand C or C++ or any of these langauges. There
are types of refactoring problems where one really wants to know e.g. the type
of the variable that an identifier refers to. Such analysis is beyond the scope
of Patrex. If you implement a Patrex-like language for, say, KDevelop that can
capture this type of information, you will be my hero.

The way Patrex tokenizes its input is not suitable for every language. For
example, it is currently hard-coded to recognize only C-style comments. If you
tackle this, a pull request would be very welcome.


License
-------

Patrex is under a MIT-style license:

Copyright (c) 2011 Nicolai Hähnle <nhaehnle@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
