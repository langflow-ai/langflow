/*
 * tkMacOSXPort.h --
 *
 *	This file is included by all of the Tk C files.  It contains
 *	information that may be configuration-dependent, such as
 *	#includes for system include files and a few other things.
 *
 * Copyright (c) 1994-1996 Sun Microsystems, Inc.
 * Copyright 2001-2009, Apple Inc.
 * Copyright (c) 2005-2009 Daniel A. Steffen <das@users.sourceforge.net>
 *
 * See the file "license.terms" for information on usage and redistribution
 * of this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKMACPORT
#define _TKMACPORT

#include <stdio.h>
#include <pwd.h>
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <ctype.h>
#include <math.h>
#include <string.h>
#include <limits.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/file.h>
#ifdef HAVE_SYS_SELECT_H
#   include <sys/select.h>
#endif
#include <sys/stat.h>
#ifndef _TCL
#   include <tcl.h>
#endif
#ifdef HAVE_SYS_TIME_H
#	include <sys/time.h>
#endif
#include <time.h>
#ifdef HAVE_INTTYPES_H
#    include <inttypes.h>
#endif
#include <unistd.h>
#if defined(__GNUC__) && !defined(__cplusplus)
#   pragma GCC diagnostic ignored "-Wc++-compat"
#endif
#include <X11/Xlib.h>
#include <X11/cursorfont.h>
#include <X11/keysym.h>
#include <X11/Xatom.h>
#include <X11/Xfuncproto.h>
#include <X11/Xutil.h>

/*
 * The following macro defines the type of the mask arguments to
 * select:
 */

#ifndef NO_FD_SET
#   define SELECT_MASK fd_set
#else
#   ifndef _AIX
	typedef long fd_mask;
#   endif
#   if defined(_IBMR2)
#	define SELECT_MASK void
#   else
#	define SELECT_MASK int
#   endif
#endif

/*
 * Used to tag functions that are only to be visible within the module being
 * built and not outside it (where this is supported by the linker).
 */

#ifndef MODULE_SCOPE
#   ifdef __cplusplus
#	define MODULE_SCOPE extern "C"
#   else
#	define MODULE_SCOPE extern
#   endif
#endif

/*
 * The following macro defines the number of fd_masks in an fd_set:
 */

#ifndef FD_SETSIZE
#   ifdef OPEN_MAX
#	define FD_SETSIZE OPEN_MAX
#   else
#	define FD_SETSIZE 256
#   endif
#endif
#if !defined(howmany)
#   define howmany(x, y) (((x)+((y)-1))/(y))
#endif
#ifndef NFDBITS
#   define NFDBITS NBBY*sizeof(fd_mask)
#endif
#define MASK_SIZE howmany(FD_SETSIZE, NFDBITS)

/*
 * Define "NBBY" (number of bits per byte) if it's not already defined.
 */

#ifndef NBBY
#   define NBBY 8
#endif

/*
 * The following define causes Tk to use its internal keysym hash table
 */

#define REDO_KEYSYM_LOOKUP

/*
 * Defines for X functions that are used by Tk but are treated as
 * no-op functions on the Macintosh.
 */

#undef XFlush
#define XFlush(display) (0)
#undef XFree
#define XFree(data) (((data) != NULL) ? (ckfree(data),0) : 0)
#undef XGrabServer
#define XGrabServer(display) (0)
#undef XNoOp
#define XNoOp(display) (LastKnownRequestProcessed(display)++,0)
#undef XUngrabServer
#define XUngrabServer(display) (0)
#undef XSynchronize
#define XSynchronize(display, onoff) (LastKnownRequestProcessed(display)++,NULL)
#undef XVisualIDFromVisual
#define XVisualIDFromVisual(visual) (visual->visualid)

/*
 * The following functions are not used on the Mac, so we stub them out.
 */

#define TkpCmapStressed(tkwin,colormap) (0)
#define TkpFreeColor(tkColPtr)
#define TkSetPixmapColormap(p,c) {}
#define TkpSync(display)

/*
 * TkMacOSXGetCapture is a legacy function used on the Mac. When fixing
 * [943d5ebe51], TkpGetCapture was added to the Windows port. Both
 * are actually the same feature and should bear the same name. However,
 * in order to avoid potential backwards incompatibilities, renaming
 * TkMacOSXGetCapture into TkpGetCapture in *PlatDecls.h shall not be
 * done in a patch release, therefore use a define here.
 */

#define TkpGetCapture TkMacOSXGetCapture

/*
 * This macro stores a representation of the window handle in a string.
 */

#define TkpPrintWindowId(buf,w) \
	snprintf((buf), TCL_INTEGER_SPACE, "0x%lx", (unsigned long) (w))

/*
 * Turn off Tk double-buffering as Aqua windows are already double-buffered.
 */

#define TK_NO_DOUBLE_BUFFERING 1
#define TK_HAS_DYNAMIC_COLORS 1
#define TK_DYNAMIC_COLORMAP 0x0fffffff

/*
 * Inform tkImgPhInstance.c that we implement TkpPutRGBAImage to render RGBA
 * images directly into a window.
 */

#define TK_CAN_RENDER_RGBA

MODULE_SCOPE int TkpPutRGBAImage(
		     Display* display, Drawable drawable, GC gc,XImage* image,
		     int src_x, int src_y, int dest_x, int dest_y,
		     unsigned int width, unsigned int height);

/*
 * Used by xcolor.c
 */

MODULE_SCOPE unsigned long TkMacOSXRGBPixel(unsigned long red, unsigned long green,
					    unsigned long blue);
#define TkpGetPixel(p) (TkMacOSXRGBPixel(p->red >> 8, p->green >> 8, p->blue >> 8))

/*
 * Used by tkAppInit
 */

#define USE_CUSTOM_EXIT_PROC
EXTERN int TkpWantsExitProc(void);
EXTERN TCL_NORETURN void TkpExitProc(void *);

#endif /* _TKMACPORT */
