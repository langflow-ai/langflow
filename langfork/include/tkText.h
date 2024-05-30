/*
 * tkText.h --
 *
 *	Declarations shared among the files that implement text widgets.
 *
 * Copyright (c) 1992-1994 The Regents of the University of California.
 * Copyright (c) 1994-1995 Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKTEXT
#define _TKTEXT

#ifndef _TK
#include "tk.h"
#endif

#ifndef _TKUNDO
#include "tkUndo.h"
#endif

/*
 * The data structure below defines a single logical line of text (from
 * newline to newline, not necessarily what appears on one display line of the
 * screen).
 */

typedef struct TkTextLine {
    struct Node *parentPtr;	/* Pointer to parent node containing line. */
    struct TkTextLine *nextPtr;	/* Next in linked list of lines with same
				 * parent node in B-tree. NULL means end of
				 * list. */
    struct TkTextSegment *segPtr;
				/* First in ordered list of segments that make
				 * up the line. */
    int *pixels;		/* Array containing two integers for each
				 * referring text widget. The first of these
				 * is the number of vertical pixels taken up
				 * by this line, whether currently displayed
				 * or not. This number is only updated
				 * asychronously. The second of these is the
				 * last epoch at which the pixel height was
				 * recalculated. */
} TkTextLine;

/*
 * -----------------------------------------------------------------------
 * Segments: each line is divided into one or more segments, where each
 * segment is one of several things, such as a group of characters, a tag
 * toggle, a mark, or an embedded widget. Each segment starts with a standard
 * header followed by a body that varies from type to type.
 * -----------------------------------------------------------------------
 */

/*
 * The data structure below defines the body of a segment that represents a
 * tag toggle. There is one of these structures at both the beginning and end
 * of each tagged range.
 */

typedef struct TkTextToggle {
    struct TkTextTag *tagPtr;	/* Tag that starts or ends here. */
    int inNodeCounts;		/* 1 means this toggle has been accounted for
				 * in node toggle counts; 0 means it hasn't,
				 * yet. */
} TkTextToggle;

/*
 * The data structure below defines line segments that represent marks. There
 * is one of these for each mark in the text.
 */

typedef struct TkTextMark {
    struct TkText *textPtr;	/* Overall information about text widget. */
    TkTextLine *linePtr;	/* Line structure that contains the
				 * segment. */
    Tcl_HashEntry *hPtr;	/* Pointer to hash table entry for mark (in
				 * sharedTextPtr->markTable). */
} TkTextMark;

/*
 * A structure of the following type holds information for each window
 * embedded in a text widget. This information is only used by the file
 * tkTextWind.c
 */

typedef struct TkTextEmbWindowClient {
    struct TkText *textPtr;	/* Information about the overall text
				 * widget. */
    Tk_Window tkwin;		/* Window for this segment. NULL means that
				 * the window hasn't been created yet. */
    int chunkCount;		/* Number of display chunks that refer to this
				 * window. */
    int displayed;		/* Non-zero means that the window has been
				 * displayed on the screen recently. */
    struct TkTextSegment *parent;
    struct TkTextEmbWindowClient *next;
} TkTextEmbWindowClient;

typedef struct TkTextEmbWindow {
    struct TkSharedText *sharedTextPtr;
				/* Information about the shared portion of the
				 * text widget. */
    Tk_Window tkwin;		/* Window for this segment. This is just a
				 * temporary value, copied from 'clients', to
				 * make option table updating easier. NULL
				 * means that the window hasn't been created
				 * yet. */
    TkTextLine *linePtr;	/* Line structure that contains this
				 * window. */
    char *create;		/* Script to create window on-demand. NULL
				 * means no such script. Malloc-ed. */
    int align;			/* How to align window in vertical space. See
				 * definitions in tkTextWind.c. */
    int padX, padY;		/* Padding to leave around each side of
				 * window, in pixels. */
    int stretch;		/* Should window stretch to fill vertical
				 * space of line (except for pady)? 0 or 1. */
    Tk_OptionTable optionTable;	/* Token representing the configuration
				 * specifications. */
    TkTextEmbWindowClient *clients;
				/* Linked list of peer-widget specific
				 * information for this embedded window. */
} TkTextEmbWindow;

/*
 * A structure of the following type holds information for each image embedded
 * in a text widget. This information is only used by the file tkTextImage.c
 */

typedef struct TkTextEmbImage {
    struct TkSharedText *sharedTextPtr;
				/* Information about the shared portion of the
				 * text widget. This is used when the image
				 * changes or is deleted. */
    TkTextLine *linePtr;	/* Line structure that contains this image. */
    char *imageString;		/* Name of the image for this segment. */
    char *imageName;		/* Name used by text widget to identify this
				 * image. May be unique-ified. */
    char *name;			/* Name used in the hash table. Used by
				 * "image names" to identify this instance of
				 * the image. */
    Tk_Image image;		/* Image for this segment. NULL means that the
				 * image hasn't been created yet. */
    int align;			/* How to align image in vertical space. See
				 * definitions in tkTextImage.c. */
    int padX, padY;		/* Padding to leave around each side of image,
				 * in pixels. */
    int chunkCount;		/* Number of display chunks that refer to this
				 * image. */
    Tk_OptionTable optionTable;	/* Token representing the configuration
				 * specifications. */
} TkTextEmbImage;

/*
 * The data structure below defines line segments.
 */

typedef struct TkTextSegment {
    const struct Tk_SegType *typePtr;
				/* Pointer to record describing segment's
				 * type. */
    struct TkTextSegment *nextPtr;
				/* Next in list of segments for this line, or
				 * NULL for end of list. */
    int size;			/* Size of this segment (# of bytes of index
				 * space it occupies). */
    union {
	char chars[TCL_UTF_MAX];	/* Characters that make up character info.
				 * Actual length varies to hold as many
				 * characters as needed.*/
	TkTextToggle toggle;	/* Information about tag toggle. */
	TkTextMark mark;	/* Information about mark. */
	TkTextEmbWindow ew;	/* Information about embedded window. */
	TkTextEmbImage ei;	/* Information about embedded image. */
    } body;
} TkTextSegment;

/*
 * Data structures of the type defined below are used during the execution of
 * Tcl commands to keep track of various interesting places in a text. An
 * index is only valid up until the next modification to the character
 * structure of the b-tree so they can't be retained across Tcl commands.
 * However, mods to marks or tags don't invalidate indices.
 */

