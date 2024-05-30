/*
 * tkMacOSXDebug.h --
 *
 *	Declarations of Macintosh specific functions for debugging MacOS events,
 *	regions, etc...
 *
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2005-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMACDEBUG
#define _TKMACDEBUG

#ifndef _TKMACINT
#include "tkMacOSXInt.h"
#endif

#ifdef TK_MAC_DEBUG

MODULE_SCOPE void* TkMacOSXGetNamedDebugSymbol(const char* module, const char* symbol);

/* Macro to abstract common use of TkMacOSXGetNamedDebugSymbol to initialize named symbols */
#define TkMacOSXInitNamedDebugSymbol(module, ret, symbol, ...) \
    static ret (* symbol)(__VA_ARGS__) = (void*)(-1L); \
    if (symbol == (void*)(-1L)) { \
	symbol = TkMacOSXGetNamedDebugSymbol(STRINGIFY(module), STRINGIFY(_##symbol));\
    }

#endif /* TK_MAC_DEBUG */

#endif
