/*
 * tk.h --
 *
 *	Declarations for Tk-related things that are visible outside of the Tk
 *	module itself.
 *
 * Copyright (c) 1989-1994 The Regents of the University of California.
 * Copyright (c) 1994 The Australian National University.
 * Copyright (c) 1994-1998 Sun Microsystems, Inc.
 * Copyright (c) 1998-2000 Ajuba Solutions.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TK
#define _TK

#include <tcl.h>
#if (TCL_MAJOR_VERSION != 8) || (TCL_MINOR_VERSION < 6)
#	error Tk 8.6 must be compiled with tcl.h from Tcl 8.6 or better
#endif

#ifndef CONST84
#   define CONST84 const
#   define CONST84_RETURN const
#endif
#ifndef CONST86
#   define CONST86 CONST84
#endif
#ifndef EXTERN
#   define EXTERN extern TCL_STORAGE_CLASS
#endif

/*
 * Utility macros: STRINGIFY takes an argument and wraps it in "" (double
 * quotation marks), JOIN joins two arguments.
 */

#ifndef STRINGIFY
#  define STRINGIFY(x) STRINGIFY1(x)
#  define STRINGIFY1(x) #x
#endif
#ifndef JOIN
#  define JOIN(a,b) JOIN1(a,b)
#  define JOIN1(a,b) a##b
#endif

/*
 * For C++ compilers, use extern "C"
 */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * When version numbers change here, you must also go into the following files
 * and update the version numbers:
 *
 * library/tk.tcl	(1 LOC patch)
 * unix/configure.in	(2 LOC Major, 2 LOC minor, 1 LOC patch)
 * win/configure.in	(as above)
 * README		(sections 0 and 1)
 * macosx/Tk-Common.xcconfig (not patchlevel) 1 LOC
 * win/README		(not patchlevel)
 * unix/README		(not patchlevel)
 * unix/tk.spec		(1 LOC patch)
 * win/tcl.m4		(not patchlevel)
 *
 * You may also need to update some of these files when the numbers change for
 * the version of Tcl that this release of Tk is compiled against.
 */

#define TK_MAJOR_VERSION	8
#define TK_MINOR_VERSION	6
#define TK_RELEASE_LEVEL	TCL_FINAL_RELEASE
#define TK_RELEASE_SERIAL	14

#define TK_VERSION		"8.6"
#define TK_PATCH_LEVEL		"8.6.14"

/*
 * A special definition used to allow this header file to be included from
 * windows or mac resource files so that they can obtain version information.
 * RC_INVOKED is defined by default by the windows RC tool and manually set
 * for macintosh.
 *
 * Resource compilers don't like all the C stuff, like typedefs and procedure
 * declarations, that occur below, so block them out.
 */

#ifndef RC_INVOKED

#if !defined(_XLIB_H) && !defined(_X11_XLIB_H_)
#if defined(__GNUC__) && !defined(__cplusplus)
#   pragma GCC diagnostic ignored "-Wc++-compat"
#endif
#   include <X11/Xlib.h>
#   ifdef MAC_OSX_TK
#	include <X11/X.h>
#   endif
#endif
#if defined(STDC_HEADERS) || defined(__STDC__) || defined(__C99__FUNC__) \
     || defined(__cplusplus) || defined(_MSC_VER) || defined(__ICC)
#   include <stddef.h>
#endif

#ifdef BUILD_tk
#undef TCL_STORAGE_CLASS
#define TCL_STORAGE_CLASS	DLLEXPORT
#endif

/*
 *----------------------------------------------------------------------
 *
 * Decide whether or not to use input methods.
 */

#if defined(XNQueryInputStyle) && !defined(_WIN32) && !defined(MAC_OSX_TK)
#define TK_USE_INPUT_METHODS
#endif

/*
 * Dummy types that are used by clients:
 */

#define Tk_ImageModel Tk_ImageMaster
typedef struct Tk_BindingTable_ *Tk_BindingTable;
typedef struct Tk_Canvas_ *Tk_Canvas;
typedef struct Tk_Cursor_ *Tk_Cursor;
typedef struct Tk_ErrorHandler_ *Tk_ErrorHandler;
typedef struct Tk_Font_ *Tk_Font;
typedef struct Tk_Image__ *Tk_Image;
typedef struct Tk_ImageMaster_ *Tk_ImageMaster;
typedef struct Tk_OptionTable_ *Tk_OptionTable;
typedef struct Tk_PostscriptInfo_ *Tk_PostscriptInfo;
typedef struct Tk_TextLayout_ *Tk_TextLayout;
typedef struct Tk_Window_ *Tk_Window;
typedef struct Tk_3DBorder_ *Tk_3DBorder;
typedef struct Tk_Style_ *Tk_Style;
typedef struct Tk_StyleEngine_ *Tk_StyleEngine;
typedef struct Tk_StyledElement_ *Tk_StyledElement;

/*
 * Additional types exported to clients.
 */

typedef const char *Tk_Uid;

/*
 *----------------------------------------------------------------------
 *
 * The enum below defines the valid types for Tk configuration options as
 * implemented by Tk_InitOptions, Tk_SetOptions, etc.
 */

typedef enum {
    TK_OPTION_BOOLEAN,
    TK_OPTION_INT,
    TK_OPTION_DOUBLE,
    TK_OPTION_STRING,
    TK_OPTION_STRING_TABLE,
    TK_OPTION_COLOR,
    TK_OPTION_FONT,
    TK_OPTION_BITMAP,
    TK_OPTION_BORDER,
    TK_OPTION_RELIEF,
    TK_OPTION_CURSOR,
    TK_OPTION_JUSTIFY,
    TK_OPTION_ANCHOR,
    TK_OPTION_SYNONYM,
    TK_OPTION_PIXELS,
    TK_OPTION_WINDOW,
    TK_OPTION_END,
    TK_OPTION_CUSTOM,
    TK_OPTION_STYLE
} Tk_OptionType;

/*
 * Structures of the following type are used by widgets to specify their
 * configuration options. Typically each widget has a static array of these
 * structures, where each element of the array describes a single
 * configuration option. The array is passed to Tk_CreateOptionTable.
 */

typedef struct Tk_OptionSpec {
    Tk_OptionType type;		/* Type of option, such as TK_OPTION_COLOR;
				 * see definitions above. Last option in table
				 * must have type TK_OPTION_END. */
    const char *optionName;	/* Name used to specify option in Tcl
				 * commands. */
    const char *dbName;		/* Name for option in option database. */
    const char *dbClass;	/* Class for option in database. */
    const char *defValue;	/* Default value for option if not specified
				 * in command line, the option database, or
				 * the system. */
    int objOffset;		/* Where in record to store a Tcl_Obj * that
				 * holds the value of this option, specified
				 * as an offset in bytes from the start of the
				 * record. Use the Tk_Offset macro to generate
				 * values for this. -1 means don't store the
				 * Tcl_Obj in the record. */
    int internalOffset;		/* Where in record to store the internal
				 * representation of the value of this option,
				 * such as an int or XColor *. This field is
				 * specified as an offset in bytes from the
				 * start of the record. Use the Tk_Offset
				 * macro to generate values for it. -1 means
				 * don't store the internal representation in
				 * the record. */
    int flags;			/* Any combination of the values defined
				 * below. */
    const void *clientData;	/* An alternate place to put option-specific
				 * data. Used for the monochrome default value
				 * for colors, etc. */
    int typeMask;		/* An arbitrary bit mask defined by the class
				 * manager; typically bits correspond to
				 * certain kinds of options such as all those
				 * that require a redisplay when they change.
				 * Tk_SetOptions returns the bit-wise OR of
				 * the typeMasks of all options that were
				 * changed. */
} Tk_OptionSpec;

/*
 * Flag values for Tk_OptionSpec structures. These flags are shared by
 * Tk_ConfigSpec structures, so be sure to coordinate any changes carefully.
 */

#define TK_OPTION_NULL_OK		(1 << 0)
#define TK_OPTION_DONT_SET_DEFAULT	(1 << 3)

/*
 * The following structure and function types are used by TK_OPTION_CUSTOM
 * options; the structure holds pointers to the functions needed by the Tk
 * option config code to handle a custom option.
 */

