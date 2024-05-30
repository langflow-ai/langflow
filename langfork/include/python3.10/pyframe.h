/* Limited C API of PyFrame API
 *
 * Include "frameobject.h" to get the PyFrameObject structure.
 */

#ifndef Py_PYFRAME_H
#define Py_PYFRAME_H
#ifdef __cplusplus
extern "C" {
#endif

typedef struct _frame PyFrameObject;

/* Return the line of code the frame is currently executing. */
PyAPI_FUNC(int) PyFrame_GetLineNumber(PyFrameObject *);

PyAPI_FUNC(PyCodeObject *) PyFrame_GetCode(PyFrameObject *frame);

#ifdef __cplusplus
}
#endif
#endif /* !Py_PYFRAME_H */
