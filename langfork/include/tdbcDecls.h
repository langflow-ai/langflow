/*
 * tdbcDecls.h --
 *
 *	Exported Stubs declarations for Tcl DataBaseConnectivity (TDBC).
 *
 * This file is (mostly) generated automatically from tdbc.decls
 *
 * Copyright (c) 2008 by Kevin B. Kenny.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 *
 * RCS: @(#) $Id$
 *
 */

/* !BEGIN!: Do not edit below this line. */

#define TDBC_STUBS_EPOCH 0
#define TDBC_STUBS_REVISION 3

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Exported function declarations:
 */

/* 0 */
TDBCAPI int		Tdbc_Init_ (Tcl_Interp* interp);
/* 1 */
TDBCAPI Tcl_Obj*	Tdbc_TokenizeSql (Tcl_Interp* interp,
				const char* statement);
/* 2 */
TDBCAPI const char*	Tdbc_MapSqlState (const char* sqlstate);

typedef struct TdbcStubs {
    int magic;
    int epoch;
    int revision;
    void *hooks;

    int (*tdbc_Init_) (Tcl_Interp* interp); /* 0 */
    Tcl_Obj* (*tdbc_TokenizeSql) (Tcl_Interp* interp, const char* statement); /* 1 */
    const char* (*tdbc_MapSqlState) (const char* sqlstate); /* 2 */
} TdbcStubs;

extern const TdbcStubs *tdbcStubsPtr;

#ifdef __cplusplus
}
#endif

#if defined(USE_TDBC_STUBS)

/*
 * Inline function declarations:
 */

#define Tdbc_Init_ \
	(tdbcStubsPtr->tdbc_Init_) /* 0 */
#define Tdbc_TokenizeSql \
	(tdbcStubsPtr->tdbc_TokenizeSql) /* 1 */
#define Tdbc_MapSqlState \
	(tdbcStubsPtr->tdbc_MapSqlState) /* 2 */

#endif /* defined(USE_TDBC_STUBS) */

/* !END!: Do not edit above this line. */