typedef int (Tk_CustomOptionSetProc) (ClientData clientData,
	Tcl_Interp *interp, Tk_Window tkwin, Tcl_Obj **value, char *widgRec,
	int offset, char *saveInternalPtr, int flags);
typedef Tcl_Obj *(Tk_CustomOptionGetProc) (ClientData clientData,
	Tk_Window tkwin, char *widgRec, int offset);
typedef void (Tk_CustomOptionRestoreProc) (ClientData clientData,
	Tk_Window tkwin, char *internalPtr, char *saveInternalPtr);
typedef void (Tk_CustomOptionFreeProc) (ClientData clientData, Tk_Window tkwin,
	char *internalPtr);

typedef struct Tk_ObjCustomOption {
    const char *name;		/* Name of the custom option. */
    Tk_CustomOptionSetProc *setProc;
				/* Function to use to set a record's option
				 * value from a Tcl_Obj */
    Tk_CustomOptionGetProc *getProc;
				/* Function to use to get a Tcl_Obj
				 * representation from an internal
				 * representation of an option. */
    Tk_CustomOptionRestoreProc *restoreProc;
				/* Function to use to restore a saved value
				 * for the internal representation. */
    Tk_CustomOptionFreeProc *freeProc;
				/* Function to use to free the internal
				 * representation of an option. */
    ClientData clientData;	/* Arbitrary one-word value passed to the
				 * handling procs. */
} Tk_ObjCustomOption;

/*
 * Macro to use to fill in "offset" fields of the Tk_OptionSpec structure.
 * Computes number of bytes from beginning of structure to a given field.
 */

#define Tk_Offset(type, field) ((int) offsetof(type, field))
/* Workaround for platforms missing offsetof(), e.g. VC++ 6.0 */
#ifndef offsetof
#   define offsetof(type, field) ((size_t) ((char *) &((type *) 0)->field))
#endif

/*
 * The following two structures are used for error handling. When config
 * options are being modified, the old values are saved in a Tk_SavedOptions
 * structure. If an error occurs, then the contents of the structure can be
 * used to restore all of the old values. The contents of this structure are
 * for the private use Tk. No-one outside Tk should ever read or write any of
 * the fields of these structures.
 */

typedef struct Tk_SavedOption {
    struct TkOption *optionPtr;	/* Points to information that describes the
				 * option. */
    Tcl_Obj *valuePtr;		/* The old value of the option, in the form of
				 * a Tcl object; may be NULL if the value was
				 * not saved as an object. */
    double internalForm;	/* The old value of the option, in some
				 * internal representation such as an int or
				 * (XColor *). Valid only if the field
				 * optionPtr->specPtr->objOffset is < 0. The
				 * space must be large enough to accommodate a
				 * double, a long, or a pointer; right now it
				 * looks like a double (i.e., 8 bytes) is big
				 * enough. Also, using a double guarantees
				 * that the field is properly aligned for
				 * storing large values. */
} Tk_SavedOption;

#ifdef TCL_MEM_DEBUG
#   define TK_NUM_SAVED_OPTIONS 2
#else
#   define TK_NUM_SAVED_OPTIONS 20
#endif

typedef struct Tk_SavedOptions {
    char *recordPtr;		/* The data structure in which to restore
				 * configuration options. */
    Tk_Window tkwin;		/* Window associated with recordPtr; needed to
				 * restore certain options. */
    int numItems;		/* The number of valid items in items field. */
    Tk_SavedOption items[TK_NUM_SAVED_OPTIONS];
				/* Items used to hold old values. */
    struct Tk_SavedOptions *nextPtr;
				/* Points to next structure in list; needed if
				 * too many options changed to hold all the
				 * old values in a single structure. NULL
				 * means no more structures. */
} Tk_SavedOptions;

/*
 * Structure used to describe application-specific configuration options:
 * indicates procedures to call to parse an option and to return a text string
 * describing an option. THESE ARE DEPRECATED; PLEASE USE THE NEW STRUCTURES
 * LISTED ABOVE.
 */

/*
 * This is a temporary flag used while tkObjConfig and new widgets are in
 * development.
 */

#ifndef __NO_OLD_CONFIG

typedef int (Tk_OptionParseProc) (ClientData clientData, Tcl_Interp *interp,
	Tk_Window tkwin, CONST84 char *value, char *widgRec, int offset);
typedef CONST86 char *(Tk_OptionPrintProc) (ClientData clientData,
	Tk_Window tkwin, char *widgRec, int offset, Tcl_FreeProc **freeProcPtr);

typedef struct Tk_CustomOption {
    Tk_OptionParseProc *parseProc;
				/* Procedure to call to parse an option and
				 * store it in converted form. */
    Tk_OptionPrintProc *printProc;
				/* Procedure to return a printable string
				 * describing an existing option. */
    ClientData clientData;	/* Arbitrary one-word value used by option
				 * parser: passed to parseProc and
				 * printProc. */
} Tk_CustomOption;

/*
 * Structure used to specify information for Tk_ConfigureWidget. Each
 * structure gives complete information for one option, including how the
 * option is specified on the command line, where it appears in the option
 * database, etc.
 */

typedef struct Tk_ConfigSpec {
    int type;			/* Type of option, such as TK_CONFIG_COLOR;
				 * see definitions below. Last option in table
				 * must have type TK_CONFIG_END. */
    CONST86 char *argvName;	/* Switch used to specify option in argv. NULL
				 * means this spec is part of a group. */
    Tk_Uid dbName;		/* Name for option in option database. */
    Tk_Uid dbClass;		/* Class for option in database. */
    Tk_Uid defValue;		/* Default value for option if not specified
				 * in command line or database. */
    int offset;			/* Where in widget record to store value; use
				 * Tk_Offset macro to generate values for
				 * this. */
    int specFlags;		/* Any combination of the values defined
				 * below; other bits are used internally by
				 * tkConfig.c. */
    CONST86 Tk_CustomOption *customPtr;
				/* If type is TK_CONFIG_CUSTOM then this is a
				 * pointer to info about how to parse and
				 * print the option. Otherwise it is
				 * irrelevant. */
} Tk_ConfigSpec;

/*
 * Type values for Tk_ConfigSpec structures. See the user documentation for
 * details.
 */

typedef enum {
    TK_CONFIG_BOOLEAN, TK_CONFIG_INT, TK_CONFIG_DOUBLE, TK_CONFIG_STRING,
    TK_CONFIG_UID, TK_CONFIG_COLOR, TK_CONFIG_FONT, TK_CONFIG_BITMAP,
    TK_CONFIG_BORDER, TK_CONFIG_RELIEF, TK_CONFIG_CURSOR,
    TK_CONFIG_ACTIVE_CURSOR, TK_CONFIG_JUSTIFY, TK_CONFIG_ANCHOR,
    TK_CONFIG_SYNONYM, TK_CONFIG_CAP_STYLE, TK_CONFIG_JOIN_STYLE,
    TK_CONFIG_PIXELS, TK_CONFIG_MM, TK_CONFIG_WINDOW, TK_CONFIG_CUSTOM,
    TK_CONFIG_END
} Tk_ConfigTypes;

/*
 * Possible values for flags argument to Tk_ConfigureWidget:
 */

#define TK_CONFIG_ARGV_ONLY	1
#define TK_CONFIG_OBJS		0x80

/*
 * Possible flag values for Tk_ConfigSpec structures. Any bits at or above
 * TK_CONFIG_USER_BIT may be used by clients for selecting certain entries.
 * Before changing any values here, coordinate with tkOldConfig.c
 * (internal-use-only flags are defined there).
 */

#define TK_CONFIG_NULL_OK		(1 << 0)
#define TK_CONFIG_COLOR_ONLY		(1 << 1)
#define TK_CONFIG_MONO_ONLY		(1 << 2)
#define TK_CONFIG_DONT_SET_DEFAULT	(1 << 3)
#define TK_CONFIG_OPTION_SPECIFIED      (1 << 4)
#define TK_CONFIG_USER_BIT		0x100
#endif /* __NO_OLD_CONFIG */

/*
 * Structure used to specify how to handle argv options.
 */

typedef struct {
    CONST86 char *key;		/* The key string that flags the option in the
				 * argv array. */
    int type;			/* Indicates option type; see below. */
    char *src;			/* Value to be used in setting dst; usage
				 * depends on type. */
    char *dst;			/* Address of value to be modified; usage
				 * depends on type. */
    CONST86 char *help;		/* Documentation message describing this
				 * option. */
} Tk_ArgvInfo;

