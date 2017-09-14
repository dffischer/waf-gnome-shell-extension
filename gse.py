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

def configure(cnf):
    cnf.env.HOME = cnf.environ['HOME']

@feature("gse")
@before_method('process_source')
def process_gse(gen):
    sources = gen.to_nodes(["metadata.json", "extension.js"]) \
            + gen.to_nodes(getattr(gen, 'source', []))
    gen.source = []  # Suppress further processing.

    uuid = getattr(gen, "uuid", None)
    if not uuid:
        raise WafError("missing uuid in {}".format(self))

    gen.bld.install_files(files=sources, dest=join(gen.env.HOME,
        ".local", "share", "gnome-shell", "extensions", uuid))
