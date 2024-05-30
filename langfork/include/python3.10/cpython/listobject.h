#ifndef Py_CPYTHON_LISTOBJECT_H
#  error "this header file must not be included directly"
#endif

typedef struct {
    PyObject_VAR_HEAD
    /* Vector of pointers to list elements.  list[0] is ob_item[0], etc. */
    PyObject **ob_item;

    /* ob_item contains space for 'allocated' elements.  The number
     * currently in use is ob_size.
     * Invariants:
     *     0 <= ob_size <= allocated
     *     len(list) == ob_size
     *     ob_item == NULL implies ob_size == allocated == 0
     * list.sort() temporarily sets allocated to -1 to detect mutations.
     *
     * Items must normally not be NULL, except during construction when
     * the list is not yet visible outside the function that builds it.
     */
    Py_ssize_t allocated;
} PyListObject;

PyAPI_FUNC(PyObject *) _PyList_Extend(PyListObject *, PyObject *);
PyAPI_FUNC(void) _PyList_DebugMallocStats(FILE *out);

/* Macro, trading safety for speed */

/* Cast argument to PyListObject* type. */
#define _PyList_CAST(op) (assert(PyList_Check(op)), (PyListObject *)(op))

#define PyList_GET_ITEM(op, i) (_PyList_CAST(op)->ob_item[i])
#define PyList_SET_ITEM(op, i, v) ((void)(_PyList_CAST(op)->ob_item[i] = (v)))
#define PyList_GET_SIZE(op)    Py_SIZE(_PyList_CAST(op))
