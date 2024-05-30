/*
 * --------------------------------------------------------------------------
 * tclthread.h --
 *
 * Global header file for the thread extension.
 *
 * Copyright (c) 2002 ActiveState Corporation.
 * Copyright (c) 2002 by Zoran Vasiljevic.
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 * ---------------------------------------------------------------------------
 */

/*
 * Thread extension version numbers are not stored here
 * because this isn't a public export file.
 */

#ifndef _TCL_THREAD_H_
#define _TCL_THREAD_H_

#include <tcl.h>

/*
 * Exported from threadCmd.c file.
 */
#ifdef __cplusplus
extern "C" {
#endif
DLLEXPORT int Thread_Init(Tcl_Interp *interp);
#ifdef __cplusplus
}
#endif

#endif /* _TCL_THREAD_H_ */
