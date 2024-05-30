#ifndef Py_CPYTHON_SYSMODULE_H
#  error "this header file must not be included directly"
#endif

PyAPI_FUNC(PyObject *) _PySys_GetObjectId(_Py_Identifier *key);
PyAPI_FUNC(int) _PySys_SetObjectId(_Py_Identifier *key, PyObject *);

PyAPI_FUNC(size_t) _PySys_GetSizeOf(PyObject *);

typedef int(*Py_AuditHookFunction)(const char *, PyObject *, void *);

PyAPI_FUNC(int) PySys_Audit(
    const char *event,
    const char *argFormat,
    ...);
PyAPI_FUNC(int) PySys_AddAuditHook(Py_AuditHookFunction, void*);
