/*
 * tkInt.h --
 *
 *	Declarations for things used internally by the Tk functions but not
 *	exported outside the module.
 *
 * Copyright (c) 1990-1994 The Regents of the University of California.
 * Copyright (c) 1994-1997 Sun Microsystems, Inc.
 * Copyright (c) 1998 by Scriptics Corporation.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKINT
#define _TKINT

#ifndef _TKPORT
#include "tkPort.h"
#endif

#define TK_OPTION_ENUM_VAR		((int)(sizeof(Tk_OptionType)&(sizeof(int)-1))<<6)

/*
 * Ensure WORDS_BIGENDIAN is defined correctly:
 * Needs to happen here in addition to configure to work with fat compiles on
 * Darwin (where configure runs only once for multiple architectures).
 */

#include <stdio.h>
#ifdef HAVE_SYS_TYPES_H
#    include <sys/types.h>
#endif
#ifdef HAVE_SYS_PARAM_H
#    include <sys/param.h>
#endif
#ifdef BYTE_ORDER
#    ifdef BIG_ENDIAN
#	 if BYTE_ORDER == BIG_ENDIAN
#	     undef WORDS_BIGENDIAN
#	     define WORDS_BIGENDIAN 1
#	 endif
#    endif
#    ifdef LITTLE_ENDIAN
#	 if BYTE_ORDER == LITTLE_ENDIAN
#	     undef WORDS_BIGENDIAN
#	 endif
#    endif
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

#ifndef JOIN
#  define JOIN(a,b) JOIN1(a,b)
#  define JOIN1(a,b) a##b
#endif

#ifndef TCL_UNUSED
#   if defined(__cplusplus)
#	define TCL_UNUSED(T) T
#   elif defined(__GNUC__) && (__GNUC__ > 2)
#	define TCL_UNUSED(T) T JOIN(dummy, __LINE__) __attribute__((unused))
#   else
#	define TCL_UNUSED(T) T JOIN(dummy, __LINE__)
#   endif
#endif

#if defined(_WIN32) && (TCL_MAJOR_VERSION < 9) && (TCL_MINOR_VERSION < 7)
# if TCL_UTF_MAX > 3
#   define Tcl_WCharToUtfDString(a,b,c) Tcl_WinTCharToUtf((TCHAR *)(a),(b)*sizeof(WCHAR),c)
#   define Tcl_UtfToWCharDString(a,b,c) (WCHAR *)Tcl_WinUtfToTChar(a,b,c)
# else
#   define Tcl_WCharToUtfDString ((char * (*)(const WCHAR *, int len, Tcl_DString *))Tcl_UniCharToUtfDString)
#   define Tcl_UtfToWCharDString ((WCHAR * (*)(const char *, int len, Tcl_DString *))Tcl_UtfToUniCharDString)
# endif
#endif

#if defined(__STDC_VERSION__) && (__STDC_VERSION__ >= 199901L)
#   define TKFLEXARRAY
#elif defined(__GNUC__) && (__GNUC__ > 2)
#   define TKFLEXARRAY 0
#else
#   define TKFLEXARRAY 1
#endif

#ifndef Tcl_GetParent
#   define Tcl_GetParent Tcl_GetMaster
#endif

/*
 * Macros used to cast between pointers and integers (e.g. when storing an int
 * in ClientData), on 64-bit architectures they avoid gcc warning about "cast
 * to/from pointer from/to integer of different size".
 */

#if !defined(INT2PTR) && !defined(PTR2INT)
#   if defined(HAVE_INTPTR_T) || defined(intptr_t)
#	define INT2PTR(p) ((void*)(intptr_t)(p))
#	define PTR2INT(p) ((int)(intptr_t)(p))
#   else
#	define INT2PTR(p) ((void*)(p))
#	define PTR2INT(p) ((int)(p))
#   endif
#endif
#if !defined(UINT2PTR) && !defined(PTR2UINT)
#   if defined(HAVE_UINTPTR_T) || defined(uintptr_t)
#	define UINT2PTR(p) ((void*)(uintptr_t)(p))
#	define PTR2UINT(p) ((unsigned int)(uintptr_t)(p))
#   else
#	define UINT2PTR(p) ((void*)(p))
#	define PTR2UINT(p) ((unsigned int)(p))
#   endif
#endif

#ifndef TCL_Z_MODIFIER
#   if defined(_WIN64)
#	define TCL_Z_MODIFIER	"I"
#   elif defined(__GNUC__) && !defined(_WIN32)
#	define TCL_Z_MODIFIER	"z"
#   else
#	define TCL_Z_MODIFIER	""
#   endif
#endif /* !TCL_Z_MODIFIER */

/*
 * Opaque type declarations:
 */

typedef struct TkColormap TkColormap;
typedef struct TkFontAttributes TkFontAttributes;
typedef struct TkGrabEvent TkGrabEvent;
typedef struct TkpCursor_ *TkpCursor;
typedef struct TkRegion_ *TkRegion;
typedef struct TkStressedCmap TkStressedCmap;
typedef struct TkBindInfo_ *TkBindInfo;
typedef struct Busy *TkBusy;

/*
 * One of the following structures is maintained for each cursor in use in the
 * system. This structure is used by tkCursor.c and the various system-
 * specific cursor files.
 */

typedef struct TkCursor {
    Tk_Cursor cursor;		/* System specific identifier for cursor. */
    Display *display;		/* Display containing cursor. Needed for
				 * disposal and retrieval of cursors. */
    int resourceRefCount;	/* Number of active uses of this cursor (each
				 * active use corresponds to a call to
				 * Tk_AllocPreserveFromObj or Tk_Preserve). If
				 * this count is 0, then this structure is no
				 * longer valid and it isn't present in a hash
				 * table: it is being kept around only because
				 * there are objects referring to it. The
				 * structure is freed when resourceRefCount
				 * and objRefCount are both 0. */
    int objRefCount;		/* Number of Tcl objects that reference this
				 * structure.. */
    Tcl_HashTable *otherTable;	/* Second table (other than idTable) used to
				 * index this entry. */
    Tcl_HashEntry *hashPtr;	/* Entry in otherTable for this structure
				 * (needed when deleting). */
    Tcl_HashEntry *idHashPtr;	/* Entry in idTable for this structure (needed
				 * when deleting). */
    struct TkCursor *nextPtr;	/* Points to the next TkCursor structure with
				 * the same name. Cursors with the same name
				 * but different displays are chained together
				 * off a single hash table entry. */
} TkCursor;

