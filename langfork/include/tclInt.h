/*
 * tclInt.h --
 *
 *	Declarations of things used internally by the Tcl interpreter.
 *
 * Copyright (c) 1987-1993 The Regents of the University of California.
 * Copyright (c) 1993-1997 Lucent Technologies.
 * Copyright (c) 1994-1998 Sun Microsystems, Inc.
 * Copyright (c) 1998-1999 by Scriptics Corporation.
 * Copyright (c) 2001, 2002 by Kevin B. Kenny.  All rights reserved.
 * Copyright (c) 2007 Daniel A. Steffen <das@users.sourceforge.net>
 * Copyright (c) 2006-2008 by Joe Mistachkin.  All rights reserved.
 * Copyright (c) 2008 by Miguel Sofer. All rights reserved.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TCLINT
#define _TCLINT

/*
 * Some numerics configuration options.
 */

#undef ACCEPT_NAN

/*
 * Common include files needed by most of the Tcl source files are included
 * here, so that system-dependent personalizations for the include files only
 * have to be made in once place. This results in a few extra includes, but
 * greater modularity. The order of the three groups of #includes is
 * important. For example, stdio.h is needed by tcl.h.
 */

#include "tclPort.h"

#include <stdio.h>

#include <ctype.h>
#ifdef NO_STDLIB_H
#   include "../compat/stdlib.h"
#else
#   include <stdlib.h>
#endif
#ifdef NO_STRING_H
#include "../compat/string.h"
#else
#include <string.h>
#endif
#if defined(STDC_HEADERS) || defined(__STDC__) || defined(__C99__FUNC__) \
     || defined(__cplusplus) || defined(_MSC_VER) || defined(__ICC)
#include <stddef.h>
#else
typedef int ptrdiff_t;
#endif

/*
 * Ensure WORDS_BIGENDIAN is defined correctly:
 * Needs to happen here in addition to configure to work with fat compiles on
 * Darwin (where configure runs only once for multiple architectures).
 */

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

/*
 * Macros used to cast between pointers and integers (e.g. when storing an int
 * in ClientData), on 64-bit architectures they avoid gcc warning about "cast
 * to/from pointer from/to integer of different size".
 */

#if !defined(INT2PTR) && !defined(PTR2INT)
#   if defined(HAVE_INTPTR_T) || defined(intptr_t)
#	define INT2PTR(p) ((void *)(intptr_t)(p))
#	define PTR2INT(p) ((int)(intptr_t)(p))
#   else
#	define INT2PTR(p) ((void *)(p))
#	define PTR2INT(p) ((int)(p))
#   endif
#endif
#if !defined(UINT2PTR) && !defined(PTR2UINT)
#   if defined(HAVE_UINTPTR_T) || defined(uintptr_t)
#	define UINT2PTR(p) ((void *)(uintptr_t)(p))
#	define PTR2UINT(p) ((unsigned int)(uintptr_t)(p))
#   else
#	define UINT2PTR(p) ((void *)(p))
#	define PTR2UINT(p) ((unsigned int)(p))
#   endif
#endif

#if defined(_WIN32) && defined(_MSC_VER)
#   define vsnprintf _vsnprintf
#   define snprintf _snprintf
#endif

/*
 * The following procedures allow namespaces to be customized to support
 * special name resolution rules for commands/variables.
 */

struct Tcl_ResolvedVarInfo;

typedef Tcl_Var (Tcl_ResolveRuntimeVarProc)(Tcl_Interp *interp,
	struct Tcl_ResolvedVarInfo *vinfoPtr);

typedef void (Tcl_ResolveVarDeleteProc)(struct Tcl_ResolvedVarInfo *vinfoPtr);

/*
 * The following structure encapsulates the routines needed to resolve a
 * variable reference at runtime. Any variable specific state will typically
 * be appended to this structure.
 */

typedef struct Tcl_ResolvedVarInfo {
    Tcl_ResolveRuntimeVarProc *fetchProc;
    Tcl_ResolveVarDeleteProc *deleteProc;
} Tcl_ResolvedVarInfo;

typedef int (Tcl_ResolveCompiledVarProc)(Tcl_Interp *interp,
	CONST84 char *name, int length, Tcl_Namespace *context,
	Tcl_ResolvedVarInfo **rPtr);

typedef int (Tcl_ResolveVarProc)(Tcl_Interp *interp, CONST84 char *name,
	Tcl_Namespace *context, int flags, Tcl_Var *rPtr);

typedef int (Tcl_ResolveCmdProc)(Tcl_Interp *interp, CONST84 char *name,
	Tcl_Namespace *context, int flags, Tcl_Command *rPtr);

typedef struct Tcl_ResolverInfo {
    Tcl_ResolveCmdProc *cmdResProc;
				/* Procedure handling command name
				 * resolution. */
    Tcl_ResolveVarProc *varResProc;
				/* Procedure handling variable name resolution
				 * for variables that can only be handled at
				 * runtime. */
    Tcl_ResolveCompiledVarProc *compiledVarResProc;
				/* Procedure handling variable name resolution
				 * at compile time. */
} Tcl_ResolverInfo;

/*
 * This flag bit should not interfere with TCL_GLOBAL_ONLY,
 * TCL_NAMESPACE_ONLY, or TCL_LEAVE_ERR_MSG; it signals that the variable
 * lookup is performed for upvar (or similar) purposes, with slightly
 * different rules:
 *    - Bug #696893 - variable is either proc-local or in the current
 *	namespace; never follow the second (global) resolution path
 *    - Bug #631741 - do not use special namespace or interp resolvers
 *
 * It should also not collide with the (deprecated) TCL_PARSE_PART1 flag
 * (Bug #835020)
 */

#define TCL_AVOID_RESOLVERS 0x40000

/*
 *----------------------------------------------------------------
 * Data structures related to namespaces.
 *----------------------------------------------------------------
 */

typedef struct Tcl_Ensemble Tcl_Ensemble;
typedef struct NamespacePathEntry NamespacePathEntry;

/*
 * Special hashtable for variables:  This is just a Tcl_HashTable with a nsPtr
 * field added at the end, so that variables can find their namespace
 * without having to copy a pointer in their struct by accessing them via
 * their hPtr->tablePtr.
 */

typedef struct TclVarHashTable {
    Tcl_HashTable table;
    struct Namespace *nsPtr;
} TclVarHashTable;

/*
 * This is for itcl - it likes to search our varTables directly :(
 */

#define TclVarHashFindVar(tablePtr, key) \
    TclVarHashCreateVar((tablePtr), (key), NULL)

/*
 * Define this to reduce the amount of space that the average namespace
 * consumes by only allocating the table of child namespaces when necessary.
 * Defining it breaks compatibility for Tcl extensions (e.g., itcl) which
 * reach directly into the Namespace structure.
 */

#undef BREAK_NAMESPACE_COMPAT

/*
 * The structure below defines a namespace.
 * Note: the first five fields must match exactly the fields in a
 * Tcl_Namespace structure (see tcl.h). If you change one, be sure to change
 * the other.
 */

typedef struct Namespace {
    char *name;			/* The namespace's simple (unqualified) name.
				 * This contains no ::'s. The name of the
				 * global namespace is "" although "::" is an
				 * synonym. */
    char *fullName;		/* The namespace's fully qualified name. This
				 * starts with ::. */
    ClientData clientData;	/* An arbitrary value associated with this
				 * namespace. */
    Tcl_NamespaceDeleteProc *deleteProc;
				/* Procedure invoked when deleting the
				 * namespace to, e.g., free clientData. */
    struct Namespace *parentPtr;/* Points to the namespace that contains this
				 * one. NULL if this is the global
				 * namespace. */
#ifndef BREAK_NAMESPACE_COMPAT
    Tcl_HashTable childTable;	/* Contains any child namespaces. Indexed by
				 * strings; values have type (Namespace *). */
#else
    Tcl_HashTable *childTablePtr;
				/* Contains any child namespaces. Indexed by
				 * strings; values have type (Namespace *). If
				 * NULL, there are no children. */
#endif
    long nsId;			/* Unique id for the namespace. */
    Tcl_Interp *interp;		/* The interpreter containing this
				 * namespace. */
    int flags;			/* OR-ed combination of the namespace status
				 * flags NS_DYING and NS_DEAD listed below. */
    int activationCount;	/* Number of "activations" or active call
				 * frames for this namespace that are on the
				 * Tcl call stack. The namespace won't be
				 * freed until activationCount becomes zero. */
    int refCount;		/* Count of references by namespaceName
				 * objects. The namespace can't be freed until
				 * refCount becomes zero. */
    Tcl_HashTable cmdTable;	/* Contains all the commands currently
				 * registered in the namespace. Indexed by
				 * strings; values have type (Command *).
				 * Commands imported by Tcl_Import have
				 * Command structures that point (via an
				 * ImportedCmdRef structure) to the Command
				 * structure in the source namespace's command
				 * table. */
    TclVarHashTable varTable;	/* Contains all the (global) variables
				 * currently in this namespace. Indexed by
				 * strings; values have type (Var *). */
    char **exportArrayPtr;	/* Points to an array of string patterns
				 * specifying which commands are exported. A
				 * pattern may include "string match" style
				 * wildcard characters to specify multiple
				 * commands; however, no namespace qualifiers
				 * are allowed. NULL if no export patterns are
				 * registered. */
    int numExportPatterns;	/* Number of export patterns currently
				 * registered using "namespace export". */
    int maxExportPatterns;	/* Number of export patterns for which space
				 * is currently allocated. */
    int cmdRefEpoch;		/* Incremented if a newly added command
				 * shadows a command for which this namespace
				 * has already cached a Command* pointer; this
				 * causes all its cached Command* pointers to
				 * be invalidated. */
    int resolverEpoch;		/* Incremented whenever (a) the name
				 * resolution rules change for this namespace
				 * or (b) a newly added command shadows a
				 * command that is compiled to bytecodes. This
				 * invalidates all byte codes compiled in the
				 * namespace, causing the code to be
				 * recompiled under the new rules.*/
    Tcl_ResolveCmdProc *cmdResProc;
				/* If non-null, this procedure overrides the
				 * usual command resolution mechanism in Tcl.
				 * This procedure is invoked within
				 * Tcl_FindCommand to resolve all command
				 * references within the namespace. */
    Tcl_ResolveVarProc *varResProc;
				/* If non-null, this procedure overrides the
				 * usual variable resolution mechanism in Tcl.
				 * This procedure is invoked within
				 * Tcl_FindNamespaceVar to resolve all
				 * variable references within the namespace at
				 * runtime. */
    Tcl_ResolveCompiledVarProc *compiledVarResProc;
				/* If non-null, this procedure overrides the
				 * usual variable resolution mechanism in Tcl.
				 * This procedure is invoked within
				 * LookupCompiledLocal to resolve variable
				 * references within the namespace at compile
				 * time. */
    int exportLookupEpoch;	/* Incremented whenever a command is added to
				 * a namespace, removed from a namespace or
				 * the exports of a namespace are changed.
				 * Allows TIP#112-driven command lists to be
				 * validated efficiently. */
    Tcl_Ensemble *ensembles;	/* List of structures that contain the details
				 * of the ensembles that are implemented on
				 * top of this namespace. */
    Tcl_Obj *unknownHandlerPtr;	/* A script fragment to be used when command
				 * resolution in this namespace fails. TIP
				 * 181. */
    int commandPathLength;	/* The length of the explicit path. */
    NamespacePathEntry *commandPathArray;
				/* The explicit path of the namespace as an
				 * array. */
    NamespacePathEntry *commandPathSourceList;
				/* Linked list of path entries that point to
				 * this namespace. */
    Tcl_NamespaceDeleteProc *earlyDeleteProc;
				/* Just like the deleteProc field (and called
				 * with the same clientData) but called at the
				 * start of the deletion process, so there is
				 * a chance for code to do stuff inside the
				 * namespace before deletion completes. */
} Namespace;

/*
 * An entry on a namespace's command resolution path.
 */

struct NamespacePathEntry {
    Namespace *nsPtr;		/* What does this path entry point to? If it
				 * is NULL, this path entry points is
				 * redundant and should be skipped. */
    Namespace *creatorNsPtr;	/* Where does this path entry point from? This
				 * allows for efficient invalidation of
				 * references when the path entry's target
				 * updates its current list of defined
				 * commands. */
    NamespacePathEntry *prevPtr, *nextPtr;
				/* Linked list pointers or NULL at either end
				 * of the list that hangs off Namespace's
				 * commandPathSourceList field. */
};

/*
 * Flags used to represent the status of a namespace:
 *
 * NS_DYING -	1 means Tcl_DeleteNamespace has been called to delete the
 *		namespace but there are still active call frames on the Tcl
 *		stack that refer to the namespace. When the last call frame
 *		referring to it has been popped, it's variables and command
 *		will be destroyed and it will be marked "dead" (NS_DEAD). The
 *		namespace can no longer be looked up by name.
 * NS_DEAD -	1 means Tcl_DeleteNamespace has been called to delete the
 *		namespace and no call frames still refer to it. Its variables
 *		and command have already been destroyed. This bit allows the
 *		namespace resolution code to recognize that the namespace is
 *		"deleted". When the last namespaceName object in any byte code
 *		unit that refers to the namespace has been freed (i.e., when
 *		the namespace's refCount is 0), the namespace's storage will
 *		be freed.
 * NS_KILLED -	1 means that TclTeardownNamespace has already been called on
 *		this namespace and it should not be called again [Bug 1355942]
 * NS_SUPPRESS_COMPILATION -
 *		Marks the commands in this namespace for not being compiled,
 *		forcing them to be looked up every time.
 */

#define NS_DYING	0x01
#define NS_DEAD		0x02
#define NS_KILLED	0x04
#define NS_SUPPRESS_COMPILATION	0x08

/*
 * Flags passed to TclGetNamespaceForQualName:
 *
 * TCL_GLOBAL_ONLY		- (see tcl.h) Look only in the global ns.
 * TCL_NAMESPACE_ONLY		- (see tcl.h) Look only in the context ns.
 * TCL_CREATE_NS_IF_UNKNOWN	- Create unknown namespaces.
 * TCL_FIND_ONLY_NS		- The name sought is a namespace name.
 */

#define TCL_CREATE_NS_IF_UNKNOWN	0x800
#define TCL_FIND_ONLY_NS		0x1000

/*
 * The client data for an ensemble command. This consists of the table of
 * commands that are actually exported by the namespace, and an epoch counter
 * that, combined with the exportLookupEpoch field of the namespace structure,
 * defines whether the table contains valid data or will need to be recomputed
 * next time the ensemble command is called.
 */

typedef struct EnsembleConfig {
    Namespace *nsPtr;		/* The namespace backing this ensemble up. */
    Tcl_Command token;		/* The token for the command that provides
				 * ensemble support for the namespace, or NULL
				 * if the command has been deleted (or never
				 * existed; the global namespace never has an
				 * ensemble command.) */
    int epoch;			/* The epoch at which this ensemble's table of
				 * exported commands is valid. */
    char **subcommandArrayPtr;	/* Array of ensemble subcommand names. At all
				 * consistent points, this will have the same
				 * number of entries as there are entries in
				 * the subcommandTable hash. */
    Tcl_HashTable subcommandTable;
				/* Hash table of ensemble subcommand names,
				 * which are its keys so this also provides
				 * the storage management for those subcommand
				 * names. The contents of the entry values are
				 * object version the prefix lists to use when
				 * substituting for the command/subcommand to
				 * build the ensemble implementation command.
				 * Has to be stored here as well as in
				 * subcommandDict because that field is NULL
				 * when we are deriving the ensemble from the
				 * namespace exports list. FUTURE WORK: use
				 * object hash table here. */
    struct EnsembleConfig *next;/* The next ensemble in the linked list of
				 * ensembles associated with a namespace. If
				 * this field points to this ensemble, the
				 * structure has already been unlinked from
				 * all lists, and cannot be found by scanning
				 * the list from the namespace's ensemble
				 * field. */
    int flags;			/* OR'ed combo of TCL_ENSEMBLE_PREFIX,
				 * ENSEMBLE_DEAD and ENSEMBLE_COMPILE. */

    /* OBJECT FIELDS FOR ENSEMBLE CONFIGURATION */

    Tcl_Obj *subcommandDict;	/* Dictionary providing mapping from
				 * subcommands to their implementing command
				 * prefixes, or NULL if we are to build the
				 * map automatically from the namespace
				 * exports. */
    Tcl_Obj *subcmdList;	/* List of commands that this ensemble
				 * actually provides, and whose implementation
				 * will be built using the subcommandDict (if
				 * present and defined) and by simple mapping
				 * to the namespace otherwise. If NULL,
				 * indicates that we are using the (dynamic)
				 * list of currently exported commands. */
    Tcl_Obj *unknownHandler;	/* Script prefix used to handle the case when
				 * no match is found (according to the rule
				 * defined by flag bit TCL_ENSEMBLE_PREFIX) or
				 * NULL to use the default error-generating
				 * behaviour. The script execution gets all
				 * the arguments to the ensemble command
				 * (including objv[0]) and will have the
				 * results passed directly back to the caller
				 * (including the error code) unless the code
				 * is TCL_CONTINUE in which case the
				 * subcommand will be re-parsed by the ensemble
				 * core, presumably because the ensemble
				 * itself has been updated. */
    Tcl_Obj *parameterList;	/* List of ensemble parameter names. */
    int numParameters;		/* Cached number of parameters. This is either
				 * 0 (if the parameterList field is NULL) or
				 * the length of the list in the parameterList
				 * field. */
} EnsembleConfig;

/*
 * Various bits for the EnsembleConfig.flags field.
 */

#define ENSEMBLE_DEAD	0x1	/* Flag value to say that the ensemble is dead
				 * and on its way out. */
#define ENSEMBLE_COMPILE 0x4	/* Flag to enable bytecode compilation of an
				 * ensemble. */

/*
 *----------------------------------------------------------------
 * Data structures related to variables. These are used primarily in tclVar.c
 *----------------------------------------------------------------
 */

/*
 * The following structure defines a variable trace, which is used to invoke a
 * specific C procedure whenever certain operations are performed on a
 * variable.
 */

typedef struct VarTrace {
    Tcl_VarTraceProc *traceProc;/* Procedure to call when operations given by
				 * flags are performed on variable. */
    ClientData clientData;	/* Argument to pass to proc. */
    int flags;			/* What events the trace procedure is
				 * interested in: OR-ed combination of
				 * TCL_TRACE_READS, TCL_TRACE_WRITES,
				 * TCL_TRACE_UNSETS and TCL_TRACE_ARRAY. */
    struct VarTrace *nextPtr;	/* Next in list of traces associated with a
				 * particular variable. */
} VarTrace;

/*
 * The following structure defines a command trace, which is used to invoke a
 * specific C procedure whenever certain operations are performed on a
 * command.
 */

typedef struct CommandTrace {
    Tcl_CommandTraceProc *traceProc;
				/* Procedure to call when operations given by
				 * flags are performed on command. */
    ClientData clientData;	/* Argument to pass to proc. */
    int flags;			/* What events the trace procedure is
				 * interested in: OR-ed combination of
				 * TCL_TRACE_RENAME, TCL_TRACE_DELETE. */
    struct CommandTrace *nextPtr;
				/* Next in list of traces associated with a
				 * particular command. */
    int refCount;		/* Used to ensure this structure is not
				 * deleted too early. Keeps track of how many
				 * pieces of code have a pointer to this
				 * structure. */
} CommandTrace;

/*
 * When a command trace is active (i.e. its associated procedure is executing)
 * one of the following structures is linked into a list associated with the
 * command's interpreter. The information in the structure is needed in order
 * for Tcl to behave reasonably if traces are deleted while traces are active.
 */

typedef struct ActiveCommandTrace {
    struct Command *cmdPtr;	/* Command that's being traced. */
    struct ActiveCommandTrace *nextPtr;
				/* Next in list of all active command traces
				 * for the interpreter, or NULL if no more. */
    CommandTrace *nextTracePtr;	/* Next trace to check after current trace
				 * procedure returns; if this trace gets
				 * deleted, must update pointer to avoid using
				 * free'd memory. */
    int reverseScan;		/* Boolean set true when traces are scanning
				 * in reverse order. */
} ActiveCommandTrace;

/*
 * When a variable trace is active (i.e. its associated procedure is
 * executing) one of the following structures is linked into a list associated
 * with the variable's interpreter. The information in the structure is needed
 * in order for Tcl to behave reasonably if traces are deleted while traces
 * are active.
 */

typedef struct ActiveVarTrace {
    struct Var *varPtr;		/* Variable that's being traced. */
    struct ActiveVarTrace *nextPtr;
				/* Next in list of all active variable traces
				 * for the interpreter, or NULL if no more. */
    VarTrace *nextTracePtr;	/* Next trace to check after current trace
				 * procedure returns; if this trace gets
				 * deleted, must update pointer to avoid using
				 * free'd memory. */
} ActiveVarTrace;

/*
 * The structure below defines a variable, which associates a string name with
 * a Tcl_Obj value. These structures are kept in procedure call frames (for
 * local variables recognized by the compiler) or in the heap (for global
 * variables and any variable not known to the compiler). For each Var
 * structure in the heap, a hash table entry holds the variable name and a
 * pointer to the Var structure.
 */

typedef struct Var {
    int flags;			/* Miscellaneous bits of information about
				 * variable. See below for definitions. */
    union {
	Tcl_Obj *objPtr;	/* The variable's object value. Used for
				 * scalar variables and array elements. */
	TclVarHashTable *tablePtr;/* For array variables, this points to
				 * information about the hash table used to
				 * implement the associative array. Points to
				 * ckalloc-ed data. */
	struct Var *linkPtr;	/* If this is a global variable being referred
				 * to in a procedure, or a variable created by
				 * "upvar", this field points to the
				 * referenced variable's Var struct. */
    } value;
} Var;

typedef struct VarInHash {
    Var var;
    int refCount;		/* Counts number of active uses of this
				 * variable: 1 for the entry in the hash
				 * table, 1 for each additional variable whose
				 * linkPtr points here, 1 for each nested
				 * trace active on variable, and 1 if the
				 * variable is a namespace variable. This
				 * record can't be deleted until refCount
				 * becomes 0. */
    Tcl_HashEntry entry;	/* The hash table entry that refers to this
				 * variable. This is used to find the name of
				 * the variable and to delete it from its
				 * hash table if it is no longer needed. It
				 * also holds the variable's name. */
} VarInHash;

/*
 * Flag bits for variables. The first two (VAR_ARRAY and VAR_LINK) are
 * mutually exclusive and give the "type" of the variable. If none is set,
 * this is a scalar variable.
 *
 * VAR_ARRAY -			1 means this is an array variable rather than
 *				a scalar variable or link. The "tablePtr"
 *				field points to the array's hash table for its
 *				elements.
 * VAR_LINK -			1 means this Var structure contains a pointer
 *				to another Var structure that either has the
 *				real value or is itself another VAR_LINK
 *				pointer. Variables like this come about
 *				through "upvar" and "global" commands, or
 *				through references to variables in enclosing
 *				namespaces.
 *
 * Flags that indicate the type and status of storage; none is set for
 * compiled local variables (Var structs).
 *
 * VAR_IN_HASHTABLE -		1 means this variable is in a hash table and
 *				the Var structure is malloc'ed. 0 if it is a
 *				local variable that was assigned a slot in a
 *				procedure frame by the compiler so the Var
 *				storage is part of the call frame.
 * VAR_DEAD_HASH		1 means that this var's entry in the hash table
 *				has already been deleted.
 * VAR_ARRAY_ELEMENT -		1 means that this variable is an array
 *				element, so it is not legal for it to be an
 *				array itself (the VAR_ARRAY flag had better
 *				not be set).
 * VAR_NAMESPACE_VAR -		1 means that this variable was declared as a
 *				namespace variable. This flag ensures it
 *				persists until its namespace is destroyed or
 *				until the variable is unset; it will persist
 *				even if it has not been initialized and is
 *				marked undefined. The variable's refCount is
 *				incremented to reflect the "reference" from
 *				its namespace.
 *
 * Flag values relating to the variable's trace and search status.
 *
 * VAR_TRACED_READ
 * VAR_TRACED_WRITE
 * VAR_TRACED_UNSET
 * VAR_TRACED_ARRAY
 * VAR_TRACE_ACTIVE -		1 means that trace processing is currently
 *				underway for a read or write access, so new
 *				read or write accesses should not cause trace
 *				procedures to be called and the variable can't
 *				be deleted.
 * VAR_SEARCH_ACTIVE
 *
 * The following additional flags are used with the CompiledLocal type defined
 * below:
 *
 * VAR_ARGUMENT -		1 means that this variable holds a procedure
 *				argument.
 * VAR_TEMPORARY -		1 if the local variable is an anonymous
 *				temporary variable. Temporaries have a NULL
 *				name.
 * VAR_RESOLVED -		1 if name resolution has been done for this
 *				variable.
 * VAR_IS_ARGS			1 if this variable is the last argument and is
 *				named "args".
 */

