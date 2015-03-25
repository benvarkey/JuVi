from IPython.kernel.zmq.kernelbase import Kernel
import pexpect
from pexpect import replwrap, EOF

from subprocess import check_output

import re
import signal

__version__ = '0.1'

VERSION_PAT = re.compile(r'version (\d+(\.\d+)+)')

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

    def _start_virtuoso(self):
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that virtuoso and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            # Lookup 'setPrompts' for setting SKILL prompt.
            self.virtuoso_child = pexpect.spawn('tcsh -c "virtuoso -nograph"', echo=False)
            self.virtuosowrapper = replwrap.REPLWrapper(self.virtuoso_child, '> ', None)
        finally:
            signal.signal(signal.SIGINT, sig)

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

        interrupted = False
        try:
            output = self.virtuosowrapper.run_command(code.rstrip(), timeout=None)
        except KeyboardInterrupt:
            self.virtuosowrapper.child.sendintr()
            interrupted = True
            self.virtuosowrapper._expect_prompt()
            output = self.virtuosowrapper.child.before
        except EOF:
            output = self.virtuosowrapper.child.before + 'Restarting Virtuoso'
            self._start_virtuoso()

        if not silent:
            image_filenames, output = extract_image_filenames(output)

            # Send standard output
            stream_content = {'name': 'stdout', 'text': output}
            self.send_response(self.iopub_socket, 'stream', stream_content)

            # Send images, if any
            for filename in image_filenames:
                try:
                    data = display_data_for_image(filename)
                except ValueError as e:
                    message = {'name': 'stdout', 'text': str(e)}
                    self.send_response(self.iopub_socket, 'stream', message)
                else:
                    self.send_response(self.iopub_socket, 'display_data', data)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        try:
            #exitcode = int(self.virtuosowrapper.run_command('echo $?').rstrip())
            # Pattern match for error? For now, ignore error messages
            exitcode = 0

        except Exception:
            exitcode = 1

        if exitcode:
            return {'status': 'error', 'execution_count': self.execution_count,
                    'ename': '', 'evalue': str(exitcode), 'traceback': []}
        else:
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


