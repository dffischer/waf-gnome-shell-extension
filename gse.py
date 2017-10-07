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
        bld(features="gse",
                uuid="some@extension",  # if not parsable from metadata.json
                schemas="a.gschema.xml b.gschema.xml",  # not noted in metadata
                source="additional data files")  # not found by import scanning

Imports of the form 'const <something> = Me.imports.<import>;' are
automatically detected in the entrypoint javascript files. An alternative
pattern to find these can be injected using the set_inclusion functions, either
globally on the context or on a dedicated task generator.

    gen = bld(features="gse", uuid="some@extension")
    gen.set_inclusion("Me.imports.(?P<import>[^ .]+)")
    gen.source = list(gen.scan_includes("library.js"))

Additional source and data files to install can manually be specified through
the source parameter. To have these scanned for includes, wrap them with the
scan_includes function available as a task generator method.
"""

from waflib.TaskGen import feature, before_method, taskgen_method, task_gen
from waflib.Errors import WafError
from waflib.Utils import to_list
from waflib.Configure import conf
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

@taskgen_method
def set_inclusion(gen, regex):
    """
    Define an alternative pattern for this generator to find include
    directives.  The given regular expression should have a group named
    'import' which yields the inclusion with dots for slashes and without the
    '.js' extension.
    """
    gen.inclusion = compile(regex)

@conf
def set_inclusion(regex):
    """
    Define a default inclusion pattern for all generators that set_inclusion
    was not called on.
    """
    task_gen.inclusion = compile(regex)
set_inclusion("const [^ =]+ ?= ?Me.imports.(?P<import>[^();]+);")

@taskgen_method
def scan_includes(gen, nodes):
    """
    Recursively scan javascript code for the generator's include pattern.
    """
    path = gen.path
    inclusion = gen.inclusion
    work = Work(*nodes)
    while work:
        current = work.pop()
        yield current
        for match in inclusion.finditer(current.read()):
            work.add(path.find_resource(
                match.group("import").replace('.', '/') + '.js'))

@feature("gse")
@before_method('process_source')
def process_gse(gen):
    # Retrieve and categorize sources.
    path = gen.path
    metadata = path.find_resource("metadata.json")
    # Installation has to look at their hierarchy from the correct root to
    # install generated files into the same location as ready available ones.
    nothing, src, bld, both = partition(categories=4,
            items=chain((metadata, ), gen.to_nodes(getattr(gen, 'source', [])),
                gen.scan_includes(chain((path.find_resource("extension.js"), ),
                    filter(lambda x: x, [path.find_resource("prefs.js")])))),
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
    metadata = metadata.read_json()
    uuid = getattr(gen, "uuid", None) or metadata["uuid"]
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
    if "settings-schema" in metadata:
        schemas += [metadata["settings-schema"] + '.gschema.xml']

    # Pass on to glib2 tool for schema processing.
    if schemas:
        gen.meths.append('process_settings')
        gen.settings_schema_files = schemas
        env.GSETTINGSSCHEMADIR = join(target, "schemas")