typedef struct TkTextIndex {
    TkTextBTree tree;		/* Tree containing desired position. */
    TkTextLine *linePtr;	/* Pointer to line containing position of
				 * interest. */
    int byteIndex;		/* Index within line of desired character (0
				 * means first one). */
    struct TkText *textPtr;	/* May be NULL, but otherwise the text widget
				 * with which this index is associated. If not
				 * NULL, then we have a refCount on the
				 * widget. */
} TkTextIndex;

/*
 * Types for procedure pointers stored in TkTextDispChunk strutures:
 */

typedef struct TkTextDispChunk TkTextDispChunk;

typedef void 		Tk_ChunkDisplayProc(struct TkText *textPtr,
			    TkTextDispChunk *chunkPtr, int x, int y,
			    int height, int baseline, Display *display,
			    Drawable dst, int screenY);
typedef void		Tk_ChunkUndisplayProc(struct TkText *textPtr,
			    TkTextDispChunk *chunkPtr);
typedef int		Tk_ChunkMeasureProc(TkTextDispChunk *chunkPtr, int x);
typedef void		Tk_ChunkBboxProc(struct TkText *textPtr,
			    TkTextDispChunk *chunkPtr, int index, int y,
			    int lineHeight, int baseline, int *xPtr,
			    int *yPtr, int *widthPtr, int *heightPtr);

/*
 * The structure below represents a chunk of stuff that is displayed together
 * on the screen. This structure is allocated and freed by generic display
 * code but most of its fields are filled in by segment-type-specific code.
 */

struct TkTextDispChunk {
    /*
     * The fields below are set by the type-independent code before calling
     * the segment-type-specific layoutProc. They should not be modified by
     * segment-type-specific code.
     */

    int x;			/* X position of chunk, in pixels. This
				 * position is measured from the left edge of
				 * the logical line, not from the left edge of
				 * the window (i.e. it doesn't change under
				 * horizontal scrolling). */
    struct TkTextDispChunk *nextPtr;
				/* Next chunk in the display line or NULL for
				 * the end of the list. */
    struct TextStyle *stylePtr;	/* Display information, known only to
				 * tkTextDisp.c. */

    /*
     * The fields below are set by the layoutProc that creates the chunk.
     */

    Tk_ChunkDisplayProc *displayProc;
				/* Procedure to invoke to draw this chunk on
				 * the display or an off-screen pixmap. */
    Tk_ChunkUndisplayProc *undisplayProc;
				/* Procedure to invoke when segment ceases to
				 * be displayed on screen anymore. */
    Tk_ChunkMeasureProc *measureProc;
				/* Procedure to find character under a given
				 * x-location. */
    Tk_ChunkBboxProc *bboxProc;	/* Procedure to find bounding box of character
				 * in chunk. */
    int numBytes;		/* Number of bytes that will be displayed in
				 * the chunk. */
    int minAscent;		/* Minimum space above the baseline needed by
				 * this chunk. */
    int minDescent;		/* Minimum space below the baseline needed by
				 * this chunk. */
    int minHeight;		/* Minimum total line height needed by this
				 * chunk. */
    int width;			/* Width of this chunk, in pixels. Initially
				 * set by chunk-specific code, but may be
				 * increased to include tab or extra space at
				 * end of line. */
    int breakIndex;		/* Index within chunk of last acceptable
				 * position for a line (break just before this
				 * byte index). <= 0 means don't break during
				 * or immediately after this chunk. */
    ClientData clientData;	/* Additional information for use of
				 * displayProc and undisplayProc. */
};

/*
 * One data structure of the following type is used for each tag in a text
 * widget. These structures are kept in sharedTextPtr->tagTable and referred
 * to in other structures.
 */

typedef enum {
    TEXT_WRAPMODE_CHAR, TEXT_WRAPMODE_NONE, TEXT_WRAPMODE_WORD,
    TEXT_WRAPMODE_NULL
} TkWrapMode;

