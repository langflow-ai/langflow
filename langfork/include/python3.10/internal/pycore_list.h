#ifndef Py_INTERNAL_LIST_H
#define Py_INTERNAL_LIST_H
#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_BUILD_CORE
#  error "this header requires Py_BUILD_CORE define"
#endif

#include "listobject.h"           // _PyList_CAST()


#define _PyList_ITEMS(op) (_PyList_CAST(op)->ob_item)


#ifdef __cplusplus
}
#endif
#endif   /* !Py_INTERNAL_LIST_H */
