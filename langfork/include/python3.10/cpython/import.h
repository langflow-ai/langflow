#ifndef Py_CPYTHON_IMPORT_H
#  error "this header file must not be included directly"
#endif

PyMODINIT_FUNC PyInit__imp(void);

PyAPI_FUNC(int) _PyImport_IsInitialized(PyInterpreterState *);

PyAPI_FUNC(PyObject *) _PyImport_GetModuleId(struct _Py_Identifier *name);
PyAPI_FUNC(int) _PyImport_SetModule(PyObject *name, PyObject *module);
PyAPI_FUNC(int) _PyImport_SetModuleString(const char *name, PyObject* module);

PyAPI_FUNC(void) _PyImport_AcquireLock(void);
PyAPI_FUNC(int) _PyImport_ReleaseLock(void);

/* Obsolete since 3.5, will be removed in 3.11. */
Py_DEPRECATED(3.10) PyAPI_FUNC(PyObject *) _PyImport_FindExtensionObject(PyObject *, PyObject *);

PyAPI_FUNC(int) _PyImport_FixupBuiltin(
    PyObject *mod,
    const char *name,            /* UTF-8 encoded string */
    PyObject *modules
    );
PyAPI_FUNC(int) _PyImport_FixupExtensionObject(PyObject*, PyObject *,
                                               PyObject *, PyObject *);

struct _inittab {
    const char *name;           /* ASCII encoded string */
    PyObject* (*initfunc)(void);
};
PyAPI_DATA(struct _inittab *) PyImport_Inittab;
PyAPI_FUNC(int) PyImport_ExtendInittab(struct _inittab *newtab);

struct _frozen {
    const char *name;                 /* ASCII encoded string */
    const unsigned char *code;
    int size;
};

/* Embedding apps may change this pointer to point to their favorite
   collection of frozen modules: */

PyAPI_DATA(const struct _frozen *) PyImport_FrozenModules;

PyAPI_DATA(PyObject *) _PyImport_GetModuleAttr(PyObject *, PyObject *);
PyAPI_DATA(PyObject *) _PyImport_GetModuleAttrString(const char *, const char *);