/*
 * The following structure is kept one-per-TkDisplay to maintain information
 * about the caret (cursor location) on this display. This is used to dictate
 * global focus location (Windows Accessibility guidelines) and to position
 * the IME or XIM over-the-spot window.
 */

typedef struct TkCaret {
    struct TkWindow *winPtr;	/* The window on which we requested caret
				 * placement. */
    int x;			/* Relative x coord of the caret. */
    int y;			/* Relative y coord of the caret. */
    int height;			/* Specified height of the window. */
} TkCaret;

/*
 * One of the following structures is maintained for each display containing a
 * window managed by Tk. In part, the structure is used to store thread-
 * specific data, since each thread will have its own TkDisplay structure.
 */

typedef struct TkDisplay {
    Display *display;		/* Xlib's info about display. */
    struct TkDisplay *nextPtr;	/* Next in list of all displays. */
    char *name;			/* Name of display (with any screen identifier
				 * removed). Malloc-ed. */
    Time lastEventTime;		/* Time of last event received for this
				 * display. */

    /*
     * Information used primarily by tk3d.c:
     */

    int borderInit;		/* 0 means borderTable needs initializing. */
    Tcl_HashTable borderTable;	/* Maps from color name to TkBorder
				 * structure. */

    /*
     * Information used by tkAtom.c only:
     */

    int atomInit;		/* 0 means stuff below hasn't been initialized
				 * yet. */
    Tcl_HashTable nameTable;	/* Maps from names to Atom's. */
    Tcl_HashTable atomTable;	/* Maps from Atom's back to names. */

    /*
     * Information used primarily by tkBind.c:
     */

    int bindInfoStale;		/* Non-zero means the variables in this part
				 * of the structure are potentially incorrect
				 * and should be recomputed. */
    unsigned int modeModMask;	/* Has one bit set to indicate the modifier
				 * corresponding to "mode shift". If no such
				 * modifier, than this is zero. */
    unsigned int metaModMask;	/* Has one bit set to indicate the modifier
				 * corresponding to the "Meta" key. If no such
				 * modifier, then this is zero. */
    unsigned int altModMask;	/* Has one bit set to indicate the modifier
				 * corresponding to the "Meta" key. If no such
				 * modifier, then this is zero. */
    enum {LU_IGNORE, LU_CAPS, LU_SHIFT} lockUsage;
				/* Indicates how to interpret lock
				 * modifier. */
    int numModKeyCodes;		/* Number of entries in modKeyCodes array
				 * below. */
    KeyCode *modKeyCodes;	/* Pointer to an array giving keycodes for all
				 * of the keys that have modifiers associated
				 * with them. Malloc'ed, but may be NULL. */

    /*
     * Information used by tkBitmap.c only:
     */

    int bitmapInit;		/* 0 means tables above need initializing. */
    int bitmapAutoNumber;	/* Used to number bitmaps. */
    Tcl_HashTable bitmapNameTable;
				/* Maps from name of bitmap to the first
				 * TkBitmap record for that name. */
    Tcl_HashTable bitmapIdTable;/* Maps from bitmap id to the TkBitmap
				 * structure for the bitmap. */
    Tcl_HashTable bitmapDataTable;
				/* Used by Tk_GetBitmapFromData to map from a
				 * collection of in-core data about a bitmap
				 * to a reference giving an automatically-
				 * generated name for the bitmap. */

    /*
     * Information used by tkCanvas.c only:
     */

    int numIdSearches;
    int numSlowSearches;

    /*
     * Used by tkColor.c only:
     */

    int colorInit;		/* 0 means color module needs initializing. */
    TkStressedCmap *stressPtr;	/* First in list of colormaps that have filled
				 * up, so we have to pick an approximate
				 * color. */
    Tcl_HashTable colorNameTable;
				/* Maps from color name to TkColor structure
				 * for that color. */
    Tcl_HashTable colorValueTable;
				/* Maps from integer RGB values to TkColor
				 * structures. */

    /*
     * Used by tkCursor.c only:
     */

    int cursorInit;		/* 0 means cursor module need initializing. */
    Tcl_HashTable cursorNameTable;
				/* Maps from a string name to a cursor to the
				 * TkCursor record for the cursor. */
    Tcl_HashTable cursorDataTable;
				/* Maps from a collection of in-core data
				 * about a cursor to a TkCursor structure. */
    Tcl_HashTable cursorIdTable;
				/* Maps from a cursor id to the TkCursor
				 * structure for the cursor. */
    char cursorString[20];	/* Used to store a cursor id string. */
    Font cursorFont;		/* Font to use for standard cursors. None
				 * means font not loaded yet. */

    /*
     * Information used by tkError.c only:
     */

    struct TkErrorHandler *errorPtr;
				/* First in list of error handlers for this
				 * display. NULL means no handlers exist at
				 * present. */
    int deleteCount;		/* Counts # of handlers deleted since last
				 * time inactive handlers were garbage-
				 * collected. When this number gets big,
				 * handlers get cleaned up. */

    /*
     * Used by tkEvent.c only:
     */

    struct TkWindowEvent *delayedMotionPtr;
				/* Points to a malloc-ed motion event whose
				 * processing has been delayed in the hopes
				 * that another motion event will come along
				 * right away and we can merge the two of them
				 * together. NULL means that there is no
				 * delayed motion event. */

    /*
     * Information used by tkFocus.c only:
     */

    int focusDebug;		/* 1 means collect focus debugging
				 * statistics. */
    struct TkWindow *implicitWinPtr;
				/* If the focus arrived at a toplevel window
				 * implicitly via an Enter event (rather than
				 * via a FocusIn event), this points to the
				 * toplevel window. Otherwise it is NULL. */
    struct TkWindow *focusPtr;	/* Points to the window on this display that
				 * should be receiving keyboard events. When
				 * multiple applications on the display have
				 * the focus, this will refer to the innermost
				 * window in the innermost application. This
				 * information isn't used on Windows, but it's
				 * needed on the Mac, and also on X11 when XIM
				 * processing is being done. */

    /*
     * Information used by tkGC.c only:
     */

    Tcl_HashTable gcValueTable; /* Maps from a GC's values to a TkGC structure
				 * describing a GC with those values. */
    Tcl_HashTable gcIdTable;    /* Maps from a GC to a TkGC. */
    int gcInit;			/* 0 means the tables below need
				 * initializing. */

    /*
     * Information used by tkGeometry.c only:
     */

    Tcl_HashTable maintainHashTable;
				/* Hash table that maps from a container's
				 * Tk_Window token to a list of windows managed
				 * by that container. */
    int geomInit;

    /*
     * Information used by tkGrid.c, tkPack.c, tkPlace.c, tkPointer.c,
     * and ttkMacOSXTheme.c:
     */

#define TkGetContainer(tkwin) (Tk_TopWinHierarchy((TkWindow *)tkwin) ? NULL : \
	(((TkWindow *)tkwin)->maintainerPtr != NULL ? \
	 ((TkWindow *)tkwin)->maintainerPtr : ((TkWindow *)tkwin)->parentPtr))

    /*
     * Information used by tkGet.c only:
     */

    Tcl_HashTable uidTable;	/* Stores all Tk_Uid used in a thread. */
    int uidInit;		/* 0 means uidTable needs initializing. */

    /*
     * Information used by tkGrab.c only:
     */

    struct TkWindow *grabWinPtr;/* Window in which the pointer is currently
				 * grabbed, or NULL if none. */
    struct TkWindow *eventualGrabWinPtr;
				/* Value that grabWinPtr will have once the
				 * grab event queue (below) has been
				 * completely emptied. */
    struct TkWindow *buttonWinPtr;
				/* Window in which first mouse button was
				 * pressed while grab was in effect, or NULL
				 * if no such press in effect. */
    struct TkWindow *serverWinPtr;
				/* If no application contains the pointer then
				 * this is NULL. Otherwise it contains the
				 * last window for which we've gotten an Enter
				 * or Leave event from the server (i.e. the
				 * last window known to have contained the
				 * pointer). Doesn't reflect events that were
				 * synthesized in tkGrab.c. */
    TkGrabEvent *firstGrabEventPtr;
				/* First in list of enter/leave events
				 * synthesized by grab code. These events must
				 * be processed in order before any other
				 * events are processed. NULL means no such
				 * events. */
    TkGrabEvent *lastGrabEventPtr;
				/* Last in list of synthesized events, or NULL
				 * if list is empty. */
    int grabFlags;		/* Miscellaneous flag values. See definitions
				 * in tkGrab.c. */

    /*
     * Information used by tkGrid.c only:
     */

    int gridInit;		/* 0 means table below needs initializing. */
    Tcl_HashTable gridHashTable;/* Maps from Tk_Window tokens to corresponding
				 * Grid structures. */

    /*
     * Information used by tkImage.c only:
     */

    int imageId;		/* Value used to number image ids. */

    /*
     * Information used by tkMacWinMenu.c only:
     */

    int postCommandGeneration;

    /*
     * Information used by tkPack.c only.
     */

    int packInit;		/* 0 means table below needs initializing. */
    Tcl_HashTable packerHashTable;
				/* Maps from Tk_Window tokens to corresponding
				 * Packer structures. */

    /*
     * Information used by tkPlace.c only.
     */

    int placeInit;		/* 0 means tables below need initializing. */
    Tcl_HashTable masterTable;	/* Maps from Tk_Window toke to the Master
				 * structure for the window, if it exists. */
    Tcl_HashTable slaveTable;	/* Maps from Tk_Window toke to the Slave
				 * structure for the window, if it exists. */

    /*
     * Information used by tkSelect.c and tkClipboard.c only:
     */

    struct TkSelectionInfo *selectionInfoPtr;
				/* First in list of selection information
				 * records. Each entry contains information
				 * about the current owner of a particular
				 * selection on this display. */
    Atom multipleAtom;		/* Atom for MULTIPLE. None means selection
				 * stuff isn't initialized. */
    Atom incrAtom;		/* Atom for INCR. */
    Atom targetsAtom;		/* Atom for TARGETS. */
    Atom timestampAtom;		/* Atom for TIMESTAMP. */
    Atom textAtom;		/* Atom for TEXT. */
    Atom compoundTextAtom;	/* Atom for COMPOUND_TEXT. */
    Atom applicationAtom;	/* Atom for TK_APPLICATION. */
    Atom windowAtom;		/* Atom for TK_WINDOW. */
    Atom clipboardAtom;		/* Atom for CLIPBOARD. */
    Atom utf8Atom;		/* Atom for UTF8_STRING. */
    Atom atomPairAtom;          /* Atom for ATOM_PAIR. */

    Tk_Window clipWindow;	/* Window used for clipboard ownership and to
				 * retrieve selections between processes. NULL
				 * means clipboard info hasn't been
				 * initialized. */
    int clipboardActive;	/* 1 means we currently own the clipboard
				 * selection, 0 means we don't. */
    struct TkMainInfo *clipboardAppPtr;
				/* Last application that owned clipboard. */
    struct TkClipboardTarget *clipTargetPtr;
				/* First in list of clipboard type information
				 * records. Each entry contains information
				 * about the buffers for a given selection
				 * target. */

    /*
     * Information used by tkSend.c only:
     */

    Tk_Window commTkwin;	/* Window used for communication between
				 * interpreters during "send" commands. NULL
				 * means send info hasn't been initialized
				 * yet. */
    Atom commProperty;		/* X's name for comm property. */
    Atom registryProperty;	/* X's name for property containing registry
				 * of interpreter names. */
    Atom appNameProperty;	/* X's name for property used to hold the
				 * application name on each comm window. */

    /*
     * Information used by tkUnixWm.c and tkWinWm.c only:
     */

    struct TkWmInfo *firstWmPtr;/* Points to first top-level window. */
    struct TkWmInfo *foregroundWmPtr;
				/* Points to the foreground window. */

    /*
     * Information used by tkVisual.c only:
     */

    TkColormap *cmapPtr;	/* First in list of all non-default colormaps
				 * allocated for this display. */

    /*
     * Miscellaneous information:
     */

