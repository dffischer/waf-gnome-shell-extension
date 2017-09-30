#!/usr/bin/python

"""
Install gnome-shell extensions.

The functions herein center around a feature called 'gse' which installs a
'metadata.json', 'extension.js', an optional 'prefs.js' and all additionaly
specified source files to a uuid-named directory for the shell to find it.

Schemas specified to the task generator or in the meta data description are
also installed and compiled when the glib2 tool is loaded.

    def configure(cnf):
        cnf.load("glib2")
        cnf.load("gse")

    def build(bld):
        bld(features="gse", uuid="some@extension",
                schemas="a.gschema.xml b.gschema.xml",  # not noted in metadata
                source="additional data files")  # not found by import scanning

Imports of the form 'const <something> = Me.imports.<import>;' are
automatically detected in the entrypoint javascript files. Additional source
and data files to install can manually be specified through the source
parameter. These are not scanned for includes.
"""

from waflib.TaskGen import feature, before_method
from waflib.Errors import WafError
from waflib.Utils import to_list
from os.path import join
from collections import deque
from functools import partial
from itertools import chain
from re import compile

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

class Work(set):
    """
    A workqueue set to which elements can only be added once, even after they
    were removed. Useful to explore a graph without iterating nodes twice.
    """
    def __init__(self, *elements):
        super().__init__(elements)
        self.seen = set(elements)

    def __contains__(self, element):
        return self.seen.__contains__(element)

    def add(self, element):
        if element not in self.seen:
            self.seen.add(element)
            super().add(element)

@feature("gse")
@before_method('process_source')
def process_gse(gen):
    # Retrieve sources.
    path = gen.path
    metadata = path.find_resource("metadata.json")
    def scan_includes(nodes, inclusion=compile(
        "const [^ =]+ ?= ?Me.imports.(?P<import>[^();]+);")):
        work = Work(*nodes)
        while work:
            current = work.pop()
            yield current
            for match in inclusion.finditer(current.read()):
                work.add(path.find_resource(
                    match.group("import").replace('.', '/') + '.js'))

    # Categorize sources.
    # Installation has to look at their hierarchy from the correct root to
    # install generated files into the same location as ready available ones.
    nothing, src, bld, both = partition(categories=4,
            items=chain((metadata, ), gen.to_nodes(getattr(gen, 'source', [])),
                scan_includes(chain((path.find_resource("extension.js"), ),
                    filter(lambda x: x, [path.find_resource("prefs.js")])),
                    path, gen.inclusion)),
            # The is_src and is_bld predicates are combined like binary flags
            # to end up with an integral predicate.
            predicate=lambda source: source.is_src() + 2 * source.is_bld())
    gen.source = []  # Suppress further processing.

    # Check for sources manually added outside the extension tree.
    bldpath = path.get_bld()
    nothing = tuple(nothing)
    if tuple(nothing):
        raise WafError("files {} neither found below {} nor {}".format(
            ', '.join(map(str, nothing)), path, bldpath))
    both = tuple(both)
    if tuple(both):
        raise WafError("files {} found both below {} and {}".format(
            ', '.join(map(str, nothing)), path, bldpath))

    # Retrieve uuid.
    uuid = getattr(gen, "uuid", None)
    if not uuid:
        raise WafError("missing uuid in {}".format(self))

    # Install.
    env = gen.env
    target = join(env.HOME,
            ".local", "share", "gnome-shell", "extensions", uuid)
    install = partial(gen.add_install_files,
            install_to=target, relative_trick=True)
    install(install_from=src)
    install(install_from=bld, cwd=bldpath)

    # Collect schemas.
    schemas = to_list(getattr(gen, 'schemas', []))
    metadata = metadata.read_json()
    if "settings-schema" in metadata:
        schemas += [metadata["settings-schema"] + '.gschema.xml']

    # Pass on to glib2 tool for schema processing.
    if schemas:
        gen.meths.append('process_settings')
        gen.settings_schema_files = schemas
        env.GSETTINGSSCHEMADIR = join(target, "schemas")