/*
 * Legal values for the type field of a Tk_ArgvInfo: see the user
 * documentation for details.
 */

#define TK_ARGV_CONSTANT		15
#define TK_ARGV_INT			16
#define TK_ARGV_STRING			17
#define TK_ARGV_UID			18
#define TK_ARGV_REST			19
#define TK_ARGV_FLOAT			20
#define TK_ARGV_FUNC			21
#define TK_ARGV_GENFUNC			22
#define TK_ARGV_HELP			23
#define TK_ARGV_CONST_OPTION		24
#define TK_ARGV_OPTION_VALUE		25
#define TK_ARGV_OPTION_NAME_VALUE	26
#define TK_ARGV_END			27

/*
 * Flag bits for passing to Tk_ParseArgv:
 */

#define TK_ARGV_NO_DEFAULTS		0x1
#define TK_ARGV_NO_LEFTOVERS		0x2
#define TK_ARGV_NO_ABBREV		0x4
#define TK_ARGV_DONT_SKIP_FIRST_ARG	0x8

/*
 * Enumerated type for describing actions to be taken in response to a
 * restrictProc established by Tk_RestrictEvents.
 */

typedef enum {
    TK_DEFER_EVENT, TK_PROCESS_EVENT, TK_DISCARD_EVENT
} Tk_RestrictAction;

/*
 * Priority levels to pass to Tk_AddOption:
 */

#define TK_WIDGET_DEFAULT_PRIO	20
#define TK_STARTUP_FILE_PRIO	40
#define TK_USER_DEFAULT_PRIO	60
#define TK_INTERACTIVE_PRIO	80
#define TK_MAX_PRIO		100

/*
 * Relief values returned by Tk_GetRelief:
 */

#define TK_RELIEF_NULL		-1
#define TK_RELIEF_FLAT		0
#define TK_RELIEF_GROOVE	1
#define TK_RELIEF_RAISED	2
#define TK_RELIEF_RIDGE		3
#define TK_RELIEF_SOLID		4
#define TK_RELIEF_SUNKEN	5

/*
 * "Which" argument values for Tk_3DBorderGC:
 */

#define TK_3D_FLAT_GC		1
#define TK_3D_LIGHT_GC		2
#define TK_3D_DARK_GC		3

/*
 * Special EnterNotify/LeaveNotify "mode" for use in events generated by
 * tkShare.c. Pick a high enough value that it's unlikely to conflict with
 * existing values (like NotifyNormal) or any new values defined in the
 * future.
 */

#define TK_NOTIFY_SHARE		20

/*
 * Enumerated type for describing a point by which to anchor something:
 */

typedef enum {
    TK_ANCHOR_N, TK_ANCHOR_NE, TK_ANCHOR_E, TK_ANCHOR_SE,
    TK_ANCHOR_S, TK_ANCHOR_SW, TK_ANCHOR_W, TK_ANCHOR_NW,
    TK_ANCHOR_CENTER
} Tk_Anchor;

/*
 * Enumerated type for describing a style of justification:
 */

typedef enum {
    TK_JUSTIFY_LEFT, TK_JUSTIFY_RIGHT, TK_JUSTIFY_CENTER
} Tk_Justify;

/*
 * The following structure is used by Tk_GetFontMetrics() to return
 * information about the properties of a Tk_Font.
 */

typedef struct Tk_FontMetrics {
    int ascent;			/* The amount in pixels that the tallest
				 * letter sticks up above the baseline, plus
				 * any extra blank space added by the designer
				 * of the font. */
    int descent;		/* The largest amount in pixels that any
				 * letter sticks below the baseline, plus any
				 * extra blank space added by the designer of
				 * the font. */
    int linespace;		/* The sum of the ascent and descent. How far
				 * apart two lines of text in the same font
				 * should be placed so that none of the
				 * characters in one line overlap any of the
				 * characters in the other line. */
} Tk_FontMetrics;

/*
 * Flags passed to Tk_MeasureChars:
 */

#define TK_WHOLE_WORDS		1
#define TK_AT_LEAST_ONE		2
#define TK_PARTIAL_OK		4

/*
 * Flags passed to Tk_ComputeTextLayout:
 */

#define TK_IGNORE_TABS		8
#define TK_IGNORE_NEWLINES	16

/*
 * Widget class procedures used to implement platform specific widget
 * behavior.
 */

typedef Window (Tk_ClassCreateProc) (Tk_Window tkwin, Window parent,
	ClientData instanceData);
typedef void (Tk_ClassWorldChangedProc) (ClientData instanceData);
typedef void (Tk_ClassModalProc) (Tk_Window tkwin, XEvent *eventPtr);

typedef struct Tk_ClassProcs {
    unsigned int size;
    Tk_ClassWorldChangedProc *worldChangedProc;
				/* Procedure to invoke when the widget needs
				 * to respond in some way to a change in the
				 * world (font changes, etc.) */
    Tk_ClassCreateProc *createProc;
				/* Procedure to invoke when the platform-
				 * dependent window needs to be created. */
    Tk_ClassModalProc *modalProc;
				/* Procedure to invoke after all bindings on a
				 * widget have been triggered in order to
				 * handle a modal loop. */
} Tk_ClassProcs;

/*
 * Simple accessor for Tk_ClassProcs structure. Checks that the structure is
 * not NULL, then checks the size field and returns either the requested
 * field, if present, or NULL if the structure is too small to have the field
 * (or NULL if the structure is NULL).
 *
 * A more general version of this function may be useful if other
 * size-versioned structure pop up in the future:
 *
 *	#define Tk_GetField(name, who, which) \
 *	    (((who) == NULL) ? NULL :
 *	    (((who)->size <= Tk_Offset(name, which)) ? NULL :(name)->which))
 */

#define Tk_GetClassProc(procs, which) \
    (((procs) == NULL) ? NULL : \
    (((procs)->size <= Tk_Offset(Tk_ClassProcs, which)) ? NULL:(procs)->which))

/*
 * Each geometry manager (the packer, the placer, etc.) is represented by a
 * structure of the following form, which indicates procedures to invoke in
 * the geometry manager to carry out certain functions.
 */

#define Tk_GeomLostContentProc Tk_GeomLostSlaveProc
typedef void (Tk_GeomRequestProc) (ClientData clientData, Tk_Window tkwin);
typedef void (Tk_GeomLostContentProc) (ClientData clientData, Tk_Window tkwin);

typedef struct Tk_GeomMgr {
    const char *name;		/* Name of the geometry manager (command used
				 * to invoke it, or name of widget class that
				 * allows embedded widgets). */
    Tk_GeomRequestProc *requestProc;
				/* Procedure to invoke when a content's
				 * requested geometry changes. */
    Tk_GeomLostContentProc *lostSlaveProc;
				/* Procedure to invoke when content is taken
				 * away from one geometry manager by another.
				 * NULL means geometry manager doesn't care
				 * when content lost. */
} Tk_GeomMgr;

/*
 * Result values returned by Tk_GetScrollInfo:
 */

#define TK_SCROLL_MOVETO	1
#define TK_SCROLL_PAGES		2
#define TK_SCROLL_UNITS		3
#define TK_SCROLL_ERROR		4

/*
 *----------------------------------------------------------------------
 *
 * Extensions to the X event set
 *
 *----------------------------------------------------------------------
 */

#define VirtualEvent	    (MappingNotify + 1)
#define ActivateNotify	    (MappingNotify + 2)
#define DeactivateNotify    (MappingNotify + 3)
#define MouseWheelEvent     (MappingNotify + 4)
#define TK_LASTEVENT	    (MappingNotify + 5)

#define MouseWheelMask	    (1L << 28)
#define ActivateMask	    (1L << 29)
#define VirtualEventMask    (1L << 30)

/*
 * A virtual event shares most of its fields with the XKeyEvent and
 * XButtonEvent structures. 99% of the time a virtual event will be an
 * abstraction of a key or button event, so this structure provides the most
 * information to the user. The only difference is the changing of the detail
 * field for a virtual event so that it holds the name of the virtual event
 * being triggered.
 *
 * When using this structure, you should ensure that you zero out all the
 * fields first using memset() or bzero().
 */

