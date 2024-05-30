
/* simple namespace object interface */

#ifndef NAMESPACEOBJECT_H
#define NAMESPACEOBJECT_H
#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_LIMITED_API
PyAPI_DATA(PyTypeObject) _PyNamespace_Type;

PyAPI_FUNC(PyObject *) _PyNamespace_New(PyObject *kwds);
#endif /* !Py_LIMITED_API */

#ifdef __cplusplus
}
#endif
#endif /* !NAMESPACEOBJECT_H */