typedef struct TkTextTag {
    const char *name;		/* Name of this tag. This field is actually a
				 * pointer to the key from the entry in
				 * sharedTextPtr->tagTable, so it needn't be
				 * freed explicitly. For 'sel' tags this is
				 * just a static string, so again need not be
				 * freed. */
    const struct TkText *textPtr;
				/* If non-NULL, then this tag only applies to
				 * the given text widget (when there are peer
				 * widgets). */
    int priority;		/* Priority of this tag within widget. 0 means
				 * lowest priority. Exactly one tag has each
				 * integer value between 0 and numTags-1. */
    struct Node *tagRootPtr;	/* Pointer into the B-Tree at the lowest node
				 * that completely dominates the ranges of
				 * text occupied by the tag. At this node
				 * there is no information about the tag. One
				 * or more children of the node do contain
				 * information about the tag. */
    int toggleCount;		/* Total number of tag toggles. */

    /*
     * Information for displaying text with this tag. The information belows
     * acts as an override on information specified by lower-priority tags.
     * If no value is specified, then the next-lower-priority tag on the text
     * determins the value. The text widget itself provides defaults if no tag
     * specifies an override.
     */

    Tk_3DBorder border;		/* Used for drawing background. NULL means no
				 * value specified here. */
    int borderWidth;		/* Width of 3-D border for background. */
    Tcl_Obj *borderWidthPtr;	/* Width of 3-D border for background. */
    char *reliefString;		/* -relief option string (malloc-ed). NULL
				 * means option not specified. */
    int relief;			/* 3-D relief for background. */
    Pixmap bgStipple;		/* Stipple bitmap for background. None means
				 * no value specified here. */
    XColor *fgColor;		/* Foreground color for text. NULL means no
				 * value specified here. */
    Tk_Font tkfont;		/* Font for displaying text. NULL means no
				 * value specified here. */
    Pixmap fgStipple;		/* Stipple bitmap for text and other
				 * foreground stuff. None means no value
				 * specified here.*/
    char *justifyString;	/* -justify option string (malloc-ed). NULL
				 * means option not specified. */
    Tk_Justify justify;		/* How to justify text: TK_JUSTIFY_LEFT,
				 * TK_JUSTIFY_RIGHT, or TK_JUSTIFY_CENTER.
				 * Only valid if justifyString is non-NULL. */
    char *lMargin1String;	/* -lmargin1 option string (malloc-ed). NULL
				 * means option not specified. */
    int lMargin1;		/* Left margin for first display line of each
				 * text line, in pixels. Only valid if
				 * lMargin1String is non-NULL. */
    char *lMargin2String;	/* -lmargin2 option string (malloc-ed). NULL
				 * means option not specified. */
    int lMargin2;		/* Left margin for second and later display
				 * lines of each text line, in pixels. Only
				 * valid if lMargin2String is non-NULL. */
    Tk_3DBorder lMarginColor;	/* Used for drawing background in left margins.
                                 * This is used for both lmargin1 and lmargin2.
				 * NULL means no value specified here. */
    char *offsetString;		/* -offset option string (malloc-ed). NULL
				 * means option not specified. */
    int offset;			/* Vertical offset of text's baseline from
				 * baseline of line. Used for superscripts and
				 * subscripts. Only valid if offsetString is
				 * non-NULL. */
    char *overstrikeString;	/* -overstrike option string (malloc-ed). NULL
				 * means option not specified. */
    int overstrike;		/* Non-zero means draw horizontal line through
				 * middle of text. Only valid if
				 * overstrikeString is non-NULL. */
    XColor *overstrikeColor;    /* Color for the overstrike. NULL means same
                                 * color as foreground. */
    char *rMarginString;	/* -rmargin option string (malloc-ed). NULL
				 * means option not specified. */
    int rMargin;		/* Right margin for text, in pixels. Only
				 * valid if rMarginString is non-NULL. */
    Tk_3DBorder rMarginColor;	/* Used for drawing background in right margin.
				 * NULL means no value specified here. */
    Tk_3DBorder selBorder;	/* Used for drawing background for selected text.
				 * NULL means no value specified here. */
    XColor *selFgColor;		/* Foreground color for selected text. NULL means
				 * no value specified here. */
    char *spacing1String;	/* -spacing1 option string (malloc-ed). NULL
				 * means option not specified. */
    int spacing1;		/* Extra spacing above first display line for
				 * text line. Only valid if spacing1String is
				 * non-NULL. */
    char *spacing2String;	/* -spacing2 option string (malloc-ed). NULL
				 * means option not specified. */
    int spacing2;		/* Extra spacing between display lines for the
				 * same text line. Only valid if
				 * spacing2String is non-NULL. */
    char *spacing3String;	/* -spacing2 option string (malloc-ed). NULL
				 * means option not specified. */
    int spacing3;		/* Extra spacing below last display line for
				 * text line. Only valid if spacing3String is
				 * non-NULL. */
    Tcl_Obj *tabStringPtr;	/* -tabs option string. NULL means option not
				 * specified. */
    struct TkTextTabArray *tabArrayPtr;
				/* Info about tabs for tag (malloc-ed) or
				 * NULL. Corresponds to tabString. */
    int tabStyle;		/* One of TABULAR or WORDPROCESSOR or NONE (if
				 * not specified). */
    char *underlineString;	/* -underline option string (malloc-ed). NULL
				 * means option not specified. */
    int underline;		/* Non-zero means draw underline underneath
				 * text. Only valid if underlineString is
				 * non-NULL. */
    XColor *underlineColor;     /* Color for the underline. NULL means same
                                 * color as foreground. */
    TkWrapMode wrapMode;	/* How to handle wrap-around for this tag.
				 * Must be TEXT_WRAPMODE_CHAR,
				 * TEXT_WRAPMODE_NONE, TEXT_WRAPMODE_WORD, or
				 * TEXT_WRAPMODE_NULL to use wrapmode for
				 * whole widget. */
    char *elideString;		/* -elide option string (malloc-ed). NULL
				 * means option not specified. */
    int elide;			/* Non-zero means that data under this tag
				 * should not be displayed. */
    int affectsDisplay;		/* Non-zero means that this tag affects the
				 * way information is displayed on the screen
				 * (so need to redisplay if tag changes). */
    Tk_OptionTable optionTable;	/* Token representing the configuration
				 * specifications. */
    int affectsDisplayGeometry;	/* Non-zero means that this tag affects the
				 * size with which information is displayed on
				 * the screen (so need to recalculate line
				 * dimensions if tag changes). */
} TkTextTag;

#define TK_TAG_AFFECTS_DISPLAY	0x1
#define TK_TAG_UNDERLINE	0x2
#define TK_TAG_JUSTIFY		0x4
#define TK_TAG_OFFSET		0x10

/*
 * The data structure below is used for searching a B-tree for transitions on
 * a single tag (or for all tag transitions). No code outside of tkTextBTree.c
 * should ever modify any of the fields in these structures, but it's OK to
 * use them for read-only information.
 */

typedef struct TkTextSearch {
    TkTextIndex curIndex;	/* Position of last tag transition returned by
				 * TkBTreeNextTag, or index of start of
				 * segment containing starting position for
				 * search if TkBTreeNextTag hasn't been called
				 * yet, or same as stopIndex if search is
				 * over. */
    TkTextSegment *segPtr;	/* Actual tag segment returned by last call to
				 * TkBTreeNextTag, or NULL if TkBTreeNextTag
				 * hasn't returned anything yet. */
    TkTextSegment *nextPtr;	/* Where to resume search in next call to
				 * TkBTreeNextTag. */
    TkTextSegment *lastPtr;	/* Stop search before just before considering
				 * this segment. */
    TkTextTag *tagPtr;		/* Tag to search for (or tag found, if allTags
				 * is non-zero). */
    int linesLeft;		/* Lines left to search (including curIndex
				 * and stopIndex). When this becomes <= 0 the
				 * search is over. */
    int allTags;		/* Non-zero means ignore tag check: search for
				 * transitions on all tags. */
} TkTextSearch;

/*
 * The following data structure describes a single tab stop. It must be kept
 * in sync with the 'tabOptionStrings' array in the function 'TkTextGetTabs'
 */

typedef enum {LEFT, RIGHT, CENTER, NUMERIC} TkTextTabAlign;

/*
 * The following are the supported styles of tabbing, used for the -tabstyle
 * option of the text widget. The last element is only used for tag options.
 */

