/*
 *  tkEntry.h --
 *
 * This module defined the structures for the Entry & SpinBox widgets.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 *
 * Copyright (c) 2002 Apple Inc.
 */

#ifndef _TKENTRY
#define _TKENTRY

#ifndef _TKINT
#include "tkInt.h"
#endif

enum EntryType {
    TK_ENTRY, TK_SPINBOX
};

/*
 * A data structure of the following type is kept for each Entry widget
 * managed by this file:
 */

typedef struct {
    Tk_Window tkwin;		/* Window that embodies the entry. NULL means
				 * that the window has been destroyed but the
				 * data structures haven't yet been cleaned
				 * up.*/
    Display *display;		/* Display containing widget. Used, among
				 * other things, so that resources can be
				 * freed even after tkwin has gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with entry. */
    Tcl_Command widgetCmd;	/* Token for entry's widget command. */
    Tk_OptionTable optionTable;	/* Table that defines configuration options
				 * available for this widget. */
    enum EntryType type;	/* Specialized type of Entry widget */

    /*
     * Fields that are set by widget commands other than "configure".
     */

    const char *string;		/* Pointer to storage for string;
				 * NULL-terminated; malloc-ed. */
    int insertPos;		/* Character index before which next typed
				 * character will be inserted. */

    /*
     * Information about what's selected, if any.
     */

    int selectFirst;		/* Character index of first selected character
				 * (-1 means nothing selected. */
    int selectLast;		/* Character index just after last selected
				 * character (-1 means nothing selected. */
    int selectAnchor;		/* Fixed end of selection (i.e. "select to"
				 * operation will use this as one end of the
				 * selection). */

    /*
     * Information for scanning:
     */

    int scanMarkX;		/* X-position at which scan started (e.g.
				 * button was pressed here). */
    int scanMarkIndex;		/* Character index of character that was at
				 * left of window when scan started. */

    /*
     * Configuration settings that are updated by Tk_ConfigureWidget.
     */

    Tk_3DBorder normalBorder;	/* Used for drawing border around whole
				 * window, plus used for background. */
    Tk_3DBorder disabledBorder;	/* Used for drawing border around whole window
				 * in disabled state, plus used for
				 * background. */
    Tk_3DBorder readonlyBorder;	/* Used for drawing border around whole window
				 * in readonly state, plus used for
				 * background. */
    int borderWidth;		/* Width of 3-D border around window. */
    Tk_Cursor cursor;		/* Current cursor for window, or NULL. */
    int exportSelection;	/* Non-zero means tie internal entry selection
				 * to X selection. */
    Tk_Font tkfont;		/* Information about text font, or NULL. */
    XColor *fgColorPtr;		/* Text color in normal mode. */
    XColor *dfgColorPtr;	/* Text color in disabled mode. */
    XColor *highlightBgColorPtr;/* Color for drawing traversal highlight area
				 * when highlight is off. */
    XColor *highlightColorPtr;	/* Color for drawing traversal highlight. */
    int highlightWidth;		/* Width in pixels of highlight to draw around
				 * widget when it has the focus. <= 0 means
				 * don't draw a highlight. */
    Tk_3DBorder insertBorder;	/* Used to draw vertical bar for insertion
				 * cursor. */
    int insertBorderWidth;	/* Width of 3-D border around insert cursor. */
    int insertOffTime;		/* Number of milliseconds cursor should spend
				 * in "off" state for each blink. */
    int insertOnTime;		/* Number of milliseconds cursor should spend
				 * in "on" state for each blink. */
    int insertWidth;		/* Total width of insert cursor. */
    Tk_Justify justify;		/* Justification to use for text within
				 * window. */
    int relief;			/* 3-D effect: TK_RELIEF_RAISED, etc. */
    Tk_3DBorder selBorder;	/* Border and background for selected
				 * characters. */
    int selBorderWidth;		/* Width of border around selection. */
    XColor *selFgColorPtr;	/* Foreground color for selected text. */
    int state;			/* Normal or disabled. Entry is read-only when
				 * disabled. */
    char *textVarName;		/* Name of variable (malloc'ed) or NULL. If
				 * non-NULL, entry's string tracks the
				 * contents of this variable and vice
				 * versa. */
    char *takeFocus;		/* Value of -takefocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. Malloc'ed, but may be NULL. */
    int prefWidth;		/* Desired width of window, measured in
				 * average characters. */
    char *scrollCmd;		/* Command prefix for communicating with
				 * scrollbar(s). Malloc'ed. NULL means no
				 * command to issue. */
    char *showChar;		/* Value of -show option. If non-NULL, first
				 * character is used for displaying all
				 * characters in entry. Malloc'ed. This is
				 * only used by the Entry widget. */

    /*
     * Fields whose values are derived from the current values of the
     * configuration settings above.
     */

    const char *displayString;	/* String to use when displaying. This may be
				 * a pointer to string, or a pointer to
				 * malloced memory with the same character
				 * length as string but whose characters are
				 * all equal to showChar. */
    int numBytes;		/* Length of string in bytes. */
    int numChars;		/* Length of string in characters. Both string
				 * and displayString have the same character
				 * length, but may have different byte lengths
				 * due to being made from different UTF-8
				 * characters. */
    int numDisplayBytes;	/* Length of displayString in bytes. */
    int inset;			/* Number of pixels on the left and right
				 * sides that are taken up by XPAD,
				 * borderWidth (if any), and highlightWidth
				 * (if any). */
    Tk_TextLayout textLayout;	/* Cached text layout information. */
    int layoutX, layoutY;	/* Origin for layout. */
    int leftX;			/* X position at which character at leftIndex
				 * is drawn (varies depending on justify). */
    int leftIndex;		/* Character index of left-most character
				 * visible in window. */
    Tcl_TimerToken insertBlinkHandler;
				/* Timer handler used to blink cursor on and
				 * off. */
    GC textGC;			/* For drawing normal text. */
    GC selTextGC;		/* For drawing selected text. */
    GC highlightGC;		/* For drawing traversal highlight. */
    int avgWidth;		/* Width of average character. */
    int xWidth;			/* Extra width to reserve for widget. Used by
				 * spinboxes for button space. */
    int flags;			/* Miscellaneous flags; see below for
				 * definitions. */

    int validate;		/* Non-zero means try to validate */
    char *validateCmd;		/* Command prefix to use when invoking
				 * validate command. NULL means don't invoke
				 * commands. Malloc'ed. */
    char *invalidCmd;		/* Command called when a validation returns 0
				 * (successfully fails), defaults to {}. */
} Entry;

