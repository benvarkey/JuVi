"""
Python wrapper for Virtuoso shell.

To be used in conjunction with IPython/Jupyter.
"""

import re
import signal
import pexpect
from pexpect import EOF
from subprocess import check_output
import subprocess


class VirtuosoExceptions(Exception):
    """
    To handle errors throws by the virtuoso shell
    """
    def __init__(self, value):
        self.value = value
        super(VirtuosoExceptions, self).__init__(value)

    def __str__(self):
        return repr(self.value)


class VirtuosoShell(object):
    """
    This class gives a python interface to the Virtuoso shell.j
    """
    prompt = [re.compile(r'\r\n>\s$'), re.compile(r'^>\s$')]
    _banner = None
    _version_re = None
    _output = ""
    _exec_error = None  # None means no error in last execution

    @property
    def banner(self):
        """
        Virtuoso shell's banner
        """
        if self._banner is None:
            self._banner = check_output(['/bin/tcsh', '-c', 'virtuoso -V'],
                                        stderr=subprocess.STDOUT)
            self._banner = self._banner.decode('utf-8')
        return self._banner

    @property
    def language_version(self):
        """
        Language version
        """
        __match__ = self._version_re.search(self.banner)
        return __match__.group(1)

    @property
    def output(self):
        """
        Last output returned by the shell
        """
        return self._output

    def __init__(self, *args, **kwargs):
        super(VirtuosoShell, self).__init__(*args, **kwargs)
        self._start_virtuoso()
        self._version_re = re.compile(r'version (\d+(\.\d+)+)')
        self._error_re = re.compile(r'([\s\S]+?)\*Error\* (.+)(\s*?)([\s\S]*)')
        self._open_paren_re = re.compile(r'\(')
        self._close_paren_re = re.compile(r'\)')
        self._dbl_quote_re = re.compile(r'"')

    def _start_virtuoso(self):
        """
        Spawn a virtuoso shell.
        """
        # Signal handlers are inherited by forked processes, and we can't
        # easily # reset it from the subprocess. Since kernelapp ignores SIGINT
        # except in # message handlers, we need to temporarily reset the SIGINT
        # handler here # so that virtuoso and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            # I could use 'setPrompts' for setting SKILL prompt, but,
            # not relevant for Jupyter
            self._shell = pexpect.spawn('tcsh -c "virtuoso -nograph"',
                                        echo=False)
            self.wait_ready()
        finally:
            signal.signal(signal.SIGINT, sig)

    def _parse_output(self):
        """
        Parse the virtuoso shell's output and handle error.

        #TODO: Can I use the skill debugger somehow?

        In case of error, set status to a tuple of the form :
            (etype, evalue, tb)
        else, set to None
        """
        self._exec_error = None
        _err_match = self._error_re.search(self._output)
        _err_output = None
        if _err_match is not None:
            self._exec_error = ("Error", 1, _err_match.group(2))
            _err_output = _err_match.group(4)
            self._output = _err_match.group(1)

            # I like the '> ' prompt before the output,
            # makes it easier to match outputs with input lines
            # _shell_outputs = self._output.split("\r\n> ")[-1]
            _shell_outputs = self._output[:_err_match.end(1)]

        if _err_output is not None:
            self._output = (_shell_outputs + '\r\n' +
                            _err_output)
        # If the shell reported any errors, throw exception
        if self._exec_error is not None:
            raise VirtuosoExceptions(self._exec_error)

    def run_raw(self, code):
        """
        Send the code as it is.

        No error checking is done.
        """
        self._shell.sendline(code)
        self.wait_ready()

    def run_cell(self, code):
        """
        Executes the 'code'

        """

        # The SKILL shell doesn't intimate the user that it is waiting for
        # a matching double-quote or a closing parenthesis.
        # Since pexpect, or for that matter the user, has no way to distinguish
        # between a hung shell and a wait for completion, I should check
        # for completion before I send it out to the SKILL interpreter.
        #
        # Nothing fancy, just whether the number of open parenthesis match
        # the closed ones, and if I have an even number of double quotes.

        self._output = ''
        if(len(self._open_paren_re.findall(code)) !=
           len(self._close_paren_re.findall(code))):
            raise VirtuosoExceptions(("Syntax Error", 1,
                                      "Unmatched parenthesis"))
        if(len(self._dbl_quote_re.findall(code)) % 2 != 0):
            raise VirtuosoExceptions(("Syntax Error", 2,
                                      "Unmatched double-quotes"))

        _code_lines = [_line.rstrip() for _line in code.split('\n') if
                       _line.rstrip() != '']
        # I like having a prompt to group outputs :-P
        self._shell.sendline('')
        for _line in _code_lines:
            self._shell.sendline(_line)
        self.wait_ready()
        self._output = self._shell.before

        # Check the output and throw exception in case of error
        self._parse_output()

        return self.output

    def get_matches(self, token):
        """
        Return a list of functions and variables starting with *token*
        """
        _cmd = 'listFunctions("^%s")' % token
        self.run_raw(_cmd)
        _matches = []
        _output = self._shell.before
        if (_output) != 'nil':
            if _output[0] == '(':
                _output = _output[1:-1]
            _matches = _output.split()

        _cmd = 'listVariables("^%s")' % token
        self.run_raw(_cmd)
        _output = self._shell.before
        if (_output) != 'nil':
            if _output[0] == '(':
                _output = _output[1:-1]
            _matches.extend(_output.split())
        return _matches

    def get_info(self, token):
        """
        Returns info on the requested object

        # TODO: get info on variables also
        """
        # Make sure that only valid function/variable names are used
        token = re.match(r'^(\w+)', token).group(1)
        _cmd = 'help(%s)' % token
        self.run_raw(_cmd)
        _info = ''
        if self._shell.before != 'nil':
            _info = self._shell.before
        return (_info, token)

    def interrupt(self):
        """
        Send an interrupt to the virtuoso shell
        """
        self._shell.sendintr()

    def wait_ready(self):
        """
        Find the prompt after the shell output.
        """
        self._shell.expect_list(self.prompt, searchwindowsize=8)

    def shutdown(self, restart):
        """
        Shutdown the shell

        #TODO: use 'restart'
        """
        try:
            self.run_cell('exit()')
        except EOF:
            self._shell.close()

    def flush(self):
        """
        clear the buffer of the messages from the virtuoso shell
        """
        while(self._shell.after != pexpect.TIMEOUT):
            self._shell.expect_list([self.prompt[0],
                                     self.prompt[1],
                                     pexpect.TIMEOUT],
                                    searchwindowsize=8, timeout=1)
        self._shell.sendline('')
        self._shell.expect_list([self.prompt[0],
                                 self.prompt[1],
                                 pexpect.TIMEOUT],
                                searchwindowsize=8, timeout=1)
        if(self._shell.after == pexpect.TIMEOUT):
            # The shell is probably hung, interrupt
            self._shell.sendcontrol('c')
            self._shell.sendline('')
        self._shell.expect_list(self.prompt, searchwindowsize=8, timeout=1)
        self._output = self._shell.before
