/*
 * tkMacOSX.h --
 *
 *	Declarations of Macintosh specific exported variables and procedures.
 *
 * Copyright (c) 1995-1997 Sun Microsystems, Inc.
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2005-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMAC
#define _TKMAC

#ifndef _TK
#include "tk.h"
#endif

/*
 * Structures and function types for handling Netscape-type in process
 * embedding where Tk does not control the top-level
 */

typedef int (Tk_MacOSXEmbedRegisterWinProc) (long winID, Tk_Window window);
typedef void* (Tk_MacOSXEmbedGetGrafPortProc) (Tk_Window window);
typedef int (Tk_MacOSXEmbedMakeContainerExistProc) (Tk_Window window);
typedef void (Tk_MacOSXEmbedGetClipProc) (Tk_Window window, void *rgn);
typedef void (Tk_MacOSXEmbedGetOffsetInParentProc) (Tk_Window window, void *ulCorner);

#include "tkPlatDecls.h"

#endif /* _TKMAC */
