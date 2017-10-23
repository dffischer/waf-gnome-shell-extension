# waftool for gnome-shell extensions

This tool teaches [Waf](http://waf.io) to install gnome-shell extensions for a single user or globally.


## Usage

[The included example](example/wscript) shows how to use it in a wafscript.

The tool can readily be loaded as long as it is found by the python module import mechanism. This is normally done by prepending the directory it resides in to the PYTHONPATH environment variable.


## Installation

The following command can be used to build an executable from the Waf Git repository including this tool.

```bash
git clone https://github.com/waf-project/waf
cd waf
git clone https://github.com/dffischer/waf-gnome-shell-extension
./waf-light configure --prefix=/usr \
  build --make-waf --tools='waf-gnome-shell-extension/gse.py'
```

To make it available to a system-wide waf installation, the included waf script can be used to place it into the waf library. [There is also a package available for Arch Linux.](https://aur.archlinux.org/packages/waf-gnome-shell-extension-git/)