#ifdef TK_USE_INPUT_METHODS
    XIM inputMethod;		/* Input method for this display. */
    XIMStyle inputStyle;	/* Input style selected for this display. */
    XFontSet inputXfs;		/* XFontSet cached for over-the-spot XIM. */
#endif /* TK_USE_INPUT_METHODS */
    Tcl_HashTable winTable;	/* Maps from X window ids to TkWindow ptrs. */

    int refCount;		/* Reference count of how many Tk applications
				 * are using this display. Used to clean up
				 * the display when we no longer have any Tk
				 * applications using it. */

    /*
     * The following field were all added for Tk8.3
     */

    int mouseButtonState;	/* Current mouse button state for this
				 * display. NOT USED as of 8.6.10 */
    Window mouseButtonWindow;	/* Window the button state was set in, added
				 * in Tk 8.4. */
    Tk_Window warpWindow;
    Tk_Window warpMainwin;	/* For finding the root window for warping
				 * purposes. */
    int warpX;
    int warpY;

    /*
     * The following field(s) were all added for Tk8.4
     */

    unsigned int flags;		/* Various flag values: these are all defined
				 * in below. */
    TkCaret caret;		/* Information about the caret for this
				 * display. This is not a pointer. */

    int iconDataSize;		/* Size of default iconphoto image data. */
    unsigned char *iconDataPtr;	/* Default iconphoto image data, if set. */