/*
 * A data structure of the following type is kept for each spinbox widget
 * managed by this file:
 */

typedef struct {
    Entry entry;		/* A pointer to the generic entry structure.
				 * This must be the first element of the
				 * Spinbox. */

    /*
     * Spinbox specific configuration settings.
     */

    Tk_3DBorder activeBorder;	/* Used for drawing border around active
				 * buttons. */
    Tk_3DBorder buttonBorder;	/* Used for drawing border around buttons. */
    Tk_Cursor bCursor;		/* cursor for buttons, or NULL. */
    int bdRelief;		/* 3-D effect: TK_RELIEF_RAISED, etc. */
    int buRelief;		/* 3-D effect: TK_RELIEF_RAISED, etc. */
    char *command;		/* Command to invoke for spin buttons. NULL
				 * means no command to issue. */

    /*
     * Spinbox specific fields for use with configuration settings above.
     */

    int wrap;			/* whether to wrap around when spinning */

    int selElement;		/* currently selected control */
    int curElement;		/* currently mouseover control */

    int repeatDelay;		/* repeat delay */
    int repeatInterval;		/* repeat interval */

    double fromValue;		/* Value corresponding to left/top of dial */
    double toValue;		/* Value corresponding to right/bottom of
				 * dial */
    double increment;		/* If > 0, all values are rounded to an even
				 * multiple of this value. */
    char *formatBuf;		/* string into which to format value.
				 * Malloc'ed. */
    char *reqFormat;		/* Snprintf conversion specifier used for the
				 * value that the users requests. Malloc'ed */
    char *valueFormat;		/* Snprintf conversion specifier used for the
				 * value. */
    char digitFormat[16];	/* Snprintf conversion specifier computed from
				 * digits and other information; used for the
				 * value. */

    char *valueStr;		/* Values List. Malloc'ed. */
    Tcl_Obj *listObj;		/* Pointer to the list object being used */
    int eIndex;			/* Holds the current index into elements */
    int nElements;		/* Holds the current count of elements */
} Spinbox;

/*
 * Assigned bits of "flags" fields of Entry structures, and what those bits
 * mean:
 *
 * REDRAW_PENDING:		Non-zero means a DoWhenIdle handler has
 *				already been queued to redisplay the entry.
 * BORDER_NEEDED:		Non-zero means 3-D border must be redrawn
 *				around window during redisplay. Normally only
 *				text portion needs to be redrawn.
 * CURSOR_ON:			Non-zero means insert cursor is displayed at
 *				present. 0 means it isn't displayed.
 * GOT_FOCUS:			Non-zero means this window has the input
 *				focus.
 * UPDATE_SCROLLBAR:		Non-zero means scrollbar should be updated
 *				during next redisplay operation.
 * GOT_SELECTION:		Non-zero means we've claimed the selection.
 * ENTRY_DELETED:		This entry has been effectively destroyed.
 * VALIDATING:			Non-zero means we are in a validateCmd
 * VALIDATE_VAR:		Non-zero means we are attempting to validate
 *				the entry's textvariable with validateCmd
 * VALIDATE_ABORT:		Non-zero if validatecommand signals an abort
 *				for current procedure and make no changes
 * ENTRY_VAR_TRACED:		Non-zero if a var trace is set.
 */

#define REDRAW_PENDING		1
#define BORDER_NEEDED		2
#define CURSOR_ON		4
#define GOT_FOCUS		8
#define UPDATE_SCROLLBAR	0x10
#define GOT_SELECTION		0x20
#define ENTRY_DELETED		0x40
#define VALIDATING		0x80
#define VALIDATE_VAR		0x100
#define VALIDATE_ABORT		0x200
#define ENTRY_VAR_TRACED	0x400

/*
 * The following enum is used to define a type for the -state option of the
 * Entry widget. These values are used as indices into the string table below.
 */

enum state {
    STATE_DISABLED, STATE_NORMAL, STATE_READONLY
};

/*
 * This is the element index corresponding to the strings in selElementNames.
 * If you modify them, you must modify the numbers here.
 */

enum selelement {
    SEL_NONE, SEL_BUTTONDOWN, SEL_BUTTONUP, SEL_NULL, SEL_ENTRY
};

/*
 * Declaration of functions used in the implementation of the native side of
 * the Entry widget.
 */

MODULE_SCOPE int	TkpDrawEntryBorderAndFocus(Entry *entryPtr,
			    Drawable d, int isSpinbox);
MODULE_SCOPE int	TkpDrawSpinboxButtons(Spinbox *sbPtr, Drawable d);

#endif /* _TKENTRY */
