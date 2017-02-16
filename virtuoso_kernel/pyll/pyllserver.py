#!/opt/anaconda/bin/python
#HACK: the above shebang will get rewritten with new install
#!/usr/bin/env python
from jupyter_core.paths import jupyter_data_dir
import zmq
import json
import re
import sys
import os

################################################################################
# This python server should be started from virtuoso (dfII) via IPC
#
# WARNING: This server application is completely insecure. Use at your own risk.
################################################################################

# Order of operation
# 1. Listen on zmq socket PYLL_ZMQ_SOCKET
# 2. Forward client commands on standard STDOUT (which is picked up by virtuoso)
# 3. Read STDIN (where virtuoso puts out results)
# 4. Forward virtuoso results on PYLL_ZMQ_SOCKET

# Since the server doesn't evaluate anything intended for virtuoso, it doesn't
# send anything on STDERR

# Protocol between server and virtuoso:
#    - Send commands to virtuoso as a string
#    - virtuoso evaluates the string
#    - virtuoso returns JSON payload
#       - There are four fields: "error", "warning", "info" and "result"
#    - Stream is terminated with a "PYLL_EOS" string on a newline

context = zmq.Context()
socket = context.socket(zmq.REP)
port = socket.bind_to_random_port("tcp://*", min_port=30000, max_port=40000, max_tries=100)
#sys.stdout.write("Server listening on port %d" % port)
#sys.stdout.flush()

# Connection information for Jupyter client
CONN_FILE = jupyter_data_dir() + "/runtime/" + "virtuoso-pyll.json"
with open(CONN_FILE, "w") as COF:
    json.dump(['localhost', port], COF)
exit_re = re.compile(r'{*exit\(\)}*')
exit_payload = ('{"error": null,\n "warning": null,\n "info": "Exiting kernel",'
                '\n "result": "t"}')

__conn_active__ = False;

def __read_ciw__():
    # Read results from virtuoso and recreate the JSON payload
    _read = True
    _result = []
    while _read:
        # Read virtuoso's JSON payload line-by-line
        _line = sys.stdin.readline().strip()
        # Terminate read on "PYLL_EOS"
        if _line == "PYLL_EOS":
            _read = False
        else:
            _result.append(_line)
    return "\n".join(_result)

while True:
    # Wait for client data
    message = socket.recv().decode()
    if __conn_active__ is False:
        sys.stdout.write('<PYLL_STATUS|printf("New client connected to the PyLLServer\n")|PYLL_STATUS>')
        sys.stdout.flush()
        __read_ciw__()
        __conn_active__ = True


    # Exit server if requested by client
    if exit_re.search(message):
        socket.send_string(exit_payload)
        # Defer exit to an explicit 'PyLLStopServer()' SKILL procedure
        # # Delete the connection JSON file
        # os.remove(CONN_FILE)
        # exit(0)  # Normal exit

        sys.stdout.write('<PYLL_STATUS|printf("Client disconnected from the PyLLServer\n")|PYLL_STATUS>')
        sys.stdout.flush()
        __read_ciw__()
        __conn_active__ = False
        continue

    # Send the command string to virtuoso
    sys.stdout.write(message)
    sys.stdout.flush()
    json_payload = __read_ciw__()
    socket.send_string(json_payload)