#ifdef TK_USE_INPUT_METHODS
    int ximGeneration;          /* Used to invalidate XIC */
#endif /* TK_USE_INPUT_METHODS */
} TkDisplay;

/*
 * Flag values for TkDisplay flags.
 *  TK_DISPLAY_COLLAPSE_MOTION_EVENTS:	(default on)
 *	Indicates that we should collapse motion events on this display
 *  TK_DISPLAY_USE_IM:			(default on, set via tk.tcl)
 *	Whether to use input methods for this display
 *  TK_DISPLAY_WM_TRACING:		(default off)
 *	Whether we should do wm tracing on this display.
 *  TK_DISPLAY_IN_WARP:			(default off)
 *	Indicates that we are in a pointer warp
 */

#define TK_DISPLAY_COLLAPSE_MOTION_EVENTS	(1 << 0)
#define TK_DISPLAY_USE_IM			(1 << 1)
#define TK_DISPLAY_WM_TRACING			(1 << 3)
#define TK_DISPLAY_IN_WARP			(1 << 4)
#define TK_DISPLAY_USE_XKB			(1 << 5)

/*
 * One of the following structures exists for each error handler created by a
 * call to Tk_CreateErrorHandler. The structure is managed by tkError.c.
 */

typedef struct TkErrorHandler {
    TkDisplay *dispPtr;		/* Display to which handler applies. */
    unsigned long firstRequest;	/* Only errors with serial numbers >= to this
				 * are considered. */
    unsigned long lastRequest;	/* Only errors with serial numbers <= to this
				 * are considered. This field is filled in
				 * when XUnhandle is called. -1 means
				 * XUnhandle hasn't been called yet. */
    int error;			/* Consider only errors with this error_code
				 * (-1 means consider all errors). */
    int request;		/* Consider only errors with this major
				 * request code (-1 means consider all major
				 * codes). */
    int minorCode;		/* Consider only errors with this minor
				 * request code (-1 means consider all minor
				 * codes). */
    Tk_ErrorProc *errorProc;	/* Function to invoke when a matching error
				 * occurs. NULL means just ignore errors. */
    ClientData clientData;	/* Arbitrary value to pass to errorProc. */
    struct TkErrorHandler *nextPtr;
				/* Pointer to next older handler for this
				 * display, or NULL for end of list. */
} TkErrorHandler;

/*
 * One of the following structures exists for each event handler created by
 * calling Tk_CreateEventHandler. This information is used by tkEvent.c only.
 */

typedef struct TkEventHandler {
    unsigned long mask;		/* Events for which to invoke proc. */
    Tk_EventProc *proc;		/* Function to invoke when an event in mask
				 * occurs. */
    ClientData clientData;	/* Argument to pass to proc. */
    struct TkEventHandler *nextPtr;
				/* Next in list of handlers associated with
				 * window (NULL means end of list). */
} TkEventHandler;

/*
 * Tk keeps one of the following data structures for each main window (created
 * by a call to TkCreateMainWindow). It stores information that is shared by
 * all of the windows associated with a particular main window.
 */