typedef struct {
    int type;
    unsigned long serial;	/* # of last request processed by server. */
    Bool send_event;		/* True if this came from a SendEvent
				 * request. */
    Display *display;		/* Display the event was read from. */
    Window event;		/* Window on which event was requested. */
    Window root;		/* Root window that the event occurred on. */
    Window subwindow;		/* Child window. */
    Time time;			/* Milliseconds. */
    int x, y;			/* Pointer x, y coordinates in event
				 * window. */
    int x_root, y_root;		/* Coordinates relative to root. */
    unsigned int state;		/* Key or button mask */
    Tk_Uid name;		/* Name of virtual event. */
    Bool same_screen;		/* Same screen flag. */
    Tcl_Obj *user_data;		/* Application-specific data reference; Tk
				 * will decrement the reference count *once*
				 * when it has finished processing the
				 * event. */
} XVirtualEvent;

typedef struct {
    int type;
    unsigned long serial;	/* # of last request processed by server. */
    Bool send_event;		/* True if this came from a SendEvent
				 * request. */
    Display *display;		/* Display the event was read from. */
    Window window;		/* Window in which event occurred. */
} XActivateDeactivateEvent;
typedef XActivateDeactivateEvent XActivateEvent;
typedef XActivateDeactivateEvent XDeactivateEvent;

/*
 *----------------------------------------------------------------------
 *
 * Macros for querying Tk_Window structures. See the manual entries for
 * documentation.
 *
 *----------------------------------------------------------------------
 */

#define Tk_Display(tkwin)	(((Tk_FakeWin *) (tkwin))->display)
#define Tk_ScreenNumber(tkwin)	(((Tk_FakeWin *) (tkwin))->screenNum)
#define Tk_Screen(tkwin) \
    (ScreenOfDisplay(Tk_Display(tkwin), Tk_ScreenNumber(tkwin)))
#define Tk_Depth(tkwin)		(((Tk_FakeWin *) (tkwin))->depth)
#define Tk_Visual(tkwin)	(((Tk_FakeWin *) (tkwin))->visual)
#define Tk_WindowId(tkwin)	(((Tk_FakeWin *) (tkwin))->window)
#define Tk_PathName(tkwin) 	(((Tk_FakeWin *) (tkwin))->pathName)
#define Tk_Name(tkwin)		(((Tk_FakeWin *) (tkwin))->nameUid)
#define Tk_Class(tkwin) 	(((Tk_FakeWin *) (tkwin))->classUid)
#define Tk_X(tkwin)		(((Tk_FakeWin *) (tkwin))->changes.x)
#define Tk_Y(tkwin)		(((Tk_FakeWin *) (tkwin))->changes.y)
#define Tk_Width(tkwin)		(((Tk_FakeWin *) (tkwin))->changes.width)
#define Tk_Height(tkwin) \
    (((Tk_FakeWin *) (tkwin))->changes.height)
#define Tk_Changes(tkwin)	(&((Tk_FakeWin *) (tkwin))->changes)
#define Tk_Attributes(tkwin)	(&((Tk_FakeWin *) (tkwin))->atts)
#define Tk_IsEmbedded(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_EMBEDDED)
#define Tk_IsContainer(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_CONTAINER)
#define Tk_IsMapped(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_MAPPED)
#define Tk_IsTopLevel(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_TOP_LEVEL)
#define Tk_HasWrapper(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_HAS_WRAPPER)
#define Tk_WinManaged(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_WIN_MANAGED)
#define Tk_TopWinHierarchy(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_TOP_HIERARCHY)
#define Tk_IsManageable(tkwin) \
    (((Tk_FakeWin *) (tkwin))->flags & TK_WM_MANAGEABLE)
#define Tk_ReqWidth(tkwin)	(((Tk_FakeWin *) (tkwin))->reqWidth)
#define Tk_ReqHeight(tkwin)	(((Tk_FakeWin *) (tkwin))->reqHeight)
/* Tk_InternalBorderWidth is deprecated */
#define Tk_InternalBorderWidth(tkwin) \
    (((Tk_FakeWin *) (tkwin))->internalBorderLeft)
#define Tk_InternalBorderLeft(tkwin) \
    (((Tk_FakeWin *) (tkwin))->internalBorderLeft)
#define Tk_InternalBorderRight(tkwin) \
    (((Tk_FakeWin *) (tkwin))->internalBorderRight)
#define Tk_InternalBorderTop(tkwin) \
    (((Tk_FakeWin *) (tkwin))->internalBorderTop)
#define Tk_InternalBorderBottom(tkwin) \
    (((Tk_FakeWin *) (tkwin))->internalBorderBottom)
#define Tk_MinReqWidth(tkwin)	(((Tk_FakeWin *) (tkwin))->minReqWidth)
#define Tk_MinReqHeight(tkwin)	(((Tk_FakeWin *) (tkwin))->minReqHeight)
#define Tk_Parent(tkwin)	(((Tk_FakeWin *) (tkwin))->parentPtr)
#define Tk_Colormap(tkwin)	(((Tk_FakeWin *) (tkwin))->atts.colormap)

/*
 * The structure below is needed by the macros above so that they can access
 * the fields of a Tk_Window. The fields not needed by the macros are declared
 * as "dummyX". The structure has its own type in order to prevent apps from
 * accessing Tk_Window fields except using official macros. WARNING!! The
 * structure definition must be kept consistent with the TkWindow structure in
 * tkInt.h. If you change one, then change the other. See the declaration in
 * tkInt.h for documentation on what the fields are used for internally.
 */

typedef struct Tk_FakeWin {
    Display *display;
    char *dummy1;		/* dispPtr */
    int screenNum;
    Visual *visual;
    int depth;
    Window window;
    char *dummy2;		/* childList */
    char *dummy3;		/* lastChildPtr */
    Tk_Window parentPtr;	/* parentPtr */
    char *dummy4;		/* nextPtr */
    char *dummy5;		/* mainPtr */
    char *pathName;
    Tk_Uid nameUid;
    Tk_Uid classUid;
    XWindowChanges changes;
    unsigned int dummy6;	/* dirtyChanges */
    XSetWindowAttributes atts;
    unsigned long dummy7;	/* dirtyAtts */
    unsigned int flags;
    char *dummy8;		/* handlerList */
#ifdef TK_USE_INPUT_METHODS
    XIC dummy9;			/* inputContext */
#endif /* TK_USE_INPUT_METHODS */
    ClientData *dummy10;	/* tagPtr */
    int dummy11;		/* numTags */
    int dummy12;		/* optionLevel */
    char *dummy13;		/* selHandlerList */
    char *dummy14;		/* geomMgrPtr */
    ClientData dummy15;		/* geomData */
    int reqWidth, reqHeight;
    int internalBorderLeft;
    char *dummy16;		/* wmInfoPtr */
    char *dummy17;		/* classProcPtr */
    ClientData dummy18;		/* instanceData */
    char *dummy19;		/* privatePtr */
    int internalBorderRight;
    int internalBorderTop;
    int internalBorderBottom;
    int minReqWidth;
    int minReqHeight;
#ifdef TK_USE_INPUT_METHODS
    int dummy20;
#endif /* TK_USE_INPUT_METHODS */
    char *dummy21;		/* geomMgrName */
    Tk_Window dummy22;		/* maintainerPtr */
} Tk_FakeWin;