/*
 * FLAGS RENUMBERED: everything breaks already, make things simpler.
 *
 * IMPORTANT: skip the values 0x10, 0x20, 0x40, 0x800 corresponding to
 * TCL_TRACE_(READS/WRITES/UNSETS/ARRAY): makes code simpler in tclTrace.c
 *
 * Keep the flag values for VAR_ARGUMENT and VAR_TEMPORARY so that old values
 * in precompiled scripts keep working.
 */

/* Type of value (0 is scalar) */
#define VAR_ARRAY		0x1
#define VAR_LINK		0x2

/* Type of storage (0 is compiled local) */
#define VAR_IN_HASHTABLE	0x4
#define VAR_DEAD_HASH		0x8
#define VAR_ARRAY_ELEMENT	0x1000
#define VAR_NAMESPACE_VAR	0x80	/* KEEP OLD VALUE for Itcl */

#define VAR_ALL_HASH \
	(VAR_IN_HASHTABLE|VAR_DEAD_HASH|VAR_NAMESPACE_VAR|VAR_ARRAY_ELEMENT)

/* Trace and search state. */

#define VAR_TRACED_READ		0x10	/* TCL_TRACE_READS */
#define VAR_TRACED_WRITE	0x20	/* TCL_TRACE_WRITES */
#define VAR_TRACED_UNSET	0x40	/* TCL_TRACE_UNSETS */
#define VAR_TRACED_ARRAY	0x800	/* TCL_TRACE_ARRAY */
#define VAR_TRACE_ACTIVE	0x2000
#define VAR_SEARCH_ACTIVE	0x4000
#define VAR_ALL_TRACES \
	(VAR_TRACED_READ|VAR_TRACED_WRITE|VAR_TRACED_ARRAY|VAR_TRACED_UNSET)

/* Special handling on initialisation (only CompiledLocal). */
#define VAR_ARGUMENT		0x100	/* KEEP OLD VALUE! See tclProc.c */
#define VAR_TEMPORARY		0x200	/* KEEP OLD VALUE! See tclProc.c */
#define VAR_IS_ARGS		0x400
#define VAR_RESOLVED		0x8000

/*
 * Macros to ensure that various flag bits are set properly for variables.
 * The ANSI C "prototypes" for these macros are:
 *
 * MODULE_SCOPE void	TclSetVarScalar(Var *varPtr);
 * MODULE_SCOPE void	TclSetVarArray(Var *varPtr);
 * MODULE_SCOPE void	TclSetVarLink(Var *varPtr);
 * MODULE_SCOPE void	TclSetVarArrayElement(Var *varPtr);
 * MODULE_SCOPE void	TclSetVarUndefined(Var *varPtr);
 * MODULE_SCOPE void	TclClearVarUndefined(Var *varPtr);
 */

#define TclSetVarScalar(varPtr) \
    (varPtr)->flags &= ~(VAR_ARRAY|VAR_LINK)

#define TclSetVarArray(varPtr) \
    (varPtr)->flags = ((varPtr)->flags & ~VAR_LINK) | VAR_ARRAY

#define TclSetVarLink(varPtr) \
    (varPtr)->flags = ((varPtr)->flags & ~VAR_ARRAY) | VAR_LINK

#define TclSetVarArrayElement(varPtr) \
    (varPtr)->flags = ((varPtr)->flags & ~VAR_ARRAY) | VAR_ARRAY_ELEMENT

#define TclSetVarUndefined(varPtr) \
    (varPtr)->flags &= ~(VAR_ARRAY|VAR_LINK);\
    (varPtr)->value.objPtr = NULL

#define TclClearVarUndefined(varPtr)

#define TclSetVarTraceActive(varPtr) \
    (varPtr)->flags |= VAR_TRACE_ACTIVE

#define TclClearVarTraceActive(varPtr) \
    (varPtr)->flags &= ~VAR_TRACE_ACTIVE

#define TclSetVarNamespaceVar(varPtr) \
    if (!TclIsVarNamespaceVar(varPtr)) {\
	(varPtr)->flags |= VAR_NAMESPACE_VAR;\
	if (TclIsVarInHash(varPtr)) {\
	    ((VarInHash *)(varPtr))->refCount++;\
	}\
    }

#define TclClearVarNamespaceVar(varPtr) \
    if (TclIsVarNamespaceVar(varPtr)) {\
	(varPtr)->flags &= ~VAR_NAMESPACE_VAR;\
	if (TclIsVarInHash(varPtr)) {\
	    ((VarInHash *)(varPtr))->refCount--;\
	}\
    }

/*
 * Macros to read various flag bits of variables.
 * The ANSI C "prototypes" for these macros are:
 *
 * MODULE_SCOPE int	TclIsVarScalar(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarLink(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarArray(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarUndefined(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarArrayElement(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarTemporary(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarArgument(Var *varPtr);
 * MODULE_SCOPE int	TclIsVarResolved(Var *varPtr);
 */

#define TclIsVarScalar(varPtr) \
    !((varPtr)->flags & (VAR_ARRAY|VAR_LINK))

#define TclIsVarLink(varPtr) \
    ((varPtr)->flags & VAR_LINK)

#define TclIsVarArray(varPtr) \
    ((varPtr)->flags & VAR_ARRAY)

#define TclIsVarUndefined(varPtr) \
    ((varPtr)->value.objPtr == NULL)

#define TclIsVarArrayElement(varPtr) \
    ((varPtr)->flags & VAR_ARRAY_ELEMENT)

#define TclIsVarNamespaceVar(varPtr) \
    ((varPtr)->flags & VAR_NAMESPACE_VAR)

#define TclIsVarTemporary(varPtr) \
    ((varPtr)->flags & VAR_TEMPORARY)

#define TclIsVarArgument(varPtr) \
    ((varPtr)->flags & VAR_ARGUMENT)

#define TclIsVarResolved(varPtr) \
    ((varPtr)->flags & VAR_RESOLVED)

#define TclIsVarTraceActive(varPtr) \
    ((varPtr)->flags & VAR_TRACE_ACTIVE)

#define TclIsVarTraced(varPtr) \
    ((varPtr)->flags & VAR_ALL_TRACES)

#define TclIsVarInHash(varPtr) \
    ((varPtr)->flags & VAR_IN_HASHTABLE)

#define TclIsVarDeadHash(varPtr) \
    ((varPtr)->flags & VAR_DEAD_HASH)

#define TclGetVarNsPtr(varPtr) \
    (TclIsVarInHash(varPtr) \
	? ((TclVarHashTable *) ((((VarInHash *) (varPtr))->entry.tablePtr)))->nsPtr \
	: NULL)

#define VarHashRefCount(varPtr) \
    ((VarInHash *) (varPtr))->refCount

/*
 * Macros for direct variable access by TEBC.
 */

#define TclIsVarDirectReadable(varPtr) \
    (   !((varPtr)->flags & (VAR_ARRAY|VAR_LINK|VAR_TRACED_READ)) \
    &&  (varPtr)->value.objPtr)

#define TclIsVarDirectWritable(varPtr) \
    !((varPtr)->flags & (VAR_ARRAY|VAR_LINK|VAR_TRACED_WRITE|VAR_DEAD_HASH))

#define TclIsVarDirectUnsettable(varPtr) \
    !((varPtr)->flags & (VAR_ARRAY|VAR_LINK|VAR_TRACED_READ|VAR_TRACED_WRITE|VAR_TRACED_UNSET|VAR_DEAD_HASH))

#define TclIsVarDirectModifyable(varPtr) \
    (   !((varPtr)->flags & (VAR_ARRAY|VAR_LINK|VAR_TRACED_READ|VAR_TRACED_WRITE)) \
    &&  (varPtr)->value.objPtr)

#define TclIsVarDirectReadable2(varPtr, arrayPtr) \
    (TclIsVarDirectReadable(varPtr) &&\
	(!(arrayPtr) || !((arrayPtr)->flags & VAR_TRACED_READ)))

#define TclIsVarDirectWritable2(varPtr, arrayPtr) \
    (TclIsVarDirectWritable(varPtr) &&\
	(!(arrayPtr) || !((arrayPtr)->flags & VAR_TRACED_WRITE)))

#define TclIsVarDirectModifyable2(varPtr, arrayPtr) \
    (TclIsVarDirectModifyable(varPtr) &&\
	(!(arrayPtr) || !((arrayPtr)->flags & (VAR_TRACED_READ|VAR_TRACED_WRITE))))

/*
 *----------------------------------------------------------------
 * Data structures related to procedures. These are used primarily in
 * tclProc.c, tclCompile.c, and tclExecute.c.
 *----------------------------------------------------------------
 */

#if defined(__STDC_VERSION__) && (__STDC_VERSION__ >= 199901L)
#   define TCLFLEXARRAY
#elif defined(__GNUC__) && (__GNUC__ > 2)
#   define TCLFLEXARRAY 0
#else
#   define TCLFLEXARRAY 1
#endif

/*
 * Forward declaration to prevent an error when the forward reference to
 * Command is encountered in the Proc and ImportRef types declared below.
 */

struct Command;

/*
 * The variable-length structure below describes a local variable of a
 * procedure that was recognized by the compiler. These variables have a name,
 * an element in the array of compiler-assigned local variables in the
 * procedure's call frame, and various other items of information. If the
 * local variable is a formal argument, it may also have a default value. The
 * compiler can't recognize local variables whose names are expressions (these
 * names are only known at runtime when the expressions are evaluated) or
 * local variables that are created as a result of an "upvar" or "uplevel"
 * command. These other local variables are kept separately in a hash table in
 * the call frame.
 */

typedef struct CompiledLocal {
    struct CompiledLocal *nextPtr;
				/* Next compiler-recognized local variable for
				 * this procedure, or NULL if this is the last
				 * local. */
    int nameLength;		/* The number of bytes in local variable's name.
				 * Among others used to speed up var lookups. */
    int frameIndex;		/* Index in the array of compiler-assigned
				 * variables in the procedure call frame. */
    int flags;			/* Flag bits for the local variable. Same as
				 * the flags for the Var structure above,
				 * although only VAR_ARGUMENT, VAR_TEMPORARY,
				 * and VAR_RESOLVED make sense. */
    Tcl_Obj *defValuePtr;	/* Pointer to the default value of an
				 * argument, if any. NULL if not an argument
				 * or, if an argument, no default value. */
    Tcl_ResolvedVarInfo *resolveInfo;
				/* Customized variable resolution info
				 * supplied by the Tcl_ResolveCompiledVarProc
				 * associated with a namespace. Each variable
				 * is marked by a unique tag during
				 * compilation, and that same tag is used to
				 * find the variable at runtime. */
    char name[TCLFLEXARRAY];		/* Name of the local variable starts here. If
				 * the name is NULL, this will just be '\0'.
				 * The actual size of this field will be large
				 * enough to hold the name. MUST BE THE LAST
				 * FIELD IN THE STRUCTURE! */
} CompiledLocal;

/*
 * The structure below defines a command procedure, which consists of a
 * collection of Tcl commands plus information about arguments and other local
 * variables recognized at compile time.
 */

typedef struct Proc {
    struct Interp *iPtr;	/* Interpreter for which this command is
				 * defined. */
    int refCount;		/* Reference count: 1 if still present in
				 * command table plus 1 for each call to the
				 * procedure that is currently active. This
				 * structure can be freed when refCount
				 * becomes zero. */
    struct Command *cmdPtr;	/* Points to the Command structure for this
				 * procedure. This is used to get the
				 * namespace in which to execute the
				 * procedure. */
    Tcl_Obj *bodyPtr;		/* Points to the ByteCode object for
				 * procedure's body command. */
    int numArgs;		/* Number of formal parameters. */
    int numCompiledLocals;	/* Count of local variables recognized by the
				 * compiler including arguments and
				 * temporaries. */
    CompiledLocal *firstLocalPtr;
				/* Pointer to first of the procedure's
				 * compiler-allocated local variables, or NULL
				 * if none. The first numArgs entries in this
				 * list describe the procedure's formal
				 * arguments. */
    CompiledLocal *lastLocalPtr;/* Pointer to the last allocated local
				 * variable or NULL if none. This has frame
				 * index (numCompiledLocals-1). */
} Proc;

/*
 * The type of functions called to process errors found during the execution
 * of a procedure (or lambda term or ...).
 */

typedef void (ProcErrorProc)(Tcl_Interp *interp, Tcl_Obj *procNameObj);

/*
 * The structure below defines a command trace. This is used to allow Tcl
 * clients to find out whenever a command is about to be executed.
 */

typedef struct Trace {
    int level;		/* Only trace commands at nesting level less
				 * than or equal to this. */
    Tcl_CmdObjTraceProc *proc;	/* Procedure to call to trace command. */
    ClientData clientData;	/* Arbitrary value to pass to proc. */
    struct Trace *nextPtr;	/* Next in list of traces for this interp. */
    int flags;			/* Flags governing the trace - see
				 * Tcl_CreateObjTrace for details. */
    Tcl_CmdObjTraceDeleteProc *delProc;
				/* Procedure to call when trace is deleted. */
} Trace;

/*
 * When an interpreter trace is active (i.e. its associated procedure is
 * executing), one of the following structures is linked into a list
 * associated with the interpreter. The information in the structure is needed
 * in order for Tcl to behave reasonably if traces are deleted while traces
 * are active.
 */

typedef struct ActiveInterpTrace {
    struct ActiveInterpTrace *nextPtr;
				/* Next in list of all active command traces
				 * for the interpreter, or NULL if no more. */
    Trace *nextTracePtr;	/* Next trace to check after current trace
				 * procedure returns; if this trace gets
				 * deleted, must update pointer to avoid using
				 * free'd memory. */
    int reverseScan;		/* Boolean set true when traces are scanning
				 * in reverse order. */
} ActiveInterpTrace;

/*
 * Flag values designating types of execution traces. See tclTrace.c for
 * related flag values.
 *
 * TCL_TRACE_ENTER_EXEC		- triggers enter/enterstep traces.
 * 				- passed to Tcl_CreateObjTrace to set up
 *				  "enterstep" traces.
 * TCL_TRACE_LEAVE_EXEC		- triggers leave/leavestep traces.
 * 				- passed to Tcl_CreateObjTrace to set up
 *				  "leavestep" traces.
 */

#define TCL_TRACE_ENTER_EXEC	1
#define TCL_TRACE_LEAVE_EXEC	2

/*
 * The structure below defines an entry in the assocData hash table which is
 * associated with an interpreter. The entry contains a pointer to a function
 * to call when the interpreter is deleted, and a pointer to a user-defined
 * piece of data.
 */

typedef struct AssocData {
    Tcl_InterpDeleteProc *proc;	/* Proc to call when deleting. */
    ClientData clientData;	/* Value to pass to proc. */
} AssocData;

/*
 * The structure below defines a call frame. A call frame defines a naming
 * context for a procedure call: its local naming scope (for local variables)
 * and its global naming scope (a namespace, perhaps the global :: namespace).
 * A call frame can also define the naming context for a namespace eval or
 * namespace inscope command: the namespace in which the command's code should
 * execute. The Tcl_CallFrame structures exist only while procedures or
 * namespace eval/inscope's are being executed, and provide a kind of Tcl call
 * stack.
 *
 * WARNING!! The structure definition must be kept consistent with the
 * Tcl_CallFrame structure in tcl.h. If you change one, change the other.
 */

/*
 * Will be grown to contain: pointers to the varnames (allocated at the end),
 * plus the init values for each variable (suitable to be memcopied on init)
 */

typedef struct LocalCache {
    int refCount;
    int numVars;
    Tcl_Obj *varName0;
} LocalCache;

#define localName(framePtr, i) \
    ((&((framePtr)->localCachePtr->varName0))[(i)])

MODULE_SCOPE void	TclFreeLocalCache(Tcl_Interp *interp,
			    LocalCache *localCachePtr);

typedef struct CallFrame {
    Namespace *nsPtr;		/* Points to the namespace used to resolve
				 * commands and global variables. */
    int isProcCallFrame;	/* If 0, the frame was pushed to execute a
				 * namespace command and var references are
				 * treated as references to namespace vars;
				 * varTablePtr and compiledLocals are ignored.
				 * If FRAME_IS_PROC is set, the frame was
				 * pushed to execute a Tcl procedure and may
				 * have local vars. */
    int objc;			/* This and objv below describe the arguments
				 * for this procedure call. */
    Tcl_Obj *const *objv;	/* Array of argument objects. */
    struct CallFrame *callerPtr;
				/* Value of interp->framePtr when this
				 * procedure was invoked (i.e. next higher in
				 * stack of all active procedures). */
    struct CallFrame *callerVarPtr;
				/* Value of interp->varFramePtr when this
				 * procedure was invoked (i.e. determines
				 * variable scoping within caller). Same as
				 * callerPtr unless an "uplevel" command or
				 * something equivalent was active in the
				 * caller). */
    int level;			/* Level of this procedure, for "uplevel"
				 * purposes (i.e. corresponds to nesting of
				 * callerVarPtr's, not callerPtr's). 1 for
				 * outermost procedure, 0 for top-level. */
    Proc *procPtr;		/* Points to the structure defining the called
				 * procedure. Used to get information such as
				 * the number of compiled local variables
				 * (local variables assigned entries ["slots"]
				 * in the compiledLocals array below). */
    TclVarHashTable *varTablePtr;
				/* Hash table containing local variables not
				 * recognized by the compiler, or created at
				 * execution time through, e.g., upvar.
				 * Initially NULL and created if needed. */
    int numCompiledLocals;	/* Count of local variables recognized
				 * by the compiler including arguments. */
    Var *compiledLocals;	/* Points to the array of local variables
				 * recognized by the compiler. The compiler
				 * emits code that refers to these variables
				 * using an index into this array. */
    ClientData clientData;	/* Pointer to some context that is used by
				 * object systems. The meaning of the contents
				 * of this field is defined by the code that
				 * sets it, and it should only ever be set by
				 * the code that is pushing the frame. In that
				 * case, the code that sets it should also
				 * have some means of discovering what the
				 * meaning of the value is, which we do not
				 * specify. */
    LocalCache *localCachePtr;
    Tcl_Obj    *tailcallPtr;
				/* NULL if no tailcall is scheduled */
} CallFrame;

#define FRAME_IS_PROC	0x1
#define FRAME_IS_LAMBDA 0x2
#define FRAME_IS_METHOD	0x4	/* The frame is a method body, and the frame's
				 * clientData field contains a CallContext
				 * reference. Part of TIP#257. */
#define FRAME_IS_OO_DEFINE 0x8	/* The frame is part of the inside workings of
				 * the [oo::define] command; the clientData
				 * field contains an Object reference that has
				 * been confirmed to refer to a class. Part of
				 * TIP#257. */

/*
 * TIP #280
 * The structure below defines a command frame. A command frame provides
 * location information for all commands executing a tcl script (source, eval,
 * uplevel, procedure bodies, ...). The runtime structure essentially contains
 * the stack trace as it would be if the currently executing command were to
 * throw an error.
 *
 * For commands where it makes sense it refers to the associated CallFrame as
 * well.
 *
 * The structures are chained in a single list, with the top of the stack
 * anchored in the Interp structure.
 *
 * Instances can be allocated on the C stack, or the heap, the former making
 * cleanup a bit simpler.
 */

typedef struct CmdFrame {
    /*
     * General data. Always available.
     */

    int type;			/* Values see below. */
    int level;			/* Number of frames in stack, prevent O(n)
				 * scan of list. */
    int *line;		/* Lines the words of the command start on. */
    int nline;
    CallFrame *framePtr;	/* Procedure activation record, may be
				 * NULL. */
    struct CmdFrame *nextPtr;	/* Link to calling frame. */
    /*
     * Data needed for Eval vs TEBC
     *
     * EXECUTION CONTEXTS and usage of CmdFrame
     *
     * Field	  TEBC		  EvalEx
     * =======	  ====		  ======
     * level	  yes		  yes
     * type	  BC/PREBC	  SRC/EVAL
     * line0	  yes		  yes
     * framePtr	  yes		  yes
     * =======	  ====		  ======
     *
     * =======	  ====		  ========= union data
     * line1	  -		  yes
     * line3	  -		  yes
     * path	  -		  yes
     * -------	  ----		  ------
     * codePtr	  yes		  -
     * pc	  yes		  -
     * =======	  ====		  ======
     *
     * =======	  ====		  ========= union cmd
     * str.cmd	  yes		  yes
     * str.len	  yes		  yes
     * -------	  ----		  ------
     */

    union {
	struct {
	    Tcl_Obj *path;	/* Path of the sourced file the command is
				 * in. */
	} eval;
	struct {
	    const void *codePtr;/* Byte code currently executed... */
	    const char *pc;	/* ... and instruction pointer. */
	} tebc;
    } data;
    Tcl_Obj *cmdObj;
    const char *cmd;		/* The executed command, if possible... */
    int len;			/* ... and its length. */
    const struct CFWordBC *litarg;
				/* Link to set of literal arguments which have
				 * ben pushed on the lineLABCPtr stack by
				 * TclArgumentBCEnter(). These will be removed
				 * by TclArgumentBCRelease. */
} CmdFrame;

typedef struct CFWord {
    CmdFrame *framePtr;		/* CmdFrame to access. */
    int word;			/* Index of the word in the command. */
    int refCount;		/* Number of times the word is on the
				 * stack. */
} CFWord;

typedef struct CFWordBC {
    CmdFrame *framePtr;		/* CmdFrame to access. */
    int pc;			/* Instruction pointer of a command in
				 * ExtCmdLoc.loc[.] */
    int word;			/* Index of word in
				 * ExtCmdLoc.loc[cmd]->line[.] */
    struct CFWordBC *prevPtr;	/* Previous entry in stack for same Tcl_Obj. */
    struct CFWordBC *nextPtr;	/* Next entry for same command call. See
				 * CmdFrame litarg field for the list start. */
    Tcl_Obj *obj;		/* Back reference to hash table key */
} CFWordBC;

/*
 * Structure to record the locations of invisible continuation lines in
 * literal scripts, as character offset from the beginning of the script. Both
 * compiler and direct evaluator use this information to adjust their line
 * counters when tracking through the script, because when it is invoked the
 * continuation line marker as a whole has been removed already, meaning that
 * the \n which was part of it is gone as well, breaking regular line
 * tracking.
 *
 * These structures are allocated and filled by both the function
 * TclSubstTokens() in the file "tclParse.c" and its caller TclEvalEx() in the
 * file "tclBasic.c", and stored in the thread-global hash table "lineCLPtr" in
 * file "tclObj.c". They are used by the functions TclSetByteCodeFromAny() and
 * TclCompileScript(), both found in the file "tclCompile.c". Their memory is
 * released by the function TclFreeObj(), in the file "tclObj.c", and also by
 * the function TclThreadFinalizeObjects(), in the same file.
 */

#define CLL_END		(-1)

