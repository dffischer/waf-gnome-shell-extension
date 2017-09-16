#!/usr/bin/python

"""
Install gnome-shell extensions.

The functions herein center around a feature called 'gse' which installs a
'metadata.json', 'extension.js' and all additionaly specified source files to a
uuid-named directory for the shell to find it.

    def configure(cnf):
        cnf.load("gse")

    def build(bld):
        bld(features="gse", uuid="some@extension", source="prefs.js")
"""

from waflib.TaskGen import feature, before_method
from waflib.Errors import WafError
from os.path import join
from collections import deque
from functools import partial

def configure(cnf):
    cnf.env.HOME = cnf.environ['HOME']

def partition(items, predicate=int, categories=2):
    """
    Split the iterator content into the given number of per-category iterators.

    The idea adapted here came to be as a technique to split a list into to
    exactly two categories by a boolesh predicate. It was originally posted to
    the comp.lang.python mailing list by Chris Angelico, improved with a deque
    tweak by Tim Chase, found on Ned Batchelder's blog at
    http://nedbatchelder.com/blog/201306/filter_a_list_into_two_parts.html
    """
    items = iter(items)
    queues = tuple(deque() for _ in range(categories))
    def iterate_category(category):
        queue = queues[category]
        while True:
            if queue:
                yield queue.popleft()
            else:
                for val in items:
                    result = predicate(val)
                    if result == category:
                        yield val
                        break
                    else:
                        queues[result].append(val)
                else:
                    break
    return map(iterate_category, range(categories))

@feature("gse")
@before_method('process_source')
def process_gse(gen):
    # Compose sources.
    sources = gen.to_nodes(["metadata.json", "extension.js"]) \
            + gen.to_nodes(getattr(gen, 'source', []))
    gen.source = []  # Suppress further processing.

    # Categorize sources.
    # Installation has to look at their hierarchy from the correct root to
    # install generated files into the same location as ready available ones.
    nothing, src, bld, both = partition(sources, categories=4, predicate=
            # The is_src and is_bld predicates are combined like binary flags
            # to end up with an integral predicate.
            lambda source: source.is_src() + 2 * source.is_bld())

    # Retrieve uuid.
    uuid = getattr(gen, "uuid", None)
    if not uuid:
        raise WafError("missing uuid in {}".format(self))

    # Install.
    install = partial(gen.add_install_files, install_to=join(gen.env.HOME,
        ".local", "share", "gnome-shell", "extensions", uuid))
    install(install_from=src)
    install(install_from=bld, cwd=bldpath)