typedef enum {
    TK_TEXT_TABSTYLE_TABULAR,
    TK_TEXT_TABSTYLE_WORDPROCESSOR,
    TK_TEXT_TABSTYLE_NONE
} TkTextTabStyle;

typedef struct TkTextTab {
    int location;		/* Offset in pixels of this tab stop from the
				 * left margin (lmargin2) of the text. */
    TkTextTabAlign alignment;	/* Where the tab stop appears relative to the
				 * text. */
} TkTextTab;

typedef struct TkTextTabArray {
    int numTabs;		/* Number of tab stops. */
    double lastTab;		/* The accurate fractional pixel position of
				 * the last tab. */
    double tabIncrement;	/* The accurate fractional pixel increment
				 * between interpolated tabs we have to create
				 * when we exceed numTabs. */
    TkTextTab tabs[TKFLEXARRAY];/* Array of tabs. The actual size will be
				 * numTabs. THIS FIELD MUST BE THE LAST IN THE
				 * STRUCTURE. */
} TkTextTabArray;

/*
 * Enumeration defining the edit modes of the widget.
 */

typedef enum {
    TK_TEXT_EDIT_INSERT,	/* insert mode */
    TK_TEXT_EDIT_DELETE,	/* delete mode */
    TK_TEXT_EDIT_REPLACE,	/* replace mode */
    TK_TEXT_EDIT_OTHER		/* none of the above */
} TkTextEditMode;

/*
 * Enumeration defining the ways in which a text widget may be modified (for
 * undo/redo handling).
 */

typedef enum {
    TK_TEXT_DIRTY_NORMAL,	/* Normal behavior. */
    TK_TEXT_DIRTY_UNDO,		/* Reverting a compound action. */
    TK_TEXT_DIRTY_REDO,		/* Reapplying a compound action. */
    TK_TEXT_DIRTY_FIXED		/* Forced to be dirty; can't be undone/redone
				 * by normal activity. */
} TkTextDirtyMode;

/*
 * The following enum is used to define a type for the -state option of the
 * Text widget.
 */

typedef enum {
    TK_TEXT_STATE_DISABLED, TK_TEXT_STATE_NORMAL
} TkTextState;

/*
 * A data structure of the following type is shared between each text widget
 * that are peers.
 */

typedef struct TkSharedText {
    int refCount;		/* Reference count this shared object. */
    TkTextBTree tree;		/* B-tree representation of text and tags for
				 * widget. */
    Tcl_HashTable tagTable;	/* Hash table that maps from tag names to
				 * pointers to TkTextTag structures. The "sel"
				 * tag does not feature in this table, since
				 * there's one of those for each text peer. */
    int numTags;		/* Number of tags currently defined for
				 * widget; needed to keep track of
				 * priorities. */
    Tcl_HashTable markTable;	/* Hash table that maps from mark names to
				 * pointers to mark segments. The special
				 * "insert" and "current" marks are not stored
				 * in this table, but directly accessed as
				 * fields of textPtr. */
    Tcl_HashTable windowTable;	/* Hash table that maps from window names to
				 * pointers to window segments. If a window
				 * segment doesn't yet have an associated
				 * window, there is no entry for it here. */
    Tcl_HashTable imageTable;	/* Hash table that maps from image names to
				 * pointers to image segments. If an image
				 * segment doesn't yet have an associated
				 * image, there is no entry for it here. */
    Tk_BindingTable bindingTable;
				/* Table of all bindings currently defined for
				 * this widget. NULL means that no bindings
				 * exist, so the table hasn't been created.
				 * Each "object" used for this table is the
				 * name of a tag. */
    int stateEpoch;		/* This is incremented each time the B-tree's
				 * contents change structurally, or when the
				 * start/end limits change, and means that any
				 * cached TkTextIndex objects are no longer
				 * valid. */
    int imageCount;		/* Used for creating unique image names. */

    /*
     * Information related to the undo/redo functionality.
     */

    TkUndoRedoStack *undoStack;	/* The undo/redo stack. */
    int undo;			/* Non-zero means the undo/redo behaviour is
				 * enabled. */
    int maxUndo;		/* The maximum depth of the undo stack
				 * expressed as the maximum number of compound
				 * statements. */
    int autoSeparators;		/* Non-zero means the separators will be
				 * inserted automatically. */
    int isDirty;		/* Flag indicating the 'dirtyness' of the
				 * text widget. If the flag is not zero,
				 * unsaved modifications have been applied to
				 * the text widget. */
    TkTextDirtyMode dirtyMode;	/* The nature of the dirtyness characterized
				 * by the isDirty flag. */
    TkTextEditMode lastEditMode;/* Keeps track of what the last edit mode
				 * was. */

    /*
     * Keep track of all the peers
     */

    struct TkText *peers;
} TkSharedText;

/*
 * The following enum is used to define a type for the -insertunfocussed
 * option of the Text widget.
 */

typedef enum {
    TK_TEXT_INSERT_NOFOCUS_HOLLOW,
    TK_TEXT_INSERT_NOFOCUS_NONE,
    TK_TEXT_INSERT_NOFOCUS_SOLID
} TkTextInsertUnfocussed;

/*
 * A data structure of the following type is kept for each text widget that
 * currently exists for this process:
 */

