#ifndef Py_CPYTHON_TRACEBACK_H
#  error "this header file must not be included directly"
#endif

typedef struct _traceback {
    PyObject_HEAD
    struct _traceback *tb_next;
    PyFrameObject *tb_frame;
    int tb_lasti;
    int tb_lineno;
} PyTracebackObject;

PyAPI_FUNC(int) _Py_DisplaySourceLine(PyObject *, PyObject *, int, int);
PyAPI_FUNC(void) _PyTraceback_Add(const char *, const char *, int);
