"""
Python wrapper for Virtuoso shell.

To be used in conjunction with IPython/Jupyter.
"""

import re
import signal
import pexpect
from pexpect import EOF
from subprocess import check_output

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
    prompt = '\r\n> $'
    _banner = None
    _version_re = None
    _output_re = None
    _output = ""
    _exec_error = None  # None means no error in last execution

    @property
    def banner(self):
        """
        Virtuoso shell's banner
        """
        if self._banner is None:
            self._banner = check_output(['/bin/tcsh', '-c', 'virtuoso -V']).decode('utf-8')
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
        self._output = self._shell.before
        # Check the output and throw exception in case of error
        self._parse_output()
        return self._output

    def __init__(self, *args, **kwargs):
        super(VirtuosoShell, self).__init__(*args, **kwargs)
        self._start_virtuoso()
        self._version_re = re.compile(r'version (\d+(\.\d+)+)')
        self._output_re = re.compile(r'\("(.*?)"\s+(\d+)\s+t\s+nil\s+\((.*?)\)\s*\)')
        self._end_output_re = re.compile('r(.*?)\r\nnil$')

    def _start_virtuoso(self):
        """
        Spawn a virtuoso shell.
        """
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that virtuoso and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            #TODO: Lookup 'setPrompts' for setting SKILL prompt.
            self._shell = pexpect.spawn('tcsh -c "virtuoso -nograph"', echo=False)
        finally:
            signal.signal(signal.SIGINT, sig)

    def _parse_output(self):
        """
        Parse the virtuoso shell's output and handle error.

        Virtuoso shell doesn't give a debug terminal, so we will
        fake one using the front-end's raw_input, in case of error.

        In case of error, set status to a tuple of the form : (etype, evalue, tb)
        else, set to None
        """
        self._exec_error = None

        # Fish for status info:

        # The output can have a stream of text ending
        # with the following format if there is an error:
        # ("errorClass" errorNumber t nil ("Error Message"))
        _parsed_output = self._output_re.search(self._output)
        self._exec_error = None
        if _parsed_output is not None:
            self._exec_error = _parsed_output.groups()
            self._exec_error = (self._exec_error[0],
                                int(self._exec_error[1]),
                                self._exec_error[2])
            self._output = self._output[:_parsed_output.start()]
        _parse_output = self._end_output_re.search(self._output)
        self._output = _parse_output.group(1)

        # If the shell reported any errors, throw exception
        if self._exec_error is not None:
            raise VirtuosoExceptions(self._exec_error)

    def run_cell(self, code):
        """
        Executes the 'code'

        #TODO: use 'store_history' and 'silent' similar to IPython
        """
        # Intercept errors in execution using 'errset' function
        _code_framed = '{errset({' + code + '}) errset.errset}'

        self._shell.sendline(_code_framed)
        self.wait_ready()

        return self._output

    def interrupt(self):
        """
        Send an interrupt to the virtuoso shell
        """
        self._shell.sendintr()

    def wait_ready(self):
        """
        Find the prompt after the shell output.
        """
        self._shell.expect(self.prompt)

    def shutdown(self, restart):
        """
        Shutdown the shell

        #TODO: use 'restart'
        """
        try:
            self._shell.sendline('exit').rstrip()
        except EOF:
            self._shell.close()