/*
 * Flag values for TkWindow (and Tk_FakeWin) structures are:
 *
 * TK_MAPPED:			1 means window is currently mapped,
 *				0 means unmapped.
 * TK_TOP_LEVEL:		1 means this is a top-level widget.
 * TK_ALREADY_DEAD:		1 means the window is in the process of
 *				being destroyed already.
 * TK_NEED_CONFIG_NOTIFY:	1 means that the window has been reconfigured
 *				before it was made to exist. At the time of
 *				making it exist a ConfigureNotify event needs
 *				to be generated.
 * TK_GRAB_FLAG:		Used to manage grabs. See tkGrab.c for details
 * TK_CHECKED_IC:		1 means we've already tried to get an input
 *				context for this window; if the ic field is
 *				NULL it means that there isn't a context for
 *				the field.
 * TK_DONT_DESTROY_WINDOW:	1 means that Tk_DestroyWindow should not
 *				invoke XDestroyWindow to destroy this widget's
 *				X window. The flag is set when the window has
 *				already been destroyed elsewhere (e.g. by
 *				another application) or when it will be
 *				destroyed later (e.g. by destroying its parent)
 * TK_WM_COLORMAP_WINDOW:	1 means that this window has at some time
 *				appeared in the WM_COLORMAP_WINDOWS property
 *				for its toplevel, so we have to remove it from
 *				that property if the window is deleted and the
 *				toplevel isn't.
 * TK_EMBEDDED:			1 means that this window (which must be a
 *				toplevel) is not a free-standing window but
 *				rather is embedded in some other application.
 * TK_CONTAINER:		1 means that this window is a container, and
 *				that some other application (either in this
 *				process or elsewhere) may be embedding itself
 *				inside the window.
 * TK_BOTH_HALVES:		1 means that this window is used for
 *				application embedding (either as container or
 *				embedded application), and both the containing
 *				and embedded halves are associated with
 *				windows in this particular process.
 * TK_WRAPPER:			1 means that this window is the extra wrapper
 *				window created around a toplevel to hold the
 *				menubar under Unix. See tkUnixWm.c for more
 *				information.
 * TK_REPARENTED:		1 means that this window has been reparented
 *				so that as far as the window system is
 *				concerned it isn't a child of its Tk parent.
 *				Initially this is used only for special Unix
 *				menubar windows.
 * TK_ANONYMOUS_WINDOW:		1 means that this window has no name, and is
 *				thus not accessible from Tk.
 * TK_HAS_WRAPPER		1 means that this window has a wrapper window
 * TK_WIN_MANAGED		1 means that this window is a child of the root
 *				window, and is managed by the window manager.
 * TK_TOP_HIERARCHY		1 means this window is at the top of a physical
 *				window hierarchy within this process, i.e. the
 *				window's parent either doesn't exist or is not
 *				owned by this Tk application.
 * TK_PROP_PROPCHANGE		1 means that PropertyNotify events in the
 *				window's children should propagate up to this
 *				window.
 * TK_WM_MANAGEABLE		1 marks a window as capable of being converted
 *				into a toplevel using [wm manage].
 * TK_CAN_INPUT_TEXT            1 means that this window accepts text input.
 *                              Used on macOS to indicate that key events can be
 *                              processed with the NSTextInputClient protocol.
 *                              Not currently accessible through the public API.
 */

#define TK_MAPPED		1
#define TK_TOP_LEVEL		2
#define TK_ALREADY_DEAD		4
#define TK_NEED_CONFIG_NOTIFY	8
#define TK_GRAB_FLAG		0x10
#define TK_CHECKED_IC		0x20
#define TK_DONT_DESTROY_WINDOW	0x40
#define TK_WM_COLORMAP_WINDOW	0x80
#define TK_EMBEDDED		0x100
#define TK_CONTAINER		0x200
#define TK_BOTH_HALVES		0x400

#define TK_WRAPPER		0x1000
#define TK_REPARENTED		0x2000
#define TK_ANONYMOUS_WINDOW	0x4000
#define TK_HAS_WRAPPER		0x8000
#define TK_WIN_MANAGED		0x10000
#define TK_TOP_HIERARCHY	0x20000
#define TK_PROP_PROPCHANGE	0x40000
#define TK_WM_MANAGEABLE	0x80000
#define TK_CAN_INPUT_TEXT       0x100000

/*
 *----------------------------------------------------------------------
 *
 * Procedure prototypes and structures used for defining new canvas items:
 *
 *----------------------------------------------------------------------
 */

typedef enum {
    TK_STATE_NULL = -1, TK_STATE_ACTIVE, TK_STATE_DISABLED,
    TK_STATE_NORMAL, TK_STATE_HIDDEN
} Tk_State;

typedef struct Tk_SmoothMethod {
    CONST86 char *name;
    int (*coordProc) (Tk_Canvas canvas, double *pointPtr, int numPoints,
	    int numSteps, XPoint xPoints[], double dblPoints[]);
    void (*postscriptProc) (Tcl_Interp *interp, Tk_Canvas canvas,
	    double *coordPtr, int numPoints, int numSteps);
} Tk_SmoothMethod;

/*
 * For each item in a canvas widget there exists one record with the following
 * structure. Each actual item is represented by a record with the following
 * stuff at its beginning, plus additional type-specific stuff after that.
 */

#define TK_TAG_SPACE 3

typedef struct Tk_Item {
    int id;			/* Unique identifier for this item (also
				 * serves as first tag for item). */
    struct Tk_Item *nextPtr;	/* Next in display list of all items in this
				 * canvas. Later items in list are drawn on
				 * top of earlier ones. */
    Tk_Uid staticTagSpace[TK_TAG_SPACE];
				/* Built-in space for limited # of tags. */
    Tk_Uid *tagPtr;		/* Pointer to array of tags. Usually points to
				 * staticTagSpace, but may point to malloc-ed
				 * space if there are lots of tags. */
    int tagSpace;		/* Total amount of tag space available at
				 * tagPtr. */
    int numTags;		/* Number of tag slots actually used at
				 * *tagPtr. */
    struct Tk_ItemType *typePtr;/* Table of procedures that implement this
				 * type of item. */
    int x1, y1, x2, y2;		/* Bounding box for item, in integer canvas
				 * units. Set by item-specific code and
				 * guaranteed to contain every pixel drawn in
				 * item. Item area includes x1 and y1 but not
				 * x2 and y2. */
    struct Tk_Item *prevPtr;	/* Previous in display list of all items in
				 * this canvas. Later items in list are drawn
				 * just below earlier ones. */
    Tk_State state;		/* State of item. */
    char *reserved1;		/* reserved for future use */
    int redraw_flags;		/* Some flags used in the canvas */

    /*
     *------------------------------------------------------------------
     * Starting here is additional type-specific stuff; see the declarations
     * for individual types to see what is part of each type. The actual space
     * below is determined by the "itemInfoSize" of the type's Tk_ItemType
     * record.
     *------------------------------------------------------------------
     */
} Tk_Item;

/*
 * Flag bits for canvases (redraw_flags):
 *
 * TK_ITEM_STATE_DEPENDANT -	1 means that object needs to be redrawn if the
 *				canvas state changes.
 * TK_ITEM_DONT_REDRAW - 	1 means that the object redraw is already been
 *				prepared, so the general canvas code doesn't
 *				need to do that any more.
 */

#define TK_ITEM_STATE_DEPENDANT		1
#define TK_ITEM_DONT_REDRAW		2

/*
 * Records of the following type are used to describe a type of item (e.g.
 * lines, circles, etc.) that can form part of a canvas widget.
 */

#ifdef USE_OLD_CANVAS
typedef int	(Tk_ItemCreateProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int argc, char **argv);
typedef int	(Tk_ItemConfigureProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int argc, char **argv, int flags);
typedef int	(Tk_ItemCoordProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int argc, char **argv);
#else
typedef int	(Tk_ItemCreateProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int objc, Tcl_Obj *const objv[]);
typedef int	(Tk_ItemConfigureProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int objc, Tcl_Obj *const objv[],
		    int flags);
typedef int	(Tk_ItemCoordProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int objc, Tcl_Obj *const objv[]);
#endif /* USE_OLD_CANVAS */
typedef void	(Tk_ItemDeleteProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    Display *display);
typedef void	(Tk_ItemDisplayProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    Display *display, Drawable dst, int x, int y, int width,
		    int height);
typedef double	(Tk_ItemPointProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    double *pointPtr);
typedef int	(Tk_ItemAreaProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    double *rectPtr);
typedef int	(Tk_ItemPostscriptProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, int prepass);
typedef void	(Tk_ItemScaleProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    double originX, double originY, double scaleX,
		    double scaleY);
typedef void	(Tk_ItemTranslateProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    double deltaX, double deltaY);
#ifdef USE_OLD_CANVAS
typedef int	(Tk_ItemIndexProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, char *indexString, int *indexPtr);
#else
typedef int	(Tk_ItemIndexProc)(Tcl_Interp *interp, Tk_Canvas canvas,
		    Tk_Item *itemPtr, Tcl_Obj *indexString, int *indexPtr);
