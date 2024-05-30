#ifndef Py_INTERNAL_LIFECYCLE_H
#define Py_INTERNAL_LIFECYCLE_H
#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_BUILD_CORE
#  error "this header requires Py_BUILD_CORE define"
#endif

#ifdef HAVE_SIGNAL_H
#include <signal.h>
#endif

#include "pycore_runtime.h"       // _PyRuntimeState

#ifndef NSIG
# if defined(_NSIG)
#  define NSIG _NSIG            /* For BSD/SysV */
# elif defined(_SIGMAX)
#  define NSIG (_SIGMAX + 1)    /* For QNX */
# elif defined(SIGMAX)
#  define NSIG (SIGMAX + 1)     /* For djgpp */
# else
#  define NSIG 64               /* Use a reasonable default value */
# endif
#endif

/* Forward declarations */
struct _PyArgv;
struct pyruntimestate;

/* True if the main interpreter thread exited due to an unhandled
 * KeyboardInterrupt exception, suggesting the user pressed ^C. */
PyAPI_DATA(int) _Py_UnhandledKeyboardInterrupt;

extern int _Py_SetFileSystemEncoding(
    const char *encoding,
    const char *errors);
extern void _Py_ClearFileSystemEncoding(void);
extern PyStatus _PyUnicode_InitEncodings(PyThreadState *tstate);
#ifdef MS_WINDOWS
extern int _PyUnicode_EnableLegacyWindowsFSEncoding(void);
#endif

PyAPI_FUNC(void) _Py_ClearStandardStreamEncoding(void);

PyAPI_FUNC(int) _Py_IsLocaleCoercionTarget(const char *ctype_loc);

/* Various one-time initializers */

extern PyStatus _PyUnicode_Init(PyInterpreterState *interp);
extern PyStatus _PyUnicode_InitTypes(void);
extern PyStatus _PyBytes_Init(PyInterpreterState *interp);
extern int _PyStructSequence_Init(void);
extern int _PyLong_Init(PyInterpreterState *interp);
extern int _PyLong_InitTypes(void);
extern PyStatus _PyTuple_Init(PyInterpreterState *interp);
extern PyStatus _PyFaulthandler_Init(int enable);
extern int _PyTraceMalloc_Init(int enable);
extern PyObject * _PyBuiltin_Init(PyInterpreterState *interp);
extern PyStatus _PySys_Create(
    PyThreadState *tstate,
    PyObject **sysmod_p);
extern PyStatus _PySys_ReadPreinitWarnOptions(PyWideStringList *options);
extern PyStatus _PySys_ReadPreinitXOptions(PyConfig *config);
extern int _PySys_UpdateConfig(PyThreadState *tstate);
extern PyStatus _PyExc_Init(PyInterpreterState *interp);
extern PyStatus _PyErr_InitTypes(void);
extern PyStatus _PyBuiltins_AddExceptions(PyObject * bltinmod);
extern void _PyFloat_Init(void);
extern int _PyFloat_InitTypes(void);
extern PyStatus _Py_HashRandomization_Init(const PyConfig *);

extern PyStatus _PyTypes_Init(void);
extern PyStatus _PyTypes_InitSlotDefs(void);
extern PyStatus _PyImportZip_Init(PyThreadState *tstate);
extern PyStatus _PyGC_Init(PyInterpreterState *interp);
extern PyStatus _PyAtExit_Init(PyInterpreterState *interp);


/* Various internal finalizers */

extern void _PyFrame_Fini(PyInterpreterState *interp);
extern void _PyDict_Fini(PyInterpreterState *interp);
extern void _PyTuple_Fini(PyInterpreterState *interp);
extern void _PyList_Fini(PyInterpreterState *interp);
extern void _PyBytes_Fini(PyInterpreterState *interp);
extern void _PyFloat_Fini(PyInterpreterState *interp);
extern void _PySlice_Fini(PyInterpreterState *interp);
extern void _PyAsyncGen_Fini(PyInterpreterState *interp);

extern int _PySignal_Init(int install_signal_handlers);
extern void _PySignal_Fini(void);

extern void _PyExc_Fini(PyInterpreterState *interp);
extern void _PyImport_Fini(void);
extern void _PyImport_Fini2(void);
extern void _PyGC_Fini(PyInterpreterState *interp);
extern void _PyType_Fini(PyInterpreterState *interp);
extern void _Py_HashRandomization_Fini(void);
extern void _PyUnicode_Fini(PyInterpreterState *interp);
extern void _PyUnicode_ClearInterned(PyInterpreterState *interp);
extern void _PyLong_Fini(PyInterpreterState *interp);
extern void _PyFaulthandler_Fini(void);
extern void _PyHash_Fini(void);
extern void _PyTraceMalloc_Fini(void);
extern void _PyWarnings_Fini(PyInterpreterState *interp);
extern void _PyAST_Fini(PyInterpreterState *interp);
extern void _PyAtExit_Fini(PyInterpreterState *interp);

extern PyStatus _PyGILState_Init(_PyRuntimeState *runtime);
extern PyStatus _PyGILState_SetTstate(PyThreadState *tstate);
extern void _PyGILState_Fini(PyInterpreterState *interp);

PyAPI_FUNC(void) _PyGC_DumpShutdownStats(PyInterpreterState *interp);

PyAPI_FUNC(PyStatus) _Py_PreInitializeFromPyArgv(
    const PyPreConfig *src_config,
    const struct _PyArgv *args);
PyAPI_FUNC(PyStatus) _Py_PreInitializeFromConfig(
    const PyConfig *config,
    const struct _PyArgv *args);


PyAPI_FUNC(int) _Py_HandleSystemExit(int *exitcode_p);

PyAPI_FUNC(PyObject*) _PyErr_WriteUnraisableDefaultHook(PyObject *unraisable);

PyAPI_FUNC(void) _PyErr_Print(PyThreadState *tstate);
PyAPI_FUNC(void) _PyErr_Display(PyObject *file, PyObject *exception,
                                PyObject *value, PyObject *tb);

PyAPI_FUNC(void) _PyThreadState_DeleteCurrent(PyThreadState *tstate);

extern void _PyAtExit_Call(PyInterpreterState *interp);

#ifdef __cplusplus
}
#endif
#endif /* !Py_INTERNAL_LIFECYCLE_H */