typedef struct ContLineLoc {
    int num;			/* Number of entries in loc, not counting the
				 * final -1 marker entry. */
    int loc[TCLFLEXARRAY];/* Table of locations, as character offsets.
				 * The table is allocated as part of the
				 * structure, extending behind the nominal end
				 * of the structure. An entry containing the
				 * value -1 is put after the last location, as
				 * end-marker/sentinel. */
} ContLineLoc;

/*
 * The following macros define the allowed values for the type field of the
 * CmdFrame structure above. Some of the values occur only in the extended
 * location data referenced via the 'baseLocPtr'.
 *
 * TCL_LOCATION_EVAL	  : Frame is for a script evaluated by EvalEx.
 * TCL_LOCATION_BC	  : Frame is for bytecode.
 * TCL_LOCATION_PREBC	  : Frame is for precompiled bytecode.
 * TCL_LOCATION_SOURCE	  : Frame is for a script evaluated by EvalEx, from a
 *			    sourced file.
 * TCL_LOCATION_PROC	  : Frame is for bytecode of a procedure.
 *
 * A TCL_LOCATION_BC type in a frame can be overridden by _SOURCE and _PROC
 * types, per the context of the byte code in execution.
 */

#define TCL_LOCATION_EVAL	(0) /* Location in a dynamic eval script. */
#define TCL_LOCATION_BC		(2) /* Location in byte code. */
#define TCL_LOCATION_PREBC	(3) /* Location in precompiled byte code, no
				     * location. */
#define TCL_LOCATION_SOURCE	(4) /* Location in a file. */
#define TCL_LOCATION_PROC	(5) /* Location in a dynamic proc. */
#define TCL_LOCATION_LAST	(6) /* Number of values in the enum. */

/*
 * Structure passed to describe procedure-like "procedures" that are not
 * procedures (e.g. a lambda) so that their details can be reported correctly
 * by [info frame]. Contains a sub-structure for each extra field.
 */

typedef Tcl_Obj * (GetFrameInfoValueProc)(ClientData clientData);
typedef struct {
    const char *name;		/* Name of this field. */
    GetFrameInfoValueProc *proc;	/* Function to generate a Tcl_Obj* from the
				 * clientData, or just use the clientData
				 * directly (after casting) if NULL. */
    ClientData clientData;	/* Context for above function, or Tcl_Obj* if
				 * proc field is NULL. */
} ExtraFrameInfoField;
typedef struct {
    int length;			/* Length of array. */
    ExtraFrameInfoField fields[2];
				/* Really as long as necessary, but this is
				 * long enough for nearly anything. */
} ExtraFrameInfo;

/*
 *----------------------------------------------------------------
 * Data structures and procedures related to TclHandles, which are a very
 * lightweight method of preserving enough information to determine if an
 * arbitrary malloc'd block has been deleted.
 *----------------------------------------------------------------
 */

typedef void **TclHandle;

/*
 *----------------------------------------------------------------
 * Experimental flag value passed to Tcl_GetRegExpFromObj. Intended for use
 * only by Expect. It will probably go away in a later release.
 *----------------------------------------------------------------
 */

#define TCL_REG_BOSONLY 002000	/* Prepend \A to pattern so it only matches at
				 * the beginning of the string. */

/*
 * These are a thin layer over TclpThreadKeyDataGet and TclpThreadKeyDataSet
 * when threads are used, or an emulation if there are no threads. These are
 * really internal and Tcl clients should use Tcl_GetThreadData.
 */

MODULE_SCOPE void *	TclThreadDataKeyGet(Tcl_ThreadDataKey *keyPtr);
MODULE_SCOPE void	TclThreadDataKeySet(Tcl_ThreadDataKey *keyPtr,
			    void *data);

/*
 * This is a convenience macro used to initialize a thread local storage ptr.
 */

#define TCL_TSD_INIT(keyPtr) \
  (ThreadSpecificData *)Tcl_GetThreadData((keyPtr), sizeof(ThreadSpecificData))

/*
 *----------------------------------------------------------------
 * Data structures related to bytecode compilation and execution. These are
 * used primarily in tclCompile.c, tclExecute.c, and tclBasic.c.
 *----------------------------------------------------------------
 */

/*
 * Forward declaration to prevent errors when the forward references to
 * Tcl_Parse and CompileEnv are encountered in the procedure type CompileProc
 * declared below.
 */

struct CompileEnv;

/*
 * The type of procedures called by the Tcl bytecode compiler to compile
 * commands. Pointers to these procedures are kept in the Command structure
 * describing each command. The integer value returned by a CompileProc must
 * be one of the following:
 *
 * TCL_OK		Compilation completed normally.
 * TCL_ERROR 		Compilation could not be completed. This can be just a
 * 			judgment by the CompileProc that the command is too
 * 			complex to compile effectively, or it can indicate
 * 			that in the current state of the interp, the command
 * 			would raise an error. The bytecode compiler will not
 * 			do any error reporting at compiler time. Error
 * 			reporting is deferred until the actual runtime,
 * 			because by then changes in the interp state may allow
 * 			the command to be successfully evaluated.
 * TCL_OUT_LINE_COMPILE	A source-compatible alias for TCL_ERROR, kept for the
 * 			sake of old code only.
 */

#define TCL_OUT_LINE_COMPILE	TCL_ERROR

typedef int (CompileProc)(Tcl_Interp *interp, Tcl_Parse *parsePtr,
	struct Command *cmdPtr, struct CompileEnv *compEnvPtr);

/*
 * The type of procedure called from the compilation hook point in
 * SetByteCodeFromAny.
 */

typedef int (CompileHookProc)(Tcl_Interp *interp,
	struct CompileEnv *compEnvPtr, ClientData clientData);

/*
 * The data structure for a (linked list of) execution stacks.
 */

typedef struct ExecStack {
    struct ExecStack *prevPtr;
    struct ExecStack *nextPtr;
    Tcl_Obj **markerPtr;
    Tcl_Obj **endPtr;
    Tcl_Obj **tosPtr;
    Tcl_Obj *stackWords[TCLFLEXARRAY];
} ExecStack;

/*
 * The data structure defining the execution environment for ByteCode's.
 * There is one ExecEnv structure per Tcl interpreter. It holds the evaluation
 * stack that holds command operands and results. The stack grows towards
 * increasing addresses. The member stackPtr points to the stackItems of the
 * currently active execution stack.
 */

typedef struct CorContext {
    struct CallFrame *framePtr;
    struct CallFrame *varFramePtr;
    struct CmdFrame *cmdFramePtr;  /* See Interp.cmdFramePtr */
    Tcl_HashTable *lineLABCPtr;    /* See Interp.lineLABCPtr */
} CorContext;

typedef struct CoroutineData {
    struct Command *cmdPtr;	/* The command handle for the coroutine. */
    struct ExecEnv *eePtr;	/* The special execution environment (stacks,
				 * etc.) for the coroutine. */
    struct ExecEnv *callerEEPtr;/* The execution environment for the caller of
				 * the coroutine, which might be the
				 * interpreter global environment or another
				 * coroutine. */
    CorContext caller;
    CorContext running;
    Tcl_HashTable *lineLABCPtr;    /* See Interp.lineLABCPtr */
    void *stackLevel;
    int auxNumLevels;		/* While the coroutine is running the
				 * numLevels of the create/resume command is
				 * stored here; for suspended coroutines it
				 * holds the nesting numLevels at yield. */
    int nargs;                  /* Number of args required for resuming this
				 * coroutine; -2 means "0 or 1" (default), -1
				 * means "any" */
} CoroutineData;

typedef struct ExecEnv {
    ExecStack *execStackPtr;	/* Points to the first item in the evaluation
				 * stack on the heap. */
    Tcl_Obj *constants[2];	/* Pointers to constant "0" and "1" objs. */
    struct Tcl_Interp *interp;
    struct NRE_callback *callbackPtr;
				/* Top callback in NRE's stack. */
    struct CoroutineData *corPtr;
    int rewind;
} ExecEnv;

#define COR_IS_SUSPENDED(corPtr) \
    ((corPtr)->stackLevel == NULL)

/*
 * The definitions for the LiteralTable and LiteralEntry structures. Each
 * interpreter contains a LiteralTable. It is used to reduce the storage
 * needed for all the Tcl objects that hold the literals of scripts compiled
 * by the interpreter. A literal's object is shared by all the ByteCodes that
 * refer to the literal. Each distinct literal has one LiteralEntry entry in
 * the LiteralTable. A literal table is a specialized hash table that is
 * indexed by the literal's string representation, which may contain null
 * characters.
 *
 * Note that we reduce the space needed for literals by sharing literal
 * objects both within a ByteCode (each ByteCode contains a local
 * LiteralTable) and across all an interpreter's ByteCodes (with the
 * interpreter's global LiteralTable).
 */

typedef struct LiteralEntry {
    struct LiteralEntry *nextPtr;
				/* Points to next entry in this hash bucket or
				 * NULL if end of chain. */
    Tcl_Obj *objPtr;		/* Points to Tcl object that holds the
				 * literal's bytes and length. */
    int refCount;		/* If in an interpreter's global literal
				 * table, the number of ByteCode structures
				 * that share the literal object; the literal
				 * entry can be freed when refCount drops to
				 * 0. If in a local literal table, -1. */
    Namespace *nsPtr;		/* Namespace in which this literal is used. We
				 * try to avoid sharing literal non-FQ command
				 * names among different namespaces to reduce
				 * shimmering. */
} LiteralEntry;

typedef struct LiteralTable {
    LiteralEntry **buckets;	/* Pointer to bucket array. Each element
				 * points to first entry in bucket's hash
				 * chain, or NULL. */
    LiteralEntry *staticBuckets[TCL_SMALL_HASH_TABLE];
				/* Bucket array used for small tables to avoid
				 * mallocs and frees. */
    int numBuckets;		/* Total number of buckets allocated at
				 * **buckets. */
    int numEntries;		/* Total number of entries present in
				 * table. */
    int rebuildSize;		/* Enlarge table when numEntries gets to be
				 * this large. */
    int mask;			/* Mask value used in hashing function. */
} LiteralTable;

/*
 * The following structure defines for each Tcl interpreter various
 * statistics-related information about the bytecode compiler and
 * interpreter's operation in that interpreter.
 */

#ifdef TCL_COMPILE_STATS
typedef struct ByteCodeStats {
    long numExecutions;		/* Number of ByteCodes executed. */
    long numCompilations;	/* Number of ByteCodes created. */
    long numByteCodesFreed;	/* Number of ByteCodes destroyed. */
    long instructionCount[256];	/* Number of times each instruction was
				 * executed. */

    double totalSrcBytes;	/* Total source bytes ever compiled. */
    double totalByteCodeBytes;	/* Total bytes for all ByteCodes. */
    double currentSrcBytes;	/* Src bytes for all current ByteCodes. */
    double currentByteCodeBytes;/* Code bytes in all current ByteCodes. */

    long srcCount[32];		/* Source size distribution: # of srcs of
				 * size [2**(n-1)..2**n), n in [0..32). */
    long byteCodeCount[32];	/* ByteCode size distribution. */
    long lifetimeCount[32];	/* ByteCode lifetime distribution (ms). */

    double currentInstBytes;	/* Instruction bytes-current ByteCodes. */
    double currentLitBytes;	/* Current literal bytes. */
    double currentExceptBytes;	/* Current exception table bytes. */
    double currentAuxBytes;	/* Current auxiliary information bytes. */
    double currentCmdMapBytes;	/* Current src<->code map bytes. */

    long numLiteralsCreated;	/* Total literal objects ever compiled. */
    double totalLitStringBytes;	/* Total string bytes in all literals. */
    double currentLitStringBytes;
				/* String bytes in current literals. */
    long literalCount[32];	/* Distribution of literal string sizes. */
} ByteCodeStats;
#endif /* TCL_COMPILE_STATS */

/*
 * Structure used in implementation of those core ensembles which are
 * partially compiled. Used as an array of these, with a terminating field
 * whose 'name' is NULL.
 */

typedef struct {
    const char *name;		/* The name of the subcommand. */
    Tcl_ObjCmdProc *proc;	/* The implementation of the subcommand. */
    CompileProc *compileProc;	/* The compiler for the subcommand. */
    Tcl_ObjCmdProc *nreProc;	/* NRE implementation of this command. */
    ClientData clientData;	/* Any clientData to give the command. */
    int unsafe;			/* Whether this command is to be hidden by
				 * default in a safe interpreter. */
} EnsembleImplMap;

/*
 *----------------------------------------------------------------
 * Data structures related to commands.
 *----------------------------------------------------------------
 */

/*
 * An imported command is created in an namespace when it imports a "real"
 * command from another namespace. An imported command has a Command structure
 * that points (via its ClientData value) to the "real" Command structure in
 * the source namespace's command table. The real command records all the
 * imported commands that refer to it in a list of ImportRef structures so
 * that they can be deleted when the real command is deleted.
 */

typedef struct ImportRef {
    struct Command *importedCmdPtr;
				/* Points to the imported command created in
				 * an importing namespace; this command
				 * redirects its invocations to the "real"
				 * command. */
    struct ImportRef *nextPtr;	/* Next element on the linked list of imported
				 * commands that refer to the "real" command.
				 * The real command deletes these imported
				 * commands on this list when it is
				 * deleted. */
} ImportRef;

/*
 * Data structure used as the ClientData of imported commands: commands
 * created in an namespace when it imports a "real" command from another
 * namespace.
 */

typedef struct ImportedCmdData {
    struct Command *realCmdPtr;	/* "Real" command that this imported command
				 * refers to. */
    struct Command *selfPtr;	/* Pointer to this imported command. Needed
				 * only when deleting it in order to remove it
				 * from the real command's linked list of
				 * imported commands that refer to it. */
} ImportedCmdData;

/*
 * A Command structure exists for each command in a namespace. The Tcl_Command
 * opaque type actually refers to these structures.
 */

typedef struct Command {
    Tcl_HashEntry *hPtr;	/* Pointer to the hash table entry that refers
				 * to this command. The hash table is either a
				 * namespace's command table or an
				 * interpreter's hidden command table. This
				 * pointer is used to get a command's name
				 * from its Tcl_Command handle. NULL means
				 * that the hash table entry has been removed
				 * already (this can happen if deleteProc
				 * causes the command to be deleted or
				 * recreated). */
    Namespace *nsPtr;		/* Points to the namespace containing this
				 * command. */
    int refCount;		/* 1 if in command hashtable plus 1 for each
				 * reference from a CmdName Tcl object
				 * representing a command's name in a ByteCode
				 * instruction sequence. This structure can be
				 * freed when refCount becomes zero. */
    int cmdEpoch;		/* Incremented to invalidate any references
				 * that point to this command when it is
				 * renamed, deleted, hidden, or exposed. */
    CompileProc *compileProc;	/* Procedure called to compile command. NULL
				 * if no compile proc exists for command. */
    Tcl_ObjCmdProc *objProc;	/* Object-based command procedure. */
    ClientData objClientData;	/* Arbitrary value passed to object proc. */
    Tcl_CmdProc *proc;		/* String-based command procedure. */
    ClientData clientData;	/* Arbitrary value passed to string proc. */
    Tcl_CmdDeleteProc *deleteProc;
				/* Procedure invoked when deleting command to,
				 * e.g., free all client data. */
    ClientData deleteData;	/* Arbitrary value passed to deleteProc. */
    int flags;			/* Miscellaneous bits of information about
				 * command. See below for definitions. */
    ImportRef *importRefPtr;	/* List of each imported Command created in
				 * another namespace when this command is
				 * imported. These imported commands redirect
				 * invocations back to this command. The list
				 * is used to remove all those imported
				 * commands when deleting this "real"
				 * command. */
    CommandTrace *tracePtr;	/* First in list of all traces set for this
				 * command. */
    Tcl_ObjCmdProc *nreProc;	/* NRE implementation of this command. */
} Command;

/*
 * Flag bits for commands.
 *
 * CMD_IS_DELETED -		If 1 the command is in the process of
 *				being deleted (its deleteProc is currently
 *				executing). Other attempts to delete the
 *				command should be ignored.
 * CMD_TRACE_ACTIVE -		If 1 the trace processing is currently
 *				underway for a rename/delete change. See the
 *				two flags below for which is currently being
 *				processed.
 * CMD_HAS_EXEC_TRACES -	If 1 means that this command has at least one
 *				execution trace (as opposed to simple
 *				delete/rename traces) in its tracePtr list.
 * CMD_COMPILES_EXPANDED -	If 1 this command has a compiler that
 *				can handle expansion (provided it is not the
 *				first word).
 * TCL_TRACE_RENAME -		A rename trace is in progress. Further
 *				recursive renames will not be traced.
 * TCL_TRACE_DELETE -		A delete trace is in progress. Further
 *				recursive deletes will not be traced.
 * (these last two flags are defined in tcl.h)
 */

#define CMD_IS_DELETED		    0x01
#define CMD_TRACE_ACTIVE	    0x02
#define CMD_HAS_EXEC_TRACES	    0x04
#define CMD_COMPILES_EXPANDED	    0x08
#define CMD_REDEF_IN_PROGRESS	    0x10
#define CMD_VIA_RESOLVER	    0x20
#define CMD_DEAD                    0x40


/*
 *----------------------------------------------------------------
 * Data structures related to name resolution procedures.
 *----------------------------------------------------------------
 */

/*
 * The interpreter keeps a linked list of name resolution schemes. The scheme
 * for a namespace is consulted first, followed by the list of schemes in an
 * interpreter, followed by the default name resolution in Tcl. Schemes are
 * added/removed from the interpreter's list by calling Tcl_AddInterpResolver
 * and Tcl_RemoveInterpResolver.
 */

typedef struct ResolverScheme {
    char *name;			/* Name identifying this scheme. */
    Tcl_ResolveCmdProc *cmdResProc;
				/* Procedure handling command name
				 * resolution. */
    Tcl_ResolveVarProc *varResProc;
				/* Procedure handling variable name resolution
				 * for variables that can only be handled at
				 * runtime. */
    Tcl_ResolveCompiledVarProc *compiledVarResProc;
				/* Procedure handling variable name resolution
				 * at compile time. */

    struct ResolverScheme *nextPtr;
				/* Pointer to next record in linked list. */
} ResolverScheme;

/*
 * Forward declaration of the TIP#143 limit handler structure.
 */

typedef struct LimitHandler LimitHandler;

/*
 * TIP #268.
 * Values for the selection mode, i.e the package require preferences.
 */

enum PkgPreferOptions {
    PKG_PREFER_LATEST, PKG_PREFER_STABLE
};

/*
 *----------------------------------------------------------------
 * This structure shadows the first few fields of the memory cache for the
 * allocator defined in tclThreadAlloc.c; it has to be kept in sync with the
 * definition there.
 * Some macros require knowledge of some fields in the struct in order to
 * avoid hitting the TSD unnecessarily. In order to facilitate this, a pointer
 * to the relevant fields is kept in the allocCache field in struct Interp.
 *----------------------------------------------------------------
 */

typedef struct AllocCache {
    struct Cache *nextPtr;	/* Linked list of cache entries. */
    Tcl_ThreadId owner;		/* Which thread's cache is this? */
    Tcl_Obj *firstObjPtr;	/* List of free objects for thread. */
    int numObjects;		/* Number of objects for thread. */
} AllocCache;

/*
 *----------------------------------------------------------------
 * This structure defines an interpreter, which is a collection of commands
 * plus other state information related to interpreting commands, such as
 * variable storage. Primary responsibility for this data structure is in
 * tclBasic.c, but almost every Tcl source file uses something in here.
 *----------------------------------------------------------------
 */