typedef struct TkMainInfo {
    int refCount;		/* Number of windows whose "mainPtr" fields
				 * point here. When this becomes zero, can
				 * free up the structure (the reference count
				 * is zero because windows can get deleted in
				 * almost any order; the main window isn't
				 * necessarily the last one deleted). */
    struct TkWindow *winPtr;	/* Pointer to main window. */
    Tcl_Interp *interp;		/* Interpreter associated with application. */
    Tcl_HashTable nameTable;	/* Hash table mapping path names to TkWindow
				 * structs for all windows related to this
				 * main window. Managed by tkWindow.c. */
    long deletionEpoch;		/* Incremented by window deletions. */
    Tk_BindingTable bindingTable;
				/* Used in conjunction with "bind" command to
				 * bind events to Tcl commands. */
    TkBindInfo bindInfo;	/* Information used by tkBind.c on a per
				 * application basis. */
    struct TkFontInfo *fontInfoPtr;
				/* Information used by tkFont.c on a per
				 * application basis. */

    /*
     * Information used only by tkFocus.c and tk*Embed.c:
     */

    struct TkToplevelFocusInfo *tlFocusPtr;
				/* First in list of records containing focus
				 * information for each top-level in the
				 * application. Used only by tkFocus.c. */
    struct TkDisplayFocusInfo *displayFocusPtr;
				/* First in list of records containing focus
				 * information for each display that this
				 * application has ever used. Used only by
				 * tkFocus.c. */

    struct ElArray *optionRootPtr;
				/* Top level of option hierarchy for this main
				 * window. NULL means uninitialized. Managed
				 * by tkOption.c. */
    Tcl_HashTable imageTable;	/* Maps from image names to Tk_ImageModel
				 * structures. Managed by tkImage.c. */
    int strictMotif;		/* This is linked to the tk_strictMotif global
				 * variable. */
    int alwaysShowSelection;	/* This is linked to the
				 * ::tk::AlwaysShowSelection variable. */
    struct TkMainInfo *nextPtr;	/* Next in list of all main windows managed by
				 * this process. */
    Tcl_HashTable busyTable;	/* Information used by [tk busy] command. */
    Tcl_ObjCmdProc *tclUpdateObjProc;
				/* Saved Tcl [update] command, used to restore
				 * Tcl's version of [update] after Tk is shut
				 * down */
    unsigned int ttkNbTabsStickBit;
    				/* Information used by ttk::notebook. */
} TkMainInfo;

/*
 * Tk keeps the following data structure for each of it's builtin bitmaps.
 * This structure is only used by tkBitmap.c and other platform specific
 * bitmap files.
 */

typedef struct {
    const void *source;		/* Bits for bitmap. */
    int width, height;		/* Dimensions of bitmap. */
    int native;			/* 0 means generic (X style) bitmap, 1 means
    				 * native style bitmap. */
} TkPredefBitmap;

/*
 * Tk keeps one of the following structures for each window. Some of the
 * information (like size and location) is a shadow of information managed by
 * the X server, and some is special information used here, such as event and
 * geometry management information. This information is (mostly) managed by
 * tkWindow.c. WARNING: the declaration below must be kept consistent with the
 * Tk_FakeWin structure in tk.h. If you change one, be sure to change the
 * other!
 */

typedef struct TkWindow {
    /*
     * Structural information:
     */

    Display *display;		/* Display containing window. */
    TkDisplay *dispPtr;		/* Tk's information about display for
				 * window. */
    int screenNum;		/* Index of screen for window, among all those
				 * for dispPtr. */
    Visual *visual;		/* Visual to use for window. If not default,
				 * MUST be set before X window is created. */
    int depth;			/* Number of bits/pixel. */
    Window window;		/* X's id for window. None means window hasn't
				 * actually been created yet, or it's been
				 * deleted. */
    struct TkWindow *childList;	/* First in list of child windows, or NULL if
				 * no children. List is in stacking order,
				 * lowest window first.*/
    struct TkWindow *lastChildPtr;
				/* Last in list of child windows (highest in
				 * stacking order), or NULL if no children. */
    struct TkWindow *parentPtr;	/* Pointer to parent window (logical parent,
				 * not necessarily X parent). NULL means
				 * either this is the main window, or the
				 * window's parent has already been deleted. */
    struct TkWindow *nextPtr;	/* Next higher sibling (in stacking order) in
				 * list of children with same parent. NULL
				 * means end of list. */
    TkMainInfo *mainPtr;	/* Information shared by all windows
				 * associated with a particular main window.
				 * NULL means this window is a rogue that is
				 * not associated with any application (at
				 * present, this only happens for the dummy
				 * windows used for "send" communication). */

    /*
     * Name and type information for the window:
     */

    char *pathName;		/* Path name of window (concatenation of all
				 * names between this window and its top-level
				 * ancestor). This is a pointer into an entry
				 * in mainPtr->nameTable. NULL means that the
				 * window hasn't been completely created
				 * yet. */
    Tk_Uid nameUid;		/* Name of the window within its parent
				 * (unique within the parent). */
    Tk_Uid classUid;		/* Class of the window. NULL means window
				 * hasn't been given a class yet. */

    /*
     * Geometry and other attributes of window. This information may not be
     * updated on the server immediately; stuff that hasn't been reflected in
     * the server yet is called "dirty". At present, information can be dirty
     * only if the window hasn't yet been created.
     */

    XWindowChanges changes;	/* Geometry and other info about window. */
    unsigned int dirtyChanges;	/* Bits indicate fields of "changes" that are
				 * dirty. */
    XSetWindowAttributes atts;	/* Current attributes of window. */
    unsigned long dirtyAtts;	/* Bits indicate fields of "atts" that are
				 * dirty. */

    unsigned int flags;		/* Various flag values: these are all defined
				 * in tk.h (confusing, but they're needed
				 * there for some query macros). */

    /*
     * Information kept by the event manager (tkEvent.c):
     */

    TkEventHandler *handlerList;/* First in list of event handlers declared
				 * for this window, or NULL if none. */
#ifdef TK_USE_INPUT_METHODS
    XIC inputContext;		/* XIM input context. */
#endif /* TK_USE_INPUT_METHODS */

    /*
     * Information used for event bindings (see "bind" and "bindtags" commands
     * in tkCmds.c):
     */

    ClientData *tagPtr;		/* Points to array of tags used for bindings
				 * on this window. Each tag is a Tk_Uid.
				 * Malloc'ed. NULL means no tags. */
    int numTags;		/* Number of tags at *tagPtr. */

    /*
     * Information used by tkOption.c to manage options for the window.
     */

    int optionLevel;		/* -1 means no option information is currently
				 * cached for this window. Otherwise this
				 * gives the level in the option stack at
				 * which info is cached. */
    /*
     * Information used by tkSelect.c to manage the selection.
     */

    struct TkSelHandler *selHandlerList;
				/* First in list of handlers for returning the
				 * selection in various forms. */

    /*
     * Information used by tkGeometry.c for geometry management.
     */

    const Tk_GeomMgr *geomMgrPtr;
				/* Information about geometry manager for this
				 * window. */
    ClientData geomData;	/* Argument for geometry manager functions. */
    int reqWidth, reqHeight;	/* Arguments from last call to
				 * Tk_GeometryRequest, or 0's if
				 * Tk_GeometryRequest hasn't been called. */
    int internalBorderLeft;	/* Width of internal border of window (0 means
				 * no internal border). Geometry managers
				 * should not normally place children on top
				 * of the border. Fields for the other three
				 * sides are found below. */

    /*
     * Information maintained by tkWm.c for window manager communication.
     */

    struct TkWmInfo *wmInfoPtr;	/* For top-level windows (and also for special
				 * Unix menubar and wrapper windows), points
				 * to structure with wm-related info (see
				 * tkWm.c). For other windows, this is
				 * NULL. */

    /*
     * Information used by widget classes.
     */

    const Tk_ClassProcs *classProcsPtr;
    ClientData instanceData;

    /*
     * Platform specific information private to each port.
     */

    struct TkWindowPrivate *privatePtr;

    /*
     * More information used by tkGeometry.c for geometry management.
     */

    /* The remaining fields of internal border. */
    int internalBorderRight;
    int internalBorderTop;
    int internalBorderBottom;

    int minReqWidth;		/* Minimum requested width. */
    int minReqHeight;		/* Minimum requested height. */
#ifdef TK_USE_INPUT_METHODS
    int ximGeneration;          /* Used to invalidate XIC */
#endif /* TK_USE_INPUT_METHODS */
    char *geomMgrName;          /* Records the name of the geometry manager. */
    struct TkWindow *maintainerPtr;
				/* The geometry container for this window. The
				 * value is NULL if the window has no container or
				 * if its container is its parent. */
} TkWindow;