#endif /* USE_OLD_CANVAS */
typedef void	(Tk_ItemCursorProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    int index);
typedef int	(Tk_ItemSelectionProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    int offset, char *buffer, int maxBytes);
#ifdef USE_OLD_CANVAS
typedef void	(Tk_ItemInsertProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    int beforeThis, char *string);
#else
typedef void	(Tk_ItemInsertProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    int beforeThis, Tcl_Obj *string);
#endif /* USE_OLD_CANVAS */
typedef void	(Tk_ItemDCharsProc)(Tk_Canvas canvas, Tk_Item *itemPtr,
		    int first, int last);

#ifndef __NO_OLD_CONFIG

typedef struct Tk_ItemType {
    CONST86 char *name;		/* The name of this type of item, such as
				 * "line". */
    int itemSize;		/* Total amount of space needed for item's
				 * record. */
    Tk_ItemCreateProc *createProc;
				/* Procedure to create a new item of this
				 * type. */
    CONST86 Tk_ConfigSpec *configSpecs; /* Pointer to array of configuration specs for
				 * this type. Used for returning configuration
				 * info. */
    Tk_ItemConfigureProc *configProc;
				/* Procedure to call to change configuration
				 * options. */
    Tk_ItemCoordProc *coordProc;/* Procedure to call to get and set the item's
				 * coordinates. */
    Tk_ItemDeleteProc *deleteProc;
				/* Procedure to delete existing item of this
				 * type. */
    Tk_ItemDisplayProc *displayProc;
				/* Procedure to display items of this type. */
    int alwaysRedraw;		/* Non-zero means displayProc should be called
				 * even when the item has been moved
				 * off-screen. */
    Tk_ItemPointProc *pointProc;/* Computes distance from item to a given
				 * point. */
    Tk_ItemAreaProc *areaProc;	/* Computes whether item is inside, outside,
				 * or overlapping an area. */
    Tk_ItemPostscriptProc *postscriptProc;
				/* Procedure to write a Postscript description
				 * for items of this type. */
    Tk_ItemScaleProc *scaleProc;/* Procedure to rescale items of this type. */
    Tk_ItemTranslateProc *translateProc;
				/* Procedure to translate items of this
				 * type. */
    Tk_ItemIndexProc *indexProc;/* Procedure to determine index of indicated
				 * character. NULL if item doesn't support
				 * indexing. */
    Tk_ItemCursorProc *icursorProc;
				/* Procedure to set insert cursor posn to just
				 * before a given position. */
    Tk_ItemSelectionProc *selectionProc;
				/* Procedure to return selection (in STRING
				 * format) when it is in this item. */
    Tk_ItemInsertProc *insertProc;
				/* Procedure to insert something into an
				 * item. */
    Tk_ItemDCharsProc *dCharsProc;
				/* Procedure to delete characters from an
				 * item. */
    struct Tk_ItemType *nextPtr;/* Used to link types together into a list. */
    char *reserved1;		/* Reserved for future extension. */
    int reserved2;		/* Carefully compatible with */
    char *reserved3;		/* Jan Nijtmans dash patch */
    char *reserved4;
} Tk_ItemType;

/*
 * Flag (used in the alwaysRedraw field) to say whether an item supports
 * point-level manipulation like the line and polygon items.
 */

#define TK_MOVABLE_POINTS	2

#endif /* __NO_OLD_CONFIG */

/*
 * The following structure provides information about the selection and the
 * insertion cursor. It is needed by only a few items, such as those that
 * display text. It is shared by the generic canvas code and the item-specific
 * code, but most of the fields should be written only by the canvas generic
 * code.
 */

typedef struct Tk_CanvasTextInfo {
    Tk_3DBorder selBorder;	/* Border and background for selected
				 * characters. Read-only to items.*/
    int selBorderWidth;		/* Width of border around selection. Read-only
				 * to items. */
    XColor *selFgColorPtr;	/* Foreground color for selected text.
				 * Read-only to items. */
    Tk_Item *selItemPtr;	/* Pointer to selected item. NULL means
				 * selection isn't in this canvas. Writable by
				 * items. */
    int selectFirst;		/* Character index of first selected
				 * character. Writable by items. */
    int selectLast;		/* Character index of last selected character.
				 * Writable by items. */
    Tk_Item *anchorItemPtr;	/* Item corresponding to "selectAnchor": not
				 * necessarily selItemPtr. Read-only to
				 * items. */
    int selectAnchor;		/* Character index of fixed end of selection
				 * (i.e. "select to" operation will use this
				 * as one end of the selection). Writable by
				 * items. */
    Tk_3DBorder insertBorder;	/* Used to draw vertical bar for insertion
				 * cursor. Read-only to items. */
    int insertWidth;		/* Total width of insertion cursor. Read-only
				 * to items. */
    int insertBorderWidth;	/* Width of 3-D border around insert cursor.
				 * Read-only to items. */
    Tk_Item *focusItemPtr;	/* Item that currently has the input focus, or
				 * NULL if no such item. Read-only to items. */
    int gotFocus;		/* Non-zero means that the canvas widget has
				 * the input focus. Read-only to items.*/
    int cursorOn;		/* Non-zero means that an insertion cursor
				 * should be displayed in focusItemPtr.
				 * Read-only to items.*/
} Tk_CanvasTextInfo;

/*
 * Structures used for Dashing and Outline.
 */

typedef struct Tk_Dash {
    int number;
    union {
	char *pt;
	char array[sizeof(char *)];
    } pattern;
} Tk_Dash;

typedef struct Tk_TSOffset {
    int flags;			/* Flags; see below for possible values */
    int xoffset;		/* x offset */
    int yoffset;		/* y offset */
} Tk_TSOffset;

/*
 * Bit fields in Tk_TSOffset->flags:
 */

#define TK_OFFSET_INDEX		1
#define TK_OFFSET_RELATIVE	2
#define TK_OFFSET_LEFT		4
#define TK_OFFSET_CENTER	8
#define TK_OFFSET_RIGHT		16
#define TK_OFFSET_TOP		32
#define TK_OFFSET_MIDDLE	64
#define TK_OFFSET_BOTTOM	128

typedef struct Tk_Outline {
    GC gc;			/* Graphics context. */
    double width;		/* Width of outline. */
    double activeWidth;		/* Width of outline. */
    double disabledWidth;	/* Width of outline. */
    int offset;			/* Dash offset. */
    Tk_Dash dash;		/* Dash pattern. */
    Tk_Dash activeDash;		/* Dash pattern if state is active. */
    Tk_Dash disabledDash;	/* Dash pattern if state is disabled. */
    void *reserved1;		/* Reserved for future expansion. */
    void *reserved2;
    void *reserved3;
    Tk_TSOffset tsoffset;	/* Stipple offset for outline. */
    XColor *color;		/* Outline color. */
    XColor *activeColor;	/* Outline color if state is active. */
    XColor *disabledColor;	/* Outline color if state is disabled. */
    Pixmap stipple;		/* Outline Stipple pattern. */
    Pixmap activeStipple;	/* Outline Stipple pattern if state is
				 * active. */
    Pixmap disabledStipple;	/* Outline Stipple pattern if state is
				 * disabled. */
} Tk_Outline;

/*
 *----------------------------------------------------------------------
 *
 * Procedure prototypes and structures used for managing images:
 *
 *----------------------------------------------------------------------
 */

typedef struct Tk_ImageType Tk_ImageType;
#ifdef USE_OLD_IMAGE
typedef int (Tk_ImageCreateProc) (Tcl_Interp *interp, char *name, int argc,
	char **argv, Tk_ImageType *typePtr, Tk_ImageMaster model,
	ClientData *clientDataPtr);
#else
typedef int (Tk_ImageCreateProc) (Tcl_Interp *interp, CONST86 char *name, int objc,
	Tcl_Obj *const objv[], CONST86 Tk_ImageType *typePtr, Tk_ImageMaster model,
	ClientData *clientDataPtr);
#endif /* USE_OLD_IMAGE */
typedef ClientData (Tk_ImageGetProc) (Tk_Window tkwin, ClientData clientData);
typedef void (Tk_ImageDisplayProc) (ClientData clientData, Display *display,
	Drawable drawable, int imageX, int imageY, int width, int height,
	int drawableX, int drawableY);