typedef struct Interp {
    /*
     * Note: the first three fields must match exactly the fields in a
     * Tcl_Interp struct (see tcl.h). If you change one, be sure to change the
     * other.
     *
     * The interpreter's result is held in both the string and the
     * objResultPtr fields. These fields hold, respectively, the result's
     * string or object value. The interpreter's result is always in the
     * result field if that is non-empty, otherwise it is in objResultPtr.
     * The two fields are kept consistent unless some C code sets
     * interp->result directly. Programs should not access result and
     * objResultPtr directly; instead, they should always get and set the
     * result using procedures such as Tcl_SetObjResult, Tcl_GetObjResult, and
     * Tcl_GetStringResult. See the SetResult man page for details.
     */

    char *result;		/* If the last command returned a string
				 * result, this points to it. Should not be
				 * accessed directly; see comment above. */
    Tcl_FreeProc *freeProc;	/* Zero means a string result is statically
				 * allocated. TCL_DYNAMIC means string result
				 * was allocated with ckalloc and should be
				 * freed with ckfree. Other values give
				 * address of procedure to invoke to free the
				 * string result. Tcl_Eval must free it before
				 * executing next command. */
    int errorLine;		/* When TCL_ERROR is returned, this gives the
				 * line number in the command where the error
				 * occurred (1 means first line). */
    const struct TclStubs *stubTable;
				/* Pointer to the exported Tcl stub table. On
				 * previous versions of Tcl this is a pointer
				 * to the objResultPtr or a pointer to a
				 * buckets array in a hash table. We therefore
				 * have to do some careful checking before we
				 * can use this. */

    TclHandle handle;		/* Handle used to keep track of when this
				 * interp is deleted. */

    Namespace *globalNsPtr;	/* The interpreter's global namespace. */
    Tcl_HashTable *hiddenCmdTablePtr;
				/* Hash table used by tclBasic.c to keep track
				 * of hidden commands on a per-interp
				 * basis. */
    ClientData interpInfo;	/* Information used by tclInterp.c to keep
				 * track of parent/child interps on a
				 * per-interp basis. */
    union {
	void (*optimizer)(void *envPtr);
	Tcl_HashTable unused2;	/* No longer used (was mathFuncTable). The
				 * unused space in interp was repurposed for
				 * pluggable bytecode optimizers. The core
				 * contains one optimizer, which can be
				 * selectively overridden by extensions. */
    } extra;
    /*
     * Information related to procedures and variables. See tclProc.c and
     * tclVar.c for usage.
     */

    int numLevels;		/* Keeps track of how many nested calls to
				 * Tcl_Eval are in progress for this
				 * interpreter. It's used to delay deletion of
				 * the table until all Tcl_Eval invocations
				 * are completed. */
    int maxNestingDepth;	/* If numLevels exceeds this value then Tcl
				 * assumes that infinite recursion has
				 * occurred and it generates an error. */
    CallFrame *framePtr;	/* Points to top-most in stack of all nested
				 * procedure invocations. */
    CallFrame *varFramePtr;	/* Points to the call frame whose variables
				 * are currently in use (same as framePtr
				 * unless an "uplevel" command is
				 * executing). */
    ActiveVarTrace *activeVarTracePtr;
				/* First in list of active traces for interp,
				 * or NULL if no active traces. */
    int returnCode;		/* [return -code] parameter. */
    CallFrame *rootFramePtr;	/* Global frame pointer for this
				 * interpreter. */
    Namespace *lookupNsPtr;	/* Namespace to use ONLY on the next
				 * TCL_EVAL_INVOKE call to Tcl_EvalObjv. */

    /*
     * Information used by Tcl_AppendResult to keep track of partial results.
     * See Tcl_AppendResult code for details.
     */

    char *appendResult;		/* Storage space for results generated by
				 * Tcl_AppendResult. Ckalloc-ed. NULL means
				 * not yet allocated. */
    int appendAvl;		/* Total amount of space available at
				 * partialResult. */
    int appendUsed;		/* Number of non-null bytes currently stored
				 * at partialResult. */

    /*
     * Information about packages. Used only in tclPkg.c.
     */

    Tcl_HashTable packageTable;	/* Describes all of the packages loaded in or
				 * available to this interpreter. Keys are
				 * package names, values are (Package *)
				 * pointers. */
    char *packageUnknown;	/* Command to invoke during "package require"
				 * commands for packages that aren't described
				 * in packageTable. Ckalloc'ed, may be
				 * NULL. */
    /*
     * Miscellaneous information:
     */

    int cmdCount;		/* Total number of times a command procedure
				 * has been called for this interpreter. */
    int evalFlags;		/* Flags to control next call to Tcl_Eval.
				 * Normally zero, but may be set before
				 * calling Tcl_Eval. See below for valid
				 * values. */
    int unused1;		/* No longer used (was termOffset) */
    LiteralTable literalTable;	/* Contains LiteralEntry's describing all Tcl
				 * objects holding literals of scripts
				 * compiled by the interpreter. Indexed by the
				 * string representations of literals. Used to
				 * avoid creating duplicate objects. */
    int compileEpoch;		/* Holds the current "compilation epoch" for
				 * this interpreter. This is incremented to
				 * invalidate existing ByteCodes when, e.g., a
				 * command with a compile procedure is
				 * redefined. */
    Proc *compiledProcPtr;	/* If a procedure is being compiled, a pointer
				 * to its Proc structure; otherwise, this is
				 * NULL. Set by ObjInterpProc in tclProc.c and
				 * used by tclCompile.c to process local
				 * variables appropriately. */
    ResolverScheme *resolverPtr;
				/* Linked list of name resolution schemes
				 * added to this interpreter. Schemes are
				 * added and removed by calling
				 * Tcl_AddInterpResolvers and
				 * Tcl_RemoveInterpResolver respectively. */
    Tcl_Obj *scriptFile;	/* NULL means there is no nested source
				 * command active; otherwise this points to
				 * pathPtr of the file being sourced. */
    int flags;			/* Various flag bits. See below. */
    long randSeed;		/* Seed used for rand() function. */
    Trace *tracePtr;		/* List of traces for this interpreter. */
    Tcl_HashTable *assocData;	/* Hash table for associating data with this
				 * interpreter. Cleaned up when this
				 * interpreter is deleted. */
    struct ExecEnv *execEnvPtr;	/* Execution environment for Tcl bytecode
				 * execution. Contains a pointer to the Tcl
				 * evaluation stack. */
    Tcl_Obj *emptyObjPtr;	/* Points to an object holding an empty
				 * string. Returned by Tcl_ObjSetVar2 when
				 * variable traces change a variable in a
				 * gross way. */
    char resultSpace[TCL_RESULT_SIZE+1];
				/* Static space holding small results. */
    Tcl_Obj *objResultPtr;	/* If the last command returned an object
				 * result, this points to it. Should not be
				 * accessed directly; see comment above. */
    Tcl_ThreadId threadId;	/* ID of thread that owns the interpreter. */

    ActiveCommandTrace *activeCmdTracePtr;
				/* First in list of active command traces for
				 * interp, or NULL if no active traces. */
    ActiveInterpTrace *activeInterpTracePtr;
				/* First in list of active traces for interp,
				 * or NULL if no active traces. */

    int tracesForbiddingInline;	/* Count of traces (in the list headed by
				 * tracePtr) that forbid inline bytecode
				 * compilation. */

    /*
     * Fields used to manage extensible return options (TIP 90).
     */

    Tcl_Obj *returnOpts;	/* A dictionary holding the options to the
				 * last [return] command. */

    Tcl_Obj *errorInfo;		/* errorInfo value (now as a Tcl_Obj). */
    Tcl_Obj *eiVar;		/* cached ref to ::errorInfo variable. */
    Tcl_Obj *errorCode;		/* errorCode value (now as a Tcl_Obj). */
    Tcl_Obj *ecVar;		/* cached ref to ::errorInfo variable. */
    int returnLevel;		/* [return -level] parameter. */

    /*
     * Resource limiting framework support (TIP#143).
     */

    struct {
	int active;		/* Flag values defining which limits have been
				 * set. */
	int granularityTicker;	/* Counter used to determine how often to
				 * check the limits. */
	int exceeded;		/* Which limits have been exceeded, described
				 * as flag values the same as the 'active'
				 * field. */

	int cmdCount;		/* Limit for how many commands to execute in
				 * the interpreter. */
	LimitHandler *cmdHandlers;
				/* Handlers to execute when the limit is
				 * reached. */
	int cmdGranularity;	/* Mod factor used to determine how often to
				 * evaluate the limit check. */

	Tcl_Time time;		/* Time limit for execution within the
				 * interpreter. */
	LimitHandler *timeHandlers;
				/* Handlers to execute when the limit is
				 * reached. */
	int timeGranularity;	/* Mod factor used to determine how often to
				 * evaluate the limit check. */
	Tcl_TimerToken timeEvent;
				/* Handle for a timer callback that will occur
				 * when the time-limit is exceeded. */

	Tcl_HashTable callbacks;/* Mapping from (interp,type) pair to data
				 * used to install a limit handler callback to
				 * run in _this_ interp when the limit is
				 * exceeded. */
    } limit;

    /*
     * Information for improved default error generation from ensembles
     * (TIP#112).
     */

    struct {
	Tcl_Obj *const *sourceObjs;
				/* What arguments were actually input into the
				 * *root* ensemble command? (Nested ensembles
				 * don't rewrite this.) NULL if we're not
				 * processing an ensemble. */
	int numRemovedObjs;	/* How many arguments have been stripped off
				 * because of ensemble processing. */
	int numInsertedObjs;	/* How many of the current arguments were
				 * inserted by an ensemble. */
    } ensembleRewrite;

    /*
     * TIP #219: Global info for the I/O system.
     */

    Tcl_Obj *chanMsg;		/* Error message set by channel drivers, for
				 * the propagation of arbitrary Tcl errors.
				 * This information, if present (chanMsg not
				 * NULL), takes precedence over a POSIX error
				 * code returned by a channel operation. */

    /*
     * Source code origin information (TIP #280).
     */

    CmdFrame *cmdFramePtr;	/* Points to the command frame containing the
				 * location information for the current
				 * command. */
    const CmdFrame *invokeCmdFramePtr;
				/* Points to the command frame which is the
				 * invoking context of the bytecode compiler.
				 * NULL when the byte code compiler is not
				 * active. */
    int invokeWord;		/* Index of the word in the command which
				 * is getting compiled. */
    Tcl_HashTable *linePBodyPtr;/* This table remembers for each statically
				 * defined procedure the location information
				 * for its body. It is keyed by the address of
				 * the Proc structure for a procedure. The
				 * values are "struct CmdFrame*". */
    Tcl_HashTable *lineBCPtr;	/* This table remembers for each ByteCode
				 * object the location information for its
				 * body. It is keyed by the address of the
				 * Proc structure for a procedure. The values
				 * are "struct ExtCmdLoc*". (See
				 * tclCompile.h) */
    Tcl_HashTable *lineLABCPtr;
    Tcl_HashTable *lineLAPtr;	/* This table remembers for each argument of a
				 * command on the execution stack the index of
				 * the argument in the command, and the
				 * location data of the command. It is keyed
				 * by the address of the Tcl_Obj containing
				 * the argument. The values are "struct
				 * CFWord*" (See tclBasic.c). This allows
				 * commands like uplevel, eval, etc. to find
				 * location information for their arguments,
				 * if they are a proper literal argument to an
				 * invoking command. Alt view: An index to the
				 * CmdFrame stack keyed by command argument
				 * holders. */
    ContLineLoc *scriptCLLocPtr;/* This table points to the location data for
				 * invisible continuation lines in the script,
				 * if any. This pointer is set by the function
				 * TclEvalObjEx() in file "tclBasic.c", and
				 * used by function ...() in the same file.
				 * It does for the eval/direct path of script
				 * execution what CompileEnv.clLoc does for
				 * the bytecode compiler.
				 */
    /*
     * TIP #268. The currently active selection mode, i.e. the package require
     * preferences.
     */

    int packagePrefer;		/* Current package selection mode. */

    /*
     * Hashtables for variable traces and searches.
     */

    Tcl_HashTable varTraces;	/* Hashtable holding the start of a variable's
				 * active trace list; varPtr is the key. */
    Tcl_HashTable varSearches;	/* Hashtable holding the start of a variable's
				 * active searches list; varPtr is the key. */
    /*
     * The thread-specific data ekeko: cache pointers or values that
     *  (a) do not change during the thread's lifetime
     *  (b) require access to TSD to determine at runtime
     *  (c) are accessed very often (e.g., at each command call)
     *
     * Note that these are the same for all interps in the same thread. They
     * just have to be initialised for the thread's parent interp, children
     * inherit the value.
     *
     * They are used by the macros defined below.
     */

    AllocCache *allocCache;
    void *pendingObjDataPtr;	/* Pointer to the Cache and PendingObjData
				 * structs for this interp's thread; see
				 * tclObj.c and tclThreadAlloc.c */
    int *asyncReadyPtr;		/* Pointer to the asyncReady indicator for
				 * this interp's thread; see tclAsync.c */
    /*
     * The pointer to the object system root ekeko. c.f. TIP #257.
     */
    void *objectFoundation;	/* Pointer to the Foundation structure of the
				 * object system, which contains things like
				 * references to key namespaces. See
				 * tclOOInt.h and tclOO.c for real definition
				 * and setup. */

    struct NRE_callback *deferredCallbacks;
				/* Callbacks that are set previous to a call
				 * to some Eval function but that actually
				 * belong to the command that is about to be
				 * called - i.e., they should be run *before*
				 * any tailcall is invoked. */

    /*
     * TIP #285, Script cancellation support.
     */

    Tcl_AsyncHandler asyncCancel;
				/* Async handler token for Tcl_CancelEval. */
    Tcl_Obj *asyncCancelMsg;	/* Error message set by async cancel handler
				 * for the propagation of arbitrary Tcl
				 * errors. This information, if present
				 * (asyncCancelMsg not NULL), takes precedence
				 * over the default error messages returned by
				 * a script cancellation operation. */

	/*
	 * TIP #348 IMPLEMENTATION  -  Substituted error stack
	 */
    Tcl_Obj *errorStack;	/* [info errorstack] value (as a Tcl_Obj). */
    Tcl_Obj *upLiteral;		/* "UP" literal for [info errorstack] */
    Tcl_Obj *callLiteral;	/* "CALL" literal for [info errorstack] */
    Tcl_Obj *innerLiteral;	/* "INNER" literal for [info errorstack] */
    Tcl_Obj *innerContext;	/* cached list for fast reallocation */
    int resetErrorStack;        /* controls cleaning up of ::errorStack */

#ifdef TCL_COMPILE_STATS
    /*
     * Statistical information about the bytecode compiler and interpreter's
     * operation. This should be the last field of Interp.
     */

    ByteCodeStats stats;	/* Holds compilation and execution statistics
				 * for this interpreter. */
#endif /* TCL_COMPILE_STATS */
} Interp;

/*
 * Macros that use the TSD-ekeko.
 */

#define TclAsyncReady(iPtr) \
    *((iPtr)->asyncReadyPtr)

/*
 * Macros for script cancellation support (TIP #285).
 */

#define TclCanceled(iPtr) \
    (((iPtr)->flags & CANCELED) || ((iPtr)->flags & TCL_CANCEL_UNWIND))

#define TclSetCancelFlags(iPtr, cancelFlags)   \
    (iPtr)->flags |= CANCELED;                 \
    if ((cancelFlags) & TCL_CANCEL_UNWIND) {   \
        (iPtr)->flags |= TCL_CANCEL_UNWIND;    \
    }

#define TclUnsetCancelFlags(iPtr) \
    (iPtr)->flags &= (~(CANCELED | TCL_CANCEL_UNWIND))

/*
 * Macros for splicing into and out of doubly linked lists. They assume
 * existence of struct items 'prevPtr' and 'nextPtr'.
 *
 * a = element to add or remove.
 * b = list head.
 *
 * TclSpliceIn adds to the head of the list.
 */

#define TclSpliceIn(a,b)			\
    (a)->nextPtr = (b);				\
    if ((b) != NULL) {				\
	(b)->prevPtr = (a);			\
    }						\
    (a)->prevPtr = NULL, (b) = (a);

#define TclSpliceOut(a,b)			\
    if ((a)->prevPtr != NULL) {			\
	(a)->prevPtr->nextPtr = (a)->nextPtr;	\
    } else {					\
	(b) = (a)->nextPtr;			\
    }						\
    if ((a)->nextPtr != NULL) {			\
	(a)->nextPtr->prevPtr = (a)->prevPtr;	\
    }

/*
 * EvalFlag bits for Interp structures:
 *
 * TCL_ALLOW_EXCEPTIONS	1 means it's OK for the script to terminate with a
 *			code other than TCL_OK or TCL_ERROR; 0 means codes
 *			other than these should be turned into errors.
 */

#define TCL_ALLOW_EXCEPTIONS		0x04
#define TCL_EVAL_FILE			0x02
#define TCL_EVAL_SOURCE_IN_FRAME	0x10
#define TCL_EVAL_NORESOLVE		0x20
#define TCL_EVAL_DISCARD_RESULT		0x40

/*
 * Flag bits for Interp structures:
 *
 * DELETED:		Non-zero means the interpreter has been deleted:
 *			don't process any more commands for it, and destroy
 *			the structure as soon as all nested invocations of
 *			Tcl_Eval are done.
 * ERR_ALREADY_LOGGED:	Non-zero means information has already been logged in
 *			iPtr->errorInfo for the current Tcl_Eval instance, so
 *			Tcl_Eval needn't log it (used to implement the "error
 *			message log" command).
 * DONT_COMPILE_CMDS_INLINE: Non-zero means that the bytecode compiler should
 *			not compile any commands into an inline sequence of
 *			instructions. This is set 1, for example, when command
 *			traces are requested.
 * RAND_SEED_INITIALIZED: Non-zero means that the randSeed value of the interp
 *			has not be initialized. This is set 1 when we first
 *			use the rand() or srand() functions.
 * SAFE_INTERP:		Non zero means that the current interp is a safe
 *			interp (i.e. it has only the safe commands installed,
 *			less privilege than a regular interp).
 * INTERP_DEBUG_FRAME:	Used for switching on various extra interpreter
 *			debug/info mechanisms (e.g. info frame eval/uplevel
 *			tracing) which are performance intensive.
 * INTERP_TRACE_IN_PROGRESS: Non-zero means that an interp trace is currently
 *			active; so no further trace callbacks should be
 *			invoked.
 * INTERP_ALTERNATE_WRONG_ARGS: Used for listing second and subsequent forms
 *			of the wrong-num-args string in Tcl_WrongNumArgs.
 *			Makes it append instead of replacing and uses
 *			different intermediate text.
 * CANCELED:		Non-zero means that the script in progress should be
 *			canceled as soon as possible. This can be checked by
 *			extensions (and the core itself) by calling
 *			Tcl_Canceled and checking if TCL_ERROR is returned.
 *			This is a one-shot flag that is reset immediately upon
 *			being detected; however, if the TCL_CANCEL_UNWIND flag
 *			is set Tcl_Canceled will continue to report that the
 *			script in progress has been canceled thereby allowing
 *			the evaluation stack for the interp to be fully
 *			unwound.
 *
 * WARNING: For the sake of some extensions that have made use of former
 * internal values, do not re-use the flag values 2 (formerly ERR_IN_PROGRESS)
 * or 8 (formerly ERROR_CODE_SET).
 */

#define DELETED				     1
#define ERR_ALREADY_LOGGED		     4
#define INTERP_DEBUG_FRAME		  0x10
#define DONT_COMPILE_CMDS_INLINE	  0x20
#define RAND_SEED_INITIALIZED		  0x40
#define SAFE_INTERP			  0x80
#define INTERP_TRACE_IN_PROGRESS	 0x200
#define INTERP_ALTERNATE_WRONG_ARGS	 0x400
#define ERR_LEGACY_COPY			 0x800
#define CANCELED			0x1000

/*
 * Maximum number of levels of nesting permitted in Tcl commands (used to
 * catch infinite recursion).
 */

#define MAX_NESTING_DEPTH	1000

/*
 * The macro below is used to modify a "char" value (e.g. by casting it to an
 * unsigned character) so that it can be used safely with macros such as
 * isspace.
 */

#define UCHAR(c) ((unsigned char) (c))

/*
 * This macro is used to properly align the memory allocated by Tcl, giving
 * the same alignment as the native malloc.
 */

#if defined(__APPLE__)
#define TCL_ALLOCALIGN	16
#else
#define TCL_ALLOCALIGN	(2*sizeof(void *))
#endif

/*
 * This macro is used to determine the offset needed to safely allocate any
 * data structure in memory. Given a starting offset or size, it "rounds up"
 * or "aligns" the offset to the next 8-byte boundary so that any data
 * structure can be placed at the resulting offset without fear of an
 * alignment error.
 *
 * WARNING!! DO NOT USE THIS MACRO TO ALIGN POINTERS: it will produce the
 * wrong result on platforms that allocate addresses that are divisible by 4
 * or 2. Only use it for offsets or sizes.
 *
 * This macro is only used by tclCompile.c in the core (Bug 926445). It
 * however not be made file static, as extensions that touch bytecodes
 * (notably tbcload) require it.
 */

#define TCL_ALIGN(x) (((int)(x) + 7) & ~7)

/*
 * The following enum values are used to specify the runtime platform setting
 * of the tclPlatform variable.
 */

typedef enum {
    TCL_PLATFORM_UNIX = 0,	/* Any Unix-like OS. */
    TCL_PLATFORM_WINDOWS = 2	/* Any Microsoft Windows OS. */
} TclPlatformType;

/*
 * The following enum values are used to indicate the translation of a Tcl
 * channel. Declared here so that each platform can define
 * TCL_PLATFORM_TRANSLATION to the native translation on that platform.
 */

typedef enum TclEolTranslation {
    TCL_TRANSLATE_AUTO,		/* Eol == \r, \n and \r\n. */
    TCL_TRANSLATE_CR,		/* Eol == \r. */
    TCL_TRANSLATE_LF,		/* Eol == \n. */
    TCL_TRANSLATE_CRLF		/* Eol == \r\n. */
} TclEolTranslation;

/*
 * Flags for TclInvoke:
 *
 * TCL_INVOKE_HIDDEN		Invoke a hidden command; if not set, invokes
 *				an exposed command.
 * TCL_INVOKE_NO_UNKNOWN	If set, "unknown" is not invoked if the
 *				command to be invoked is not found. Only has
 *				an effect if invoking an exposed command,
 *				i.e. if TCL_INVOKE_HIDDEN is not also set.
 * TCL_INVOKE_NO_TRACEBACK	Does not record traceback information if the
 *				invoked command returns an error. Used if the
 *				caller plans on recording its own traceback
 *				information.
 */

#define	TCL_INVOKE_HIDDEN	(1<<0)
#define TCL_INVOKE_NO_UNKNOWN	(1<<1)
#define TCL_INVOKE_NO_TRACEBACK	(1<<2)

/*
 * The structure used as the internal representation of Tcl list objects. This
 * struct is grown (reallocated and copied) as necessary to hold all the
 * list's element pointers. The struct might contain more slots than currently
 * used to hold all element pointers. This is done to make append operations
 * faster.
 */

typedef struct List {
    int refCount;
    int maxElemCount;		/* Total number of element array slots. */
    int elemCount;		/* Current number of list elements. */
    int canonicalFlag;		/* Set if the string representation was
				 * derived from the list representation. May
				 * be ignored if there is no string rep at
				 * all.*/
    Tcl_Obj *elements;		/* First list element; the struct is grown to
				 * accommodate all elements. */
} List;

#define LIST_MAX \
	(1 + (int)(((size_t)UINT_MAX - sizeof(List))/sizeof(Tcl_Obj *)))
#define LIST_SIZE(numElems) \
	(unsigned)(sizeof(List) + (((numElems) - 1) * sizeof(Tcl_Obj *)))

/*
 * Macro used to get the elements of a list object.
 */

#define ListRepPtr(listPtr) \
    ((List *) (listPtr)->internalRep.twoPtrValue.ptr1)

/* Not used any more */
#define ListSetIntRep(objPtr, listRepPtr) \
    (objPtr)->internalRep.twoPtrValue.ptr1 = (void *)(listRepPtr), \
    (objPtr)->internalRep.twoPtrValue.ptr2 = NULL, \
    (listRepPtr)->refCount++, \
    (objPtr)->typePtr = &tclListType

#define ListObjGetElements(listPtr, objc, objv) \
    ((objv) = &(ListRepPtr(listPtr)->elements), \
     (objc) = ListRepPtr(listPtr)->elemCount)

#define ListObjLength(listPtr, len) \
    ((len) = ListRepPtr(listPtr)->elemCount)

#define ListObjIsCanonical(listPtr) \
    (((listPtr)->bytes == NULL) || ListRepPtr(listPtr)->canonicalFlag)

#define TclListObjGetElements(interp, listPtr, objcPtr, objvPtr) \
    (((listPtr)->typePtr == &tclListType) \
	    ? ((ListObjGetElements((listPtr), *(objcPtr), *(objvPtr))), TCL_OK)\
	    : Tcl_ListObjGetElements((interp), (listPtr), (objcPtr), (objvPtr)))

#define TclListObjLength(interp, listPtr, lenPtr) \
    (((listPtr)->typePtr == &tclListType) \
	    ? ((ListObjLength((listPtr), *(lenPtr))), TCL_OK)\
	    : Tcl_ListObjLength((interp), (listPtr), (lenPtr)))

#define TclListObjIsCanonical(listPtr) \
    (((listPtr)->typePtr == &tclListType) ? ListObjIsCanonical((listPtr)) : 0)

/*
 * Modes for collecting (or not) in the implementations of TclNRForeachCmd,
 * TclNRLmapCmd and their compilations.
 */

#define TCL_EACH_KEEP_NONE  0	/* Discard iteration result like [foreach] */
#define TCL_EACH_COLLECT    1	/* Collect iteration result like [lmap] */

/*
 * Macros providing a faster path to integers: Tcl_GetLongFromObj,
 * Tcl_GetIntFromObj and TclGetIntForIndex.
 *
 * WARNING: these macros eval their args more than once.
 */

#define TclGetLongFromObj(interp, objPtr, longPtr) \
    (((objPtr)->typePtr == &tclIntType)	\
	    ? ((*(longPtr) = (objPtr)->internalRep.longValue), TCL_OK) \
	    : Tcl_GetLongFromObj((interp), (objPtr), (longPtr)))

#if (LONG_MAX == INT_MAX)
#define TclGetIntFromObj(interp, objPtr, intPtr) \
    (((objPtr)->typePtr == &tclIntType)	\
	    ? ((*(intPtr) = (objPtr)->internalRep.longValue), TCL_OK) \
	    : Tcl_GetIntFromObj((interp), (objPtr), (intPtr)))
#define TclGetIntForIndexM(interp, objPtr, endValue, idxPtr) \
    (((objPtr)->typePtr == &tclIntType)	\
	    ? ((*(idxPtr) = (objPtr)->internalRep.longValue), TCL_OK) \
	    : TclGetIntForIndex((interp), (objPtr), (endValue), (idxPtr)))
#else
#define TclGetIntFromObj(interp, objPtr, intPtr) \
    (((objPtr)->typePtr == &tclIntType \
	    && (objPtr)->internalRep.longValue >= -(Tcl_WideInt)(UINT_MAX) \
	    && (objPtr)->internalRep.longValue <= (Tcl_WideInt)(UINT_MAX))	\
	    ? ((*(intPtr) = (objPtr)->internalRep.longValue), TCL_OK) \
	    : Tcl_GetIntFromObj((interp), (objPtr), (intPtr)))
#define TclGetIntForIndexM(interp, objPtr, endValue, idxPtr) \
    (((objPtr)->typePtr == &tclIntType \
	    && (objPtr)->internalRep.longValue >= INT_MIN \
	    && (objPtr)->internalRep.longValue <= INT_MAX)	\
	    ? ((*(idxPtr) = (objPtr)->internalRep.longValue), TCL_OK) \
	    : TclGetIntForIndex((interp), (objPtr), (endValue), (idxPtr)))
#endif

/*
 * Macro used to save a function call for common uses of
 * Tcl_GetWideIntFromObj(). The ANSI C "prototype" is:
 *
 * MODULE_SCOPE int TclGetWideIntFromObj(Tcl_Interp *interp, Tcl_Obj *objPtr,
 *			Tcl_WideInt *wideIntPtr);
 */