typedef struct TkText {
    /*
     * Information related to and accessed by widget peers and the
     * TkSharedText handling routines.
     */

    TkSharedText *sharedTextPtr;/* Shared section of all peers. */
    struct TkText *next;	/* Next in list of linked peers. */
    TkTextLine *start;		/* First B-tree line to show, or NULL to start
				 * at the beginning. */
    TkTextLine *end;		/* Last B-tree line to show, or NULL for up to
				 * the end. */
    int pixelReference;		/* Counter into the current tree reference
				 * index corresponding to this widget. */
    int abortSelections;	/* Set to 1 whenever the text is modified in a
				 * way that interferes with selection
				 * retrieval: used to abort incremental
				 * selection retrievals. */

    /*
     * Standard Tk widget information and text-widget specific items
     */

    Tk_Window tkwin;		/* Window that embodies the text. NULL means
				 * that the window has been destroyed but the
				 * data structures haven't yet been cleaned
				 * up.*/
    Display *display;		/* Display for widget. Needed, among other
				 * things, to allow resources to be freed even
				 * after tkwin has gone away. */
    Tcl_Interp *interp;		/* Interpreter associated with widget. Used to
				 * delete widget command. */
    Tcl_Command widgetCmd;	/* Token for text's widget command. */
    int state;			/* Either STATE_NORMAL or STATE_DISABLED. A
				 * text widget is read-only when disabled. */

    /*
     * Default information for displaying (may be overridden by tags applied
     * to ranges of characters).
     */

    Tk_3DBorder border;		/* Structure used to draw 3-D border and
				 * default background. */
    int borderWidth;		/* Width of 3-D border to draw around entire
				 * widget. */
    int padX, padY;		/* Padding between text and window border. */
    int relief;			/* 3-d effect for border around entire widget:
				 * TK_RELIEF_RAISED etc. */
    int highlightWidth;		/* Width in pixels of highlight to draw around
				 * widget when it has the focus. <= 0 means
				 * don't draw a highlight. */
    XColor *highlightBgColorPtr;
				/* Color for drawing traversal highlight area
				 * when highlight is off. */
    XColor *highlightColorPtr;	/* Color for drawing traversal highlight. */
    Tk_Cursor cursor;		/* Current cursor for window, or NULL. */
    XColor *fgColor;		/* Default foreground color for text. */
    Tk_Font tkfont;		/* Default font for displaying text. */
    int charWidth;		/* Width of average character in default
				 * font. */
    int charHeight;		/* Height of average character in default
				 * font, including line spacing. */
    int spacing1;		/* Default extra spacing above first display
				 * line for each text line. */
    int spacing2;		/* Default extra spacing between display lines
				 * for the same text line. */
    int spacing3;		/* Default extra spacing below last display
				 * line for each text line. */
    Tcl_Obj *tabOptionPtr; 	/* Value of -tabs option string. */
    TkTextTabArray *tabArrayPtr;
				/* Information about tab stops (malloc'ed).
				 * NULL means perform default tabbing
				 * behavior. */
    int tabStyle;		/* One of TABULAR or WORDPROCESSOR. */

    /*
     * Additional information used for displaying:
     */

    TkWrapMode wrapMode;	/* How to handle wrap-around. Must be
				 * TEXT_WRAPMODE_CHAR, TEXT_WRAPMODE_NONE, or
				 * TEXT_WRAPMODE_WORD. */
    int width, height;		/* Desired dimensions for window, measured in
				 * characters. */
    int setGrid;		/* Non-zero means pass gridding information to
				 * window manager. */
    int prevWidth, prevHeight;	/* Last known dimensions of window; used to
				 * detect changes in size. */
    TkTextIndex topIndex;	/* Identifies first character in top display
				 * line of window. */
    struct TextDInfo *dInfoPtr;	/* Information maintained by tkTextDisp.c. */

    /*
     * Information related to selection.
     */

    TkTextTag *selTagPtr;	/* Pointer to "sel" tag. Used to tell when a
				 * new selection has been made. */
    Tk_3DBorder selBorder;	/* Border and background for selected
				 * characters. This is a copy of information
				 * in *selTagPtr, so it shouldn't be
				 * explicitly freed. */
    Tk_3DBorder inactiveSelBorder;
				/* Border and background for selected
				 * characters when they don't have the
				 * focus. */
    int selBorderWidth;		/* Width of border around selection. */
    Tcl_Obj *selBorderWidthPtr;	/* Width of border around selection. */
    XColor *selFgColorPtr;	/* Foreground color for selected text. This is
				 * a copy of information in *selTagPtr, so it
				 * shouldn't be explicitly freed. */
    int exportSelection;	/* Non-zero means tie "sel" tag to X
				 * selection. */
    TkTextIndex selIndex;	/* Used during multi-pass selection
				 * retrievals. This index identifies the next
				 * character to be returned from the
				 * selection. */

    /*
     * Information related to insertion cursor:
     */

    TkTextSegment *insertMarkPtr;
				/* Points to segment for "insert" mark. */
    Tk_3DBorder insertBorder;	/* Used to draw vertical bar for insertion
				 * cursor. */
    int insertWidth;		/* Total width of insert cursor. */
    int insertBorderWidth;	/* Width of 3-D border around insert cursor */
    TkTextInsertUnfocussed insertUnfocussed;
				/* How to display the insert cursor when the
				 * text widget does not have the focus. */
    int insertOnTime;		/* Number of milliseconds cursor should spend
				 * in "on" state for each blink. */
    int insertOffTime;		/* Number of milliseconds cursor should spend
				 * in "off" state for each blink. */
    Tcl_TimerToken insertBlinkHandler;
				/* Timer handler used to blink cursor on and
				 * off. */

    /*
     * Information used for event bindings associated with tags:
     */

    TkTextSegment *currentMarkPtr;
				/* Pointer to segment for "current" mark, or
				 * NULL if none. */
    XEvent pickEvent;		/* The event from which the current character
				 * was chosen. Must be saved so that we can
				 * repick after modifications to the text. */
    int numCurTags;		/* Number of tags associated with character at
				 * current mark. */
    TkTextTag **curTagArrayPtr;	/* Pointer to array of tags for current mark,
				 * or NULL if none. */

    /*
     * Miscellaneous additional information:
     */

    char *takeFocus;		/* Value of -takeFocus option; not used in the
				 * C code, but used by keyboard traversal
				 * scripts. Malloc'ed, but may be NULL. */
    char *xScrollCmd;		/* Prefix of command to issue to update
				 * horizontal scrollbar when view changes. */
    char *yScrollCmd;		/* Prefix of command to issue to update
				 * vertical scrollbar when view changes. */
    int flags;			/* Miscellaneous flags; see below for
				 * definitions. */
    Tk_OptionTable optionTable;	/* Token representing the configuration
				 * specifications. */
    int refCount;		/* Number of cached TkTextIndex objects
				 * refering to us. */
    int insertCursorType;	/* 0 = standard insertion cursor, 1 = block
				 * cursor. */

    /*
     * Copies of information from the shared section relating to the undo/redo
     * functonality
     */

    int undo;			/* Non-zero means the undo/redo behaviour is
				 * enabled. */
    int maxUndo;		/* The maximum depth of the undo stack
				 * expressed as the maximum number of compound
				 * statements. */
    int autoSeparators;		/* Non-zero means the separators will be
				 * inserted automatically. */
    Tcl_Obj *afterSyncCmd;	/* Command to be executed when lines are up to
                                 * date */
} TkText;

