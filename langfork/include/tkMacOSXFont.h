/*
 * tkMacOSXFont.h --
 *
 *	Contains the Macintosh implementation of the platform-independent
 *	font package interface.
 *
 * Copyright (c) 1990-1994 The Regents of the University of California.
 * Copyright (c) 1994-1997 Sun Microsystems, Inc.
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2006-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef TKMACOSXFONT_H
#define TKMACOSXFONT_H 1

#include "tkFont.h"

#ifndef _TKMACINT
#include "tkMacOSXInt.h"
#endif

/*
 * Function prototypes
 */

MODULE_SCOPE Tcl_Obj * TkMacOSXFontDescriptionForNSFontAndNSFontAttributes(
	NSFont *nsFont, NSDictionary *nsAttributes);

#endif /*TKMACOSXFONT_H*/