#ifdef TCL_WIDE_INT_IS_LONG
#define TclGetWideIntFromObj(interp, objPtr, wideIntPtr) \
    (((objPtr)->typePtr == &tclIntType)					\
	? (*(wideIntPtr) = (Tcl_WideInt)				\
		((objPtr)->internalRep.longValue), TCL_OK) :		\
	Tcl_GetWideIntFromObj((interp), (objPtr), (wideIntPtr)))
#else /* !TCL_WIDE_INT_IS_LONG */
#define TclGetWideIntFromObj(interp, objPtr, wideIntPtr)		\
    (((objPtr)->typePtr == &tclWideIntType)				\
	? (*(wideIntPtr) = (objPtr)->internalRep.wideValue, TCL_OK) :	\
    ((objPtr)->typePtr == &tclIntType)					\
	? (*(wideIntPtr) = (Tcl_WideInt)				\
		((objPtr)->internalRep.longValue), TCL_OK) :		\
	Tcl_GetWideIntFromObj((interp), (objPtr), (wideIntPtr)))
#endif /* TCL_WIDE_INT_IS_LONG */

/*
 * Flag values for TclTraceDictPath().
 *
 * DICT_PATH_READ indicates that all entries on the path must exist but no
 * updates will be needed.
 *
 * DICT_PATH_UPDATE indicates that we are going to be doing an update at the
 * tip of the path, so duplication of shared objects should be done along the
 * way.
 *
 * DICT_PATH_EXISTS indicates that we are performing an existence test and a
 * lookup failure should therefore not be an error. If (and only if) this flag
 * is set, TclTraceDictPath() will return the special value
 * DICT_PATH_NON_EXISTENT if the path is not traceable.
 *
 * DICT_PATH_CREATE (which also requires the DICT_PATH_UPDATE bit to be set)
 * indicates that we are to create non-existent dictionaries on the path.
 */

#define DICT_PATH_READ		0
#define DICT_PATH_UPDATE	1
#define DICT_PATH_EXISTS	2
#define DICT_PATH_CREATE	5

#define DICT_PATH_NON_EXISTENT	((Tcl_Obj *) (void *) 1)

/*
 *----------------------------------------------------------------
 * Data structures related to the filesystem internals
 *----------------------------------------------------------------
 */

/*
 * The version_2 filesystem is private to Tcl. As and when these changes have
 * been thoroughly tested and investigated a new public filesystem interface
 * will be released. The aim is more versatile virtual filesystem interfaces,
 * more efficiency in 'path' manipulation and usage, and cleaner filesystem
 * code internally.
 */

#define TCL_FILESYSTEM_VERSION_2	((Tcl_FSVersion) 0x2)
typedef ClientData (TclFSGetCwdProc2)(ClientData clientData);
typedef int (Tcl_FSLoadFileProc2) (Tcl_Interp *interp, Tcl_Obj *pathPtr,
	Tcl_LoadHandle *handlePtr, Tcl_FSUnloadFileProc **unloadProcPtr, int flags);

/*
 * The following types are used for getting and storing platform-specific file
 * attributes in tclFCmd.c and the various platform-versions of that file.
 * This is done to have as much common code as possible in the file attributes
 * code. For more information about the callbacks, see TclFileAttrsCmd in
 * tclFCmd.c.
 */

typedef int (TclGetFileAttrProc)(Tcl_Interp *interp, int objIndex,
	Tcl_Obj *fileName, Tcl_Obj **attrObjPtrPtr);
typedef int (TclSetFileAttrProc)(Tcl_Interp *interp, int objIndex,
	Tcl_Obj *fileName, Tcl_Obj *attrObjPtr);

typedef struct TclFileAttrProcs {
    TclGetFileAttrProc *getProc;/* The procedure for getting attrs. */
    TclSetFileAttrProc *setProc;/* The procedure for setting attrs. */
} TclFileAttrProcs;

/*
 * Opaque handle used in pipeline routines to encapsulate platform-dependent
 * state.
 */

typedef struct TclFile_ *TclFile;

/*
 * The "globParameters" argument of the function TclGlob is an or'ed
 * combination of the following values:
 */

#define TCL_GLOBMODE_NO_COMPLAIN	1
#define TCL_GLOBMODE_JOIN		2
#define TCL_GLOBMODE_DIR		4
#define TCL_GLOBMODE_TAILS		8

typedef enum Tcl_PathPart {
    TCL_PATH_DIRNAME,
    TCL_PATH_TAIL,
    TCL_PATH_EXTENSION,
    TCL_PATH_ROOT
} Tcl_PathPart;

/*
 *----------------------------------------------------------------
 * Data structures related to obsolete filesystem hooks
 *----------------------------------------------------------------
 */

typedef int (TclStatProc_)(const char *path, struct stat *buf);
typedef int (TclAccessProc_)(const char *path, int mode);
typedef Tcl_Channel (TclOpenFileChannelProc_)(Tcl_Interp *interp,
	const char *fileName, const char *modeString, int permissions);

/*
 *----------------------------------------------------------------
 * Data structures related to procedures
 *----------------------------------------------------------------
 */

typedef Tcl_CmdProc *TclCmdProcType;
typedef Tcl_ObjCmdProc *TclObjCmdProcType;

/*
 *----------------------------------------------------------------
 * Data structures for process-global values.
 *----------------------------------------------------------------
 */

typedef void (TclInitProcessGlobalValueProc)(char **valuePtr, int *lengthPtr,
	Tcl_Encoding *encodingPtr);

/*
 * A ProcessGlobalValue struct exists for each internal value in Tcl that is
 * to be shared among several threads. Each thread sees a (Tcl_Obj) copy of
 * the value, and the gobal value is kept as a counted string, with epoch and
 * mutex control. Each ProcessGlobalValue struct should be a static variable in
 * some file.
 */

typedef struct ProcessGlobalValue {
    int epoch;			/* Epoch counter to detect changes in the
				 * global value. */
    int numBytes;		/* Length of the global string. */
    char *value;		/* The global string value. */
    Tcl_Encoding encoding;	/* system encoding when global string was
				 * initialized. */
    TclInitProcessGlobalValueProc *proc;
    				/* A procedure to initialize the global string
				 * copy when a "get" request comes in before
				 * any "set" request has been received. */
    Tcl_Mutex mutex;		/* Enforce orderly access from multiple
				 * threads. */
    Tcl_ThreadDataKey key;	/* Key for per-thread data holding the
				 * (Tcl_Obj) copy for each thread. */
} ProcessGlobalValue;

/*
 *----------------------------------------------------------------------
 * Flags for TclParseNumber
 *----------------------------------------------------------------------
 */

#define TCL_PARSE_DECIMAL_ONLY		1
				/* Leading zero doesn't denote octal or
				 * hex. */
#define TCL_PARSE_OCTAL_ONLY		2
				/* Parse octal even without prefix. */
#define TCL_PARSE_HEXADECIMAL_ONLY	4
				/* Parse hexadecimal even without prefix. */
#define TCL_PARSE_INTEGER_ONLY		8
				/* Disable floating point parsing. */
#define TCL_PARSE_SCAN_PREFIXES		16
				/* Use [scan] rules dealing with 0?
				 * prefixes. */
#define TCL_PARSE_NO_WHITESPACE		32
				/* Reject leading/trailing whitespace. */
#define TCL_PARSE_BINARY_ONLY	64
				/* Parse binary even without prefix. */

/*
 *----------------------------------------------------------------------
 * Type values TclGetNumberFromObj
 *----------------------------------------------------------------------
 */

#define TCL_NUMBER_LONG		1
#define TCL_NUMBER_WIDE		2
#define TCL_NUMBER_BIG		3
#define TCL_NUMBER_DOUBLE	4
#define TCL_NUMBER_NAN		5

/*
 *----------------------------------------------------------------
 * Variables shared among Tcl modules but not used by the outside world.
 *----------------------------------------------------------------
 */

MODULE_SCOPE char *tclNativeExecutableName;
MODULE_SCOPE int tclFindExecutableSearchDone;
MODULE_SCOPE char *tclMemDumpFileName;
MODULE_SCOPE TclPlatformType tclPlatform;
MODULE_SCOPE Tcl_NotifierProcs tclNotifierHooks;

MODULE_SCOPE Tcl_Encoding tclIdentityEncoding;

/*
 * TIP #233 (Virtualized Time)
 * Data for the time hooks, if any.
 */

MODULE_SCOPE Tcl_GetTimeProc *tclGetTimeProcPtr;
MODULE_SCOPE Tcl_ScaleTimeProc *tclScaleTimeProcPtr;
MODULE_SCOPE ClientData tclTimeClientData;

/*
 * Variables denoting the Tcl object types defined in the core.
 */

MODULE_SCOPE const Tcl_ObjType tclBignumType;
MODULE_SCOPE const Tcl_ObjType tclBooleanType;
MODULE_SCOPE const Tcl_ObjType tclByteArrayType;
MODULE_SCOPE const Tcl_ObjType tclByteCodeType;
MODULE_SCOPE const Tcl_ObjType tclDoubleType;
MODULE_SCOPE const Tcl_ObjType tclEndOffsetType;
MODULE_SCOPE const Tcl_ObjType tclIntType;
MODULE_SCOPE const Tcl_ObjType tclListType;
MODULE_SCOPE const Tcl_ObjType tclDictType;
MODULE_SCOPE const Tcl_ObjType tclProcBodyType;
MODULE_SCOPE const Tcl_ObjType tclStringType;
MODULE_SCOPE const Tcl_ObjType tclArraySearchType;
MODULE_SCOPE const Tcl_ObjType tclEnsembleCmdType;
#ifndef TCL_WIDE_INT_IS_LONG
MODULE_SCOPE const Tcl_ObjType tclWideIntType;
#endif
MODULE_SCOPE const Tcl_ObjType tclRegexpType;
MODULE_SCOPE Tcl_ObjType tclCmdNameType;

/*
 * Variables denoting the hash key types defined in the core.
 */

MODULE_SCOPE const Tcl_HashKeyType tclArrayHashKeyType;
MODULE_SCOPE const Tcl_HashKeyType tclOneWordHashKeyType;
MODULE_SCOPE const Tcl_HashKeyType tclStringHashKeyType;
MODULE_SCOPE const Tcl_HashKeyType tclObjHashKeyType;

/*
 * The head of the list of free Tcl objects, and the total number of Tcl
 * objects ever allocated and freed.
 */

MODULE_SCOPE Tcl_Obj *	tclFreeObjList;

#ifdef TCL_COMPILE_STATS
MODULE_SCOPE long	tclObjsAlloced;
MODULE_SCOPE long	tclObjsFreed;
#define TCL_MAX_SHARED_OBJ_STATS 5
MODULE_SCOPE long	tclObjsShared[TCL_MAX_SHARED_OBJ_STATS];
#endif /* TCL_COMPILE_STATS */

/*
 * Pointer to a heap-allocated string of length zero that the Tcl core uses as
 * the value of an empty string representation for an object. This value is
 * shared by all new objects allocated by Tcl_NewObj.
 */

MODULE_SCOPE char *	tclEmptyStringRep;
MODULE_SCOPE char	tclEmptyString;

enum CheckEmptyStringResult {
	TCL_EMPTYSTRING_UNKNOWN = -1, TCL_EMPTYSTRING_NO, TCL_EMPTYSTRING_YES
};

/*
 *----------------------------------------------------------------
 * Procedures shared among Tcl modules but not used by the outside world,
 * introduced by/for NRE.
 *----------------------------------------------------------------
 */

MODULE_SCOPE Tcl_ObjCmdProc TclNRApplyObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNREvalObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRCatchObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRExprObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRForObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRForeachCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRIfObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRLmapCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRPackageObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRSourceObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRSubstObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRSwitchObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRTryObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRUplevelObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRWhileObjCmd;

MODULE_SCOPE Tcl_NRPostProc TclNRForIterCallback;
MODULE_SCOPE Tcl_NRPostProc TclNRCoroutineActivateCallback;
MODULE_SCOPE Tcl_ObjCmdProc TclNRTailcallObjCmd;
MODULE_SCOPE Tcl_NRPostProc TclNRTailcallEval;
MODULE_SCOPE Tcl_ObjCmdProc TclNRCoroutineObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRYieldObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRYieldmObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRYieldToObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRInvoke;
MODULE_SCOPE Tcl_NRPostProc TclNRReleaseValues;

MODULE_SCOPE void  TclSetTailcall(Tcl_Interp *interp, Tcl_Obj *tailcallPtr);
MODULE_SCOPE void  TclPushTailcallPoint(Tcl_Interp *interp);

/* These two can be considered for the public api */
MODULE_SCOPE void  TclMarkTailcall(Tcl_Interp *interp);
MODULE_SCOPE void  TclSkipTailcall(Tcl_Interp *interp);

/*
 * This structure holds the data for the various iteration callbacks used to
 * NRE the 'for' and 'while' commands. We need a separate structure because we
 * have more than the 4 client data entries we can provide directly thorugh
 * the callback API. It is the 'word' information which puts us over the
 * limit. It is needed because the loop body is argument 4 of 'for' and
 * argument 2 of 'while'. Not providing the correct index confuses the #280
 * code. We TclSmallAlloc/Free this.
 */

typedef struct ForIterData {
    Tcl_Obj *cond;		/* Loop condition expression. */
    Tcl_Obj *body;		/* Loop body. */
    Tcl_Obj *next;		/* Loop step script, NULL for 'while'. */
    const char *msg;		/* Error message part. */
    int word;			/* Index of the body script in the command */
} ForIterData;

/* TIP #357 - Structure doing the bookkeeping of handles for Tcl_LoadFile
 *            and Tcl_FindSymbol. This structure corresponds to an opaque
 *            typedef in tcl.h */

typedef void* TclFindSymbolProc(Tcl_Interp* interp, Tcl_LoadHandle loadHandle,
				const char* symbol);
struct Tcl_LoadHandle_ {
    ClientData clientData;	/* Client data is the load handle in the
				 * native filesystem if a module was loaded
				 * there, or an opaque pointer to a structure
				 * for further bookkeeping on load-from-VFS
				 * and load-from-memory */
    TclFindSymbolProc* findSymbolProcPtr;
				/* Procedure that resolves symbols in a
				 * loaded module */
    Tcl_FSUnloadFileProc* unloadFileProcPtr;
				/* Procedure that unloads a loaded module */
};

/* Flags for conversion of doubles to digit strings */

#define TCL_DD_SHORTEST 		0x4
				/* Use the shortest possible string */
#define TCL_DD_STEELE   		0x5
				/* Use the original Steele&White algorithm */
#define TCL_DD_E_FORMAT 		0x2
				/* Use a fixed-length string of digits,
				 * suitable for E format*/
#define TCL_DD_F_FORMAT 		0x3
				/* Use a fixed number of digits after the
				 * decimal point, suitable for F format */

#define TCL_DD_SHORTEN_FLAG 		0x4
				/* Allow return of a shorter digit string
				 * if it converts losslessly */
#define TCL_DD_NO_QUICK 		0x8
				/* Debug flag: forbid quick FP conversion */

#define TCL_DD_CONVERSION_TYPE_MASK	0x3
				/* Mask to isolate the conversion type */
#define TCL_DD_STEELE0 			0x1
				/* 'Steele&White' after masking */
#define TCL_DD_SHORTEST0		0x0
				/* 'Shortest possible' after masking */

/*
 *----------------------------------------------------------------
 * Procedures shared among Tcl modules but not used by the outside world:
 *----------------------------------------------------------------
 */

MODULE_SCOPE void	TclAppendBytesToByteArray(Tcl_Obj *objPtr,
			    const unsigned char *bytes, int len);
MODULE_SCOPE void	TclAppendUtfToUtf(Tcl_Obj *objPtr,
			    const char *bytes, int numBytes);
MODULE_SCOPE void	TclAdvanceContinuations(int *line, int **next,
			    int loc);
MODULE_SCOPE void	TclAdvanceLines(int *line, const char *start,
			    const char *end);
MODULE_SCOPE void	TclArgumentEnter(Tcl_Interp *interp,
			    Tcl_Obj *objv[], int objc, CmdFrame *cf);
MODULE_SCOPE void	TclArgumentRelease(Tcl_Interp *interp,
			    Tcl_Obj *objv[], int objc);
MODULE_SCOPE void	TclArgumentBCEnter(Tcl_Interp *interp,
			    Tcl_Obj *objv[], int objc,
			    void *codePtr, CmdFrame *cfPtr, int cmd, int pc);
MODULE_SCOPE void	TclArgumentBCRelease(Tcl_Interp *interp,
			    CmdFrame *cfPtr);
MODULE_SCOPE void	TclArgumentGet(Tcl_Interp *interp, Tcl_Obj *obj,
			    CmdFrame **cfPtrPtr, int *wordPtr);
MODULE_SCOPE double	TclBignumToDouble(const mp_int *bignum);
MODULE_SCOPE int	TclByteArrayMatch(const unsigned char *string,
			    int strLen, const unsigned char *pattern,
			    int ptnLen, int flags);
MODULE_SCOPE double	TclCeil(const mp_int *a);
MODULE_SCOPE void	TclChannelPreserve(Tcl_Channel chan);
MODULE_SCOPE void	TclChannelRelease(Tcl_Channel chan);
MODULE_SCOPE int	TclCheckArrayTraces(Tcl_Interp *interp, Var *varPtr,
			    Var *arrayPtr, Tcl_Obj *name, int index);
MODULE_SCOPE int	TclCheckBadOctal(Tcl_Interp *interp,
			    const char *value);
MODULE_SCOPE int	TclCheckEmptyString(Tcl_Obj *objPtr);
MODULE_SCOPE int	TclChanCaughtErrorBypass(Tcl_Interp *interp,
			    Tcl_Channel chan);
MODULE_SCOPE Tcl_ObjCmdProc TclChannelNamesCmd;
MODULE_SCOPE Tcl_NRPostProc TclClearRootEnsemble;
MODULE_SCOPE ContLineLoc *TclContinuationsEnter(Tcl_Obj *objPtr, int num,
			    int *loc);
MODULE_SCOPE void	TclContinuationsEnterDerived(Tcl_Obj *objPtr,
			    int start, int *clNext);
MODULE_SCOPE ContLineLoc *TclContinuationsGet(Tcl_Obj *objPtr);
MODULE_SCOPE void	TclContinuationsCopy(Tcl_Obj *objPtr,
			    Tcl_Obj *originObjPtr);
MODULE_SCOPE int	TclConvertElement(const char *src, int length,
			    char *dst, int flags);
MODULE_SCOPE Tcl_Command TclCreateObjCommandInNs(Tcl_Interp *interp,
			    const char *cmdName, Tcl_Namespace *nsPtr,
			    Tcl_ObjCmdProc *proc, ClientData clientData,
			    Tcl_CmdDeleteProc *deleteProc);
MODULE_SCOPE Tcl_Command TclCreateEnsembleInNs(Tcl_Interp *interp,
			    const char *name, Tcl_Namespace *nameNamespacePtr,
			    Tcl_Namespace *ensembleNamespacePtr, int flags);
MODULE_SCOPE void	TclDeleteNamespaceVars(Namespace *nsPtr);
MODULE_SCOPE int	TclFindDictElement(Tcl_Interp *interp,
			    const char *dict, int dictLength,
			    const char **elementPtr, const char **nextPtr,
			    int *sizePtr, int *literalPtr);
/* TIP #280 - Modified token based evaluation, with line information. */
MODULE_SCOPE int	TclEvalEx(Tcl_Interp *interp, const char *script,
			    int numBytes, int flags, int line,
			    int *clNextOuter, const char *outerScript);
MODULE_SCOPE Tcl_ObjCmdProc TclFileAttrsCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileCopyCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileDeleteCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileLinkCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileMakeDirsCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileReadLinkCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileRenameCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclFileTemporaryCmd;
MODULE_SCOPE void	TclCreateLateExitHandler(Tcl_ExitProc *proc,
			    ClientData clientData);
MODULE_SCOPE void	TclDeleteLateExitHandler(Tcl_ExitProc *proc,
			    ClientData clientData);
MODULE_SCOPE char *	TclDStringAppendObj(Tcl_DString *dsPtr,
			    Tcl_Obj *objPtr);
MODULE_SCOPE char *	TclDStringAppendDString(Tcl_DString *dsPtr,
			    Tcl_DString *toAppendPtr);
MODULE_SCOPE Tcl_Obj *	TclDStringToObj(Tcl_DString *dsPtr);
MODULE_SCOPE Tcl_Obj *const *TclFetchEnsembleRoot(Tcl_Interp *interp,
			    Tcl_Obj *const *objv, int objc, int *objcPtr);
MODULE_SCOPE Tcl_Obj *const *TclEnsembleGetRewriteValues(Tcl_Interp *interp);
MODULE_SCOPE Tcl_Namespace *TclEnsureNamespace(Tcl_Interp *interp,
			    Tcl_Namespace *namespacePtr);
MODULE_SCOPE void	TclFinalizeAllocSubsystem(void);
MODULE_SCOPE void	TclFinalizeAsync(void);
MODULE_SCOPE void	TclFinalizeDoubleConversion(void);
MODULE_SCOPE void	TclFinalizeEncodingSubsystem(void);
MODULE_SCOPE void	TclFinalizeEnvironment(void);
MODULE_SCOPE void	TclFinalizeEvaluation(void);
MODULE_SCOPE void	TclFinalizeExecution(void);
MODULE_SCOPE void	TclFinalizeIOSubsystem(void);
MODULE_SCOPE void	TclFinalizeFilesystem(void);
MODULE_SCOPE void	TclResetFilesystem(void);
MODULE_SCOPE void	TclFinalizeLoad(void);
MODULE_SCOPE void	TclFinalizeLock(void);
MODULE_SCOPE void	TclFinalizeMemorySubsystem(void);
MODULE_SCOPE void	TclFinalizeNotifier(void);
MODULE_SCOPE void	TclFinalizeObjects(void);
MODULE_SCOPE void	TclFinalizePreserve(void);
MODULE_SCOPE void	TclFinalizeSynchronization(void);
MODULE_SCOPE void	TclFinalizeThreadAlloc(void);
MODULE_SCOPE void	TclFinalizeThreadAllocThread(void);
MODULE_SCOPE void	TclFinalizeThreadData(int quick);
MODULE_SCOPE void	TclFinalizeThreadObjects(void);
MODULE_SCOPE double	TclFloor(const mp_int *a);
MODULE_SCOPE void	TclFormatNaN(double value, char *buffer);
MODULE_SCOPE int	TclFSFileAttrIndex(Tcl_Obj *pathPtr,
			    const char *attributeName, int *indexPtr);
MODULE_SCOPE Tcl_Command TclNRCreateCommandInNs(Tcl_Interp *interp,
			    const char *cmdName, Tcl_Namespace *nsPtr,
			    Tcl_ObjCmdProc *proc, Tcl_ObjCmdProc *nreProc,
			    ClientData clientData, Tcl_CmdDeleteProc *deleteProc);
MODULE_SCOPE int	TclNREvalFile(Tcl_Interp *interp, Tcl_Obj *pathPtr,
			    const char *encodingName);
MODULE_SCOPE int *	TclGetAsyncReadyPtr(void);
MODULE_SCOPE Tcl_Obj *	TclGetBgErrorHandler(Tcl_Interp *interp);
MODULE_SCOPE int	TclGetChannelFromObj(Tcl_Interp *interp,
			    Tcl_Obj *objPtr, Tcl_Channel *chanPtr,
			    int *modePtr, int flags);
MODULE_SCOPE CmdFrame *	TclGetCmdFrameForProcedure(Proc *procPtr);
MODULE_SCOPE int	TclGetCompletionCodeFromObj(Tcl_Interp *interp,
			    Tcl_Obj *value, int *code);
MODULE_SCOPE int	TclGetNumberFromObj(Tcl_Interp *interp,
			    Tcl_Obj *objPtr, ClientData *clientDataPtr,
			    int *typePtr);