typedef void (Tk_ImageFreeProc) (ClientData clientData, Display *display);
typedef void (Tk_ImageDeleteProc) (ClientData clientData);
typedef void (Tk_ImageChangedProc) (ClientData clientData, int x, int y,
	int width, int height, int imageWidth, int imageHeight);
typedef int (Tk_ImagePostscriptProc) (ClientData clientData,
	Tcl_Interp *interp, Tk_Window tkwin, Tk_PostscriptInfo psinfo,
	int x, int y, int width, int height, int prepass);

/*
 * The following structure represents a particular type of image (bitmap, xpm
 * image, etc.). It provides information common to all images of that type,
 * such as the type name and a collection of procedures in the image manager
 * that respond to various events. Each image manager is represented by one of
 * these structures.
 */

struct Tk_ImageType {
    CONST86 char *name;		/* Name of image type. */
    Tk_ImageCreateProc *createProc;
				/* Procedure to call to create a new image of
				 * this type. */
    Tk_ImageGetProc *getProc;	/* Procedure to call the first time
				 * Tk_GetImage is called in a new way (new
				 * visual or screen). */
    Tk_ImageDisplayProc *displayProc;
				/* Call to draw image, in response to
				 * Tk_RedrawImage calls. */
    Tk_ImageFreeProc *freeProc;	/* Procedure to call whenever Tk_FreeImage is
				 * called to release an instance of an
				 * image. */
    Tk_ImageDeleteProc *deleteProc;
				/* Procedure to call to delete image. It will
				 * not be called until after freeProc has been
				 * called for each instance of the image. */
    Tk_ImagePostscriptProc *postscriptProc;
				/* Procedure to call to produce postscript
				 * output for the image. */
    struct Tk_ImageType *nextPtr;
				/* Next in list of all image types currently
				 * known. Filled in by Tk, not by image
				 * manager. */
    char *reserved;		/* reserved for future expansion */
};

/*
 *----------------------------------------------------------------------
 *
 * Additional definitions used to manage images of type "photo".
 *
 *----------------------------------------------------------------------
 */

/*
 * The following type is used to identify a particular photo image to be
 * manipulated:
 */

typedef void *Tk_PhotoHandle;

/*
 * The following structure describes a block of pixels in memory:
 */

typedef struct Tk_PhotoImageBlock {
    unsigned char *pixelPtr;	/* Pointer to the first pixel. */
    int width;			/* Width of block, in pixels. */
    int height;			/* Height of block, in pixels. */
    int pitch;			/* Address difference between corresponding
				 * pixels in successive lines. */
    int pixelSize;		/* Address difference between successive
				 * pixels in the same line. */
    int offset[4];		/* Address differences between the red, green,
				 * blue and alpha components of the pixel and
				 * the pixel as a whole. */
} Tk_PhotoImageBlock;

/*
 * The following values control how blocks are combined into photo images when
 * the alpha component of a pixel is not 255, a.k.a. the compositing rule.
 */

#define TK_PHOTO_COMPOSITE_OVERLAY	0
#define TK_PHOTO_COMPOSITE_SET		1

/*
 * Procedure prototypes and structures used in reading and writing photo
 * images:
 */

typedef struct Tk_PhotoImageFormat Tk_PhotoImageFormat;
#ifdef USE_OLD_IMAGE
typedef int (Tk_ImageFileMatchProc) (Tcl_Channel chan, char *fileName,
	char *formatString, int *widthPtr, int *heightPtr);
typedef int (Tk_ImageStringMatchProc) (char *string, char *formatString,
	int *widthPtr, int *heightPtr);
typedef int (Tk_ImageFileReadProc) (Tcl_Interp *interp, Tcl_Channel chan,
	char *fileName, char *formatString, Tk_PhotoHandle imageHandle,
	int destX, int destY, int width, int height, int srcX, int srcY);
typedef int (Tk_ImageStringReadProc) (Tcl_Interp *interp, char *string,
	char *formatString, Tk_PhotoHandle imageHandle, int destX, int destY,
	int width, int height, int srcX, int srcY);
typedef int (Tk_ImageFileWriteProc) (Tcl_Interp *interp, char *fileName,
	char *formatString, Tk_PhotoImageBlock *blockPtr);
typedef int (Tk_ImageStringWriteProc) (Tcl_Interp *interp,
	Tcl_DString *dataPtr, char *formatString, Tk_PhotoImageBlock *blockPtr);
#else
typedef int (Tk_ImageFileMatchProc) (Tcl_Channel chan, const char *fileName,
	Tcl_Obj *format, int *widthPtr, int *heightPtr, Tcl_Interp *interp);
typedef int (Tk_ImageStringMatchProc) (Tcl_Obj *dataObj, Tcl_Obj *format,
	int *widthPtr, int *heightPtr, Tcl_Interp *interp);
typedef int (Tk_ImageFileReadProc) (Tcl_Interp *interp, Tcl_Channel chan,
	const char *fileName, Tcl_Obj *format, Tk_PhotoHandle imageHandle,
	int destX, int destY, int width, int height, int srcX, int srcY);
typedef int (Tk_ImageStringReadProc) (Tcl_Interp *interp, Tcl_Obj *dataObj,
	Tcl_Obj *format, Tk_PhotoHandle imageHandle, int destX, int destY,
	int width, int height, int srcX, int srcY);
typedef int (Tk_ImageFileWriteProc) (Tcl_Interp *interp, const char *fileName,
	Tcl_Obj *format, Tk_PhotoImageBlock *blockPtr);
typedef int (Tk_ImageStringWriteProc) (Tcl_Interp *interp, Tcl_Obj *format,
	Tk_PhotoImageBlock *blockPtr);
#endif /* USE_OLD_IMAGE */

/*
 * The following structure represents a particular file format for storing
 * images (e.g., PPM, GIF, JPEG, etc.). It provides information to allow image
 * files of that format to be recognized and read into a photo image.
 */

struct Tk_PhotoImageFormat {
    CONST86 char *name;		/* Name of image file format */
    Tk_ImageFileMatchProc *fileMatchProc;
				/* Procedure to call to determine whether an
				 * image file matches this format. */
    Tk_ImageStringMatchProc *stringMatchProc;
				/* Procedure to call to determine whether the
				 * data in a string matches this format. */
    Tk_ImageFileReadProc *fileReadProc;
				/* Procedure to call to read data from an
				 * image file into a photo image. */
    Tk_ImageStringReadProc *stringReadProc;
				/* Procedure to call to read data from a
				 * string into a photo image. */
    Tk_ImageFileWriteProc *fileWriteProc;
				/* Procedure to call to write data from a
				 * photo image to a file. */
    Tk_ImageStringWriteProc *stringWriteProc;
				/* Procedure to call to obtain a string
				 * representation of the data in a photo
				 * image.*/
    struct Tk_PhotoImageFormat *nextPtr;
				/* Next in list of all photo image formats
				 * currently known. Filled in by Tk, not by
				 * image format handler. */
};

/*
 *----------------------------------------------------------------------
 *
 * Procedure prototypes and structures used for managing styles:
 *
 *----------------------------------------------------------------------
 */

/*
 * Style support version tag.
 */

#define TK_STYLE_VERSION_1      0x1
#define TK_STYLE_VERSION        TK_STYLE_VERSION_1

/*
 * The following structures and prototypes are used as static templates to
 * declare widget elements.
 */

typedef void (Tk_GetElementSizeProc) (ClientData clientData, char *recordPtr,
	const Tk_OptionSpec **optionsPtr, Tk_Window tkwin, int width,
	int height, int inner, int *widthPtr, int *heightPtr);
typedef void (Tk_GetElementBoxProc) (ClientData clientData, char *recordPtr,
	const Tk_OptionSpec **optionsPtr, Tk_Window tkwin, int x, int y,
	int width, int height, int inner, int *xPtr, int *yPtr, int *widthPtr,
	int *heightPtr);
typedef int (Tk_GetElementBorderWidthProc) (ClientData clientData,
	char *recordPtr, const Tk_OptionSpec **optionsPtr, Tk_Window tkwin);
typedef void (Tk_DrawElementProc) (ClientData clientData, char *recordPtr,
	const Tk_OptionSpec **optionsPtr, Tk_Window tkwin, Drawable d, int x,
	int y, int width, int height, int state);

