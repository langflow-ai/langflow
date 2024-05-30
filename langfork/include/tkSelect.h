/*
 * tkSelect.h --
 *
 *	Declarations of types shared among the files that implement selection
 *	support.
 *
 * Copyright (c) 1995 Sun Microsystems, Inc.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TKSELECT
#define _TKSELECT

/*
 * When a selection is owned by a window on a given display, one of the
 * following structures is present on a list of current selections in the
 * display structure. The structure is used to record the current owner of a
 * selection for use in later retrieval requests. There is a list of such
 * structures because a display can have multiple different selections active
 * at the same time.
 */

typedef struct TkSelectionInfo {
    Atom selection;		/* Selection name, e.g. XA_PRIMARY. */
    Tk_Window owner;		/* Current owner of this selection. */
    int serial;			/* Serial number of last XSelectionSetOwner
				 * request made to server for this selection
				 * (used to filter out redundant
				 * SelectionClear events). */
    Time time;			/* Timestamp used to acquire selection. */
    Tk_LostSelProc *clearProc;	/* Procedure to call when owner loses
				 * selection. */
    ClientData clearData;	/* Info to pass to clearProc. */
    struct TkSelectionInfo *nextPtr;
				/* Next in list of current selections on this
				 * display. NULL means end of list. */
} TkSelectionInfo;

/*
 * One of the following structures exists for each selection handler created
 * for a window by calling Tk_CreateSelHandler. The handlers are linked in a
 * list rooted in the TkWindow structure.
 */

typedef struct TkSelHandler {
    Atom selection;		/* Selection name, e.g. XA_PRIMARY. */
    Atom target;		/* Target type for selection conversion, such
				 * as TARGETS or STRING. */
    Atom format;		/* Format in which selection info will be
				 * returned, such as STRING or ATOM. */
    Tk_SelectionProc *proc;	/* Procedure to generate selection in this
				 * format. */
    ClientData clientData;	/* Argument to pass to proc. */
    int size;			/* Size of units returned by proc (8 for
				 * STRING, 32 for almost anything else). */
    struct TkSelHandler *nextPtr;
				/* Next selection handler associated with same
				 * window (NULL for end of list). */
} TkSelHandler;

/*
 * When the selection is being retrieved, one of the following structures is
 * present on a list of pending selection retrievals. The structure is used to
 * communicate between the background procedure that requests the selection
 * and the foreground event handler that processes the events in which the
 * selection is returned. There is a list of such structures so that there can
 * be multiple simultaneous selection retrievals (e.g. on different displays).
 */

typedef struct TkSelRetrievalInfo {
    Tcl_Interp *interp;		/* Interpreter for error reporting. */
    TkWindow *winPtr;		/* Window used as requestor for selection. */
    Atom selection;		/* Selection being requested. */
    Atom property;		/* Property where selection will appear. */
    Atom target;		/* Desired form for selection. */
    Tk_GetSelProc *proc;	/* Procedure to call to handle pieces of
				 * selection. */
    ClientData clientData;	/* Argument for proc. */
    int result;			/* Initially -1. Set to a Tcl return value
				 * once the selection has been retrieved. */
    Tcl_TimerToken timeout;	/* Token for current timeout procedure. */
    int idleTime;		/* Number of seconds that have gone by without
				 * hearing anything from the selection
				 * owner. */
    Tcl_EncodingState encState;	/* Holds intermediate state during translations
				 * of data that cross buffer boundaries. */
    int encFlags;		/* Encoding translation state flags. */
    Tcl_DString buf;		/* Buffer to hold translation data. */
    struct TkSelRetrievalInfo *nextPtr;
				/* Next in list of all pending selection
				 * retrievals. NULL means end of list. */
} TkSelRetrievalInfo;

/*
 * The clipboard contains a list of buffers of various types and formats. All
 * of the buffers of a given type will be returned in sequence when the
 * CLIPBOARD selection is retrieved. All buffers of a given type on the same
 * clipboard must have the same format. The TkClipboardTarget structure is
 * used to record the information about a chain of buffers of the same type.
 */

typedef struct TkClipboardBuffer {
    char *buffer;		/* Null terminated data buffer. */
    long length;		/* Length of string in buffer. */
    struct TkClipboardBuffer *nextPtr;
				/* Next in list of buffers. NULL means end of
				 * list . */
} TkClipboardBuffer;

typedef struct TkClipboardTarget {
    Atom type;			/* Type conversion supported. */
    Atom format;		/* Representation used for data. */
    TkClipboardBuffer *firstBufferPtr;
				/* First in list of data buffers. */
    TkClipboardBuffer *lastBufferPtr;
				/* Last in list of clipboard buffers. Used to
				 * speed up appends. */
    struct TkClipboardTarget *nextPtr;
				/* Next in list of targets on clipboard. NULL
				 * means end of list. */
} TkClipboardTarget;

/*
 * It is possible for a Tk_SelectionProc to delete the handler that it
 * represents. If this happens, the code that is retrieving the selection
 * needs to know about it so it doesn't use the now-defunct handler structure.
 * One structure of the following form is created for each retrieval in
 * progress, so that the retriever can find out if its handler is deleted. All
 * of the pending retrievals (if there are more than one) are linked into a
 * list.
 */

typedef struct TkSelInProgress {
    TkSelHandler *selPtr;	/* Handler being executed. If this handler is
				 * deleted, the field is set to NULL. */
    struct TkSelInProgress *nextPtr;
				/* Next higher nested search. */
} TkSelInProgress;

/*
 * Chunk size for retrieving selection. It's defined both in words and in
 * bytes; the word size is used to allocate buffer space that's guaranteed to
 * be word-aligned and that has an extra character for the terminating NULL.
 */

#define TK_SEL_BYTES_AT_ONCE 4000
#define TK_SEL_WORDS_AT_ONCE 1001

/*
 * Declarations for procedures that are used by the selection-related files
 * but shouldn't be used anywhere else in Tk (or by Tk clients):
 */

MODULE_SCOPE TkSelInProgress *TkSelGetInProgress(void);
MODULE_SCOPE void	TkSelSetInProgress(TkSelInProgress *pendingPtr);
MODULE_SCOPE void	TkSelClearSelection(Tk_Window tkwin, XEvent *eventPtr);
MODULE_SCOPE int	TkSelDefaultSelection(TkSelectionInfo *infoPtr,
			    Atom target, char *buffer, int maxBytes,
			    Atom *typePtr);
#ifndef TkSelUpdateClipboard
MODULE_SCOPE void	TkSelUpdateClipboard(TkWindow *winPtr,
			    TkClipboardTarget *targetPtr);
#endif

#endif /* _TKSELECT */
