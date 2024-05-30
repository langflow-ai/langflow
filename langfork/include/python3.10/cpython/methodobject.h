#ifndef Py_CPYTHON_METHODOBJECT_H
#  error "this header file must not be included directly"
#endif

PyAPI_DATA(PyTypeObject) PyCMethod_Type;

#define PyCMethod_CheckExact(op) Py_IS_TYPE(op, &PyCMethod_Type)
#define PyCMethod_Check(op) PyObject_TypeCheck(op, &PyCMethod_Type)

/* Macros for direct access to these values. Type checks are *not*
   done, so use with care. */
#define PyCFunction_GET_FUNCTION(func) \
        (((PyCFunctionObject *)func) -> m_ml -> ml_meth)
#define PyCFunction_GET_SELF(func) \
        (((PyCFunctionObject *)func) -> m_ml -> ml_flags & METH_STATIC ? \
         NULL : ((PyCFunctionObject *)func) -> m_self)
#define PyCFunction_GET_FLAGS(func) \
        (((PyCFunctionObject *)func) -> m_ml -> ml_flags)
#define PyCFunction_GET_CLASS(func) \
    (((PyCFunctionObject *)func) -> m_ml -> ml_flags & METH_METHOD ? \
         ((PyCMethodObject *)func) -> mm_class : NULL)

typedef struct {
    PyObject_HEAD
    PyMethodDef *m_ml; /* Description of the C function to call */
    PyObject    *m_self; /* Passed as 'self' arg to the C func, can be NULL */
    PyObject    *m_module; /* The __module__ attribute, can be anything */
    PyObject    *m_weakreflist; /* List of weak references */
    vectorcallfunc vectorcall;
} PyCFunctionObject;

typedef struct {
    PyCFunctionObject func;
    PyTypeObject *mm_class; /* Class that defines this method */
} PyCMethodObject;
