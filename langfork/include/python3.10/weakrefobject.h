/* Weak references objects for Python. */

#ifndef Py_WEAKREFOBJECT_H
#define Py_WEAKREFOBJECT_H
#ifdef __cplusplus
extern "C" {
#endif


typedef struct _PyWeakReference PyWeakReference;

/* PyWeakReference is the base struct for the Python ReferenceType, ProxyType,
 * and CallableProxyType.
 */
#ifndef Py_LIMITED_API
struct _PyWeakReference {
    PyObject_HEAD

    /* The object to which this is a weak reference, or Py_None if none.
     * Note that this is a stealth reference:  wr_object's refcount is
     * not incremented to reflect this pointer.
     */
    PyObject *wr_object;

    /* A callable to invoke when wr_object dies, or NULL if none. */
    PyObject *wr_callback;

    /* A cache for wr_object's hash code.  As usual for hashes, this is -1
     * if the hash code isn't known yet.
     */
    Py_hash_t hash;

    /* If wr_object is weakly referenced, wr_object has a doubly-linked NULL-
     * terminated list of weak references to it.  These are the list pointers.
     * If wr_object goes away, wr_object is set to Py_None, and these pointers
     * have no meaning then.
     */
    PyWeakReference *wr_prev;
    PyWeakReference *wr_next;
};
#endif

PyAPI_DATA(PyTypeObject) _PyWeakref_RefType;
PyAPI_DATA(PyTypeObject) _PyWeakref_ProxyType;
PyAPI_DATA(PyTypeObject) _PyWeakref_CallableProxyType;

#define PyWeakref_CheckRef(op) PyObject_TypeCheck(op, &_PyWeakref_RefType)
#define PyWeakref_CheckRefExact(op) \
        Py_IS_TYPE(op, &_PyWeakref_RefType)
#define PyWeakref_CheckProxy(op) \
        (Py_IS_TYPE(op, &_PyWeakref_ProxyType) || \
         Py_IS_TYPE(op, &_PyWeakref_CallableProxyType))

#define PyWeakref_Check(op) \
        (PyWeakref_CheckRef(op) || PyWeakref_CheckProxy(op))


PyAPI_FUNC(PyObject *) PyWeakref_NewRef(PyObject *ob,
                                              PyObject *callback);
PyAPI_FUNC(PyObject *) PyWeakref_NewProxy(PyObject *ob,
                                                PyObject *callback);
PyAPI_FUNC(PyObject *) PyWeakref_GetObject(PyObject *ref);

#ifndef Py_LIMITED_API
PyAPI_FUNC(Py_ssize_t) _PyWeakref_GetWeakrefCount(PyWeakReference *head);

PyAPI_FUNC(void) _PyWeakref_ClearRef(PyWeakReference *self);
#endif

/* Explanation for the Py_REFCNT() check: when a weakref's target is part
   of a long chain of deallocations which triggers the trashcan mechanism,
   clearing the weakrefs can be delayed long after the target's refcount
   has dropped to zero.  In the meantime, code accessing the weakref will
   be able to "see" the target object even though it is supposed to be
   unreachable.  See issue #16602. */

#define PyWeakref_GET_OBJECT(ref)                           \
    (Py_REFCNT(((PyWeakReference *)(ref))->wr_object) > 0   \
     ? ((PyWeakReference *)(ref))->wr_object                \
     : Py_None)


#ifdef __cplusplus
}
#endif
#endif /* !Py_WEAKREFOBJECT_H */