/*
 * String tables:
 */

MODULE_SCOPE const char *const tkStateStrings[];
MODULE_SCOPE const char *const tkCompoundStrings[];

/*
 * Real definition of some events. Note that these events come from outside
 * but have internally generated pieces added to them.
 */

typedef struct {
    XKeyEvent keyEvent;		/* The real event from X11. */
#ifdef _WIN32
    char trans_chars[XMaxTransChars];
                            /* translated characters */
    unsigned char nbytes;
#elif !defined(MAC_OSX_TK)
    char *charValuePtr;		/* A pointer to a string that holds the key's
				 * %A substitution text (before backslash
				 * adding), or NULL if that has not been
				 * computed yet. If non-NULL, this string was
				 * allocated with ckalloc(). */
    int charValueLen;		/* Length of string in charValuePtr when that
				 * is non-NULL. */
    KeySym keysym;		/* Key symbol computed after input methods
				 * have been invoked */
#endif
} TkKeyEvent;

/*
 * Flags passed to TkpMakeMenuWindow's 'transient' argument.
 */

#define TK_MAKE_MENU_TEAROFF	0	/* Only non-transient case. */
#define TK_MAKE_MENU_POPUP	1
#define TK_MAKE_MENU_DROPDOWN	2

/*
 * The following structure is used with TkMakeEnsemble to create ensemble
 * commands and optionally to create sub-ensembles.
 */

typedef struct TkEnsemble {
    const char *name;
    Tcl_ObjCmdProc *proc;
    const struct TkEnsemble *subensemble;
} TkEnsemble;

/*
 * The following structure is used as a two way map between integers and
 * strings, usually to map between an internal C representation and the
 * strings used in Tcl.
 */

typedef struct TkStateMap {
    int numKey;			/* Integer representation of a value. */
    const char *strKey;		/* String representation of a value. */
} TkStateMap;

/*
 * This structure is used by the Mac and Window porting layers as the internal
 * representation of a clip_mask in a GC.
 */

typedef struct TkpClipMask {
    int type;			/* TKP_CLIP_PIXMAP or TKP_CLIP_REGION. */
    union {
	Pixmap pixmap;
	TkRegion region;
    } value;
} TkpClipMask;

#define TKP_CLIP_PIXMAP 0
#define TKP_CLIP_REGION 1

/*
 * Return values from TkGrabState:
 */

#define TK_GRAB_NONE		0
#define TK_GRAB_IN_TREE		1
#define TK_GRAB_ANCESTOR	2
#define TK_GRAB_EXCLUDED	3

/*
 * Additional flag for TkpMeasureCharsInContext. Coordinate with other flags
 * for this routine, but don't make public until TkpMeasureCharsInContext is
 * made public, too.
 */

#define TK_ISOLATE_END		32

/*
 * The macro below is used to modify a "char" value (e.g. by casting it to an
 * unsigned character) so that it can be used safely with macros such as
 * isspace().
 */

#define UCHAR(c) ((unsigned char) (c))

/*
 * The following symbol is used in the mode field of FocusIn events generated
 * by an embedded application to request the input focus from its container.
 */

#define EMBEDDED_APP_WANTS_FOCUS (NotifyNormal + 20)

/*
 * The following special modifier mask bits are defined, to indicate logical
 * modifiers such as Meta and Alt that may float among the actual modifier
 * bits.
 */

#define META_MASK	(AnyModifier<<1)
#define ALT_MASK	(AnyModifier<<2)
#define EXTENDED_MASK	(AnyModifier<<3)

/*
 * Mask that selects any of the state bits corresponding to buttons, plus
 * masks that select individual buttons' bits:
 */

#define ALL_BUTTONS \
	(Button1Mask|Button2Mask|Button3Mask|Button4Mask|Button5Mask)


MODULE_SCOPE unsigned TkGetButtonMask(unsigned);