MODULE_SCOPE int	TclGetOpenModeEx(Tcl_Interp *interp,
			    const char *modeString, int *seekFlagPtr,
			    int *binaryPtr);
MODULE_SCOPE Tcl_Obj *	TclGetProcessGlobalValue(ProcessGlobalValue *pgvPtr);
MODULE_SCOPE Tcl_Obj *	TclGetSourceFromFrame(CmdFrame *cfPtr, int objc,
			    Tcl_Obj *const objv[]);
MODULE_SCOPE char *	TclGetStringStorage(Tcl_Obj *objPtr,
			    unsigned int *sizePtr);
MODULE_SCOPE int	TclGlob(Tcl_Interp *interp, char *pattern,
			    Tcl_Obj *unquotedPrefix, int globFlags,
			    Tcl_GlobTypeData *types);
MODULE_SCOPE int	TclIncrObj(Tcl_Interp *interp, Tcl_Obj *valuePtr,
			    Tcl_Obj *incrPtr);
MODULE_SCOPE Tcl_Obj *	TclIncrObjVar2(Tcl_Interp *interp, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, Tcl_Obj *incrPtr, int flags);
MODULE_SCOPE Tcl_ObjCmdProc TclInfoExistsCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclInfoCoroutineCmd;
MODULE_SCOPE Tcl_Obj *	TclInfoFrame(Tcl_Interp *interp, CmdFrame *framePtr);
MODULE_SCOPE Tcl_ObjCmdProc TclInfoGlobalsCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclInfoLocalsCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclInfoVarsCmd;
MODULE_SCOPE void	TclInitAlloc(void);
MODULE_SCOPE void	TclInitDbCkalloc(void);
MODULE_SCOPE void	TclInitDoubleConversion(void);
MODULE_SCOPE void	TclInitEmbeddedConfigurationInformation(
			    Tcl_Interp *interp);
MODULE_SCOPE void	TclInitEncodingSubsystem(void);
MODULE_SCOPE void	TclInitIOSubsystem(void);
MODULE_SCOPE void	TclInitLimitSupport(Tcl_Interp *interp);
MODULE_SCOPE void	TclInitNamespaceSubsystem(void);
MODULE_SCOPE void	TclInitNotifier(void);
MODULE_SCOPE void	TclInitObjSubsystem(void);
MODULE_SCOPE const char *TclInitSubsystems(void);
MODULE_SCOPE int	TclInterpReady(Tcl_Interp *interp);
MODULE_SCOPE int	TclIsBareword(int byte);
MODULE_SCOPE Tcl_Obj *	TclJoinPath(int elements, Tcl_Obj * const objv[],
			    int forceRelative);
MODULE_SCOPE int	TclJoinThread(Tcl_ThreadId id, int *result);
MODULE_SCOPE void	TclLimitRemoveAllHandlers(Tcl_Interp *interp);
MODULE_SCOPE Tcl_Obj *	TclLindexList(Tcl_Interp *interp,
			    Tcl_Obj *listPtr, Tcl_Obj *argPtr);
MODULE_SCOPE Tcl_Obj *	TclLindexFlat(Tcl_Interp *interp, Tcl_Obj *listPtr,
			    int indexCount, Tcl_Obj *const indexArray[]);
/* TIP #280 */
MODULE_SCOPE void	TclListLines(Tcl_Obj *listObj, int line, int n,
			    int *lines, Tcl_Obj *const *elems);
MODULE_SCOPE Tcl_Obj *	TclListObjCopy(Tcl_Interp *interp, Tcl_Obj *listPtr);
MODULE_SCOPE Tcl_Obj *	TclLsetList(Tcl_Interp *interp, Tcl_Obj *listPtr,
			    Tcl_Obj *indexPtr, Tcl_Obj *valuePtr);
MODULE_SCOPE Tcl_Obj *	TclLsetFlat(Tcl_Interp *interp, Tcl_Obj *listPtr,
			    int indexCount, Tcl_Obj *const indexArray[],
			    Tcl_Obj *valuePtr);
MODULE_SCOPE Tcl_Command TclMakeEnsemble(Tcl_Interp *interp, const char *name,
			    const EnsembleImplMap map[]);
MODULE_SCOPE int	TclMaxListLength(const char *bytes, int numBytes,
			    const char **endPtr);
MODULE_SCOPE int	TclMergeReturnOptions(Tcl_Interp *interp, int objc,
			    Tcl_Obj *const objv[], Tcl_Obj **optionsPtrPtr,
			    int *codePtr, int *levelPtr);
MODULE_SCOPE Tcl_Obj *  TclNoErrorStack(Tcl_Interp *interp, Tcl_Obj *options);
MODULE_SCOPE int	TclNokia770Doubles(void);
MODULE_SCOPE void	TclNsDecrRefCount(Namespace *nsPtr);
MODULE_SCOPE int	TclNamespaceDeleted(Namespace *nsPtr);
MODULE_SCOPE void	TclObjVarErrMsg(Tcl_Interp *interp, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, const char *operation,
			    const char *reason, int index);
MODULE_SCOPE int	TclObjInvokeNamespace(Tcl_Interp *interp,
			    int objc, Tcl_Obj *const objv[],
			    Tcl_Namespace *nsPtr, int flags);
MODULE_SCOPE int	TclObjUnsetVar2(Tcl_Interp *interp,
			    Tcl_Obj *part1Ptr, Tcl_Obj *part2Ptr, int flags);
MODULE_SCOPE int	TclParseBackslash(const char *src,
			    int numBytes, int *readPtr, char *dst);
MODULE_SCOPE int	TclParseNumber(Tcl_Interp *interp, Tcl_Obj *objPtr,
			    const char *expected, const char *bytes,
			    int numBytes, const char **endPtrPtr, int flags);
MODULE_SCOPE void	TclParseInit(Tcl_Interp *interp, const char *string,
			    int numBytes, Tcl_Parse *parsePtr);
MODULE_SCOPE int	TclParseAllWhiteSpace(const char *src, int numBytes);
MODULE_SCOPE int	TclProcessReturn(Tcl_Interp *interp,
			    int code, int level, Tcl_Obj *returnOpts);
MODULE_SCOPE int	TclpObjLstat(Tcl_Obj *pathPtr, Tcl_StatBuf *buf);
MODULE_SCOPE Tcl_Obj *	TclpTempFileName(void);
MODULE_SCOPE Tcl_Obj *  TclpTempFileNameForLibrary(Tcl_Interp *interp, Tcl_Obj* pathPtr);
MODULE_SCOPE Tcl_Obj *	TclNewFSPathObj(Tcl_Obj *dirPtr, const char *addStrRep,
			    int len);
MODULE_SCOPE int	TclpDeleteFile(const void *path);
MODULE_SCOPE void	TclpFinalizeCondition(Tcl_Condition *condPtr);
MODULE_SCOPE void	TclpFinalizeMutex(Tcl_Mutex *mutexPtr);
MODULE_SCOPE void	TclpFinalizePipes(void);
MODULE_SCOPE void	TclpFinalizeSockets(void);
MODULE_SCOPE int	TclCreateSocketAddress(Tcl_Interp *interp,
			    struct addrinfo **addrlist,
			    const char *host, int port, int willBind,
			    const char **errorMsgPtr);
MODULE_SCOPE int	TclpThreadCreate(Tcl_ThreadId *idPtr,
			    Tcl_ThreadCreateProc *proc, ClientData clientData,
			    int stackSize, int flags);
MODULE_SCOPE int	TclpFindVariable(const char *name, int *lengthPtr);
MODULE_SCOPE void	TclpInitLibraryPath(char **valuePtr,
			    int *lengthPtr, Tcl_Encoding *encodingPtr);
MODULE_SCOPE void	TclpInitLock(void);
MODULE_SCOPE void	TclpInitPlatform(void);
MODULE_SCOPE void	TclpInitUnlock(void);
MODULE_SCOPE Tcl_Obj *	TclpObjListVolumes(void);
MODULE_SCOPE void	TclpGlobalLock(void);
MODULE_SCOPE void	TclpGlobalUnlock(void);
MODULE_SCOPE int	TclpObjNormalizePath(Tcl_Interp *interp,
			    Tcl_Obj *pathPtr, int nextCheckpoint);
MODULE_SCOPE void	TclpNativeJoinPath(Tcl_Obj *prefix, const char *joining);
MODULE_SCOPE Tcl_Obj *	TclpNativeSplitPath(Tcl_Obj *pathPtr, int *lenPtr);
MODULE_SCOPE Tcl_PathType TclpGetNativePathType(Tcl_Obj *pathPtr,
			    int *driveNameLengthPtr, Tcl_Obj **driveNameRef);
MODULE_SCOPE int	TclCrossFilesystemCopy(Tcl_Interp *interp,
			    Tcl_Obj *source, Tcl_Obj *target);
MODULE_SCOPE int	TclpMatchInDirectory(Tcl_Interp *interp,
			    Tcl_Obj *resultPtr, Tcl_Obj *pathPtr,
			    const char *pattern, Tcl_GlobTypeData *types);
MODULE_SCOPE ClientData	TclpGetNativeCwd(ClientData clientData);
MODULE_SCOPE Tcl_FSDupInternalRepProc TclNativeDupInternalRep;
MODULE_SCOPE Tcl_Obj *	TclpObjLink(Tcl_Obj *pathPtr, Tcl_Obj *toPtr,
			    int linkType);
MODULE_SCOPE int	TclpObjChdir(Tcl_Obj *pathPtr);
MODULE_SCOPE Tcl_Channel TclpOpenTemporaryFile(Tcl_Obj *dirObj,
			    Tcl_Obj *basenameObj, Tcl_Obj *extensionObj,
			    Tcl_Obj *resultingNameObj);
MODULE_SCOPE Tcl_Obj *	TclPathPart(Tcl_Interp *interp, Tcl_Obj *pathPtr,
			    Tcl_PathPart portion);
MODULE_SCOPE char *	TclpReadlink(const char *fileName,
			    Tcl_DString *linkPtr);
MODULE_SCOPE void	TclpSetVariables(Tcl_Interp *interp);
MODULE_SCOPE void *	TclThreadStorageKeyGet(Tcl_ThreadDataKey *keyPtr);
MODULE_SCOPE void	TclThreadStorageKeySet(Tcl_ThreadDataKey *keyPtr,
			    void *data);
MODULE_SCOPE void	TclpThreadExit(int status);
MODULE_SCOPE void	TclRememberCondition(Tcl_Condition *mutex);
MODULE_SCOPE void	TclRememberJoinableThread(Tcl_ThreadId id);
MODULE_SCOPE void	TclRememberMutex(Tcl_Mutex *mutex);
MODULE_SCOPE void	TclRemoveScriptLimitCallbacks(Tcl_Interp *interp);
MODULE_SCOPE int	TclReToGlob(Tcl_Interp *interp, const char *reStr,
			    int reStrLen, Tcl_DString *dsPtr, int *flagsPtr,
			    int *quantifiersFoundPtr);
MODULE_SCOPE unsigned int TclScanElement(const char *string, int length,
			    char *flagPtr);
MODULE_SCOPE void	TclSetBgErrorHandler(Tcl_Interp *interp,
			    Tcl_Obj *cmdPrefix);
MODULE_SCOPE void	TclSetBignumInternalRep(Tcl_Obj *objPtr,
			    mp_int *bignumValue);
MODULE_SCOPE int	TclSetBooleanFromAny(Tcl_Interp *interp, Tcl_Obj *objPtr);
MODULE_SCOPE void	TclSetCmdNameObj(Tcl_Interp *interp, Tcl_Obj *objPtr,
			    Command *cmdPtr);
MODULE_SCOPE void	TclSetDuplicateObj(Tcl_Obj *dupPtr, Tcl_Obj *objPtr);
MODULE_SCOPE void	TclSetProcessGlobalValue(ProcessGlobalValue *pgvPtr,
			    Tcl_Obj *newValue, Tcl_Encoding encoding);
MODULE_SCOPE void	TclSignalExitThread(Tcl_ThreadId id, int result);
MODULE_SCOPE void	TclSpellFix(Tcl_Interp *interp,
			    Tcl_Obj *const *objv, int objc, int subIdx,
			    Tcl_Obj *bad, Tcl_Obj *fix);
MODULE_SCOPE void *	TclStackRealloc(Tcl_Interp *interp, void *ptr,
			    int numBytes);

typedef int (*memCmpFn_t)(const void*, const void*, size_t);
MODULE_SCOPE int	TclStringCmp(Tcl_Obj *value1Ptr, Tcl_Obj *value2Ptr,
			    int checkEq, int nocase, int reqlength);
MODULE_SCOPE int	TclUniCharNcasecmp(const void*, const void*, size_t);
MODULE_SCOPE int	TclUtfNcasecmp(const void*, const void*, size_t);
MODULE_SCOPE int	TclUtfNcmp(const void*, const void*, size_t);
MODULE_SCOPE int	TclUniCharNcmp(const void*, const void*, size_t);
MODULE_SCOPE int	TclUtfNcmp2(const void*, const void*, size_t);
MODULE_SCOPE int	TclStringCmpOpts(Tcl_Interp *interp, int objc, Tcl_Obj *const objv[],
			    int *nocase, int *reqlength);
MODULE_SCOPE int	TclStringMatch(const char *str, int strLen,
			    const char *pattern, int ptnLen, int flags);
MODULE_SCOPE int	TclStringMatchObj(Tcl_Obj *stringObj,
			    Tcl_Obj *patternObj, int flags);
MODULE_SCOPE Tcl_Obj *	TclStringReverse(Tcl_Obj *objPtr);
MODULE_SCOPE void	TclSubstCompile(Tcl_Interp *interp, const char *bytes,
			    int numBytes, int flags, int line,
			    struct CompileEnv *envPtr);
MODULE_SCOPE int	TclSubstOptions(Tcl_Interp *interp, int numOpts,
			    Tcl_Obj *const opts[], int *flagPtr);
MODULE_SCOPE void	TclSubstParse(Tcl_Interp *interp, const char *bytes,
			    int numBytes, int flags, Tcl_Parse *parsePtr,
			    Tcl_InterpState *statePtr);
MODULE_SCOPE int	TclSubstTokens(Tcl_Interp *interp, Tcl_Token *tokenPtr,
			    int count, int *tokensLeftPtr, int line,
			    int *clNextOuter, const char *outerScript);
MODULE_SCOPE int	TclTrim(const char *bytes, int numBytes,
			    const char *trim, int numTrim, int *trimRight);
MODULE_SCOPE int	TclTrimLeft(const char *bytes, int numBytes,
			    const char *trim, int numTrim);
MODULE_SCOPE int	TclTrimRight(const char *bytes, int numBytes,
			    const char *trim, int numTrim);
MODULE_SCOPE int	TclUtfCasecmp(const char *cs, const char *ct);
MODULE_SCOPE int	TclUtfToUCS4(const char *, int *);
MODULE_SCOPE int	TclUCS4ToUtf(int, char *);
MODULE_SCOPE int	TclUCS4ToLower(int ch);
#if TCL_UTF_MAX == 4
    MODULE_SCOPE int	TclGetUCS4(Tcl_Obj *, int);
    MODULE_SCOPE int	TclUniCharToUCS4(const Tcl_UniChar *, int *);
#else
#   define TclGetUCS4 Tcl_GetUniChar
#   define TclUniCharToUCS4(src, ptr) (*ptr = *(src),1)
#endif

/*
 * Bytes F0-F4 are start-bytes for 4-byte sequences.
 * Byte 0xED can be the start-byte of an upper surrogate. In that case,
 * TclUtfToUCS4() might read the lower surrogate following it too.
 */
#   define TclUCS4Complete(src, length) (((unsigned)(UCHAR(*(src)) - 0xF0) < 5) \
	    ? ((length) >= 4) : (UCHAR(*(src)) == 0xED) ? ((length) >= 6) : Tcl_UtfCharComplete((src), (length)))
MODULE_SCOPE Tcl_Obj *	TclpNativeToNormalized(ClientData clientData);
MODULE_SCOPE Tcl_Obj *	TclpFilesystemPathType(Tcl_Obj *pathPtr);
MODULE_SCOPE int	TclpDlopen(Tcl_Interp *interp, Tcl_Obj *pathPtr,
			    Tcl_LoadHandle *loadHandle,
			    Tcl_FSUnloadFileProc **unloadProcPtr, int flags);
MODULE_SCOPE int	TclpUtime(Tcl_Obj *pathPtr, struct utimbuf *tval);
#ifdef TCL_LOAD_FROM_MEMORY
MODULE_SCOPE void *	TclpLoadMemoryGetBuffer(Tcl_Interp *interp, int size);
MODULE_SCOPE int	TclpLoadMemory(Tcl_Interp *interp, void *buffer,
			    int size, int codeSize, Tcl_LoadHandle *loadHandle,
			    Tcl_FSUnloadFileProc **unloadProcPtr, int flags);
#endif
MODULE_SCOPE void	TclInitThreadStorage(void);
MODULE_SCOPE void	TclFinalizeThreadDataThread(void);
MODULE_SCOPE void	TclFinalizeThreadStorage(void);

/* TclWideMUInt -- wide integer used for measurement calculations: */
#if (!defined(_WIN32) || !defined(_MSC_VER) || (_MSC_VER >= 1400))
#   define TclWideMUInt Tcl_WideUInt
#else
/* older MSVS may not allow conversions between unsigned __int64 and double) */
#   define TclWideMUInt Tcl_WideInt
#endif
#ifdef TCL_WIDE_CLICKS
MODULE_SCOPE Tcl_WideInt TclpGetWideClicks(void);
MODULE_SCOPE double	TclpWideClicksToNanoseconds(Tcl_WideInt clicks);
MODULE_SCOPE double	TclpWideClickInMicrosec(void);
#else
#   ifdef _WIN32
#	define TCL_WIDE_CLICKS 1
MODULE_SCOPE Tcl_WideInt TclpGetWideClicks(void);
MODULE_SCOPE double	TclpWideClickInMicrosec(void);
#	define		TclpWideClicksToNanoseconds(clicks) \
				((double)(clicks) * TclpWideClickInMicrosec() * 1000)
#   endif
#endif
MODULE_SCOPE Tcl_WideInt TclpGetMicroseconds(void);

MODULE_SCOPE int	TclZlibInit(Tcl_Interp *interp);
MODULE_SCOPE void *	TclpThreadCreateKey(void);
MODULE_SCOPE void	TclpThreadDeleteKey(void *keyPtr);
MODULE_SCOPE void	TclpThreadSetGlobalTSD(void *tsdKeyPtr, void *ptr);
MODULE_SCOPE void *	TclpThreadGetGlobalTSD(void *tsdKeyPtr);
MODULE_SCOPE void	TclErrorStackResetIf(Tcl_Interp *interp,
			    const char *msg, int length);

/*
 * Many parsing tasks need a common definition of whitespace.
 * Use this routine and macro to achieve that and place
 * optimization (fragile on changes) in one place.
 */

MODULE_SCOPE int	TclIsSpaceProc(int byte);
#	define TclIsSpaceProcM(byte) \
		(((byte) > 0x20) ? 0 : TclIsSpaceProc(byte))

/*
 *----------------------------------------------------------------
 * Command procedures in the generic core:
 *----------------------------------------------------------------
 */