/*
 * Flag values for TkText records:
 *
 * GOT_SELECTION:		Non-zero means we've already claimed the
 *				selection.
 * INSERT_ON:			Non-zero means insertion cursor should be
 *				displayed on screen.
 * GOT_FOCUS:			Non-zero means this window has the input
 *				focus.
 * BUTTON_DOWN:			1 means that a mouse button is currently down;
 *				this is used to implement grabs for the
 *				duration of button presses.
 * UPDATE_SCROLLBARS:		Non-zero means scrollbar(s) should be updated
 *				during next redisplay operation.
 * NEED_REPICK			This appears unused and should probably be
 *				ignored.
 * OPTIONS_FREED		The widget's options have been freed.
 * DESTROYED			The widget is going away.
 */

#define GOT_SELECTION		1
#define INSERT_ON		2
#define GOT_FOCUS		4
#define BUTTON_DOWN		8
#define UPDATE_SCROLLBARS	0x10
#define NEED_REPICK		0x20
#define OPTIONS_FREED		0x40
#define DESTROYED		0x80

/*
 * Records of the following type define segment types in terms of a collection
 * of procedures that may be called to manipulate segments of that type.
 */

typedef TkTextSegment *	Tk_SegSplitProc(struct TkTextSegment *segPtr,
			    int index);
typedef int		Tk_SegDeleteProc(struct TkTextSegment *segPtr,
			    TkTextLine *linePtr, int treeGone);
typedef TkTextSegment *	Tk_SegCleanupProc(struct TkTextSegment *segPtr,
			    TkTextLine *linePtr);
typedef void		Tk_SegLineChangeProc(struct TkTextSegment *segPtr,
			    TkTextLine *linePtr);
typedef int		Tk_SegLayoutProc(struct TkText *textPtr,
			    struct TkTextIndex *indexPtr,
			    TkTextSegment *segPtr, int offset, int maxX,
			    int maxChars, int noCharsYet, TkWrapMode wrapMode,
			    struct TkTextDispChunk *chunkPtr);
typedef void		Tk_SegCheckProc(TkTextSegment *segPtr,
			    TkTextLine *linePtr);

typedef struct Tk_SegType {
    const char *name;		/* Name of this kind of segment. */
    int leftGravity;		/* If a segment has zero size (e.g. a mark or
				 * tag toggle), does it attach to character to
				 * its left or right? 1 means left, 0 means
				 * right. */
    Tk_SegSplitProc *splitProc;	/* Procedure to split large segment into two
				 * smaller ones. */
    Tk_SegDeleteProc *deleteProc;
				/* Procedure to call to delete segment. */
    Tk_SegCleanupProc *cleanupProc;
				/* After any change to a line, this procedure
				 * is invoked for all segments left in the
				 * line to perform any cleanup they wish
				 * (e.g. joining neighboring segments). */
    Tk_SegLineChangeProc *lineChangeProc;
				/* Invoked when a segment is about to be moved
				 * from its current line to an earlier line
				 * because of a deletion. The linePtr is that
				 * for the segment's old line. CleanupProc
				 * will be invoked after the deletion is
				 * finished. */
    Tk_SegLayoutProc *layoutProc;
				/* Returns size information when figuring out
				 * what to display in window. */
    Tk_SegCheckProc *checkProc;	/* Called during consistency checks to check
				 * internal consistency of segment. */
} Tk_SegType;

/*
 * The following type and items describe different flags for text widget items
 * to count. They are used in both tkText.c and tkTextIndex.c, in
 * 'CountIndices', 'TkTextIndexBackChars', 'TkTextIndexForwChars', and
 * 'TkTextIndexCount'.
 */

typedef int TkTextCountType;

#define COUNT_CHARS 0
#define COUNT_INDICES 1
#define COUNT_DISPLAY 2
#define COUNT_DISPLAY_CHARS (COUNT_CHARS | COUNT_DISPLAY)
#define COUNT_DISPLAY_INDICES (COUNT_INDICES | COUNT_DISPLAY)

/*
 * The following structure is used to keep track of elided text taking account
 * of different tag priorities, it is need for quick calculations of whether a
 * single index is elided, and to start at a given index and maintain a
 * correct elide state as we move or count forwards or backwards.
 */

#define LOTSA_TAGS 1000
typedef struct TkTextElideInfo {
    int numTags;		/* Total tags in widget. */
    int elide;			/* Is the state currently elided. */
    int elidePriority;		/* Tag priority controlling elide state. */
    TkTextSegment *segPtr;	/* Segment to look at next. */
    int segOffset;		/* Offset of segment within line. */
    int deftagCnts[LOTSA_TAGS];
    TkTextTag *deftagPtrs[LOTSA_TAGS];
    int *tagCnts;		/* 0 or 1 depending if the tag with that
				 * priority is on or off. */
    TkTextTag **tagPtrs;	/* Only filled with a tagPtr if the
				 * corresponding tagCnt is 1. */
} TkTextElideInfo;

/*
 * The constant below is used to specify a line when what is really wanted is
 * the entire text. For now, just use a very big number.
 */

#define TK_END_OF_TEXT		1000000

/*
 * The following definition specifies the maximum number of characters needed
 * in a string to hold a position specifier.
 */

#define TK_POS_CHARS		30

/*
 * Mask used for those options which may impact the pixel height calculations
 * of individual lines displayed in the widget.
 */

#define TK_TEXT_LINE_GEOMETRY	1

/*
 * Mask used for those options which may impact the start and end lines used
 * in the widget.
 */

#define TK_TEXT_LINE_RANGE	2

/*
 * Used as 'action' values in calls to TkTextInvalidateLineMetrics
 */

#define TK_TEXT_INVALIDATE_ONLY		0
#define TK_TEXT_INVALIDATE_INSERT	1
#define TK_TEXT_INVALIDATE_DELETE	2

/*
 * Used as special 'pickPlace' values in calls to TkTextSetYView. Zero or
 * positive values indicate a number of pixels.
 */

#define TK_TEXT_PICKPLACE	-1
#define TK_TEXT_NOPIXELADJUST	-2

/*
 * Declarations for variables shared among the text-related files:
 */

