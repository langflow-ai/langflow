/*
 * tkMacOSXInt.h --
 *
 *	Declarations of Macintosh specific shared variables and procedures.
 *
 * Copyright (c) 1995-1997 Sun Microsystems, Inc.
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2005-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMACINT
#define _TKMACINT

#ifndef _TKINT
#include "tkInt.h"
#endif

/*
 * Include platform specific public interfaces.
 */

#ifndef _TKMAC
#include "tkMacOSX.h"
#import <Cocoa/Cocoa.h>
#endif

/*
 * Define compatibility platform types used in the structures below so that
 * this header can be included without pulling in the platform headers.
 */

#ifndef _TKMACPRIV
#   ifndef CGGEOMETRY_H_
#	ifndef CGFLOAT_DEFINED
#	    if __LP64__
#		define CGFloat double
#	    else
#		define CGFloat float
#	    endif
#	endif
#	define CGSize struct {CGFloat width; CGFloat height;}
#   endif
#   ifndef CGCONTEXT_H_
#	define CGContextRef void *
#   endif
#   ifndef CGCOLOR_H_
#	define CGColorRef void *
#   endif
#   ifndef __HISHAPE__
#	define HIShapeRef void *
#   endif
#   ifndef _APPKITDEFINES_H
#	define NSView void *
#   endif
#endif

struct TkWindowPrivate {
    TkWindow *winPtr;		/* Ptr to tk window or NULL if Pixmap */
    NSView *view;
    CGContextRef context;
    int xOff;			/* X offset from toplevel window */
    int yOff;			/* Y offset from toplevel window */
    CGSize size;
    HIShapeRef visRgn;		/* Visible region of window */
    HIShapeRef aboveVisRgn;	/* Visible region of window & its children */
    HIShapeRef drawRgn;		/* Clipped drawing region */
    int referenceCount;		/* Don't delete toplevel until children are
				 * gone. */
    struct TkWindowPrivate *toplevel;
				/* Pointer to the toplevel datastruct. */
    CGFloat fillRGBA[4];        /* Background used by the ttk FillElement */
    int flags;			/* Various state see defines below. */
};
typedef struct TkWindowPrivate MacDrawable;

/*
 * Defines use for the flags field of the MacDrawable data structure.
 */

#define TK_SCROLLBAR_GROW	0x01
#define TK_CLIP_INVALID		0x02
#define TK_HOST_EXISTS		0x04
#define TK_DRAWN_UNDER_MENU	0x08
#define TK_IS_PIXMAP		0x10
#define TK_IS_BW_PIXMAP		0x20
#define TK_DO_NOT_DRAW          0x40
#define TTK_HAS_CONTRASTING_BG  0x80

/*
 * I am reserving TK_EMBEDDED = 0x100 in the MacDrawable flags
 * This is defined in tk.h. We need to duplicate the TK_EMBEDDED flag in the
 * TkWindow structure for the window, but in the MacWin. This way we can
 * still tell what the correct port is after the TKWindow structure has been
 * freed. This actually happens when you bind destroy of a toplevel to
 * Destroy of a child.
 */

/*
 * This structure is for handling Netscape-type in process
 * embedding where Tk does not control the top-level. It contains
 * various functions that are needed by Mac specific routines, like
 * TkMacOSXGetDrawablePort. The definitions of the function types
 * are in tkMacOSX.h.
 */

typedef struct {
    Tk_MacOSXEmbedRegisterWinProc *registerWinProc;
    Tk_MacOSXEmbedGetGrafPortProc *getPortProc;
    Tk_MacOSXEmbedMakeContainerExistProc *containerExistProc;
    Tk_MacOSXEmbedGetClipProc *getClipProc;
    Tk_MacOSXEmbedGetOffsetInParentProc *getOffsetProc;
} TkMacOSXEmbedHandler;

MODULE_SCOPE TkMacOSXEmbedHandler *tkMacOSXEmbedHandler;

/*
 * Undef compatibility platform types defined above.
 */

#ifndef _TKMACPRIV
#   ifndef CGGEOMETRY_H_
#	ifndef CGFLOAT_DEFINED
#	    undef CGFloat
#	endif
#	undef CGSize
#   endif
#   ifndef CGCONTEXT_H_
#	undef CGContextRef
#   endif
#   ifndef CGCOLOR_H_
#	undef CGColorRef
#   endif
#   ifndef __HISHAPE__
#	undef HIShapeRef
#   endif
#   ifndef _APPKITDEFINES_H
#	undef NSView
#   endif
#endif

/*
 * Defines used for TkMacOSXInvalidateWindow
 */

#define TK_WINDOW_ONLY 0
#define TK_PARENT_WINDOW 1

/*
 * Accessor for the privatePtr flags field for the TK_HOST_EXISTS field
 */

#define TkMacOSXHostToplevelExists(tkwin) \
    (((TkWindow *) (tkwin))->privatePtr->toplevel->flags & TK_HOST_EXISTS)

/*
 * Defines used for the flags argument to TkGenWMConfigureEvent.
 */

#define TK_LOCATION_CHANGED	1
#define TK_SIZE_CHANGED		2
#define TK_BOTH_CHANGED		3
#define TK_MACOSX_HANDLE_EVENT_IMMEDIATELY 1024

/*
 * Defines for tkTextDisp.c and tkFont.c
 */

#define TK_LAYOUT_WITH_BASE_CHUNKS	1
#define TK_DRAW_IN_CONTEXT		1

/*
 * Prototypes of internal procs not in the stubs table.
 */

MODULE_SCOPE void TkMacOSXDefaultStartupScript(void);
MODULE_SCOPE void TkpClipDrawableToRect(Display *display, Drawable d, int x,
	int y, int width, int height);
MODULE_SCOPE Bool TkTestLogDisplay(Drawable drawable);

/*
 * Include the stubbed internal platform-specific API.
 */

#include "tkIntPlatDecls.h"

#endif /* _TKMACINT */

/*
 * Local Variables:
 * mode: objc
 * c-basic-offset: 4
 * fill-column: 79
 * coding: utf-8
 * End:
 */
