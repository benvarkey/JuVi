/* server.il

Adapted from A. D. Beckett's example code from Cadence support

Refer to 'server.py' for protocol
*/

procedure(PyLLServerListener(ipcID data)

let((result (err_payload nil) warn_payload stdout_payload)
    rexCompile("<PYLL_STATUS|\\(.*\\)|PYLL_STATUS>")
    if(rexExecute(data)
    then
    {
        evalstring(rexSubstitute("\\1"))
        drain(poport)
    }
    else
        let(((poport outstring()))
        unless(errset({result=evalstring(data) warn_payload=getWarn() result})
            sprintf(err_payload "%L" car(nth(4 errset.errset)))
        );unless

        if(type(result) != 'string sprintf(result "%L" result))
        if(warn_payload == nil warn_payload = "null" sprintf(warn_payload "%L" warn_payload))
        when(err_payload == nil err_payload = "null")
        if((stdout_payload = getOutstring(poport)) == "" stdout_payload = "null" 
            sprintf(stdout_payload "%L" stdout_payload))

        ipcWriteProcess(ipcID "{\n")
        ipcWriteProcess(ipcID "\"error\": ")
        ipcWriteProcess(ipcID err_payload)
        ipcWriteProcess(ipcID ",\n\"warning\": ")
        ipcWriteProcess(ipcID warn_payload)
        ipcWriteProcess(ipcID ",\n\"info\": ")
        ipcWriteProcess(ipcID stdout_payload)
        ipcWriteProcess(ipcID ",\n\"result\": ")
        ipcWriteProcess(ipcID sprintf(nil "%L" result))
        ipcWriteProcess(ipcID "\n}")

        );let
    );if
    ; Terminate transmission with "PYLL_EOS"
    ipcWriteProcess(ipcID sprintf(nil "\nPYLL_EOS\n"))
);let
);

procedure(PyLLServerTermHandler(ipcID exitStatus)
    if(exitStatus == 0
        printf("Python server exited normally\n")
        printf("Python server exited with code %L\n" exitStatus)
    )
    __pyll_process__ = nil
);procedure

procedure(PyLLStartServer()
    if(__pyll_process__ == nil
    then
        printf("Starting PyLL Server from path '%s'\n" __pyll_path__)
        __pyll_process__ = ipcBeginProcess(strcat(__pyll_path__ "/pyllserver.py") "" 'PyLLServerListener nil 'PyLLServerTermHandler)
    else
        printf("PyLLServer (%L) is already active\n" __pyll_process__)
    );if
        

);procedure

procedure(PyLLStopServer()
    if(__pyll_process__ == nil
    then
        printf("PyLL Server is not active\n")
    else
        ipcKillProcess(__pyll_process__)
    );
);procedure

__pyll_path__ = strcat("/" buildString(reverse(cdr(reverse(parseString(simplifyFilename(which(get_filename(piport))) "/")))) "/"))
__pyll_process__ = nil
;PyLLStartServer()