MODULE_SCOPE int	tkBTreeDebug;
MODULE_SCOPE int	tkTextDebug;
MODULE_SCOPE const Tk_SegType tkTextCharType;
MODULE_SCOPE const Tk_SegType tkTextLeftMarkType;
MODULE_SCOPE const Tk_SegType tkTextRightMarkType;
MODULE_SCOPE const Tk_SegType tkTextToggleOnType;
MODULE_SCOPE const Tk_SegType tkTextToggleOffType;
MODULE_SCOPE const Tk_SegType tkTextEmbWindowType;
MODULE_SCOPE const Tk_SegType tkTextEmbImageType;

/*
 * Convenience macros for use by B-tree clients which want to access pixel
 * information on each line. Currently only used by TkTextDisp.c
 */

#define TkBTreeLinePixelCount(text, line) \
	(line)->pixels[2*(text)->pixelReference]
#define TkBTreeLinePixelEpoch(text, line) \
	(line)->pixels[1+2*(text)->pixelReference]

/*
 * Declarations for procedures that are used by the text-related files but
 * shouldn't be used anywhere else in Tk (or by Tk clients):
 */

MODULE_SCOPE int	TkBTreeAdjustPixelHeight(const TkText *textPtr,
			    TkTextLine *linePtr, int newPixelHeight,
			    int mergedLogicalLines);
MODULE_SCOPE int	TkBTreeCharTagged(const TkTextIndex *indexPtr,
			    TkTextTag *tagPtr);
MODULE_SCOPE void	TkBTreeCheck(TkTextBTree tree);
MODULE_SCOPE TkTextBTree TkBTreeCreate(TkSharedText *sharedTextPtr);
MODULE_SCOPE void	TkBTreeAddClient(TkTextBTree tree, TkText *textPtr,
			    int defaultHeight);
MODULE_SCOPE void	TkBTreeClientRangeChanged(TkText *textPtr,
			    int defaultHeight);
MODULE_SCOPE void	TkBTreeRemoveClient(TkTextBTree tree,
			    TkText *textPtr);
MODULE_SCOPE void	TkBTreeDestroy(TkTextBTree tree);
MODULE_SCOPE void	TkBTreeDeleteIndexRange(TkTextBTree tree,
			    TkTextIndex *index1Ptr, TkTextIndex *index2Ptr);
MODULE_SCOPE int	TkBTreeEpoch(TkTextBTree tree);
MODULE_SCOPE TkTextLine *TkBTreeFindLine(TkTextBTree tree,
			    const TkText *textPtr, int line);
MODULE_SCOPE TkTextLine *TkBTreeFindPixelLine(TkTextBTree tree,
			    const TkText *textPtr, int pixels,
			    int *pixelOffset);
MODULE_SCOPE TkTextTag **TkBTreeGetTags(const TkTextIndex *indexPtr,
			    const TkText *textPtr, int *numTagsPtr);
MODULE_SCOPE void	TkBTreeInsertChars(TkTextBTree tree,
			    TkTextIndex *indexPtr, const char *string);
MODULE_SCOPE int	TkBTreeLinesTo(const TkText *textPtr,
			    TkTextLine *linePtr);
MODULE_SCOPE int	TkBTreePixelsTo(const TkText *textPtr,
			    TkTextLine *linePtr);
MODULE_SCOPE void	TkBTreeLinkSegment(TkTextSegment *segPtr,
			    TkTextIndex *indexPtr);
MODULE_SCOPE TkTextLine *TkBTreeNextLine(const TkText *textPtr,
			    TkTextLine *linePtr);
MODULE_SCOPE int	TkBTreeNextTag(TkTextSearch *searchPtr);
MODULE_SCOPE int	TkBTreeNumPixels(TkTextBTree tree,
			    const TkText *textPtr);
MODULE_SCOPE TkTextLine *TkBTreePreviousLine(TkText *textPtr,
			    TkTextLine *linePtr);
MODULE_SCOPE int	TkBTreePrevTag(TkTextSearch *searchPtr);
MODULE_SCOPE void	TkBTreeStartSearch(TkTextIndex *index1Ptr,
			    TkTextIndex *index2Ptr, TkTextTag *tagPtr,
			    TkTextSearch *searchPtr);
MODULE_SCOPE void	TkBTreeStartSearchBack(TkTextIndex *index1Ptr,
			    TkTextIndex *index2Ptr, TkTextTag *tagPtr,
			    TkTextSearch *searchPtr);
MODULE_SCOPE int	TkBTreeTag(TkTextIndex *index1Ptr,
			    TkTextIndex *index2Ptr, TkTextTag *tagPtr,
			    int add);
MODULE_SCOPE void	TkBTreeUnlinkSegment(TkTextSegment *segPtr,
			    TkTextLine *linePtr);
MODULE_SCOPE void	TkTextBindProc(ClientData clientData,
			    XEvent *eventPtr);
MODULE_SCOPE void	TkTextSelectionEvent(TkText *textPtr);
MODULE_SCOPE int	TkTextIndexBbox(TkText *textPtr,
			    const TkTextIndex *indexPtr, int *xPtr, int *yPtr,
			    int *widthPtr, int *heightPtr, int *charWidthPtr);
MODULE_SCOPE int	TkTextCharLayoutProc(TkText *textPtr,
			    TkTextIndex *indexPtr, TkTextSegment *segPtr,
			    int offset, int maxX, int maxChars, int noBreakYet,
			    TkWrapMode wrapMode, TkTextDispChunk *chunkPtr);
MODULE_SCOPE void	TkTextCreateDInfo(TkText *textPtr);
MODULE_SCOPE int	TkTextDLineInfo(TkText *textPtr,
			    const TkTextIndex *indexPtr, int *xPtr, int *yPtr,
			    int *widthPtr, int *heightPtr, int *basePtr);
MODULE_SCOPE void	TkTextEmbWinDisplayProc(TkText *textPtr,
			    TkTextDispChunk *chunkPtr, int x, int y,
			    int lineHeight, int baseline, Display *display,
			    Drawable dst, int screenY);
MODULE_SCOPE TkTextTag *TkTextCreateTag(TkText *textPtr,
			    const char *tagName, int *newTag);
