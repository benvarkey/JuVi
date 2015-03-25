"""
Virtuoso kernel for Jupyter. 

Heavily borrowed from : https://github.com/takluyver/bash_kernel
"""
from IPython.kernel.zmq.kernelbase import Kernel
from IPython.display import HTML
import pexpect
from pexpect import replwrap, EOF

from subprocess import check_output

import re
import signal

__version__ = '0.1'

VERSION_PAT = re.compile(r'version (\d+(\.\d+)+)')
ERROR_TAGS = ['<p style="color:red;"><b>', '</b></p>']

from .images import (
    extract_image_filenames, display_data_for_image, image_setup_cmd
)


class VirtuosoKernel(Kernel):
    implementation = 'virtuoso_kernel'
    implementation_version = __version__

    @property
    def language_version(self):
        _match_ = VERSION_PAT.search(self.banner)
        return _match_.group(1)

    _banner = None

    @property
    def banner(self):
        if self._banner is None:
            self._banner = check_output(['/bin/tcsh', '-c "virtuoso -V"']).decode('utf-8')
        return self._banner

    language_info = {'name': 'SKILL',
                     'codemirror_mode': 'scheme',
                     'mimetype': 'text/x-script.scheme',
                     'file_extension': '.il'}

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self._start_virtuoso()
        self.re_error_prg = re.compile('\*Error\*')

    def _start_virtuoso(self):
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that virtuoso and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            # Lookup 'setPrompts' for setting SKILL prompt.
            self.virtuoso_child = pexpect.spawn('tcsh -c "virtuoso -nograph"', echo=False)
            self.virtuosowrapper = replwrap.REPLWrapper(self.virtuoso_child, '\r\n> ', None)
        finally:
            signal.signal(signal.SIGINT, sig)

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

        interrupted = False
        ## Preprocess the code to make a list of single-line instructions,
        ## because, I want the output from each line to be shown
        ## and also because, the Ocean shell expects one command per line
        ##code_lines = [line for line in code.splitlines() if line.strip() != '']
        ##code_processed = '\r\n'.join(code_lines)

        code_processed = '{\r\n' + code + '\r\n}'
        #code_processed = code
        try:
            #output_list = [self.virtuosowrapper.run_command(_cline.rstrip(), timeout=None) for _cline in code_lines]
            #output = '\r\n'.join(output_list)
            self.virtuosowrapper.child.sendline(code_processed)
            self.virtuosowrapper.child.expect('\r\n> $')
            output = self.virtuosowrapper.child.before
        except KeyboardInterrupt:
            self.virtuosowrapper.child.sendintr()
            interrupted = True
            self.virtuosowrapper._expect_prompt()
            output = self.virtuosowrapper.child.before
        except EOF:
            output = self.virtuosowrapper.child.before + 'Restarting Virtuoso'
            self._start_virtuoso()

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        exitcode = 0
        exitmsg = ''
        try:
            _mres = self.re_error_prg.search(output)
            if _mres is not None:
                exitcode = 2
                exitmsg = 'Error'

        except Exception:
            exitcode = 1
            exitmsg = 'Unknown Exception'

        if not silent:
            image_filenames, output = extract_image_filenames(output)

            # Send images, if any
            for filename in image_filenames:
                try:
                    data = display_data_for_image(filename)
                except ValueError as e:
                    message = {'name': 'stdout', 'text': str(e)}
                    self.send_response(self.iopub_socket, 'stream', message)
                else:
                    self.send_response(self.iopub_socket, 'display_data', data)
        if exitcode:
            # Send formatted output
            _out = HTML(ERROR_TAGS[0] + 'Traceback:' + ERROR_TAGS[1])
            err_content = {
                    'source' : 'kernel',
                    'data' : {
                        'text/html' : _out.data,
                        'text/plain' : 'Traceback:'
                        },
                    'metadata' : {}}
            self.send_response(self.iopub_socket, 'display_data', err_content)
            err_content = {
                    'ename': str(exitmsg), 
                    'evalue': str(exitcode), 
                    'traceback': [output]
                    }
            self.send_response(self.iopub_socket, 'error', err_content)

            return {'status': 'error', 'execution_count': self.execution_count,
                    'ename': str(exitmsg), 'evalue': str(exitcode), 'traceback': []}
        else:
            # Send standard output
            #stream_content = {'name': 'stdout', 'text': output}
            #self.send_response(self.iopub_socket, 'stream', stream_content)

            # Use execution results
            execute_content = {
                    'execution_count' : self.execution_count,
                    'data' : {'text/plain' : output},
                    'metadata' : {}
                    }
            self.send_response(self.iopub_socket, 'execute_result', execute_content)

            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

    def do_complete(self, code, cursor_pos):
        code = code[:cursor_pos]
        default = {'matches': [], 'cursor_start': 0,
                   'cursor_end': cursor_pos, 'metadata': dict(),
                   'status': 'ok'}

        if not code or code[-1] == ' ':
            return default

        tokens = code.replace(';', ' ').split()
        if not tokens:
            return default

        token = tokens[-1]
        start = cursor_pos - len(token)
        cmd = 'listFunctions("^%s")' % token
        output = self.virtuosowrapper.run_command(cmd).rstrip()
        matches = output.split()

        cmd = 'listVariables("^%s")' % token
        output = self.virtuosowrapper.run_command(cmd).rstrip()
        matches.extend(output.split())

        if not matches:
            return default
        matches = [m for m in matches if m.startswith(token)]

        return {'matches': matches, 'cursor_start': start,
                'cursor_end': cursor_pos, 'metadata': dict(),
                'status': 'ok'}

    def do_shutdown(self, restart):
        try:
            self.virtuosowrapper.run_command('exit').rstrip()
        except EOF:
            self.virtuosowrapper.child.close()
        return {'restart' : False}
