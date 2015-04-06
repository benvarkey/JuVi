"""
Virtuoso kernel for Jupyter.

Inspired by https://github.com/takluyver/bash_kernel
"""
from IPython.kernel.zmq.kernelbase import Kernel
from IPython.display import HTML, Image
from IPython.kernel import (
    get_connection_file, get_connection_info, connect_qtconsole
)
from .shell import VirtuosoShell, VirtuosoExceptions
from pexpect import EOF
import colorama
import re
import time
import os

__version__ = '0.1'


class VirtuosoKernel(Kernel):
    """
    Kernel to connect virtuoso to Jupyter front-end
    """
    implementation = 'virtuoso_kernel'
    implementation_version = __version__
    language = 'SKILL'

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
                'version': self.language_version,
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

    _err_header = HTML('<span style="color:red; font-family:monospace">'
                       'Traceback:</span>')

    def __init__(self, **kwargs):
        super(VirtuosoKernel, self).__init__(**kwargs)
        self._start_virtuoso()
        colorama.init()
        self._plot_re = re.compile(r'[^\w]?\w*?[pP]lot\w*\(')
        self._cell_magic_re = re.compile(r'^%+(\S+)')
        self._plt_width = 8.0
        self._plt_height = 5.0
        self._plt_resolution = 96
        self._plt_file_name = None

        # Start a new window to handle plots
        self._shell.run_raw("__win_id__ = awvCreatePlotWindow()")
        self._shell.flush()

    def _start_virtuoso(self):
        """
        Start the virtuoso shell
        """
        self._shell = VirtuosoShell()

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        """
        Execute the *code* block sent by the front-end.
        """
        if code.strip() == '':
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

        shell = self._shell
        output = None
        interrupted = False
        exec_error = None

        # Check for cell magic and handle magic
        _magic_match = self._cell_magic_re.search(code)
        if(_magic_match is not None):
            _exec_status, _exec_message = self._handle_magics(
                _magic_match.group(1), code)

            if _exec_status is True:
                return {'status': 'ok',
                        'execution_count': self.execution_count,
                        'payload': [],
                        'user_expressions': {}}
            else:
                return {'status': 'error',
                        'execution_count': self.execution_count,
                        'ename': str('CellMagicError'),
                        'evalue': str(1),
                        'traceback': _exec_message['traceback']}

        # Handle plots separately to display inline.
        # If there is a 'plot(...)' command in the code,
        # ask the shell to save a .png  hardcopy at the end
        # and display the image inline.
        _plot_match = self._plot_re.search(code)

        # If there is a plot request, clear the plot window first.
        if(_plot_match is not None):
            self._shell.run_raw("clearAll()")

        try:
            output = shell.run_cell(code)
        except KeyboardInterrupt:
            shell.interrupt()
            interrupted = True
            shell.wait_ready()
            output = shell.output
        except EOF:
            output = shell.output + '\r\nRestarting Virtuoso'
            self._start_virtuoso()
        except VirtuosoExceptions as vexcp:
            exec_error = vexcp.value
            output = shell.output

        if(_plot_match is not None):
            # Ask the shell to save a hardcopy
            self._plt_file_name = '/tmp/jupyter_virtuoso_%s.png' % \
                                  str(time.time())
            _plt_cmd = ('saveGraphImage(?window __win_id__ ?fileName "%s" '
                        '?width %f ?height %f ?units "inch" '
                        '?resolution %d ?resolutionUnits "pixels/in" '
                        '?saveEachSubwindowSeparately nil)') %\
                       (self._plt_file_name, self._plt_width, self._plt_height,
                        self._plt_resolution)
            self._shell.run_raw(_plt_cmd)

            if(os.path.isfile(self._plt_file_name)):
                # Display this image inline
                _image = Image(filename=self._plt_file_name)
                display_content = {'source': "kernel",
                                   'data': {'image/png':
                                            _image.data.encode('base64')},
                                   'metadata': {}}
                self.send_response(self.iopub_socket, 'display_data',
                                   display_content)

                # Delete the hardcopy
                os.remove(self._plt_file_name)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        if (not silent) and (output != ''):
            execute_content = {'execution_count': self.execution_count,
                               'data': {'text/plain': output},
                               'metadata': {}}
            self.send_response(self.iopub_socket, 'execute_result',
                               execute_content)

        if exec_error is not None:
            html_content = {'source': 'kernel', 'data': {'text/html':
                                                         self._err_header.data,
                                                         'text/plain':
                                                         (colorama.Fore.RED +
                                                          'Traceback:' +
                                                          colorama.Fore.RESET)
                                                         },
                            'metadata': {}}
            self.send_response(self.iopub_socket, 'display_data', html_content)

            # TODO: Need to get a proper traceback like in ultraTB
            # tb_content = ["", 0, "", exec_error[2]]
            tb_content = [exec_error[2]]
            err_content = {'execution_count': self.execution_count,
                           'ename': str(exec_error[0]),
                           'evalue': str(exec_error[1]),
                           'traceback': tb_content}
            self.send_response(self.iopub_socket, 'error', err_content)

            return {'status': 'error',
                    'execution_count': self.execution_count,
                    'ename': str(exec_error[0]),
                    'evalue': str(exec_error[1]),
                    'traceback': tb_content}
        else:
            return {'status': 'ok',
                    'execution_count': self.execution_count,
                    'payload': [],
                    'user_expressions': {}}

    def do_complete(self, code, cursor_pos):
        code = code[:cursor_pos]
        default = {'matches': [],
                   'cursor_start': 0,
                   'cursor_end': cursor_pos,
                   'metadata': dict(),
                   'status': 'ok'}

        if not code or code[-1] == ' ':
            return default

        _lines = code.splitlines(True)
        if not _lines:
            return default

        _matches, _token = self._shell.get_matches(_lines[-1])
        # when completing methods/attributes, _token is ''
        _cstart = cursor_pos - len(_token)

        if len(_matches) == 0:
            return default

        start = cursor_pos - len(_token)
        return {'matches': _matches,
                'cursor_start': _cstart,
                'cursor_end': cursor_pos,
                'metadata': dict(),
                'status': 'ok'}

    def _html_introspection(self, info, keyword):
        import re
        info = re.sub(r'(\?\w+)', r'<i>\1</i>', info, count=0)
        info = re.sub(r'(%s)' % keyword, r'<b>\1</b>', info, count=0)
        return HTML(info)

    def do_inspect(self, code, cursor_pos, detail_level=0):
        """
        Object introspection
        """
        code = code[:cursor_pos]
        default = {'status': 'ok',
                   'data': {},
                   'metadata': dict(),
                   'found': False}

        if not code or code[-1] == ' ':
            return default

        _tokens = code.split()
        if not _tokens:
            return default

        _token = _tokens[-1]
        _info = self._shell.get_info(_token)

        if len(_info) == 0:
            return default

        # 'text/html': HTML().data
        # _html_info = self._html_introspection(_info, _token)
        # _tt_info = self._pretty_introspection(_info, _token)
        # return {'status': 'ok',
        #         'data': {'text/html': _html_info.data,
        #                  'text/plain': _tt_info},
        #         'metadata': dict(),
        #         'found': True}
        return {'status': 'ok',
                'data': {'text/plain': _info},
                'metadata': dict(),
                'found': True}

    def do_shutdown(self, restart):
        """
        Shutdown the shell
        """
        self._shell.shutdown(restart)
        return {'restart': restart}

    def _handle_magics(self, magic_code, code):
        """
        Handle cell magics
        """
        _exec_status = False
        _content = None
        err_content = None
        if(magic_code == 'connect_info'):
            try:
                connection_file = get_connection_file()
                _content = get_connection_info(unpack=False)
            except Exception as e:
                error("Could not get connection info: %r" % e)
                return

        if(magic_code == 'history'):
            _args = re.search(r'^%(\S+)(?:\s*)(\d*)', code)
            self._shell.run_raw('history(' + _args.group(2) + ')')
            _content = self._shell.output[:-1]

        if(magic_code == 'help'):
            _args = re.search(r'^%(\S+)(?:\s*)(\S*)', code)
            _content = self._shell.get_info(_args.group(2))

        if(magic_code == 'image'):
            _args = re.search(r'^%(\S+)(?:\s*)(\S*)', code)
            return self._show_image_inline(_args.group(2))

        if(magic_code == 'flush'):
            self._shell.flush()
            _content = ''

        if(_content is not None):
            execute_content = {'execution_count': self.execution_count,
                               'data': {'text/plain': _content},
                               'metadata': {}}
            self.send_response(self.iopub_socket, 'execute_result',
                               execute_content)
            _exec_status = True
        else:
            err_content = {'execution_count': self.execution_count,
                           'ename': str('CellMagicError'),
                           'evalue': str(1),
                           'traceback': ['Invalid cell magic']}
            self.send_response(self.iopub_socket, 'error', err_content)

        return _exec_status, err_content

    def _show_image_inline(self, filename):
        _exec_status = False
        err_content = None
        if(os.path.isfile(filename)):
            # Display this image inline
            _image = Image(filename=filename)
            display_content = {'source': "kernel",
                               'data': {'image/png':
                                        _image.data.encode('base64')},
                               'metadata': {}}
            self.send_response(self.iopub_socket, 'display_data',
                               display_content)
            _exec_status = True
        else:
            err_content = {'execution_count': self.execution_count,
                           'ename': str('CellMagicError'),
                           'evalue': str(2),
                           'traceback': ['Image not found']}
            self.send_response(self.iopub_socket, 'error', err_content)
        return _exec_status, err_content
