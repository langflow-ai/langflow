/*
 * tdbc.h --
 *
 *	Declarations of the public API for Tcl DataBase Connectivity (TDBC)
 *
 * Copyright (c) 2006 by Kevin B. Kenny
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 *
 * RCS: @(#) $Id$
 *
 *-----------------------------------------------------------------------------
 */

#ifndef TDBC_H_INCLUDED
#define TDBC_H_INCLUDED 1

#include <tcl.h>

#ifndef TDBCAPI
#   if defined(BUILD_tdbc)
#	define TDBCAPI MODULE_SCOPE
#   else
#	define TDBCAPI extern
#	undef USE_TDBC_STUBS
#	define USE_TDBC_STUBS 1
#   endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

#if defined(BUILD_tdbc)
DLLEXPORT int		Tdbc_Init(Tcl_Interp *interp);
#elif defined(STATIC_BUILD)
extern    int		Tdbc_Init(Tcl_Interp* interp);
#else
DLLIMPORT int		Tdbc_Init(Tcl_Interp* interp);
#endif

#define Tdbc_InitStubs(interp) TdbcInitializeStubs(interp, \
        TDBC_VERSION, TDBC_STUBS_EPOCH,	TDBC_STUBS_REVISION)
#if defined(USE_TDBC_STUBS)
    TDBCAPI const char* TdbcInitializeStubs(
        Tcl_Interp* interp, const char* version, int epoch, int revision);
#else
#    define TdbcInitializeStubs(interp, version, epoch, revision) \
        (Tcl_PkgRequire(interp, "tdbc", version))
#endif

#ifdef __cplusplus
}
#endif

/*
 * TDBC_VERSION and TDBC_PATCHLEVEL here must match the ones that
 * appear near the top of configure.ac.
 */

#define	TDBC_VERSION	"1.1"
#define TDBC_PATCHLEVEL "1.1.7"

/*
 * Include the Stubs declarations for the public API, generated from
 * tdbc.decls.
 */

#include "tdbcDecls.h"

#endif

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