MODULE_SCOPE void	TkTextFreeDInfo(TkText *textPtr);
MODULE_SCOPE void	TkTextDeleteTag(TkText *textPtr, TkTextTag *tagPtr);
MODULE_SCOPE void	TkTextFreeTag(TkText *textPtr, TkTextTag *tagPtr);
MODULE_SCOPE int	TkTextGetObjIndex(Tcl_Interp *interp, TkText *textPtr,
			    Tcl_Obj *idxPtr, TkTextIndex *indexPtr);
MODULE_SCOPE int	TkTextSharedGetObjIndex(Tcl_Interp *interp,
			    TkSharedText *sharedTextPtr, Tcl_Obj *idxPtr,
			    TkTextIndex *indexPtr);
MODULE_SCOPE const	TkTextIndex *TkTextGetIndexFromObj(Tcl_Interp *interp,
			    TkText *textPtr, Tcl_Obj *objPtr);
MODULE_SCOPE TkTextTabArray *TkTextGetTabs(Tcl_Interp *interp,
			    TkText *textPtr, Tcl_Obj *stringPtr);
MODULE_SCOPE void	TkTextFindDisplayLineEnd(TkText *textPtr,
			    TkTextIndex *indexPtr, int end, int *xOffset);
MODULE_SCOPE void	TkTextIndexBackChars(const TkText *textPtr,
			    const TkTextIndex *srcPtr, int count,
			    TkTextIndex *dstPtr, TkTextCountType type);
MODULE_SCOPE int	TkTextIndexCmp(const TkTextIndex *index1Ptr,
			    const TkTextIndex *index2Ptr);
MODULE_SCOPE int	TkTextIndexCountBytes(const TkText *textPtr,
			    const TkTextIndex *index1Ptr,
			    const TkTextIndex *index2Ptr);
MODULE_SCOPE int	TkTextIndexCount(const TkText *textPtr,
			    const TkTextIndex *index1Ptr,
			    const TkTextIndex *index2Ptr,
			    TkTextCountType type);
MODULE_SCOPE void	TkTextIndexForwChars(const TkText *textPtr,
			    const TkTextIndex *srcPtr, int count,
			    TkTextIndex *dstPtr, TkTextCountType type);
MODULE_SCOPE void	TkTextIndexOfX(TkText *textPtr, int x,
			    TkTextIndex *indexPtr);
MODULE_SCOPE int	TkTextIndexYPixels(TkText *textPtr,
			    const TkTextIndex *indexPtr);
MODULE_SCOPE TkTextSegment *TkTextIndexToSeg(const TkTextIndex *indexPtr,
			    int *offsetPtr);
MODULE_SCOPE void	TkTextLostSelection(ClientData clientData);
MODULE_SCOPE TkTextIndex *TkTextMakeCharIndex(TkTextBTree tree, TkText *textPtr,
			    int lineIndex, int charIndex,
			    TkTextIndex *indexPtr);
MODULE_SCOPE int	TkTextMeasureDown(TkText *textPtr,
			    TkTextIndex *srcPtr, int distance);
MODULE_SCOPE void	TkTextFreeElideInfo(TkTextElideInfo *infoPtr);
MODULE_SCOPE int	TkTextIsElided(const TkText *textPtr,
			    const TkTextIndex *indexPtr,
			    TkTextElideInfo *infoPtr);
MODULE_SCOPE int	TkTextMakePixelIndex(TkText *textPtr,
			    int pixelIndex, TkTextIndex *indexPtr);
MODULE_SCOPE void	TkTextInvalidateLineMetrics(
			    TkSharedText *sharedTextPtr, TkText *textPtr,
			    TkTextLine *linePtr, int lineCount, int action);
MODULE_SCOPE int	TkTextUpdateLineMetrics(TkText *textPtr, int lineNum,
			    int endLine, int doThisMuch);
MODULE_SCOPE int	TkTextUpdateOneLine(TkText *textPtr,
			    TkTextLine *linePtr, int pixelHeight,
			    TkTextIndex *indexPtr, int partialCalc);
MODULE_SCOPE int	TkTextMarkCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextMarkNameToIndex(TkText *textPtr,
			    const char *name, TkTextIndex *indexPtr);
MODULE_SCOPE void	TkTextMarkSegToIndex(TkText *textPtr,
			    TkTextSegment *markPtr, TkTextIndex *indexPtr);
MODULE_SCOPE void	TkTextEventuallyRepick(TkText *textPtr);
MODULE_SCOPE Bool	TkTextPendingsync(TkText *textPtr);
MODULE_SCOPE void	TkTextPickCurrent(TkText *textPtr, XEvent *eventPtr);
MODULE_SCOPE void	TkTextPixelIndex(TkText *textPtr, int x, int y,
			    TkTextIndex *indexPtr, int *nearest);
MODULE_SCOPE Tcl_Obj *	TkTextNewIndexObj(TkText *textPtr,
			    const TkTextIndex *indexPtr);
MODULE_SCOPE void	TkTextRedrawRegion(TkText *textPtr, int x, int y,
			    int width, int height);
MODULE_SCOPE void	TkTextRedrawTag(TkSharedText *sharedTextPtr,
			    TkText *textPtr, TkTextIndex *index1Ptr,
			    TkTextIndex *index2Ptr, TkTextTag *tagPtr,
			    int withTag);
MODULE_SCOPE void	TkTextRelayoutWindow(TkText *textPtr, int mask);
MODULE_SCOPE int	TkTextScanCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextSeeCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextSegToOffset(const TkTextSegment *segPtr,
			    const TkTextLine *linePtr);
MODULE_SCOPE void	TkTextSetYView(TkText *textPtr,
			    TkTextIndex *indexPtr, int pickPlace);
MODULE_SCOPE int	TkTextTagCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextImageCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextImageIndex(TkText *textPtr,
			    const char *name, TkTextIndex *indexPtr);
MODULE_SCOPE int	TkTextWindowCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int	TkTextWindowIndex(TkText *textPtr, const char *name,
			    TkTextIndex *indexPtr);
MODULE_SCOPE int	TkTextYviewCmd(TkText *textPtr, Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE void	TkTextWinFreeClient(Tcl_HashEntry *hPtr,
			    TkTextEmbWindowClient *client);
MODULE_SCOPE void       TkTextRunAfterSyncCmd(ClientData clientData);
MODULE_SCOPE int        TkTextIndexAdjustToStartEnd(TkText *textPtr,
			    TkTextIndex *indexPtr, int err);
#endif /* _TKTEXT */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
