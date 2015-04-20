# JuVi - Jupyter kernel for Cadence's Virtuoso Shell

The *SKILL* &copy; framework from *Cadence* &copy; is a powerful tool for design automation within Cadence's ecosystem.
However, the default *Virtuoso* &copy; shell leaves something to be desired. Enter IPython/Jupyter...

I have been using IPython for some time. When the IPython team introduced the *Notebook* interface, I found it useful,
since, I had been using *Mathematica* &copy; for a while and loved the idea of easily creating documents with formatted text 
interspersed with code. I have also used SKILL for a while, but, as useful as it is, using it interactively is frustrating.
Then, Jupyter was forked from IPython, and the team made available a clean API for the Kernel, and I found the 
[Bash Kernel](https://github.com/takluyver/bash_kernel), which uses `pexpect`.
The gears started turning and I now have a Kernel for *SKILL* (or more accurately, for *Virtuoso*).

# Features

  For *SKILL* specific syntax support in the Notebook,
  use [*SKILL* mode for Code Mirror](https://github.com/benvarkey/CodeMirrorSkill).

* Tab-complete built-in function and variable names.
* Shift+Tab for function help tool-tips.
* `->` and `~>` + Tab automatically lists properties.
* `plot` functions create figures inline (for Notebooks).
* Multi-instruction cells generate multiple outputs, numbered by the order of execution
(no number for single instruction cells).
  Note that *SKILL* provides `{...}` to return only the last instruction's output.
* Single line cell magics - `%help`, `%history`, `%image`, `%flush`, `%connect_info`, for now.
  Currently, the rest of the cell's contents are ignored.

# Installation
I have tested this only on Python-2.7.8+ and IPython-3.0.0+.

Once you have the prerequisites (see below), clone the repository and

    python setup.py install
    
You should now have a new entry, *Virtuoso*, in the notebook interface's *New* pull-down menu.

If you want to use the console, launch with 

    ipython console --kernel=virtuoso
  
## Prerequisites
* [*pexpect*] (https://pexpect.readthedocs.org/en/latest/install.html) : `pip install pexpect`.
This is required to talk to the *Virtuoso* shell from Python.

* [*colorama*] (https://github.com/tartley/colorama) : `pip install colorama`. This is required for colored outputs.
For now, it is not an optional requirement.

# License
   Copyright 2015 Ben Varkey Benjamin

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