MODULE_SCOPE Tcl_ObjCmdProc Tcl_AfterObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_AppendObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ApplyObjCmd;
MODULE_SCOPE Tcl_Command TclInitArrayCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_Command TclInitBinaryCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_BreakObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_CaseObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_CatchObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_CdObjCmd;
MODULE_SCOPE Tcl_Command TclInitChanCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc TclChanCreateObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclChanPostEventObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclChanPopObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclChanPushObjCmd;
MODULE_SCOPE void	TclClockInit(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc TclClockOldscanObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_CloseObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ConcatObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ContinueObjCmd;
MODULE_SCOPE Tcl_TimerToken TclCreateAbsoluteTimerHandler(
			    Tcl_Time *timePtr, Tcl_TimerProc *proc,
			    ClientData clientData);
MODULE_SCOPE Tcl_ObjCmdProc TclDefaultBgErrorHandlerObjCmd;
MODULE_SCOPE Tcl_Command TclInitDictCmd(Tcl_Interp *interp);
MODULE_SCOPE int	TclDictWithFinish(Tcl_Interp *interp, Var *varPtr,
			    Var *arrayPtr, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, int index, int pathc,
			    Tcl_Obj *const pathv[], Tcl_Obj *keysPtr);
MODULE_SCOPE Tcl_Obj *	TclDictWithInit(Tcl_Interp *interp, Tcl_Obj *dictPtr,
			    int pathc, Tcl_Obj *const pathv[]);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_DisassembleObjCmd;

/* Assemble command function */
MODULE_SCOPE Tcl_ObjCmdProc Tcl_AssembleObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNRAssembleObjCmd;
MODULE_SCOPE Tcl_Command TclInitEncodingCmd(Tcl_Interp *interp);
MODULE_SCOPE int	TclMakeEncodingCommandSafe(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_EofObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ErrorObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_EvalObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ExecObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ExitObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ExprObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FblockedObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FconfigureObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FcopyObjCmd;
MODULE_SCOPE Tcl_Command TclInitFileCmd(Tcl_Interp *interp);
MODULE_SCOPE int	TclMakeFileCommandSafe(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FileEventObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FlushObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ForObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ForeachObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_FormatObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_GetsObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_GlobalObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_GlobObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_IfObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_IncrObjCmd;
MODULE_SCOPE Tcl_Command TclInitInfoCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_InterpObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_JoinObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LappendObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LassignObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LindexObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LinsertObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LlengthObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ListObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LmapObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LoadObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LrangeObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LrepeatObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LreplaceObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LreverseObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LsearchObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LsetObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_LsortObjCmd;
MODULE_SCOPE Tcl_Command TclInitNamespaceCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc TclNamespaceEnsembleCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_OpenObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_PackageObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_PidObjCmd;
MODULE_SCOPE Tcl_Command TclInitPrefixCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_PutsObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_PwdObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ReadObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_RegexpObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_RegsubObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_RenameObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_RepresentationCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ReturnObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ScanObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SeekObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SetObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SplitObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SocketObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SourceObjCmd;
MODULE_SCOPE Tcl_Command TclInitStringCmd(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SubstObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_SwitchObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_TellObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_ThrowObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_TimeObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_TimeRateObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_TraceObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_TryObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_UnloadObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_UnsetObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_UpdateObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_UplevelObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_UpvarObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_VariableObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_VwaitObjCmd;
MODULE_SCOPE Tcl_ObjCmdProc Tcl_WhileObjCmd;

/*
 *----------------------------------------------------------------
 * Compilation procedures for commands in the generic core:
 *----------------------------------------------------------------
 */

MODULE_SCOPE CompileProc TclCompileAppendCmd;
MODULE_SCOPE CompileProc TclCompileArrayExistsCmd;
MODULE_SCOPE CompileProc TclCompileArraySetCmd;
MODULE_SCOPE CompileProc TclCompileArrayUnsetCmd;
MODULE_SCOPE CompileProc TclCompileBreakCmd;
MODULE_SCOPE CompileProc TclCompileCatchCmd;
MODULE_SCOPE CompileProc TclCompileClockClicksCmd;
MODULE_SCOPE CompileProc TclCompileClockReadingCmd;
MODULE_SCOPE CompileProc TclCompileConcatCmd;
MODULE_SCOPE CompileProc TclCompileContinueCmd;
MODULE_SCOPE CompileProc TclCompileDictAppendCmd;
MODULE_SCOPE CompileProc TclCompileDictCreateCmd;
MODULE_SCOPE CompileProc TclCompileDictExistsCmd;
MODULE_SCOPE CompileProc TclCompileDictForCmd;
MODULE_SCOPE CompileProc TclCompileDictGetCmd;
MODULE_SCOPE CompileProc TclCompileDictIncrCmd;
MODULE_SCOPE CompileProc TclCompileDictLappendCmd;
MODULE_SCOPE CompileProc TclCompileDictMapCmd;
MODULE_SCOPE CompileProc TclCompileDictMergeCmd;
MODULE_SCOPE CompileProc TclCompileDictSetCmd;
MODULE_SCOPE CompileProc TclCompileDictUnsetCmd;
MODULE_SCOPE CompileProc TclCompileDictUpdateCmd;
MODULE_SCOPE CompileProc TclCompileDictWithCmd;
MODULE_SCOPE CompileProc TclCompileEnsemble;
MODULE_SCOPE CompileProc TclCompileErrorCmd;
MODULE_SCOPE CompileProc TclCompileExprCmd;
MODULE_SCOPE CompileProc TclCompileForCmd;
MODULE_SCOPE CompileProc TclCompileForeachCmd;
MODULE_SCOPE CompileProc TclCompileFormatCmd;
MODULE_SCOPE CompileProc TclCompileGlobalCmd;
MODULE_SCOPE CompileProc TclCompileIfCmd;
MODULE_SCOPE CompileProc TclCompileInfoCommandsCmd;
MODULE_SCOPE CompileProc TclCompileInfoCoroutineCmd;
MODULE_SCOPE CompileProc TclCompileInfoExistsCmd;
MODULE_SCOPE CompileProc TclCompileInfoLevelCmd;
MODULE_SCOPE CompileProc TclCompileInfoObjectClassCmd;
MODULE_SCOPE CompileProc TclCompileInfoObjectIsACmd;
MODULE_SCOPE CompileProc TclCompileInfoObjectNamespaceCmd;
MODULE_SCOPE CompileProc TclCompileIncrCmd;
MODULE_SCOPE CompileProc TclCompileLappendCmd;
MODULE_SCOPE CompileProc TclCompileLassignCmd;
MODULE_SCOPE CompileProc TclCompileLindexCmd;
MODULE_SCOPE CompileProc TclCompileLinsertCmd;
MODULE_SCOPE CompileProc TclCompileListCmd;
MODULE_SCOPE CompileProc TclCompileLlengthCmd;
MODULE_SCOPE CompileProc TclCompileLmapCmd;
MODULE_SCOPE CompileProc TclCompileLrangeCmd;
MODULE_SCOPE CompileProc TclCompileLreplaceCmd;
MODULE_SCOPE CompileProc TclCompileLsetCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceCodeCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceCurrentCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceOriginCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceQualifiersCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceTailCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceUpvarCmd;
MODULE_SCOPE CompileProc TclCompileNamespaceWhichCmd;
MODULE_SCOPE CompileProc TclCompileNoOp;
MODULE_SCOPE CompileProc TclCompileObjectNextCmd;
MODULE_SCOPE CompileProc TclCompileObjectNextToCmd;
MODULE_SCOPE CompileProc TclCompileObjectSelfCmd;
MODULE_SCOPE CompileProc TclCompileRegexpCmd;
MODULE_SCOPE CompileProc TclCompileRegsubCmd;
MODULE_SCOPE CompileProc TclCompileReturnCmd;
MODULE_SCOPE CompileProc TclCompileSetCmd;
MODULE_SCOPE CompileProc TclCompileStringCatCmd;
MODULE_SCOPE CompileProc TclCompileStringCmpCmd;
MODULE_SCOPE CompileProc TclCompileStringEqualCmd;
MODULE_SCOPE CompileProc TclCompileStringFirstCmd;
MODULE_SCOPE CompileProc TclCompileStringIndexCmd;
MODULE_SCOPE CompileProc TclCompileStringIsCmd;
MODULE_SCOPE CompileProc TclCompileStringLastCmd;
MODULE_SCOPE CompileProc TclCompileStringLenCmd;
MODULE_SCOPE CompileProc TclCompileStringMapCmd;
MODULE_SCOPE CompileProc TclCompileStringMatchCmd;
MODULE_SCOPE CompileProc TclCompileStringRangeCmd;
MODULE_SCOPE CompileProc TclCompileStringReplaceCmd;
MODULE_SCOPE CompileProc TclCompileStringToLowerCmd;
MODULE_SCOPE CompileProc TclCompileStringToTitleCmd;
MODULE_SCOPE CompileProc TclCompileStringToUpperCmd;
MODULE_SCOPE CompileProc TclCompileStringTrimCmd;
MODULE_SCOPE CompileProc TclCompileStringTrimLCmd;
MODULE_SCOPE CompileProc TclCompileStringTrimRCmd;
MODULE_SCOPE CompileProc TclCompileSubstCmd;
MODULE_SCOPE CompileProc TclCompileSwitchCmd;
MODULE_SCOPE CompileProc TclCompileTailcallCmd;
MODULE_SCOPE CompileProc TclCompileThrowCmd;
MODULE_SCOPE CompileProc TclCompileTryCmd;
MODULE_SCOPE CompileProc TclCompileUnsetCmd;
MODULE_SCOPE CompileProc TclCompileUpvarCmd;
MODULE_SCOPE CompileProc TclCompileVariableCmd;
MODULE_SCOPE CompileProc TclCompileWhileCmd;
MODULE_SCOPE CompileProc TclCompileYieldCmd;
MODULE_SCOPE CompileProc TclCompileYieldToCmd;
MODULE_SCOPE CompileProc TclCompileBasic0ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic1ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic2ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic3ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic0Or1ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic1Or2ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic2Or3ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic0To2ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasic1To3ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasicMin0ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasicMin1ArgCmd;
MODULE_SCOPE CompileProc TclCompileBasicMin2ArgCmd;

MODULE_SCOPE Tcl_ObjCmdProc TclInvertOpCmd;
MODULE_SCOPE CompileProc TclCompileInvertOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNotOpCmd;
MODULE_SCOPE CompileProc TclCompileNotOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclAddOpCmd;
MODULE_SCOPE CompileProc TclCompileAddOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclMulOpCmd;
MODULE_SCOPE CompileProc TclCompileMulOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclAndOpCmd;
MODULE_SCOPE CompileProc TclCompileAndOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclOrOpCmd;
MODULE_SCOPE CompileProc TclCompileOrOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclXorOpCmd;
MODULE_SCOPE CompileProc TclCompileXorOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclPowOpCmd;
MODULE_SCOPE CompileProc TclCompilePowOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclLshiftOpCmd;
MODULE_SCOPE CompileProc TclCompileLshiftOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclRshiftOpCmd;
MODULE_SCOPE CompileProc TclCompileRshiftOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclModOpCmd;
MODULE_SCOPE CompileProc TclCompileModOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNeqOpCmd;
MODULE_SCOPE CompileProc TclCompileNeqOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclStrneqOpCmd;
MODULE_SCOPE CompileProc TclCompileStrneqOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclInOpCmd;
MODULE_SCOPE CompileProc TclCompileInOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclNiOpCmd;
MODULE_SCOPE CompileProc TclCompileNiOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclMinusOpCmd;
MODULE_SCOPE CompileProc TclCompileMinusOpCmd;
MODULE_SCOPE Tcl_ObjCmdProc TclDivOpCmd;
MODULE_SCOPE CompileProc TclCompileDivOpCmd;
MODULE_SCOPE CompileProc TclCompileLessOpCmd;
MODULE_SCOPE CompileProc TclCompileLeqOpCmd;
MODULE_SCOPE CompileProc TclCompileGreaterOpCmd;
MODULE_SCOPE CompileProc TclCompileGeqOpCmd;
MODULE_SCOPE CompileProc TclCompileEqOpCmd;
MODULE_SCOPE CompileProc TclCompileStreqOpCmd;

MODULE_SCOPE CompileProc TclCompileAssembleCmd;

/*
 * Functions defined in generic/tclVar.c and currently exported only for use
 * by the bytecode compiler and engine. Some of these could later be placed in
 * the public interface.
 */

MODULE_SCOPE Var *	TclObjLookupVarEx(Tcl_Interp * interp,
			    Tcl_Obj *part1Ptr, Tcl_Obj *part2Ptr, int flags,
			    const char *msg, int createPart1,
			    int createPart2, Var **arrayPtrPtr);
MODULE_SCOPE Var *	TclLookupArrayElement(Tcl_Interp *interp,
			    Tcl_Obj *arrayNamePtr, Tcl_Obj *elNamePtr,
			    int flags, const char *msg,
			    int createPart1, int createPart2,
			    Var *arrayPtr, int index);
MODULE_SCOPE Tcl_Obj *	TclPtrGetVarIdx(Tcl_Interp *interp,
			    Var *varPtr, Var *arrayPtr, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, int flags, int index);
MODULE_SCOPE Tcl_Obj *	TclPtrSetVarIdx(Tcl_Interp *interp,
			    Var *varPtr, Var *arrayPtr, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, Tcl_Obj *newValuePtr,
			    int flags, int index);
MODULE_SCOPE Tcl_Obj *	TclPtrIncrObjVarIdx(Tcl_Interp *interp,
			    Var *varPtr, Var *arrayPtr, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, Tcl_Obj *incrPtr,
			    int flags, int index);
MODULE_SCOPE int	TclPtrObjMakeUpvarIdx(Tcl_Interp *interp,
			    Var *otherPtr, Tcl_Obj *myNamePtr, int myFlags,
			    int index);
MODULE_SCOPE int	TclPtrUnsetVarIdx(Tcl_Interp *interp, Var *varPtr,
			    Var *arrayPtr, Tcl_Obj *part1Ptr,
			    Tcl_Obj *part2Ptr, int flags,
			    int index);
MODULE_SCOPE void	TclInvalidateNsPath(Namespace *nsPtr);
MODULE_SCOPE void	TclFindArrayPtrElements(Var *arrayPtr,
			    Tcl_HashTable *tablePtr);

/*
 * The new extended interface to the variable traces.
 */

MODULE_SCOPE int	TclObjCallVarTraces(Interp *iPtr, Var *arrayPtr,
			    Var *varPtr, Tcl_Obj *part1Ptr, Tcl_Obj *part2Ptr,
			    int flags, int leaveErrMsg, int index);

/*
 * So tclObj.c and tclDictObj.c can share these implementations.
 */

MODULE_SCOPE int	TclCompareObjKeys(void *keyPtr, Tcl_HashEntry *hPtr);
MODULE_SCOPE void	TclFreeObjEntry(Tcl_HashEntry *hPtr);
MODULE_SCOPE unsigned	TclHashObjKey(Tcl_HashTable *tablePtr, void *keyPtr);

MODULE_SCOPE int	TclFullFinalizationRequested(void);

/*
 * Utility routines for encoding index values as integers. Used by both
 * some of the command compilers and by [lsort] and [lsearch].
 */

MODULE_SCOPE int	TclIndexEncode(Tcl_Interp *interp, Tcl_Obj *objPtr,
			    int before, int after, int *indexPtr);
MODULE_SCOPE int	TclIndexDecode(int encoded, int endValue);

MODULE_SCOPE void	TclBN_s_mp_reverse(unsigned char *s, size_t len);

/* Constants used in index value encoding routines. */
#define TCL_INDEX_END           (-2)
#define TCL_INDEX_BEFORE        (-1)
#define TCL_INDEX_START         (0)
#define TCL_INDEX_AFTER         (INT_MAX)

/*
 *----------------------------------------------------------------
 * Macros used by the Tcl core to create and release Tcl objects.
 * TclNewObj(objPtr) creates a new object denoting an empty string.
 * TclDecrRefCount(objPtr) decrements the object's reference count, and frees
 * the object if its reference count is zero. These macros are inline versions
 * of Tcl_NewObj() and Tcl_DecrRefCount(). Notice that the names differ in not
 * having a "_" after the "Tcl". Notice also that these macros reference their
 * argument more than once, so you should avoid calling them with an
 * expression that is expensive to compute or has side effects. The ANSI C
 * "prototypes" for these macros are:
 *
 * MODULE_SCOPE void	TclNewObj(Tcl_Obj *objPtr);
 * MODULE_SCOPE void	TclDecrRefCount(Tcl_Obj *objPtr);
 *
 * These macros are defined in terms of two macros that depend on memory
 * allocator in use: TclAllocObjStorage, TclFreeObjStorage. They are defined
 * below.
 *----------------------------------------------------------------
 */

/*
 * DTrace object allocation probe macros.
 */

#ifdef USE_DTRACE
#ifndef _TCLDTRACE_H
#include "tclDTrace.h"
#endif
#define	TCL_DTRACE_OBJ_CREATE(objPtr)	TCL_OBJ_CREATE(objPtr)
#define	TCL_DTRACE_OBJ_FREE(objPtr)	TCL_OBJ_FREE(objPtr)
#else /* USE_DTRACE */
#define	TCL_DTRACE_OBJ_CREATE(objPtr)	{}
#define	TCL_DTRACE_OBJ_FREE(objPtr)	{}
#endif /* USE_DTRACE */

#ifdef TCL_COMPILE_STATS
#  define TclIncrObjsAllocated() \
    tclObjsAlloced++
#  define TclIncrObjsFreed() \
    tclObjsFreed++
#else
#  define TclIncrObjsAllocated()
#  define TclIncrObjsFreed()
#endif /* TCL_COMPILE_STATS */

#  define TclAllocObjStorage(objPtr)		\
	TclAllocObjStorageEx(NULL, (objPtr))

#  define TclFreeObjStorage(objPtr)		\
	TclFreeObjStorageEx(NULL, (objPtr))

#ifndef TCL_MEM_DEBUG
# define TclNewObj(objPtr) \
    TclIncrObjsAllocated(); \
    TclAllocObjStorage(objPtr); \
    (objPtr)->refCount = 0; \
    (objPtr)->bytes    = tclEmptyStringRep; \
    (objPtr)->length   = 0; \
    (objPtr)->typePtr  = NULL; \
    TCL_DTRACE_OBJ_CREATE(objPtr)

/*
 * Invalidate the string rep first so we can use the bytes value for our
 * pointer chain, and signal an obj deletion (as opposed to shimmering) with
 * 'length == -1'.
 * Use empty 'if ; else' to handle use in unbraced outer if/else conditions.
 */

# define TclDecrRefCount(objPtr) \
    if ((objPtr)->refCount-- > 1) ; else { \
	if (!(objPtr)->typePtr || !(objPtr)->typePtr->freeIntRepProc) { \
	    TCL_DTRACE_OBJ_FREE(objPtr); \
	    if ((objPtr)->bytes \
		    && ((objPtr)->bytes != tclEmptyStringRep)) { \
		ckfree((char *)(objPtr)->bytes); \
	    } \
	    (objPtr)->length = -1; \
	    TclFreeObjStorage(objPtr); \
	    TclIncrObjsFreed(); \
	} else { \
	    TclFreeObj(objPtr); \
	} \
    }

#if defined(PURIFY)

/*
 * The PURIFY mode is like the regular mode, but instead of doing block
 * Tcl_Obj allocation and keeping a freed list for efficiency, it always
 * allocates and frees a single Tcl_Obj so that tools like Purify can better
 * track memory leaks.
 */

#  define TclAllocObjStorageEx(interp, objPtr) \
	(objPtr) = (Tcl_Obj *)ckalloc(sizeof(Tcl_Obj))

#  define TclFreeObjStorageEx(interp, objPtr) \
	ckfree((char *)(objPtr))

#undef USE_THREAD_ALLOC
#undef USE_TCLALLOC
#elif defined(TCL_THREADS) && defined(USE_THREAD_ALLOC)

/*
 * The TCL_THREADS mode is like the regular mode but allocates Tcl_Obj's from
 * per-thread caches.
 */

MODULE_SCOPE Tcl_Obj *	TclThreadAllocObj(void);
MODULE_SCOPE void	TclThreadFreeObj(Tcl_Obj *);
MODULE_SCOPE Tcl_Mutex *TclpNewAllocMutex(void);
MODULE_SCOPE void	TclFreeAllocCache(void *);
MODULE_SCOPE void *	TclpGetAllocCache(void);
MODULE_SCOPE void	TclpSetAllocCache(void *);
MODULE_SCOPE void	TclpFreeAllocMutex(Tcl_Mutex *mutex);
MODULE_SCOPE void	TclpFreeAllocCache(void *);

/*
 * These macros need to be kept in sync with the code of TclThreadAllocObj()
 * and TclThreadFreeObj().
 *
 * Note that the optimiser should resolve the case (interp==NULL) at compile
 * time.
 */

#  define ALLOC_NOBJHIGH 1200

#  define TclAllocObjStorageEx(interp, objPtr)				\
    do {								\
	AllocCache *cachePtr;						\
	if (((interp) == NULL) ||					\
		((cachePtr = ((Interp *)(interp))->allocCache),		\
			(cachePtr->numObjects == 0))) {			\
	    (objPtr) = TclThreadAllocObj();				\
	} else {							\
	    (objPtr) = cachePtr->firstObjPtr;				\
	    cachePtr->firstObjPtr = (Tcl_Obj *)(objPtr)->internalRep.twoPtrValue.ptr1; \
	    --cachePtr->numObjects;					\
	}								\
    } while (0)

#  define TclFreeObjStorageEx(interp, objPtr)				\
    do {								\
	AllocCache *cachePtr;						\
	if (((interp) == NULL) ||					\
		((cachePtr = ((Interp *)(interp))->allocCache),		\
			((cachePtr->numObjects == 0) ||			\
			(cachePtr->numObjects >= ALLOC_NOBJHIGH)))) {	\
	    TclThreadFreeObj(objPtr);					\
	} else {							\
	    (objPtr)->internalRep.twoPtrValue.ptr1 = cachePtr->firstObjPtr; \
	    cachePtr->firstObjPtr = objPtr;				\
	    ++cachePtr->numObjects;					\
	}								\
    } while (0)

#else /* not PURIFY or USE_THREAD_ALLOC */

#if defined(USE_TCLALLOC) && USE_TCLALLOC
    MODULE_SCOPE void TclFinalizeAllocSubsystem();
    MODULE_SCOPE void TclInitAlloc();
#else
#   define USE_TCLALLOC 0
#endif

#ifdef TCL_THREADS
/* declared in tclObj.c */
MODULE_SCOPE Tcl_Mutex	tclObjMutex;
#endif

#  define TclAllocObjStorageEx(interp, objPtr) \
    do {								\
	Tcl_MutexLock(&tclObjMutex);					\
	if (tclFreeObjList == NULL) {					\
	    TclAllocateFreeObjects();					\
	}								\
	(objPtr) = tclFreeObjList;					\
	tclFreeObjList = (Tcl_Obj *)					\
		tclFreeObjList->internalRep.twoPtrValue.ptr1;		\
	Tcl_MutexUnlock(&tclObjMutex);					\
    } while (0)

#  define TclFreeObjStorageEx(interp, objPtr) \
    do {							       \
	Tcl_MutexLock(&tclObjMutex);				       \
	(objPtr)->internalRep.twoPtrValue.ptr1 = (void *) tclFreeObjList; \
	tclFreeObjList = (objPtr);				       \
	Tcl_MutexUnlock(&tclObjMutex);				       \
    } while (0)
#endif

#else /* TCL_MEM_DEBUG */
MODULE_SCOPE void	TclDbInitNewObj(Tcl_Obj *objPtr, const char *file,
			    int line);

# define TclDbNewObj(objPtr, file, line) \
    do { \
	TclIncrObjsAllocated();						\
	(objPtr) = (Tcl_Obj *)						\
		Tcl_DbCkalloc(sizeof(Tcl_Obj), (file), (line));		\
	TclDbInitNewObj((objPtr), (file), (line));			\
	TCL_DTRACE_OBJ_CREATE(objPtr);					\
    } while (0)

# define TclNewObj(objPtr) \
    TclDbNewObj(objPtr, __FILE__, __LINE__);

# define TclDecrRefCount(objPtr) \
    Tcl_DbDecrRefCount(objPtr, __FILE__, __LINE__)

# define TclNewListObjDirect(objc, objv) \
    TclDbNewListObjDirect(objc, objv, __FILE__, __LINE__)

#undef USE_THREAD_ALLOC
#endif /* TCL_MEM_DEBUG */

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to set a Tcl_Obj's string representation to a
 * copy of the "len" bytes starting at "bytePtr". This code works even if the
 * byte array contains NULLs as long as the length is correct. Because "len"
 * is referenced multiple times, it should be as simple an expression as
 * possible. The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE void TclInitStringRep(Tcl_Obj *objPtr, char *bytePtr, int len);
 *
 * This macro should only be called on an unshared objPtr where
 *  objPtr->typePtr->freeIntRepProc == NULL
 *----------------------------------------------------------------
 */

#define TclInitStringRep(objPtr, bytePtr, len) \
    if ((len) == 0) { \
	(objPtr)->bytes	 = tclEmptyStringRep; \
	(objPtr)->length = 0; \
    } else { \
	(objPtr)->bytes = (char *) ckalloc((unsigned int)(len) + 1U); \
	memcpy((objPtr)->bytes, (bytePtr), (len)); \
	(objPtr)->bytes[len] = '\0'; \
	(objPtr)->length = (len); \
    }

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to get the string representation's byte array
 * pointer from a Tcl_Obj. This is an inline version of Tcl_GetString(). The
 * macro's expression result is the string rep's byte pointer which might be
 * NULL. The bytes referenced by this pointer must not be modified by the
 * caller. The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE char *	TclGetString(Tcl_Obj *objPtr);
 *----------------------------------------------------------------
 */

#define TclGetString(objPtr) \
    ((objPtr)->bytes? (objPtr)->bytes : Tcl_GetString(objPtr))

#define TclGetStringFromObj(objPtr, lenPtr) \
    ((objPtr)->bytes \
	    ? (*(lenPtr) = (objPtr)->length, (objPtr)->bytes)	\
	    : Tcl_GetStringFromObj((objPtr), (lenPtr)))

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to clean out an object's internal
 * representation. Does not actually reset the rep's bytes. The ANSI C
 * "prototype" for this macro is:
 *
 * MODULE_SCOPE void	TclFreeIntRep(Tcl_Obj *objPtr);
 *----------------------------------------------------------------
 */

#define TclFreeIntRep(objPtr) \
    if ((objPtr)->typePtr != NULL) { \
	if ((objPtr)->typePtr->freeIntRepProc != NULL) { \
	    (objPtr)->typePtr->freeIntRepProc(objPtr); \
	} \
	(objPtr)->typePtr = NULL; \
    }

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to clean out an object's string representation.
 * The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE void	TclInvalidateStringRep(Tcl_Obj *objPtr);
 *----------------------------------------------------------------
 */

#define TclInvalidateStringRep(objPtr) \
    do { \
	Tcl_Obj *_isobjPtr = (Tcl_Obj *)(objPtr); \
	if (_isobjPtr->bytes != NULL) { \
	    if (_isobjPtr->bytes != tclEmptyStringRep) { \
		ckfree((char *)_isobjPtr->bytes); \
	    } \
	    _isobjPtr->bytes = NULL; \
	} \
    } while (0)

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to test whether an object has a
 * string representation (or is a 'pure' internal value).
 * The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE int	TclHasStringRep(Tcl_Obj *objPtr);
 *----------------------------------------------------------------
 */

#define TclHasStringRep(objPtr) \
    ((objPtr)->bytes != NULL)

/*
 *----------------------------------------------------------------
 * Macros used by the Tcl core to grow Tcl_Token arrays. They use the same
 * growth algorithm as used in tclStringObj.c for growing strings. The ANSI C
 * "prototype" for this macro is:
 *
 * MODULE_SCOPE void	TclGrowTokenArray(Tcl_Token *tokenPtr, int used,
 *				int available, int append,
 *				Tcl_Token *staticPtr);
 * MODULE_SCOPE void	TclGrowParseTokenArray(Tcl_Parse *parsePtr,
 *				int append);
 *----------------------------------------------------------------
 */

/* General tuning for minimum growth in Tcl growth algorithms */
#ifndef TCL_MIN_GROWTH
#  ifdef TCL_GROWTH_MIN_ALLOC
     /* Support for any legacy tuners */
#    define TCL_MIN_GROWTH TCL_GROWTH_MIN_ALLOC
#  else
#    define TCL_MIN_GROWTH 1024
#  endif
#endif

/* Token growth tuning, default to the general value. */
#ifndef TCL_MIN_TOKEN_GROWTH
#define TCL_MIN_TOKEN_GROWTH TCL_MIN_GROWTH/sizeof(Tcl_Token)
#endif

#define TCL_MAX_TOKENS (int)(UINT_MAX / sizeof(Tcl_Token))
#define TclGrowTokenArray(tokenPtr, used, available, append, staticPtr)	\
    do {								\
	int _needed = (used) + (append);					\
	if (_needed > TCL_MAX_TOKENS) {					\
	    Tcl_Panic("max # of tokens for a Tcl parse (%d) exceeded",	\
		    TCL_MAX_TOKENS);					\
	}								\
	if (_needed > (available)) {					\
	    int allocated = 2 * _needed;					\
	    Tcl_Token *oldPtr = (tokenPtr);				\
	    Tcl_Token *newPtr;						\
	    if (oldPtr == (staticPtr)) {				\
		oldPtr = NULL;						\
	    }								\
	    if (allocated > TCL_MAX_TOKENS) {				\
		allocated = TCL_MAX_TOKENS;				\
	    }								\
	    newPtr = (Tcl_Token *) attemptckrealloc((char *) oldPtr,	\
		    allocated * sizeof(Tcl_Token));	\
	    if (newPtr == NULL) {					\
		allocated = _needed + (append) + TCL_MIN_TOKEN_GROWTH;	\
		if (allocated > TCL_MAX_TOKENS) {			\
		    allocated = TCL_MAX_TOKENS;				\
		}							\
		newPtr = (Tcl_Token *) ckrealloc((char *) oldPtr,	\
			allocated * sizeof(Tcl_Token)); \
	    }								\
	    (available) = allocated;					\
	    if (oldPtr == NULL) {					\
		memcpy(newPtr, staticPtr,				\
			(used) * sizeof(Tcl_Token));		\
	    }								\
	    (tokenPtr) = newPtr;					\
	}								\
    } while (0)

#define TclGrowParseTokenArray(parsePtr, append)			\
    TclGrowTokenArray((parsePtr)->tokenPtr, (parsePtr)->numTokens,	\
	    (parsePtr)->tokensAvailable, (append),			\
	    (parsePtr)->staticTokens)

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core get a unicode char from a utf string. It checks
 * to see if we have a one-byte utf char before calling the real
 * Tcl_UtfToUniChar, as this will save a lot of time for primarily ASCII
 * string handling. The macro's expression result is 1 for the 1-byte case or
 * the result of Tcl_UtfToUniChar. The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE int	TclUtfToUniChar(const char *string, Tcl_UniChar *ch);
 *----------------------------------------------------------------
 */

#define TclUtfToUniChar(str, chPtr) \
	(((UCHAR(*(str))) < 0x80) ?		\
	    ((*(chPtr) = UCHAR(*(str))), 1)	\
	    : Tcl_UtfToUniChar(str, chPtr))

/*
 *----------------------------------------------------------------
 * Macro counterpart of the Tcl_NumUtfChars() function. To be used in speed-
 * -sensitive points where it pays to avoid a function call in the common case
 * of counting along a string of all one-byte characters.  The ANSI C
 * "prototype" for this macro is:
 *
 * MODULE_SCOPE void	TclNumUtfChars(int numChars, const char *bytes,
 *				int numBytes);
 *----------------------------------------------------------------
 */

#define TclNumUtfChars(numChars, bytes, numBytes) \
    do { \
	int _count, _i = (numBytes); \
	unsigned char *_str = (unsigned char *) (bytes); \
	while (_i && (*_str < 0xC0)) { _i--; _str++; } \
	_count = (numBytes) - _i; \
	if (_i) { \
	    _count += Tcl_NumUtfChars((bytes) + _count, _i); \
	} \
	(numChars) = _count; \
    } while (0);

#define TclUtfPrev(src, start) \
	(((src) < (start)+2) ? (start) : \
	(UCHAR(*((src) - 1))) < 0x80 ? (src)-1 : \
	Tcl_UtfPrev(src, start))

/*
 *----------------------------------------------------------------
 * Macro that encapsulates the logic that determines when it is safe to
 * interpret a string as a byte array directly. In summary, the object must be
 * a byte array and must not have a string representation (as the operations
 * that it is used in are defined on strings, not byte arrays). Theoretically
 * it is possible to also be efficient in the case where the object's bytes
 * field is filled by generation from the byte array (c.f. list canonicality)
 * but we don't do that at the moment since this is purely about efficiency.
 * The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE int	TclIsPureByteArray(Tcl_Obj *objPtr);
 *----------------------------------------------------------------
 */

#define TclIsPureByteArray(objPtr) \
	(((objPtr)->typePtr==&tclByteArrayType) && ((objPtr)->bytes==NULL))
#define TclIsPureDict(objPtr) \
	(((objPtr)->bytes==NULL) && ((objPtr)->typePtr==&tclDictType))

#define TclIsPureList(objPtr) \
	(((objPtr)->bytes==NULL) && ((objPtr)->typePtr==&tclListType))

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to compare Unicode strings. On big-endian
 * systems we can use the more efficient memcmp, but this would not be
 * lexically correct on little-endian systems. The ANSI C "prototype" for
 * this macro is:
 *
 * MODULE_SCOPE int	TclUniCharNcmp(const void *cs,
 *			    const void *ct, size_t n);
 *----------------------------------------------------------------
 */

#if defined(WORDS_BIGENDIAN) && (TCL_UTF_MAX != 4)
#   define TclUniCharNcmp(cs,ct,n) memcmp((cs),(ct),(n)*sizeof(Tcl_UniChar))
#endif /* WORDS_BIGENDIAN */

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to increment a namespace's export epoch
 * counter. The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE void	TclInvalidateNsCmdLookup(Namespace *nsPtr);
 *----------------------------------------------------------------
 */

#define TclInvalidateNsCmdLookup(nsPtr) \
    if ((nsPtr)->numExportPatterns) {		\
	(nsPtr)->exportLookupEpoch++;		\
    }						\
    if ((nsPtr)->commandPathLength) {		\
	(nsPtr)->cmdRefEpoch++;			\
    }

/*
 *----------------------------------------------------------------------
 *
 * Core procedure added to libtommath for bignum manipulation.
 *
 *----------------------------------------------------------------------
 */

MODULE_SCOPE Tcl_PackageInitProc TclTommath_Init;

/*
 *----------------------------------------------------------------------
 *
 * External (platform specific) initialization routine, these declarations
 * explicitly don't use EXTERN since this code does not get compiled into the
 * library:
 *
 *----------------------------------------------------------------------
 */

MODULE_SCOPE Tcl_PackageInitProc TclplatformtestInit;
MODULE_SCOPE Tcl_PackageInitProc TclObjTest_Init;
MODULE_SCOPE Tcl_PackageInitProc TclThread_Init;
MODULE_SCOPE Tcl_PackageInitProc Procbodytest_Init;
MODULE_SCOPE Tcl_PackageInitProc Procbodytest_SafeInit;

/*
 *----------------------------------------------------------------
 * Macro used by the Tcl core to check whether a pattern has any characters
 * special to [string match]. The ANSI C "prototype" for this macro is:
 *
 * MODULE_SCOPE int	TclMatchIsTrivial(const char *pattern);
 *----------------------------------------------------------------
 */

#define TclMatchIsTrivial(pattern) \
    (strpbrk((pattern), "*[?\\") == NULL)

/*
 *----------------------------------------------------------------
 * Macros used by the Tcl core to set a Tcl_Obj's numeric representation
 * avoiding the corresponding function calls in time critical parts of the
 * core. They should only be called on unshared objects. The ANSI C
 * "prototypes" for these macros are:
 *
 * MODULE_SCOPE void	TclSetIntObj(Tcl_Obj *objPtr, int intValue);
 * MODULE_SCOPE void	TclSetLongObj(Tcl_Obj *objPtr, long longValue);
 * MODULE_SCOPE void	TclSetBooleanObj(Tcl_Obj *objPtr, int intValue);
 * MODULE_SCOPE void	TclSetWideIntObj(Tcl_Obj *objPtr, Tcl_WideInt w);
 * MODULE_SCOPE void	TclSetDoubleObj(Tcl_Obj *objPtr, double d);
 *----------------------------------------------------------------
 */

#define TclSetLongObj(objPtr, i) \
    do {						\
	TclInvalidateStringRep(objPtr);			\
	TclFreeIntRep(objPtr);				\
	(objPtr)->internalRep.longValue = (long)(i);	\
	(objPtr)->typePtr = &tclIntType;		\
    } while (0)

#define TclSetIntObj(objPtr, l) \
    TclSetLongObj(objPtr, l)

/*
 * NOTE: There is to be no such thing as a "pure" boolean. Boolean values set
 * programmatically go straight to being "int" Tcl_Obj's, with value 0 or 1.
 * The only "boolean" Tcl_Obj's shall be those holding the cached boolean
 * value of strings like: "yes", "no", "true", "false", "on", "off".
 */

#define TclSetBooleanObj(objPtr, b) \
    TclSetLongObj(objPtr, (b)!=0);

#ifndef TCL_WIDE_INT_IS_LONG
#define TclSetWideIntObj(objPtr, w) \
    do {							\
	TclInvalidateStringRep(objPtr);				\
	TclFreeIntRep(objPtr);					\
	(objPtr)->internalRep.wideValue = (Tcl_WideInt)(w);	\
	(objPtr)->typePtr = &tclWideIntType;			\
    } while (0)
#endif

#define TclSetDoubleObj(objPtr, d) \
    do {							\
	TclInvalidateStringRep(objPtr);				\
	TclFreeIntRep(objPtr);					\
	(objPtr)->internalRep.doubleValue = (double)(d);	\
	(objPtr)->typePtr = &tclDoubleType;			\
    } while (0)

/*
 *----------------------------------------------------------------
 * Macros used by the Tcl core to create and initialise objects of standard
 * types, avoiding the corresponding function calls in time critical parts of
 * the core. The ANSI C "prototypes" for these macros are:
 *
 * MODULE_SCOPE void	TclNewIntObj(Tcl_Obj *objPtr, int i);
 * MODULE_SCOPE void	TclNewLongObj(Tcl_Obj *objPtr, long l);
 * MODULE_SCOPE void	TclNewBooleanObj(Tcl_Obj *objPtr, int b);
 * MODULE_SCOPE void	TclNewWideObj(Tcl_Obj *objPtr, Tcl_WideInt w);
 * MODULE_SCOPE void	TclNewDoubleObj(Tcl_Obj *objPtr, double d);
 * MODULE_SCOPE void	TclNewStringObj(Tcl_Obj *objPtr, char *s, int len);
 * MODULE_SCOPE void	TclNewLiteralStringObj(Tcl_Obj*objPtr, char*sLiteral);
 *
 *----------------------------------------------------------------
 */

#ifndef TCL_MEM_DEBUG
#define TclNewLongObj(objPtr, i) \
    do {						\
	TclIncrObjsAllocated();				\
	TclAllocObjStorage(objPtr);			\
	(objPtr)->refCount = 0;				\
	(objPtr)->bytes = NULL;				\
	(objPtr)->internalRep.longValue = (long)(i);	\
	(objPtr)->typePtr = &tclIntType;		\
	TCL_DTRACE_OBJ_CREATE(objPtr);			\
    } while (0)

#define TclNewIntObj(objPtr, l) \
    TclNewLongObj(objPtr, l)

/*
 * NOTE: There is to be no such thing as a "pure" boolean.
 * See comment above TclSetBooleanObj macro above.
 */
#define TclNewBooleanObj(objPtr, b) \
    TclNewLongObj((objPtr), (b)!=0)

#define TclNewDoubleObj(objPtr, d) \
    do {							\
	TclIncrObjsAllocated();					\
	TclAllocObjStorage(objPtr);				\
	(objPtr)->refCount = 0;					\
	(objPtr)->bytes = NULL;					\
	(objPtr)->internalRep.doubleValue = (double)(d);	\
	(objPtr)->typePtr = &tclDoubleType;			\
	TCL_DTRACE_OBJ_CREATE(objPtr);				\
    } while (0)

#define TclNewStringObj(objPtr, s, len) \
    do {							\
	TclIncrObjsAllocated();					\
	TclAllocObjStorage(objPtr);				\
	(objPtr)->refCount = 0;					\
	TclInitStringRep((objPtr), (s), (len));			\
	(objPtr)->typePtr = NULL;				\
	TCL_DTRACE_OBJ_CREATE(objPtr);				\
    } while (0)

#else /* TCL_MEM_DEBUG */
#define TclNewIntObj(objPtr, i) \
    (objPtr) = Tcl_NewIntObj(i)

#define TclNewLongObj(objPtr, l) \
    (objPtr) = Tcl_NewLongObj(l)

#define TclNewBooleanObj(objPtr, b) \
    (objPtr) = Tcl_NewBooleanObj(b)

#define TclNewDoubleObj(objPtr, d) \
    (objPtr) = Tcl_NewDoubleObj(d)

#define TclNewStringObj(objPtr, s, len) \
    (objPtr) = Tcl_NewStringObj((s), (len))
#endif /* TCL_MEM_DEBUG */

/*
 * The sLiteral argument *must* be a string literal; the incantation with
 * sizeof(sLiteral "") will fail to compile otherwise.
 */
#define TclNewLiteralStringObj(objPtr, sLiteral) \
    TclNewStringObj((objPtr), (sLiteral), sizeof(sLiteral "") - 1)

/*
 *----------------------------------------------------------------
 * Convenience macros for DStrings.
 * The ANSI C "prototypes" for these macros are:
 *
 * MODULE_SCOPE char * TclDStringAppendLiteral(Tcl_DString *dsPtr,
 *			const char *sLiteral);
 * MODULE_SCOPE void   TclDStringClear(Tcl_DString *dsPtr);
 */

#define TclDStringAppendLiteral(dsPtr, sLiteral) \
    Tcl_DStringAppend((dsPtr), (sLiteral), sizeof(sLiteral "") - 1)
#define TclDStringClear(dsPtr) \
    Tcl_DStringSetLength((dsPtr), 0)

/*
 *----------------------------------------------------------------
 * Macros used by the Tcl core to test for some special double values.
 * The ANSI C "prototypes" for these macros are:
 *
 * MODULE_SCOPE int	TclIsInfinite(double d);
 * MODULE_SCOPE int	TclIsNaN(double d);
 */

#ifdef _MSC_VER
#    define TclIsInfinite(d)	(!(_finite((d))))
#    define TclIsNaN(d)		(_isnan((d)))
#else
#    define TclIsInfinite(d)	((d) > DBL_MAX || (d) < -DBL_MAX)
#    ifdef NO_ISNAN
#	 define TclIsNaN(d)	((d) != (d))
#    else
#	 define TclIsNaN(d)	(isnan(d))
#    endif
#endif

/*
 * ----------------------------------------------------------------------
 * Macro to use to find the offset of a field in a structure. Computes number
 * of bytes from beginning of structure to a given field.
 */

#ifdef offsetof
#define TclOffset(type, field) ((int) offsetof(type, field))
#else
#define TclOffset(type, field) ((int) ((char *) &((type *) 0)->field))
#endif

/*
 *----------------------------------------------------------------
 * Inline version of Tcl_GetCurrentNamespace and Tcl_GetGlobalNamespace.
 */

#define TclGetCurrentNamespace(interp) \
    (Tcl_Namespace *) ((Interp *)(interp))->varFramePtr->nsPtr

#define TclGetGlobalNamespace(interp) \
    (Tcl_Namespace *) ((Interp *)(interp))->globalNsPtr

/*
 *----------------------------------------------------------------
 * Inline version of TclCleanupCommand; still need the function as it is in
 * the internal stubs, but the core can use the macro instead.
 */

#define TclCleanupCommandMacro(cmdPtr)		\
    do {					\
	if ((cmdPtr)->refCount-- <= 1) {	\
	    ckfree(cmdPtr);			\
	}					\
    } while (0)

/*
 *----------------------------------------------------------------
 * Inline versions of Tcl_LimitReady() and Tcl_LimitExceeded to limit number
 * of calls out of the critical path. Note that this code isn't particularly
 * readable; the non-inline version (in tclInterp.c) is much easier to
 * understand. Note also that these macros takes different args (iPtr->limit)
 * to the non-inline version.
 */

#define TclLimitExceeded(limit) ((limit).exceeded != 0)

#define TclLimitReady(limit)						\
    (((limit).active == 0) ? 0 :					\
    (++(limit).granularityTicker,					\
    ((((limit).active & TCL_LIMIT_COMMANDS) &&				\
	    (((limit).cmdGranularity == 1) ||				\
	    ((limit).granularityTicker % (limit).cmdGranularity == 0)))	\
	    ? 1 :							\
    (((limit).active & TCL_LIMIT_TIME) &&				\
	    (((limit).timeGranularity == 1) ||				\
	    ((limit).granularityTicker % (limit).timeGranularity == 0)))\
	    ? 1 : 0)))

/*
 * Compile-time assertions: these produce a compile time error if the
 * expression is not known to be true at compile time. If the assertion is
 * known to be false, the compiler (or optimizer?) will error out with
 * "division by zero". If the assertion cannot be evaluated at compile time,
 * the compiler will error out with "non-static initializer".
 *
 * Adapted with permission from
 * http://www.pixelbeat.org/programming/gcc/static_assert.html
 */

#define TCL_CT_ASSERT(e) \
    {enum { ct_assert_value = 1/(!!(e)) };}

/*
 *----------------------------------------------------------------
 * Allocator for small structs (<=sizeof(Tcl_Obj)) using the Tcl_Obj pool.
 * Only checked at compile time.
 *
 * ONLY USE FOR CONSTANT nBytes.
 *
 * DO NOT LET THEM CROSS THREAD BOUNDARIES
 *----------------------------------------------------------------
 */

#define TclSmallAlloc(nbytes, memPtr) \
    TclSmallAllocEx(NULL, (nbytes), (memPtr))

#define TclSmallFree(memPtr) \
    TclSmallFreeEx(NULL, (memPtr))

#ifndef TCL_MEM_DEBUG
#define TclSmallAllocEx(interp, nbytes, memPtr) \
    do {								\
	Tcl_Obj *_objPtr;						\
	TCL_CT_ASSERT((nbytes)<=sizeof(Tcl_Obj));			\
	TclIncrObjsAllocated();						\
	TclAllocObjStorageEx((interp), (_objPtr));			\
	*(void **)&(memPtr) = (void *) (_objPtr);			\
    } while (0)

#define TclSmallFreeEx(interp, memPtr) \
    do {								\
	TclFreeObjStorageEx((interp), (Tcl_Obj *)(memPtr));		\
	TclIncrObjsFreed();						\
    } while (0)

#else    /* TCL_MEM_DEBUG */
#define TclSmallAllocEx(interp, nbytes, memPtr) \
    do {								\
	Tcl_Obj *_objPtr;						\
	TCL_CT_ASSERT((nbytes)<=sizeof(Tcl_Obj));			\
	TclNewObj(_objPtr);						\
	*(void **)&(memPtr) = (void *)_objPtr;				\
    } while (0)

#define TclSmallFreeEx(interp, memPtr) \
    do {								\
	Tcl_Obj *_objPtr = (Tcl_Obj *)(memPtr);				\
	_objPtr->bytes = NULL;						\
	_objPtr->typePtr = NULL;					\
	_objPtr->refCount = 1;						\
	TclDecrRefCount(_objPtr);					\
    } while (0)
#endif   /* TCL_MEM_DEBUG */

/*
 * Support for Clang Static Analyzer <http://clang-analyzer.llvm.org>
 */

#if defined(PURIFY) && defined(__clang__)
#if __has_feature(attribute_analyzer_noreturn) && \
	!defined(Tcl_Panic) && defined(Tcl_Panic_TCL_DECLARED)
void Tcl_Panic(const char *, ...) __attribute__((analyzer_noreturn));
#endif
#if !defined(CLANG_ASSERT)
#include <assert.h>
#define CLANG_ASSERT(x) assert(x)
#endif
#elif !defined(CLANG_ASSERT)
#define CLANG_ASSERT(x)
#endif /* PURIFY && __clang__ */

/*
 *----------------------------------------------------------------
 * Parameters, structs and macros for the non-recursive engine (NRE)
 *----------------------------------------------------------------
 */

#define NRE_USE_SMALL_ALLOC	1  /* Only turn off for debugging purposes. */
#ifndef NRE_ENABLE_ASSERTS
#define NRE_ENABLE_ASSERTS	0
#endif

/*
 * This is the main data struct for representing NR commands. It is designed
 * to fit in sizeof(Tcl_Obj) in order to exploit the fastest memory allocator
 * available.
 */

typedef struct NRE_callback {
    Tcl_NRPostProc *procPtr;
    ClientData data[4];
    struct NRE_callback *nextPtr;
} NRE_callback;

#define TOP_CB(iPtr) (((Interp *)(iPtr))->execEnvPtr->callbackPtr)

/*
 * Inline version of Tcl_NRAddCallback.
 */

#define TclNRAddCallback(interp,postProcPtr,data0,data1,data2,data3) \
    do {								\
	NRE_callback *_callbackPtr;					\
	TCLNR_ALLOC((interp), (_callbackPtr));				\
	_callbackPtr->procPtr = (postProcPtr);				\
	_callbackPtr->data[0] = (ClientData)(data0);			\
	_callbackPtr->data[1] = (ClientData)(data1);			\
	_callbackPtr->data[2] = (ClientData)(data2);			\
	_callbackPtr->data[3] = (ClientData)(data3);			\
	_callbackPtr->nextPtr = TOP_CB(interp);				\
	TOP_CB(interp) = _callbackPtr;					\
    } while (0)

#if NRE_USE_SMALL_ALLOC
#define TCLNR_ALLOC(interp, ptr) \
    TclSmallAllocEx(interp, sizeof(NRE_callback), (ptr))
#define TCLNR_FREE(interp, ptr)  TclSmallFreeEx((interp), (ptr))
#else
#define TCLNR_ALLOC(interp, ptr) \
    ((ptr) = (void *)ckalloc(sizeof(NRE_callback)))
#define TCLNR_FREE(interp, ptr)  ckfree((char *) (ptr))
#endif

#if NRE_ENABLE_ASSERTS
#define NRE_ASSERT(expr) assert((expr))
#else
#define NRE_ASSERT(expr)
#endif

#include "tclIntDecls.h"
#include "tclIntPlatDecls.h"
#include "tclTomMathDecls.h"

#if !defined(USE_TCL_STUBS) && !defined(TCL_MEM_DEBUG)
#define Tcl_AttemptAlloc        TclpAlloc
#define Tcl_AttemptRealloc      TclpRealloc
#define Tcl_Free                TclpFree
#endif

/*
 * Special hack for macOS, where the static linker (technically the 'ar'
 * command) hates empty object files, and accepts no flags to make it shut up.
 *
 * These symbols are otherwise completely useless.
 *
 * They can't be written to or written through. They can't be seen by any
 * other code. They use a separate attribute (supported by all macOS
 * compilers, which are derivatives of clang or gcc) to stop the compilation
 * from moaning. They will be excluded during the final linking stage.
 *
 * Other platforms get nothing at all. That's good.
 */

#ifdef MAC_OSX_TCL
#define TCL_MAC_EMPTY_FILE(name) \
    static __attribute__((used)) const void *const TclUnusedFile_ ## name = NULL;
#else
#define TCL_MAC_EMPTY_FILE(name)
#endif /* MAC_OSX_TCL */

/*
 * Other externals.
 */

MODULE_SCOPE size_t TclEnvEpoch;	/* Epoch of the tcl environment
					 * (if changed with tcl-env). */

#endif /* _TCLINT */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
