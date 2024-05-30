/*
 * tkBusy.h --
 *
 *	This file defines the type of the structure describing a busy window.
 *
 * Copyright 1993-1998 Lucent Technologies, Inc.
 *
 *	The "busy" command was created by George Howlett. Adapted for
 *	integration into Tk by Jos Decoster and Donal K. Fellows.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

typedef struct Busy {
    Display *display;		/* Display of busy window */
    Tcl_Interp *interp;		/* Interpreter where "busy" command was
				 * created. It's used to key the searches in
				 * the window hierarchy. See the "windows"
				 * command. */
    Tk_Window tkBusy;		/* Busy window: Transparent window used to
				 * block delivery of events to windows
				 * underneath it. */
    Tk_Window tkParent;		/* Parent window of the busy window. It may be
				 * the reference window (if the reference is a
				 * toplevel) or a mutual ancestor of the
				 * reference window */
    Tk_Window tkRef;		/* Reference window of the busy window. It is
				 * used to manage the size and position of the
				 * busy window. */
    int x, y;			/* Position of the reference window */
    int width, height;		/* Size of the reference window. Retained to
				 * know if the reference window has been
				 * reconfigured to a new size. */
    int menuBar;		/* Menu bar flag. */
    Tk_Cursor cursor;		/* Cursor for the busy window. */
    Tcl_HashEntry *hashPtr;	/* Used the delete the busy window entry out
				 * of the global hash table. */
    Tcl_HashTable *tablePtr;
    Tk_OptionTable optionTable;
} Busy;