/*
 * Object types not declared in tkObj.c need to be mentioned here so they can
 * be properly registered with Tcl:
 */

MODULE_SCOPE const Tcl_ObjType tkBorderObjType;
MODULE_SCOPE const Tcl_ObjType tkBitmapObjType;
MODULE_SCOPE const Tcl_ObjType tkColorObjType;
MODULE_SCOPE const Tcl_ObjType tkCursorObjType;
MODULE_SCOPE const Tcl_ObjType tkFontObjType;
MODULE_SCOPE const Tcl_ObjType tkStateKeyObjType;
MODULE_SCOPE const Tcl_ObjType tkTextIndexType;

/*
 * Miscellaneous variables shared among Tk modules but not exported to the
 * outside world:
 */

MODULE_SCOPE const Tk_SmoothMethod tkBezierSmoothMethod;
MODULE_SCOPE Tk_ImageType	tkBitmapImageType;
MODULE_SCOPE Tk_PhotoImageFormat tkImgFmtGIF;
MODULE_SCOPE void		(*tkHandleEventProc) (XEvent* eventPtr);
MODULE_SCOPE Tk_PhotoImageFormat tkImgFmtPNG;
MODULE_SCOPE Tk_PhotoImageFormat tkImgFmtPPM;
MODULE_SCOPE TkMainInfo		*tkMainWindowList;
MODULE_SCOPE Tk_ImageType	tkPhotoImageType;
MODULE_SCOPE Tcl_HashTable	tkPredefBitmapTable;

MODULE_SCOPE const char *const tkWebColors[20];

/*
 * The definition of pi, at least from the perspective of double-precision
 * floats.
 */

#ifndef PI
#ifdef M_PI
#define PI	M_PI
#else
#define PI	3.14159265358979323846
#endif
#endif

/*
 * Support for Clang Static Analyzer <https://clang-analyzer.llvm.org/>
 */

#if defined(PURIFY) && defined(__clang__)
#if __has_feature(attribute_analyzer_noreturn) && \
	!defined(Tcl_Panic) && defined(Tcl_Panic_TCL_DECLARED)
void Tcl_Panic(const char *, ...) __attribute__((analyzer_noreturn));
#endif
#if !defined(CLANG_ASSERT)
#define CLANG_ASSERT(x) assert(x)
#endif
#elif !defined(CLANG_ASSERT)
#define CLANG_ASSERT(x)
#endif /* PURIFY && __clang__ */

/*
 * The following magic value is stored in the "send_event" field of FocusIn
 * and FocusOut events. This allows us to separate "real" events coming from
 * the server from those that we generated.
 */

#define GENERATED_FOCUS_EVENT_MAGIC	((Bool) 0x547321ac)

/*
 * Exported internals.
 */

#include "tkIntDecls.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Themed widget set init function, and handler called when Tk is destroyed.
 */

MODULE_SCOPE int	Ttk_Init(Tcl_Interp *interp);
MODULE_SCOPE void	Ttk_TkDestroyedHandler(Tcl_Interp *interp);

/*
 * Internal functions shared among Tk modules but not exported to the outside
 * world:
 */

