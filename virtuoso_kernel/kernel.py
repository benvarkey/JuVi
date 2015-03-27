"""
Virtuoso kernel for Jupyter.

Inspired by https://github.com/takluyver/bash_kernel
"""
from IPython.kernel.zmq.kernelbase import Kernel
from IPython.display import HTML
from .shell import VirtuosoShell, VirtuosoExceptions
from pexpect import EOF

__version__ = '0.1'

class VirtuosoKernel(Kernel):
    implementation = 'virtuoso_kernel'
    implementation_version = __version__
    language = 'SKILL'
    _ERROR_TAGS = ('<p style="color:red;"><i>', '</i></p>')

    @property
    def language_version(self):
        """
        Language version
        """
        return self._shell.language_version

    @property
    def language_info(self):
        """
        Language info
        """
        return {'name': 'SKILL',
                'version' : self.language_version,
                'mimetype': 'text/x-scheme',
                'file_extension': 'il',
                'pygments_lexer': 'scheme',
                'codemirror_mode': 'scheme'}

    @property
    def banner(self):
        """
        Shell's banner
        """
        return self._shell.banner


    def __init__(self, **kwargs):
        super(VirtuosoKernel, self).__init__(**kwargs)
        self._shell = None

    def _start_virtuoso(self):
        """
        Start the virtuoso shell
        """
        self._shell = VirtuosoShell()
        self._shell.wait_ready()

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        """
        Execute the *code* block sent by the front-end.
        """
        shell = self._shell
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

        output = None
        interrupted = False
        exec_error = None
        try:
            output = shell.run_cell(code)
        except KeyboardInterrupt:
            shell.interrupt()
            interrupted = True
            shell.wait_ready()
            output = shell.output()
        except EOF:
            output = shell.output() + '\r\nRestarting Virtuoso'
            self._start_virtuoso()
        except VirtuosoExceptions as vexcp:
            exec_error = vexcp.value

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        if not silent:
            if exec_error is not None:
                _out = HTML(self._ERROR_TAGS[0] + 'Traceback:' + self._ERROR_TAGS[1])
                html_content = {'source' : 'kernel', 'data' : {'text/html' :
                                                               _out.data,
                                                               'text/plain' :
                                                               'Traceback:'},
                                'metadata' : {}}
                self.send_response(self.iopub_socket, 'display_data', html_content)

                err_content = {'execution_count': self.execution_count,
                               'ename': str(exec_error[0]),
                               'evalue': str(exec_error[1]),
                               'traceback': [exec_error[2]]}
                self.send_response(self.iopub_socket, 'error', err_content)

                return {'status': 'error',
                        'execution_count': self.execution_count,
                        'ename': str(exec_error[0]),
                        'evalue': str(exec_error[1]),
                        'traceback': [exec_error[2]]}
            else:
                execute_content = {'execution_count' : self.execution_count,
                                   'data' : {'text/plain' : output},
                                   'metadata' : {}}
                self.send_response(self.iopub_socket, 'execute_result', execute_content)

                return {'status': 'ok',
                        'execution_count': self.execution_count,
                        'payload': [],
                        'user_expressions': {}}

    def do_complete(self, code, cursor_pos):
        """
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
        """
        pass

    def do_shutdown(self, restart):
        """
        Shutdown the shell
        """
        self._shell.shutdown(restart)
        return {'restart' : restart}
