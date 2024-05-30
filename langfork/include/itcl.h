/*
 * itcl.h --
 *
 * This file contains definitions for the C-implemeted part of a Itcl
 * this version of [incr Tcl] (Itcl) is a completely new implementation
 * based on TclOO extension of Tcl 8.5
 * It tries to provide the same interfaces as the original implementation
 * of Michael J. McLennan
 * Some small pieces of code are taken from that implementation
 *
 * Copyright (c) 2007 by Arnulf P. Wiedemann
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

/*
 * ------------------------------------------------------------------------
 *      PACKAGE:  [incr Tcl]
 *  DESCRIPTION:  Object-Oriented Extensions to Tcl
 *
 *  [incr Tcl] provides object-oriented extensions to Tcl, much as
 *  C++ provides object-oriented extensions to C.  It provides a means
 *  of encapsulating related procedures together with their shared data
 *  in a local namespace that is hidden from the outside world.  It
 *  promotes code re-use through inheritance.  More than anything else,
 *  it encourages better organization of Tcl applications through the
 *  object-oriented paradigm, leading to code that is easier to
 *  understand and maintain.
 *
 *  ADDING [incr Tcl] TO A Tcl-BASED APPLICATION:
 *
 *    To add [incr Tcl] facilities to a Tcl application, modify the
 *    Tcl_AppInit() routine as follows:
 *
 *    1) Include this header file near the top of the file containing
 *       Tcl_AppInit():
 *
 *         #include "itcl.h"
*
 *    2) Within the body of Tcl_AppInit(), add the following lines:
 *
 *         if (Itcl_Init(interp) == TCL_ERROR) {
 *             return TCL_ERROR;
 *         }
 *
 *    3) Link your application with libitcl.a
 *
 *    NOTE:  An example file "tclAppInit.c" containing the changes shown
 *           above is included in this distribution.
 *
 *---------------------------------------------------------------------
 */

#ifndef ITCL_H_INCLUDED
#define ITCL_H_INCLUDED

#include <tcl.h>

#if (TCL_MAJOR_VERSION == 8) && defined(TCL_MINOR_VERSION) && (TCL_MINOR_VERSION < 6)
#    error Itcl 4 build requires tcl.h from Tcl 8.6 or later
#endif

/*
 * For C++ compilers, use extern "C"
 */

#ifdef __cplusplus
extern "C" {
#endif

#ifndef TCL_ALPHA_RELEASE
#   define TCL_ALPHA_RELEASE    0
#endif
#ifndef TCL_BETA_RELEASE
#   define TCL_BETA_RELEASE     1
#endif
#ifndef TCL_FINAL_RELEASE
#   define TCL_FINAL_RELEASE    2
#endif

#define ITCL_MAJOR_VERSION	4
#define ITCL_MINOR_VERSION	2
#define ITCL_RELEASE_LEVEL      TCL_FINAL_RELEASE
#define ITCL_RELEASE_SERIAL     4

#define ITCL_VERSION            "4.2"
#define ITCL_PATCH_LEVEL        "4.2.4"


/*
 * A special definition used to allow this header file to be included from
 * windows resource files so that they can obtain version information.
 * RC_INVOKED is defined by default by the windows RC tool.
 *
 * Resource compilers don't like all the C stuff, like typedefs and function
 * declarations, that occur below, so block them out.
 */

#ifndef RC_INVOKED

#define ITCL_NAMESPACE          "::itcl"

#ifndef ITCLAPI
#   if defined(BUILD_itcl)
#	define ITCLAPI MODULE_SCOPE
#   else
#	define ITCLAPI extern
#	undef USE_ITCL_STUBS
#	define USE_ITCL_STUBS 1
#   endif
#endif

#if defined(BUILD_itcl) && !defined(STATIC_BUILD)
#   define ITCL_EXTERN extern DLLEXPORT
#else
#   define ITCL_EXTERN extern
#endif

ITCL_EXTERN int Itcl_Init(Tcl_Interp *interp);
ITCL_EXTERN int Itcl_SafeInit(Tcl_Interp *interp);

/*
 * Protection levels:
 *
 * ITCL_PUBLIC    - accessible from any namespace
 * ITCL_PROTECTED - accessible from namespace that imports in "protected" mode
 * ITCL_PRIVATE   - accessible only within the namespace that contains it
 */
#define ITCL_PUBLIC           1
#define ITCL_PROTECTED        2
#define ITCL_PRIVATE          3
#define ITCL_DEFAULT_PROTECT  4

#if (TCL_MAJOR_VERSION == 8) && (TCL_MINOR_VERSION < 7) && !defined(Tcl_Size)
#    define Tcl_Size int
#endif

/*
 *  Generic stack.
 */
typedef struct Itcl_Stack {
    void **values;               /* values on stack */
    Tcl_Size len;                  /* number of values on stack */
    Tcl_Size max;                  /* maximum size of stack */
    void *space[5];              /* initial space for stack data */
} Itcl_Stack;

#define Itcl_GetStackSize(stackPtr) ((stackPtr)->len)

/*
 *  Generic linked list.
 */
struct Itcl_List;
typedef struct Itcl_ListElem {
    struct Itcl_List* owner;     /* list containing this element */
    void *value;                 /* value associated with this element */
    struct Itcl_ListElem *prev;  /* previous element in linked list */
    struct Itcl_ListElem *next;  /* next element in linked list */
} Itcl_ListElem;

typedef struct Itcl_List {
    int validate;                /* validation stamp */
    Tcl_Size num;                  /* number of elements */
    struct Itcl_ListElem *head;  /* previous element in linked list */
    struct Itcl_ListElem *tail;  /* next element in linked list */
} Itcl_List;

#define Itcl_FirstListElem(listPtr) ((listPtr)->head)
#define Itcl_LastListElem(listPtr)  ((listPtr)->tail)
#define Itcl_NextListElem(elemPtr)  ((elemPtr)->next)
#define Itcl_PrevListElem(elemPtr)  ((elemPtr)->prev)
#define Itcl_GetListLength(listPtr) ((listPtr)->num)
#define Itcl_GetListValue(elemPtr)  ((elemPtr)->value)

/*
 *  Token representing the state of an interpreter.
 */
typedef struct Itcl_InterpState_ *Itcl_InterpState;


/*
 * Include all the public API, generated from itcl.decls.
 */

#include "itclDecls.h"

#endif /* RC_INVOKED */

/*
 * end block for C++
 */

#ifdef __cplusplus
}
#endif

#endif /* ITCL_H_INCLUDED */
