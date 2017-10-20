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

The configuration flag '--global' optionally switches to system-wide
installation for all users. To process it, the tool has to be loaded in the
configure and option functions.
"""

from waflib.TaskGen import feature, before_method, taskgen_method, task_gen
from waflib.Errors import WafError
from waflib.Utils import to_list
from waflib.Configure import conf
from waflib.Task import Task
from os.path import join
from collections import deque
from functools import partial
from itertools import chain
from re import compile
from contextlib import suppress

def options(opt):
    opt.add_option('--global', action='store_true', dest='glob', default=False,
            help="Install globally instead of for the current user only.")

def configure(cnf):
    env = cnf.env
    if cnf.options.glob:
        cnf.load('gnu_dirs')
        env.EXTDIR = join(env.DATAROOTDIR, "gnome-shell", "extensions", "{}")
        env.SCHEMADIR = join(env.DATAROOTDIR, "glib-2.0", "schemas")
    else:
        env.EXTDIR = join(cnf.environ['HOME'],
            ".local", "share", "gnome-shell", "extensions", "{}")
        env.SCHEMADIR = join(env.EXTDIR, "schemas")

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
            work.add(path.find_or_declare(
                match.group("import").replace('.', '/') + '.js'))

@feature("gse")
@before_method('process_source')
def process_gse(gen):
    path = gen.path
    gen.create_task('gse_producer', inputs=[
        path.find_or_declare("metadata.json"),
        path.find_or_declare("extension.js"),
        path.find_or_declare("prefs.js")
    ], **{parameter: getattr(gen, parameter)
        # Propagete a set of parameters.
        for parameter in gen.__dict__.keys()
        & set(('source', 'uuid', 'schemas'))})
    gen.source = []  # Suppress further processing.

class gse_producer(Task):
    always_run = True

    def scan(self):
        """
        Find implicit dependencies using the generator's scan_includes.

        The process is reentrant on non-existing files: When a node to be
        scanned for includes is missing, the current iteration is saved and all
        dependencies found up until now are returned, including the missing
        one. This shortly after causes are_implicit_nodes_ready to find a task
        generator producing this file. When the task was run, this scanner
        method is invoked again and scanning continues where it left off.  As
        it is now a prerequisite, execution will never return when the file
        cannot be produced.
        """
        deps, scanner = getattr(self, 'scan_in_progress', None) or \
                ([], self.generator.scan_includes(self.inputs[1:]))
        for node in scanner:
            deps.append(node)
            if not node.exists():
                self.scan_in_progress = deps, scanner
                break
        else:
            # no scan in progress any longer
            with suppress(AttributeError):
                del(self.scan_in_progress)
        return (deps, ())

    def sig_explicit_deps(self):
        try:
            return super().sig_explicit_deps()
        except FileNotFoundError:
            # Remove prefs.js as it is optional
            self.inputs = self.inputs[0:2]
            return super().sig_explicit_deps()

    def run(self):
        more_tasks = self.more_tasks = []

        gen = self.generator
        bld = gen.bld
        env = gen.env
        metadata_node = self.inputs[0]
        metadata = metadata_node.read_json()

        # Retrieve uuid.
        uuid = getattr(gen, "uuid", None) or metadata["uuid"]
        if not uuid:
            raise WafError("missing uuid in {}".format(self))

        if bld.is_install:
            # Retrieve and categorize sources.
            path = gen.path
            # Installation has to look at their hierarchy from the correct root to
            # install generated files into the same location as static ones.
            nothing, srcnodes, bldnodes, both = partition(categories=4,
                    items=chain((metadata_node, ), bld.node_deps[self.uid()],
                        gen.to_nodes(getattr(self, 'source', []))),
                    # The is_src and is_bld predicates are combined like binary
                    # flags to end up with an integral predicate.
                    predicate=lambda source: source.is_src() + 2 * source.is_bld())

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

            # Install.
            target = env.EXTDIR.format(uuid)
            install = partial(gen.add_install_files,
                    install_to=target, relative_trick=True)
            more_tasks += [install(install_from=srcnodes),
                    install(install_from=bldnodes, cwd=bldpath)]

        # Collect schemas.
        schemas = to_list(getattr(gen, 'schemas', []))
        if "settings-schema" in metadata:
            schemas += [metadata["settings-schema"] + '.gschema.xml']

        # Pass on to glib2 tool for schema processing.
        if schemas:
            gen = bld(features="glib2", settings_schema_files = schemas)
            gen.env.GSETTINGSSCHEMADIR = env.SCHEMADIR.format(uuid)
            gen.post()
            more_tasks += gen.tasks

    @staticmethod
    def keyword():
        return "Collecting"

gse_producer.__name__ = "GNOME Shell extension"
