"""
Python wrapper for Virtuoso shell.

To be used in conjunction with IPython/Jupyter.
"""

import zmq
import re
#import signal
#import pexpect
#from pexpect import EOF
#from subprocess import check_output
#import subprocess
#from time import sleep
import colorama


class VirtuosoExceptions(Exception):
    """
    To handle errors throws by the virtuoso shell
    """
    def __init__(self, value):
        self.value = value
        super(VirtuosoExceptions, self).__init__(value)

    def __str__(self):
        return repr(self.value)


class VirtuosoShellClient(object):
    """
    This is the client that talks to dfII's python server
    """
    def __init__(self, port=None):
        super(VirtuosoShellClient, self).__init__()
        self.port = port
        if self.port is None:
            #TODO: get port from config
            self.port=66666
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:%s" % self.port)

    def write(self, payload):
        #TODO: make sure the payload type is correct
        self.socket.send_string(u"%s\n" % payload)

    def read(self):
        return self.socket.recv().decode()

    def close(self):
        #TODO: Finish this function
        print("close() TBD")

class VirtuosoShell(object):
    """
    This class gives a python interface to the Virtuoso shell.
    """
    _banner = None
    _version_re = None
    _output = ""
    _exec_error = None  # None means no error in last execution

    @property
    def banner(self):
        """
        Virtuoso shell's banner
        """
        #TODO: Get actual response
        #if self._banner is None:
        #    self._banner = check_output(['/bin/tcsh', '-c', 'virtuoso -V'],
        #                                stderr=subprocess.STDOUT)
        #    self._banner = self._banner.decode('utf-8')
        self._banner = "Fake Shell version 0.00\n"
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
        self.prompt = [re.compile(r'\r\n<<pyvi>> $'),
                       re.compile(r'^<<pyvi>> $')]
        self._shell_available_re = re.compile(r'"__jupyter_kernel_ready__"'
                                              r'[\s\S]+')
        self._version_re = re.compile(r'version (\d+(\.\d+)+)')
        self._error_re = re.compile(r'^([\s\S]*?)\*Error\*'
                                    r'(.+)(\s*)([\s\S]*)')
        self._open_braces_re = re.compile(r'\{')
        self._close_braces_re = re.compile(r'\}')
        self._open_paren_re = re.compile(r'\(')
        self._close_paren_re = re.compile(r'\)')
        self._dbl_quote_re = re.compile(r'"')
        self._output_prompt_re = re.compile(r'<<pyvi>> ')
        self._object_prop_re = re.compile(r'(\w+?)\s*([-~]>)(\w*?)$')
        self._object_prop_list_re = re.compile(r'\((\w+?)\)\s*([-~]>)(\w*?)$')
        self._var_name_re = re.compile(r'\s*(\w+)$')
        self.match_dict = {self._object_prop_re: lambda _match: '%s%s?' %
                           (_match.group(1), _match.group(2)),
                           self._object_prop_list_re: lambda _match:
                           'car(%s)%s?' % (_match.group(1), _match.group(2)),
                           self._var_name_re: lambda _match:
                           'listFunctions("^%s" t)\r\nlistVariables("^%s")' %
                           (_match.group(1), _match.group(1))}
        self._start_virtuoso()

    def _start_virtuoso(self):
        """
        Spawn a virtuoso shell.
        """
        #self._shell = pexpect.spawn('tcsh -c "virtuoso -nograph"',
        #                            echo=False)
        #self._shell.expect(r'> $', searchwindowsize=64)
        #self._output = self._shell.before
        #self._shell.sendline('setPrompts("<<pyvi>> " ' '"<%d<pyvi>> ")')
        ## sleep(0.5)
        ## self._shell.expect(r'<<pyvi>> ', searchwindowsize=64)
        #self._shell.expect_list(self.prompt, searchwindowsize=64)

        #TODO: pass the correct port
        self._shell = VirtuosoShellClient()

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
        if _err_match is not None:
            self._exec_error = ("Error", 1, _err_match.group(2))

        # number the output line
        _output_list = [_line.rstrip() for _line in
                        self._output_prompt_re.split(self._output) if
                        _line.rstrip() != '']
        _out_num = 1
        _color = colorama.Fore.YELLOW
        self._output = ''
        _single_line = (len(_output_list) == 1)
        for _oline in _output_list:
            if self._error_re.search(_oline) is not None:
                _color = colorama.Fore.RED
                if(not _single_line):
                    self._output += ('%s%s%d> %s%s%s\n' %
                                     (colorama.Style.BRIGHT, _color, _out_num,
                                      _oline, colorama.Fore.RESET,
                                      colorama.Style.NORMAL))
                else:
                    self._output += ('%s%s%s%s%s\n' % (colorama.Style.BRIGHT,
                                                       _color, _oline,
                                                       colorama.Fore.RESET,
                                                       colorama.Style.NORMAL))
            else:
                _color = colorama.Fore.YELLOW
                if(not _single_line):
                    self._output += '%s%d>%s %s\n' % (_color, _out_num,
                                                      colorama.Fore.RESET,
                                                      _oline)
                else:
                    self._output += '%s\n' % (_oline)
            _out_num += 1
        self._output = self.output.rstrip()
        # If the shell reported any errors, throw exception
        if self._exec_error is not None:
            raise VirtuosoExceptions(self._exec_error)

    def _pretty_introspection(self, info, keyword):
        import re
        # Optional keywords
        info = re.sub(r'(\?\w+)', r'%s\1%s' % (colorama.Fore.YELLOW,
                                               colorama.Fore.RESET), info,
                      count=0)
        # Required arguments
        info = re.sub(r'(\s*)(%s\()([\r\n]*)([\w\s]+)([\s\S]+)' % keyword,
                      r'\1\2\3%s\4%s\5' % (colorama.Fore.GREEN,
                                           colorama.Fore.RESET), info)
        # Function name
        info = re.sub(r'(%s)(\()' % keyword,
                      r'%s\1%s\2' % (colorama.Fore.BLUE,
                                     colorama.Fore.RESET),
                      info, count=0)
        return info[:-1]

    def run_raw(self, code, raw_mode=True):
        """
        Send the code as it is.

        No error checking is done.
        """
        self._shell.write(code)
        self.wait_ready(raw_mode)

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

        if(len(self._open_braces_re.findall(code)) !=
           len(self._close_braces_re.findall(code))):
            raise VirtuosoExceptions(("Syntax Error", 1,
                                      "Unmatched braces"))
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
        # except if there is only one line
        #if(len(_code_lines) > 1):
        #    self._shell.write('')
        #for _line in _code_lines:
        #    self._shell.write(_line)
        #TODO: cleanup code
        self._output = ''
        for _line in _code_lines:
            self._shell.write(_line)
            self._output += self._shell.read()
            self._output += "\n"

        # Check the output and throw exception in case of error
        self._parse_output()

        return self.output

    def get_matches(self, code_line):
        """
        Return a list of functions and variables matching the line's end or
        in case of '->' or '~>', a list of attributes.
        """
        _cmd = None
        _token = ''
        _match_list = []
        _match = self._object_prop_re.search(code_line)
        _raw_mode = True
        if(_match is None):
            _match = self._object_prop_list_re.search(code_line)
        if(_match is None):
            _match = self._var_name_re.search(code_line)
            _raw_mode = False
        if(_match is not None):
            _cmd = self.match_dict[_match.re](_match)
            _token = _match.group(1)
            self.run_raw(_cmd, raw_mode=_raw_mode)
            if(self._error_re.search(self._output) is None):
                _output = self._output.replace('(', ' ')
                _output = _output.replace(')', ' ')
                _output = _output.replace('nil', ' ')
                _output = self._output_prompt_re.sub(' ', _output)
                _match_list = _output.split()
                if(len(_match.groups()) == 3):
                    # when there is part of an attr.
                    _token = _match.group(3)
                    if(_token != ''):
                        _match_list = [_match for _match in _match_list if
                                       _match.startswith(_token)]

        return((_match_list, _token))

    def get_info(self, token):
        """
        Returns info on the requested object

        # TODO: get info on variables also
        """
        # Make sure that only valid function/variable names are used
        if token.rstrip() != '':
            token = re.match(r'(\S+?)\s*$', token).group(1)
        _cmd = 'help(%s)' % token
        self.run_raw(_cmd)
        _info = ''
        #if self._shell.before != 'nil':
        #    _info = self._shell.before
        if self._output != 'nil':
            _info = self._output
        return (self._pretty_introspection(_info, token))

    def interrupt(self):
        """
        Send an interrupt to the virtuoso shell
        """
        #self._shell.sendintr()
        #TODO: finish this
        pass

    def wait_ready(self, raw_mode=False):
        """
        Find the prompt after the shell output.
        """
        #if(raw_mode):
        #    self._shell.expect_list(self.prompt, searchwindowsize=64)
        #    self._output = self._shell.before
        #    return

        #self._shell.sendline('println("__jupyter_kernel_ready__")')
        #self._output = ''
        #_exp_list = [pexpect.TIMEOUT]
        #_exp_list.extend(self.prompt)
        #self._shell.expect_list(_exp_list, searchwindowsize=64)
        #while(self._shell_available_re.search(self._shell.before) is None):
        #    self._output += (self._shell.before + '\r\n')
        #    sleep(0.1)
        #    self._shell.expect_list(_exp_list, searchwindowsize=64)
        #self._output += self._shell_available_re.sub('', self._shell.before)
        self._output = self._shell.read()

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
        #while(self._shell.after != pexpect.TIMEOUT):
        #    self._shell.expect_list([self.prompt[0],
        #                             self.prompt[1],
        #                             pexpect.TIMEOUT],
        #                            searchwindowsize=64, timeout=1)
        #self._shell.write('')
        #self._shell.expect_list([self.prompt[0],
        #                         self.prompt[1],
        #                         pexpect.TIMEOUT],
        #                        searchwindowsize=64, timeout=1)
        #if(self._shell.after == pexpect.TIMEOUT):
        #    # The shell is probably hung, interrupt
        #    self._shell.sendcontrol('c')
        #    self._shell.write('')
        #    self._shell.expect_list(self.prompt, searchwindowsize=64,
        #                            timeout=5)
        #self._output = self._shell.before
        #TODO: Delete this function
        print("flush() is no longer needed")