typedef struct Tk_ElementOptionSpec {
    char *name;			/* Name of the required option. */
    Tk_OptionType type;		/* Accepted option type. TK_OPTION_END means
				 * any. */
} Tk_ElementOptionSpec;

typedef struct Tk_ElementSpec {
    int version;		/* Version of the style support. */
    char *name;			/* Name of element. */
    Tk_ElementOptionSpec *options;
				/* List of required options. Last one's name
				 * must be NULL. */
    Tk_GetElementSizeProc *getSize;
				/* Compute the external (resp. internal) size
				 * of the element from its desired internal
				 * (resp. external) size. */
    Tk_GetElementBoxProc *getBox;
				/* Compute the inscribed or bounding boxes
				 * within a given area. */
    Tk_GetElementBorderWidthProc *getBorderWidth;
				/* Return the element's internal border width.
				 * Mostly useful for widgets. */
    Tk_DrawElementProc *draw;	/* Draw the element in the given bounding
				 * box. */
} Tk_ElementSpec;

/*
 * Element state flags. Can be OR'ed.
 */

#define TK_ELEMENT_STATE_ACTIVE         1<<0
#define TK_ELEMENT_STATE_DISABLED       1<<1
#define TK_ELEMENT_STATE_FOCUS          1<<2
#define TK_ELEMENT_STATE_PRESSED        1<<3

/*
 *----------------------------------------------------------------------
 *
 * The definitions below provide backward compatibility for functions and
 * types related to event handling that used to be in Tk but have moved to
 * Tcl.
 *
 *----------------------------------------------------------------------
 */

#define TK_READABLE		TCL_READABLE
#define TK_WRITABLE		TCL_WRITABLE
#define TK_EXCEPTION		TCL_EXCEPTION

#define TK_DONT_WAIT		TCL_DONT_WAIT
#define TK_X_EVENTS		TCL_WINDOW_EVENTS
#define TK_WINDOW_EVENTS	TCL_WINDOW_EVENTS
#define TK_FILE_EVENTS		TCL_FILE_EVENTS
#define TK_TIMER_EVENTS		TCL_TIMER_EVENTS
#define TK_IDLE_EVENTS		TCL_IDLE_EVENTS
#define TK_ALL_EVENTS		TCL_ALL_EVENTS

#define Tk_IdleProc		Tcl_IdleProc
#define Tk_FileProc		Tcl_FileProc
#define Tk_TimerProc		Tcl_TimerProc
#define Tk_TimerToken		Tcl_TimerToken

#define Tk_BackgroundError	Tcl_BackgroundError
#define Tk_CancelIdleCall	Tcl_CancelIdleCall
#define Tk_CreateFileHandler	Tcl_CreateFileHandler
#define Tk_CreateTimerHandler	Tcl_CreateTimerHandler
#define Tk_DeleteFileHandler	Tcl_DeleteFileHandler
#define Tk_DeleteTimerHandler	Tcl_DeleteTimerHandler
#define Tk_DoOneEvent		Tcl_DoOneEvent
#define Tk_DoWhenIdle		Tcl_DoWhenIdle
#define Tk_Sleep		Tcl_Sleep

/* Additional stuff that has moved to Tcl: */

#define Tk_EventuallyFree	Tcl_EventuallyFree
#define Tk_FreeProc		Tcl_FreeProc
#define Tk_Preserve		Tcl_Preserve
#define Tk_Release		Tcl_Release

/* Removed Tk_Main, use macro instead */
#if defined(_WIN32) || defined(__CYGWIN__)
#define Tk_Main(argc, argv, proc) Tk_MainEx(argc, argv, proc, \
	(Tcl_FindExecutable(0), (Tcl_CreateInterp)()))
#else
#define Tk_Main(argc, argv, proc) Tk_MainEx(argc, argv, proc, \
	(Tcl_FindExecutable(argv[0]), (Tcl_CreateInterp)()))
#endif
const char *		Tk_InitStubs(Tcl_Interp *interp, const char *version,
				int exact);
EXTERN const char *	Tk_PkgInitStubsCheck(Tcl_Interp *interp,
				const char *version, int exact);

#ifndef USE_TK_STUBS
#define Tk_InitStubs(interp, version, exact) \
    Tk_PkgInitStubsCheck(interp, version, exact)
#endif /* USE_TK_STUBS */

#define Tk_InitImageArgs(interp, argc, argv) /**/

/*
 *----------------------------------------------------------------------
 *
 * Additional procedure types defined by Tk.
 *
 *----------------------------------------------------------------------
 */

typedef int (Tk_ErrorProc) (ClientData clientData, XErrorEvent *errEventPtr);
typedef void (Tk_EventProc) (ClientData clientData, XEvent *eventPtr);
typedef int (Tk_GenericProc) (ClientData clientData, XEvent *eventPtr);
typedef int (Tk_ClientMessageProc) (Tk_Window tkwin, XEvent *eventPtr);
typedef int (Tk_GetSelProc) (ClientData clientData, Tcl_Interp *interp,
	CONST86 char *portion);
typedef void (Tk_LostSelProc) (ClientData clientData);
typedef Tk_RestrictAction (Tk_RestrictProc) (ClientData clientData,
	XEvent *eventPtr);
typedef int (Tk_SelectionProc) (ClientData clientData, int offset,
	char *buffer, int maxBytes);

/*
 *----------------------------------------------------------------------
 *
 * Platform independent exported procedures and variables.
 *
 *----------------------------------------------------------------------
 */

#include "tkDecls.h"

#ifdef USE_OLD_IMAGE
#undef Tk_CreateImageType
#define Tk_CreateImageType		Tk_CreateOldImageType
#undef Tk_CreatePhotoImageFormat
#define Tk_CreatePhotoImageFormat	Tk_CreateOldPhotoImageFormat
#endif /* USE_OLD_IMAGE */

/*
 *----------------------------------------------------------------------
 *
 * Allow users to say that they don't want to alter their source to add extra
 * arguments to Tk_PhotoPutBlock() et al; DO NOT DEFINE THIS WHEN BUILDING TK.
 *
 * This goes after the inclusion of the stubbed-decls so that the declarations
 * of what is actually there can be correct.
 */

#ifdef USE_COMPOSITELESS_PHOTO_PUT_BLOCK
#   ifdef Tk_PhotoPutBlock
#	undef Tk_PhotoPutBlock
#   endif
#   define Tk_PhotoPutBlock		Tk_PhotoPutBlock_NoComposite
#   ifdef Tk_PhotoPutZoomedBlock
#	undef Tk_PhotoPutZoomedBlock
#   endif
#   define Tk_PhotoPutZoomedBlock	Tk_PhotoPutZoomedBlock_NoComposite
#   define USE_PANIC_ON_PHOTO_ALLOC_FAILURE
#else /* !USE_COMPOSITELESS_PHOTO_PUT_BLOCK */
#   ifdef USE_PANIC_ON_PHOTO_ALLOC_FAILURE
#	ifdef Tk_PhotoPutBlock
#	    undef Tk_PhotoPutBlock
#	endif
#	define Tk_PhotoPutBlock		Tk_PhotoPutBlock_Panic
#	ifdef Tk_PhotoPutZoomedBlock
#	    undef Tk_PhotoPutZoomedBlock
#	endif
#	define Tk_PhotoPutZoomedBlock	Tk_PhotoPutZoomedBlock_Panic
#   endif /* USE_PANIC_ON_PHOTO_ALLOC_FAILURE */
#endif /* USE_COMPOSITELESS_PHOTO_PUT_BLOCK */
#ifdef USE_PANIC_ON_PHOTO_ALLOC_FAILURE
#   ifdef Tk_PhotoExpand
#	undef Tk_PhotoExpand
#   endif
#   define Tk_PhotoExpand		Tk_PhotoExpand_Panic
#   ifdef Tk_PhotoSetSize
#	undef Tk_PhotoSetSize
#   endif
#   define Tk_PhotoSetSize		Tk_PhotoSetSize_Panic
#endif /* USE_PANIC_ON_PHOTO_ALLOC_FAILURE */

#undef TCL_STORAGE_CLASS
#define TCL_STORAGE_CLASS DLLIMPORT

#endif /* RC_INVOKED */

/*
 * end block for C++
 */

#ifdef __cplusplus
}
#endif

#endif /* _TK */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