MODULE_SCOPE int	Tk_BellObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_BindObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_BindtagsObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_BusyObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ButtonObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_CanvasObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int argc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_CheckbuttonObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ClipboardObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ChooseColorObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ChooseDirectoryObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_DestroyObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_EntryObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_EventObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_FrameObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_FocusObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_FontObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_GetOpenFileObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_GetSaveFileObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_GrabObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_GridObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ImageObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_LabelObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_LabelframeObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ListboxObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_LowerObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_MenuObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_MenubuttonObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_MessageBoxObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_MessageObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_PanedWindowObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_OptionObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_PackObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_PlaceObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_RadiobuttonObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_RaiseObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ScaleObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ScrollbarObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_SelectionObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_SendObjCmd(ClientData clientData,
			    Tcl_Interp *interp,int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_SpinboxObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_TextObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_TkwaitObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_ToplevelObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_UpdateObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_WinfoObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE int	Tk_WmObjCmd(ClientData clientData, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);

MODULE_SCOPE int	Tk_GetDoublePixelsFromObj(Tcl_Interp *interp,
			    Tk_Window tkwin, Tcl_Obj *objPtr,
			    double *doublePtr);
#define TkSetGeometryContainer TkSetGeometryMaster
MODULE_SCOPE int	TkSetGeometryContainer(Tcl_Interp *interp,
			    Tk_Window tkwin, const char *name);
#define TkFreeGeometryContainer TkFreeGeometryMaster
MODULE_SCOPE void	TkFreeGeometryContainer(Tk_Window tkwin,
			    const char *name);

MODULE_SCOPE void	TkEventInit(void);
MODULE_SCOPE void	TkRegisterObjTypes(void);
MODULE_SCOPE int	TkDeadAppObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkCanvasGetCoordObj(Tcl_Interp *interp,
			    Tk_Canvas canvas, Tcl_Obj *obj,
			    double *doublePtr);
MODULE_SCOPE int	TkGetDoublePixels(Tcl_Interp *interp, Tk_Window tkwin,
			    const char *string, double *doublePtr);
MODULE_SCOPE int	TkPostscriptImage(Tcl_Interp *interp, Tk_Window tkwin,
			    Tk_PostscriptInfo psInfo, XImage *ximage,
			    int x, int y, int width, int height);
MODULE_SCOPE void       TkMapTopFrame(Tk_Window tkwin);
MODULE_SCOPE XEvent *	TkpGetBindingXEvent(Tcl_Interp *interp);
MODULE_SCOPE void	TkCreateExitHandler(Tcl_ExitProc *proc,
			    void *clientData);
MODULE_SCOPE void	TkDeleteExitHandler(Tcl_ExitProc *proc,
			    ClientData clientData);
MODULE_SCOPE Tcl_ExitProc	TkFinalize;
MODULE_SCOPE Tcl_ExitProc	TkFinalizeThread;
MODULE_SCOPE void	TkpBuildRegionFromAlphaData(TkRegion region,
			    unsigned x, unsigned y, unsigned width,
			    unsigned height, unsigned char *dataPtr,
			    unsigned pixelStride, unsigned lineStride);
MODULE_SCOPE void	TkAppendPadAmount(Tcl_Obj *bufferObj,
			    const char *buffer, int pad1, int pad2);
MODULE_SCOPE int	TkParsePadAmount(Tcl_Interp *interp,
			    Tk_Window tkwin, Tcl_Obj *objPtr,
			    int *pad1Ptr, int *pad2Ptr);
MODULE_SCOPE void       TkFocusSplit(TkWindow *winPtr);
MODULE_SCOPE void       TkFocusJoin(TkWindow *winPtr);
MODULE_SCOPE int	TkpAlwaysShowSelection(Tk_Window tkwin);
MODULE_SCOPE void	TkpDrawCharsInContext(Display * display,
			    Drawable drawable, GC gc, Tk_Font tkfont,
			    const char *source, int numBytes, int rangeStart,
			    int rangeLength, int x, int y);
MODULE_SCOPE void	TkpDrawAngledCharsInContext(Display * display,
			    Drawable drawable, GC gc, Tk_Font tkfont,
			    const char *source, int numBytes, int rangeStart,
			    int rangeLength, double x, double y, double angle);
MODULE_SCOPE int	TkpMeasureCharsInContext(Tk_Font tkfont,
			    const char *source, int numBytes, int rangeStart,
			    int rangeLength, int maxLength, int flags,
			    int *lengthPtr);
MODULE_SCOPE void	TkUnderlineCharsInContext(Display *display,
			    Drawable drawable, GC gc, Tk_Font tkfont,
			    const char *string, int numBytes, int x, int y,
			    int firstByte, int lastByte);
MODULE_SCOPE void	TkpGetFontAttrsForChar(Tk_Window tkwin, Tk_Font tkfont,
			    int c, struct TkFontAttributes *faPtr);
MODULE_SCOPE Tcl_Obj *	TkNewWindowObj(Tk_Window tkwin);
MODULE_SCOPE void	TkpShowBusyWindow(TkBusy busy);
MODULE_SCOPE void	TkpHideBusyWindow(TkBusy busy);
MODULE_SCOPE void	TkpMakeTransparentWindowExist(Tk_Window tkwin,
			    Window parent);
MODULE_SCOPE void	TkpCreateBusy(Tk_FakeWin *winPtr, Tk_Window tkRef,
			    Window *parentPtr, Tk_Window tkParent,
			    TkBusy busy);
MODULE_SCOPE int	TkBackgroundEvalObjv(Tcl_Interp *interp,
			    int objc, Tcl_Obj *const *objv, int flags);
MODULE_SCOPE void	TkSendVirtualEvent(Tk_Window tgtWin,
			    const char *eventName, Tcl_Obj *detail);
MODULE_SCOPE Tcl_Command TkMakeEnsemble(Tcl_Interp *interp,
			    const char *nsname, const char *name,
			    ClientData clientData, const TkEnsemble *map);
MODULE_SCOPE int	TkInitTkCmd(Tcl_Interp *interp,
			    ClientData clientData);
MODULE_SCOPE int	TkInitFontchooser(Tcl_Interp *interp,
			    ClientData clientData);
MODULE_SCOPE void	TkpWarpPointer(TkDisplay *dispPtr);
MODULE_SCOPE void	TkpCancelWarp(TkDisplay *dispPtr);
MODULE_SCOPE int	TkListCreateFrame(ClientData clientData,
			    Tcl_Interp *interp, Tcl_Obj *listObj,
			    int toplevel, Tcl_Obj *nameObj);

#ifdef _WIN32
#define TkParseColor XParseColor
#else
MODULE_SCOPE Status TkParseColor (Display * display,
				Colormap map, const char* spec,
				XColor * colorPtr);
#endif
#ifdef HAVE_XFT
MODULE_SCOPE void	TkUnixSetXftClipRegion(TkRegion clipRegion);
#endif

MODULE_SCOPE void	TkpCopyRegion(TkRegion dst, TkRegion src);

#if !defined(__cplusplus) && !defined(c_plusplus)
# define c_class class
#endif

/* Tcl 8.6 has a different definition of Tcl_UniChar than other Tcl versions for TCL_UTF_MAX > 3 */
#if TCL_UTF_MAX > (3 + (TCL_MAJOR_VERSION == 8 && TCL_MINOR_VERSION == 6))
#   define TkUtfToUniChar Tcl_UtfToUniChar
#   define TkUniCharToUtf Tcl_UniCharToUtf
#   define TkUtfPrev Tcl_UtfPrev
#   define TkUtfAtIndex Tcl_UtfAtIndex
#else
    MODULE_SCOPE int TkUtfToUniChar(const char *, int *);
    MODULE_SCOPE int TkUniCharToUtf(int, char *);
    MODULE_SCOPE const char *TkUtfPrev(const char *, const char *);
    MODULE_SCOPE const char *TkUtfAtIndex(const char *src, int index);
#endif

/*
 * Unsupported commands.
 */

MODULE_SCOPE int	TkUnsupported1ObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[]);

/*
 * For Tktest.
 */
MODULE_SCOPE int SquareObjCmd(ClientData clientData,
			    Tcl_Interp *interp, int objc,
			    Tcl_Obj * const objv[]);
MODULE_SCOPE int	TkOldTestInit(Tcl_Interp *interp);
#if !(defined(_WIN32) || defined(MAC_OSX_TK))
#define TkplatformtestInit(x) TCL_OK
#else
MODULE_SCOPE int	TkplatformtestInit(Tcl_Interp *interp);
#endif

#ifdef __cplusplus
}
#endif

#endif /* _TKINT */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
