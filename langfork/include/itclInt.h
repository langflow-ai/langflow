/*
 * itclInt.h --
 *
 * This file contains internal definitions for the C-implemented part of a
 * Itcl
 *
 * Copyright (c) 2007 by Arnulf P. Wiedemann
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif
#ifdef HAVE_STDINT_H
#include <stdint.h>
#endif
#include <stddef.h>

/*
 * Used to tag functions that are only to be visible within the module being
 * built and not outside it (where this is supported by the linker).
 */

#ifndef MODULE_SCOPE
#   ifdef __cplusplus
#       define MODULE_SCOPE extern "C"
#   else
#       define MODULE_SCOPE extern
#   endif
#endif

#include <string.h>
#include <ctype.h>
#include <tclOO.h>
#include "itcl.h"
#include "itclMigrate2TclCore.h"
#include "itclTclIntStubsFcn.h"

/*
 * Utility macros: STRINGIFY takes an argument and wraps it in "" (double
 * quotation marks).
 */

#ifndef STRINGIFY
#  define STRINGIFY(x) STRINGIFY1(x)
#  define STRINGIFY1(x) #x
#endif

/*
 * MSVC 8.0 started to mark many standard C library functions depreciated
 * including the *printf family and others. Tell it to shut up.
 * (_MSC_VER is 1200 for VC6, 1300 or 1310 for vc7.net, 1400 for 8.0)
 */
#if defined(_MSC_VER)
#   pragma warning(disable:4244)
#   if _MSC_VER >= 1400
#	pragma warning(disable:4267)
#	pragma warning(disable:4996)
#   endif
#endif

#ifndef TCL_INDEX_NONE
# define TCL_INDEX_NONE	(-1)
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

#if TCL_MAJOR_VERSION == 8
#   define ITCL_Z_MODIFIER ""
#else
#   define ITCL_Z_MODIFIER TCL_Z_MODIFIER
#endif

/*
 * Since the Tcl/Tk distribution doesn't perform any asserts,
 * dynamic loading can fail to find the __assert function.
 * As a workaround, we'll include our own.
 */

#undef  assert
#if defined(NDEBUG) && !defined(DEBUG)
#define assert(EX) ((void)0)
#else /* !NDEBUG || DEBUG */
#define assert(EX) (void)((EX) || (Itcl_Assert(STRINGIFY(EX), __FILE__, __LINE__), 0))
#endif

#define ITCL_INTERP_DATA "itcl_data"
#define ITCL_TK_VERSION "8.6"

/*
 * Convenience macros for iterating through hash tables. FOREACH_HASH_DECLS
 * sets up the declarations needed for the main macro, FOREACH_HASH, which
 * does the actual iteration. FOREACH_HASH_VALUE is a restricted version that
 * only iterates over values.
 */

#define FOREACH_HASH_DECLS \
    Tcl_HashEntry *hPtr;Tcl_HashSearch search
#define FOREACH_HASH(key,val,tablePtr) \
    for(hPtr=Tcl_FirstHashEntry((tablePtr),&search); hPtr!=NULL ? \
	    (*(void **)&(key)=Tcl_GetHashKey((tablePtr),hPtr),\
	    *(void **)&(val)=Tcl_GetHashValue(hPtr),1):0; hPtr=Tcl_NextHashEntry(&search))
#define FOREACH_HASH_VALUE(val,tablePtr) \
    for(hPtr=Tcl_FirstHashEntry((tablePtr),&search); hPtr!=NULL ? \
	    (*(void **)&(val)=Tcl_GetHashValue(hPtr),1):0;hPtr=Tcl_NextHashEntry(&search))

/*
 * What sort of size of things we like to allocate.
 */

#define ALLOC_CHUNK 8

#define ITCL_INT_NAMESPACE	    ITCL_NAMESPACE"::internal"
#define ITCL_INTDICTS_NAMESPACE	    ITCL_INT_NAMESPACE"::dicts"
#define ITCL_VARIABLES_NAMESPACE    ITCL_INT_NAMESPACE"::variables"
#define ITCL_COMMANDS_NAMESPACE	    ITCL_INT_NAMESPACE"::commands"

typedef struct ItclFoundation {
    Itcl_Stack methodCallStack;
    Tcl_Command dispatchCommand;
} ItclFoundation;

typedef struct ItclArgList {
    struct ItclArgList *nextPtr;        /* pointer to next argument */
    Tcl_Obj *namePtr;           /* name of the argument */
    Tcl_Obj *defaultValuePtr;   /* default value or NULL if none */
} ItclArgList;

/*
 *  Common info for managing all known objects.
 *  Each interpreter has one of these data structures stored as
 *  clientData in the "itcl" namespace.  It is also accessible
 *  as associated data via the key ITCL_INTERP_DATA.
 */
struct ItclClass;
struct ItclObject;
struct ItclMemberFunc;
struct EnsembleInfo;
struct ItclDelegatedOption;
struct ItclDelegatedFunction;

typedef struct ItclObjectInfo {
    Tcl_Interp *interp;             /* interpreter that manages this info */
    Tcl_HashTable objects;          /* list of all known objects key is
                                     * ioPtr */
    Tcl_HashTable objectCmds;       /* list of known objects using accessCmd */
    Tcl_HashTable unused5;          /* list of known objects using namePtr */
    Tcl_HashTable classes;          /* list of all known classes,
                                     * key is iclsPtr */
    Tcl_HashTable nameClasses;      /* maps from fullNamePtr to iclsPtr */
    Tcl_HashTable namespaceClasses; /* maps from nsPtr to iclsPtr */
    Tcl_HashTable procMethods;      /* maps from procPtr to mFunc */
    Tcl_HashTable instances;        /* maps from instanceNumber to ioPtr */
    Tcl_HashTable unused8;          /* maps from ioPtr to instanceNumber */
    Tcl_HashTable frameContext;     /* maps frame to context stack */
    Tcl_HashTable classTypes;       /* maps from class type i.e. "widget"
                                     * to define value i.e. ITCL_WIDGET */
    int protection;                 /* protection level currently in effect */
    int useOldResolvers;            /* whether to use the "old" style
                                     * resolvers or the CallFrame resolvers */
    Itcl_Stack clsStack;            /* stack of class definitions currently
                                     * being parsed */
    Itcl_Stack unused;              /* Removed */
    Itcl_Stack unused6;		    /* obsolete field */
    struct ItclObject *currIoPtr;   /* object currently being constructed
                                     * set only during calling of constructors
				     * otherwise NULL */
    Tcl_ObjectMetadataType *class_meta_type;
                                    /* type for getting the Itcl class info
                                     * from a TclOO Tcl_Object */
    const Tcl_ObjectMetadataType *object_meta_type;
                                    /* type for getting the Itcl object info
                                     * from a TclOO Tcl_Object */
    Tcl_Object clazzObjectPtr;      /* the root object of Itcl */
    Tcl_Class clazzClassPtr;        /* the root class of Itcl */
    struct EnsembleInfo *ensembleInfo;
    struct ItclClass *currContextIclsPtr;
                                    /* context class for delegated option
                                     * handling */
    int currClassFlags;             /* flags for the class just in creation */
    int buildingWidget;             /* set if in construction of a widget */
    Tcl_Size unparsedObjc;         /* number options not parsed by
                                       ItclExtendedConfigure/-Cget function */
    Tcl_Obj **unparsedObjv;         /* options not parsed by
                                       ItclExtendedConfigure/-Cget function */
    int functionFlags;              /* used for creating of ItclMemberCode */
    int unused7;
    struct ItclDelegatedOption *currIdoPtr;
                                    /* the current delegated option info */
    int inOptionHandling;           /* used to indicate for type/widget ...
                                     * that there is an option processing
				     * and methods are allowed to be called */
            /* these are the Tcl_Obj Ptrs for the clazz unknown procedure */
	    /* need to store them to be able to free them at the end */
    int itclWidgetInitted;          /* set to 1 if itclWidget.tcl has already
                                     * been called
				     */
    int itclHullCmdsInitted;        /* set to 1 if itclHullCmds.tcl has already
                                     * been called
				     */
    Tcl_Obj *unused2;
    Tcl_Obj *unused3;
    Tcl_Obj *unused4;
    Tcl_Obj *infoVarsPtr;
    Tcl_Obj *unused9;
    Tcl_Obj *infoVars4Ptr;
    Tcl_Obj *typeDestructorArgumentPtr;
    struct ItclObject *lastIoPtr;   /* last object constructed */
    Tcl_Command infoCmd;
} ItclObjectInfo;

typedef struct EnsembleInfo {
    Tcl_HashTable ensembles;        /* list of all known ensembles */
    Tcl_HashTable subEnsembles;     /* list of all known subensembles */
    Tcl_Size numEnsembles;
    Tcl_Namespace *ensembleNsPtr;
} EnsembleInfo;
/*
 *  Representation for each [incr Tcl] class.
 */
#define ITCL_CLASS		              0x1
#define ITCL_TYPE		              0x2
#define ITCL_WIDGET		              0x4
#define ITCL_WIDGETADAPTOR	              0x8
#define ITCL_ECLASS		             0x10
#define ITCL_NWIDGET		             0x20
#define ITCL_WIDGET_FRAME	             0x40
#define ITCL_WIDGET_LABEL_FRAME	             0x80
#define ITCL_WIDGET_TOPLEVEL	            0x100
#define ITCL_WIDGET_TTK_FRAME               0x200
#define ITCL_WIDGET_TTK_LABEL_FRAME	    0x400
#define ITCL_WIDGET_TTK_TOPLEVEL            0x800
#define ITCL_CLASS_IS_DELETED              0x1000
#define ITCL_CLASS_IS_DESTROYED            0x2000
#define ITCL_CLASS_NS_IS_DESTROYED         0x4000
#define ITCL_CLASS_IS_RENAMED              0x8000 /* unused */
#define ITCL_CLASS_IS_FREED               0x10000
#define ITCL_CLASS_DERIVED_RELEASED       0x20000
#define ITCL_CLASS_NS_TEARDOWN            0x40000
#define ITCL_CLASS_NO_VARNS_DELETE        0x80000
#define ITCL_CLASS_SHOULD_VARNS_DELETE   0x100000
#define ITCL_CLASS_DESTRUCTOR_CALLED     0x400000


typedef struct ItclClass {
    Tcl_Obj *namePtr;             /* class name */
    Tcl_Obj *fullNamePtr;         /* fully qualified class name */
    Tcl_Interp *interp;           /* interpreter that manages this info */
    Tcl_Namespace *nsPtr;         /* namespace representing class scope */
    Tcl_Command accessCmd;        /* access command for creating instances */
    Tcl_Command thisCmd;          /* needed for deletion of class */

    struct ItclObjectInfo *infoPtr;
                                  /* info about all known objects
				   * and other stuff like stacks */
    Itcl_List bases;              /* list of base classes */
    Itcl_List derived;            /* list of all derived classes */
    Tcl_HashTable heritage;       /* table of all base classes.  Look up
                                   * by pointer to class definition.  This
                                   * provides fast lookup for inheritance
                                   * tests. */
    Tcl_Obj *initCode;            /* initialization code for new objs */
    Tcl_HashTable variables;      /* definitions for all data members
                                     in this class.  Look up simple string
                                     names and get back ItclVariable* ptrs */
    Tcl_HashTable options;        /* definitions for all option members
                                     in this class.  Look up simple string
                                     names and get back ItclOption* ptrs */
    Tcl_HashTable components;     /* definitions for all component members
                                     in this class.  Look up simple string
                                     names and get back ItclComponent* ptrs */
    Tcl_HashTable functions;      /* definitions for all member functions
                                     in this class.  Look up simple string
                                     names and get back ItclMemberFunc* ptrs */
    Tcl_HashTable delegatedOptions; /* definitions for all delegated options
                                     in this class.  Look up simple string
                                     names and get back
				     ItclDelegatedOption * ptrs */
    Tcl_HashTable delegatedFunctions; /* definitions for all delegated methods
                                     or procs in this class.  Look up simple
				     string names and get back
				     ItclDelegatedFunction * ptrs */
    Tcl_HashTable methodVariables; /* definitions for all methodvariable members
                                     in this class.  Look up simple string
                                     names and get back
				     ItclMethodVariable* ptrs */
    Tcl_Size numInstanceVars;    /* number of instance vars in variables
                                     table */
    Tcl_HashTable classCommons;   /* used for storing variable namespace
                                   * string for Tcl_Resolve */
    Tcl_HashTable resolveVars;    /* all possible names for variables in
                                   * this class (e.g., x, foo::x, etc.) */
    Tcl_HashTable resolveCmds;    /* all possible names for functions in
                                   * this class (e.g., x, foo::x, etc.) */
    Tcl_HashTable contextCache;   /* cache for function contexts */
    struct ItclMemberFunc *unused2;
                                  /* the class constructor or NULL */
    struct ItclMemberFunc *unused3;
                                  /* the class destructor or NULL */
    struct ItclMemberFunc *unused1;
    Tcl_Resolve *resolvePtr;
    Tcl_Obj *widgetClassPtr;      /* class name for widget if class is a
                                   * ::itcl::widget */
    Tcl_Obj *hullTypePtr;         /* hulltype name for widget if class is a
                                   * ::itcl::widget */
    Tcl_Object oPtr;		  /* TclOO class object */
    Tcl_Class  clsPtr;            /* TclOO class */
    Tcl_Size numCommons;         /* number of commons in this class */
    Tcl_Size numVariables;       /* number of variables in this class */
    Tcl_Size numOptions;         /* number of options in this class */
    Tcl_Size unique;             /* unique number for #auto generation */
    int flags;                    /* maintains class status */
    Tcl_Size callRefCount;       /* prevent deleting of class if refcount>1 */
    Tcl_Obj *typeConstructorPtr;  /* initialization for types */
    int destructorHasBeenCalled;  /* prevent multiple invocations of destrcutor */
    Tcl_Size refCount;
} ItclClass;

typedef struct ItclHierIter {
    ItclClass *current;           /* current position in hierarchy */
    Itcl_Stack stack;             /* stack used for traversal */
} ItclHierIter;

#define ITCL_OBJECT_IS_DELETED           0x01
#define ITCL_OBJECT_IS_DESTRUCTED        0x02
#define ITCL_OBJECT_IS_DESTROYED         0x04
#define ITCL_OBJECT_IS_RENAMED           0x08
#define ITCL_OBJECT_CLASS_DESTRUCTED     0x10
#define ITCL_TCLOO_OBJECT_IS_DELETED     0x20
#define ITCL_OBJECT_DESTRUCT_ERROR       0x40
#define ITCL_OBJECT_SHOULD_VARNS_DELETE  0x80
#define ITCL_OBJECT_ROOT_METHOD          0x8000

/*
 *  Representation for each [incr Tcl] object.
 */
typedef struct ItclObject {
    ItclClass *iclsPtr;          /* most-specific class */
    Tcl_Command accessCmd;       /* object access command */

    Tcl_HashTable *constructed;  /* temp storage used during construction */
    Tcl_HashTable *destructed;   /* temp storage used during destruction */
    Tcl_HashTable objectVariables;
                                 /* used for storing Tcl_Var entries for
				  * variable resolving, key is ivPtr of
				  * variable, value is varPtr */
    Tcl_HashTable objectOptions; /* definitions for all option members
                                     in this object. Look up option namePtr
                                     names and get back ItclOption* ptrs */
    Tcl_HashTable objectComponents; /* definitions for all component members
                                     in this object. Look up component namePtr
                                     names and get back ItclComponent* ptrs */
    Tcl_HashTable objectMethodVariables;
                                 /* definitions for all methodvariable members
                                     in this object. Look up methodvariable
				     namePtr names and get back
				     ItclMethodVariable* ptrs */
    Tcl_HashTable objectDelegatedOptions;
                                  /* definitions for all delegated option
				     members in this object. Look up option
				     namePtr names and get back
				     ItclOption* ptrs */
    Tcl_HashTable objectDelegatedFunctions;
                                  /* definitions for all delegated function
				     members in this object. Look up function
				     namePtr names and get back
				     ItclMemberFunc * ptrs */
    Tcl_HashTable contextCache;   /* cache for function contexts */
    Tcl_Obj *namePtr;
    Tcl_Obj *origNamePtr;         /* the original name before any rename */
    Tcl_Obj *createNamePtr;       /* the temp name before any rename
                                   * mostly used for widgetadaptor
				   * because that hijackes the name
				   * often when installing the hull */
    Tcl_Interp *interp;
    ItclObjectInfo *infoPtr;
    Tcl_Obj *varNsNamePtr;
    Tcl_Object oPtr;             /* the TclOO object */
    Tcl_Resolve *resolvePtr;
    int flags;
    Tcl_Size callRefCount;       /* prevent deleting of object if refcount > 1 */
    Tcl_Obj *hullWindowNamePtr;   /* the window path name for the hull
                                   * (before renaming in installhull) */
    int destructorHasBeenCalled;  /* is set when the destructor is called
                                   * to avoid callin destructor twice */
    int noComponentTrace;         /* don't call component traces if
                                   * setting components in DelegationInstall */
    int hadConstructorError;      /* needed for multiple calls of CallItclObjectCmd */
} ItclObject;

#define ITCL_IGNORE_ERRS  0x002  /* useful for construction/destruction */

typedef struct ItclResolveInfo {
    int flags;
    ItclClass *iclsPtr;
    ItclObject *ioPtr;
} ItclResolveInfo;

#define ITCL_RESOLVE_CLASS		0x01
#define ITCL_RESOLVE_OBJECT		0x02

/*
 *  Implementation for any code body in an [incr Tcl] class.
 */
typedef struct ItclMemberCode {
    int flags;                  /* flags describing implementation */
    Tcl_Size argcount;         /* number of args in arglist */
    Tcl_Size maxargcount;      /* max number of args in arglist */
    Tcl_Obj *usagePtr;          /* usage string for error messages */
    Tcl_Obj *argumentPtr;       /* the function arguments */
    Tcl_Obj *bodyPtr;           /* the function body */
    ItclArgList *argListPtr;    /* the parsed arguments */
    union {
        Tcl_CmdProc *argCmd;    /* (argc,argv) C implementation */
        Tcl_ObjCmdProc *objCmd; /* (objc,objv) C implementation */
    } cfunc;
    void *clientData;           /* client data for C implementations */
} ItclMemberCode;

/*
 *  Flag bits for ItclMemberCode:
 */
#define ITCL_IMPLEMENT_NONE    0x001  /* no implementation */
#define ITCL_IMPLEMENT_TCL     0x002  /* Tcl implementation */
#define ITCL_IMPLEMENT_ARGCMD  0x004  /* (argc,argv) C implementation */
#define ITCL_IMPLEMENT_OBJCMD  0x008  /* (objc,objv) C implementation */
#define ITCL_IMPLEMENT_C       0x00c  /* either kind of C implementation */

#define Itcl_IsMemberCodeImplemented(mcode) \
    (((mcode)->flags & ITCL_IMPLEMENT_NONE) == 0)

/*
 *  Flag bits for ItclMember: functions and variables
 */
#define ITCL_COMMON            0x010  /* non-zero => is a "proc" or common
                                       * variable */

/*
 *  Flag bits for ItclMember: functions
 */
#define ITCL_CONSTRUCTOR       0x020  /* non-zero => is a constructor */
#define ITCL_DESTRUCTOR        0x040  /* non-zero => is a destructor */
#define ITCL_ARG_SPEC          0x080  /* non-zero => has an argument spec */
#define ITCL_BODY_SPEC         0x100  /* non-zero => has an body spec */
#define ITCL_BUILTIN           0x400  /* non-zero => built-in method */
#define ITCL_COMPONENT         0x800  /* non-zero => component */
#define ITCL_TYPE_METHOD       0x1000 /* non-zero => typemethod */
#define ITCL_METHOD            0x2000 /* non-zero => method */

/*
 *  Flag bits for ItclMember: variables
 */
#define ITCL_THIS_VAR          0x20   /* non-zero => built-in "this" variable */
#define ITCL_OPTIONS_VAR       0x40   /* non-zero => built-in "itcl_options"
                                       * variable */
#define ITCL_TYPE_VAR          0x80   /* non-zero => built-in "type" variable */
                                      /* no longer used ??? */
#define ITCL_SELF_VAR          0x100  /* non-zero => built-in "self" variable */
#define ITCL_SELFNS_VAR        0x200  /* non-zero => built-in "selfns"
                                       * variable */
#define ITCL_WIN_VAR           0x400  /* non-zero => built-in "win" variable */
#define ITCL_COMPONENT_VAR     0x800  /* non-zero => component variable */
#define ITCL_HULL_VAR          0x1000 /* non-zero => built-in "itcl_hull"
                                       * variable */
#define ITCL_OPTION_READONLY   0x2000 /* non-zero => readonly */
#define ITCL_VARIABLE          0x4000 /* non-zero => normal variable */
#define ITCL_TYPE_VARIABLE     0x8000 /* non-zero => typevariable */
#define ITCL_OPTION_INITTED    0x10000 /* non-zero => option has been initialized */
#define ITCL_OPTION_COMP_VAR   0x20000 /* variable to collect option components of extendedclass  */

/*
 *  Instance components.
 */
struct ItclVariable;
typedef struct ItclComponent {
    Tcl_Obj *namePtr;           /* member name */
    struct ItclVariable *ivPtr; /* variable for this component */
    int flags;
    int haveKeptOptions;
    Tcl_HashTable keptOptions;  /* table of options to keep */
} ItclComponent;

#define ITCL_COMPONENT_INHERIT	0x01
#define ITCL_COMPONENT_PUBLIC	0x02

typedef struct ItclDelegatedFunction {
    Tcl_Obj *namePtr;
    ItclComponent *icPtr;
    Tcl_Obj *asPtr;
    Tcl_Obj *usingPtr;
    Tcl_HashTable exceptions;
    int flags;
} ItclDelegatedFunction;

/*
 *  Representation of member functions in an [incr Tcl] class.
 */
typedef struct ItclMemberFunc {
    Tcl_Obj* namePtr;           /* member name */
    Tcl_Obj* fullNamePtr;       /* member name with "class::" qualifier */
    ItclClass* iclsPtr;         /* class containing this member */
    int protection;             /* protection level */
    int flags;                  /* flags describing member (see above) */
    ItclObjectInfo *infoPtr;
    ItclMemberCode *codePtr;    /* code associated with member */
    Tcl_Command accessCmd;      /* Tcl command installed for this function */
    Tcl_Size argcount;         /* number of args in arglist */
    Tcl_Size maxargcount;      /* max number of args in arglist */
    Tcl_Obj *usagePtr;          /* usage string for error messages */
    Tcl_Obj *argumentPtr;       /* the function arguments */
    Tcl_Obj *builtinArgumentPtr; /* the function arguments for builtin functions */
    Tcl_Obj *origArgsPtr;       /* the argument string of the original definition */
    Tcl_Obj *bodyPtr;           /* the function body */
    ItclArgList *argListPtr;    /* the parsed arguments */
    ItclClass *declaringClassPtr; /* the class which declared the method/proc */
    void *tmPtr;                /* TclOO methodPtr */
    ItclDelegatedFunction *idmPtr;
                                /* if the function is delegated != NULL */
} ItclMemberFunc;

/*
 *  Instance variables.
 */
typedef struct ItclVariable {
    Tcl_Obj *namePtr;           /* member name */
    Tcl_Obj *fullNamePtr;       /* member name with "class::" qualifier */
    ItclClass *iclsPtr;         /* class containing this member */
    ItclObjectInfo *infoPtr;
    ItclMemberCode *codePtr;    /* code associated with member */
    Tcl_Obj *init;              /* initial value */
    Tcl_Obj *arrayInitPtr;      /* initial value if variable should be array */
    int protection;             /* protection level */
    int flags;                  /* flags describing member (see below) */
    int initted;                /* is set when first time initted, to check
                                 * for example itcl_hull var, which can be only
				 * initialized once */
} ItclVariable;


struct ItclOption;

typedef struct ItclDelegatedOption {
    Tcl_Obj *namePtr;
    Tcl_Obj *resourceNamePtr;
    Tcl_Obj *classNamePtr;
    struct ItclOption *ioptPtr;  /* the option name or null for "*" */
    ItclComponent *icPtr;        /* the component where the delegation goes
                                  * to */
    Tcl_Obj *asPtr;
    Tcl_HashTable exceptions;    /* exceptions from delegation */
} ItclDelegatedOption;

/*
 *  Instance options.
 */
typedef struct ItclOption {
                                /* within a class hierarchy there must be only
				 * one option with the same name !! */
    Tcl_Obj *namePtr;           /* member name */
    Tcl_Obj *fullNamePtr;       /* member name with "class::" qualifier */
    Tcl_Obj *resourceNamePtr;
    Tcl_Obj *classNamePtr;
    ItclClass *iclsPtr;         /* class containing this member */
    int protection;             /* protection level */
    int flags;                  /* flags describing member (see below) */
    ItclMemberCode *codePtr;    /* code associated with member */
    Tcl_Obj *defaultValuePtr;   /* initial value */
    Tcl_Obj *cgetMethodPtr;
    Tcl_Obj *cgetMethodVarPtr;
    Tcl_Obj *configureMethodPtr;
    Tcl_Obj *configureMethodVarPtr;
    Tcl_Obj *validateMethodPtr;
    Tcl_Obj *validateMethodVarPtr;
    ItclDelegatedOption *idoPtr;
                                /* if the option is delegated != NULL */
} ItclOption;

/*
 *  Instance methodvariables.
 */
typedef struct ItclMethodVariable {
    Tcl_Obj *namePtr;           /* member name */
    Tcl_Obj *fullNamePtr;       /* member name with "class::" qualifier */
    ItclClass *iclsPtr;         /* class containing this member */
    int protection;             /* protection level */
    int flags;                  /* flags describing member (see below) */
    Tcl_Obj *defaultValuePtr;
    Tcl_Obj *callbackPtr;
} ItclMethodVariable;

#define VAR_TYPE_VARIABLE 	1
#define VAR_TYPE_COMMON 	2

#define CMD_TYPE_METHOD 	1
#define CMD_TYPE_PROC 		2

typedef struct ItclClassCmdInfo {
    int type;
    int protection;
#if TCL_MAJOR_VERSION == 8
    int cmdNum; /* not actually used */
#endif
    Tcl_Namespace *nsPtr;
    Tcl_Namespace *declaringNsPtr;
} ItclClassCmdInfo;

/*
 *  Instance variable lookup entry.
 */
typedef struct ItclVarLookup {
    ItclVariable* ivPtr;      /* variable definition */
    int usage;                /* number of uses for this record */
    int accessible;           /* non-zero => accessible from class with
                               * this lookup record in its resolveVars */
    char *leastQualName;      /* simplist name for this variable, with
                               * the fewest qualifiers.  This string is
                               * taken from the resolveVars table, so
                               * it shouldn't be freed. */
    Tcl_Size varNum;
    Tcl_Var varPtr;
} ItclVarLookup;

/*
 *  Instance command lookup entry.
 */
typedef struct ItclCmdLookup {
    ItclMemberFunc* imPtr;    /* function definition */
#if TCL_MAJOR_VERSION == 8
    int cmdNum; /* not actually used */
#endif
    ItclClassCmdInfo *classCmdInfoPtr;
    Tcl_Command cmdPtr;
} ItclCmdLookup;

typedef struct ItclCallContext {
    int objectFlags;
    Tcl_Namespace *nsPtr;
    ItclObject *ioPtr;
    ItclMemberFunc *imPtr;
    Tcl_Size refCount;
} ItclCallContext;

/*
 * The macro below is used to modify a "char" value (e.g. by casting
 * it to an unsigned character) so that it can be used safely with
 * macros such as isspace.
 */

#define UCHAR(c) ((unsigned char) (c))
/*
 * Macros used to cast between pointers and integers (e.g. when storing an int
 * in ClientData), on 64-bit architectures they avoid gcc warning about "cast
 * to/from pointer from/to integer of different size".
 */

#if !defined(INT2PTR)
#   define INT2PTR(p) ((void *)(ptrdiff_t)(p))
#endif
#if !defined(PTR2INT)
#   define PTR2INT(p) ((ptrdiff_t)(p))
#endif

#ifdef ITCL_DEBUG
MODULE_SCOPE int _itcl_debug_level;
MODULE_SCOPE void ItclShowArgs(int level, const char *str, size_t objc,
	Tcl_Obj *const *objv);
#else
#define ItclShowArgs(a,b,c,d) do {(void)(c);(void)(d);} while(0)
#endif

MODULE_SCOPE Tcl_ObjCmdProc ItclCallCCommand;
MODULE_SCOPE Tcl_ObjCmdProc ItclObjectUnknownCommand;
MODULE_SCOPE int ItclCheckCallProc(void *clientData, Tcl_Interp *interp,
	Tcl_ObjectContext contextPtr, Tcl_CallFrame *framePtr, int *isFinished);

MODULE_SCOPE void ItclPreserveClass(ItclClass *iclsPtr);
MODULE_SCOPE void ItclReleaseClass(void *iclsPtr);

MODULE_SCOPE ItclFoundation *ItclGetFoundation(Tcl_Interp *interp);
MODULE_SCOPE Tcl_ObjCmdProc ItclClassCommandDispatcher;
MODULE_SCOPE Tcl_Command Itcl_CmdAliasProc(Tcl_Interp *interp,
	Tcl_Namespace *nsPtr, const char *cmdName, void *clientData);
MODULE_SCOPE Tcl_Var Itcl_VarAliasProc(Tcl_Interp *interp,
	Tcl_Namespace *nsPtr, const char *VarName, void *clientData);
MODULE_SCOPE int ItclIsClass(Tcl_Interp *interp, Tcl_Command cmd);
MODULE_SCOPE int ItclCheckCallMethod(void *clientData, Tcl_Interp *interp,
	Tcl_ObjectContext contextPtr, Tcl_CallFrame *framePtr, int *isFinished);
MODULE_SCOPE int ItclAfterCallMethod(void *clientData, Tcl_Interp *interp,
	Tcl_ObjectContext contextPtr, Tcl_Namespace *nsPtr, int result);
MODULE_SCOPE void ItclReportObjectUsage(Tcl_Interp *interp,
	ItclObject *contextIoPtr, Tcl_Namespace *callerNsPtr,
	Tcl_Namespace *contextNsPtr);
MODULE_SCOPE int ItclMapMethodNameProc(Tcl_Interp *interp, Tcl_Object oPtr,
	Tcl_Class *startClsPtr, Tcl_Obj *methodObj);
MODULE_SCOPE int ItclCreateArgList(Tcl_Interp *interp, const char *str,
	Tcl_Size *argcPtr, Tcl_Size *maxArgcPtr, Tcl_Obj **usagePtr,
	ItclArgList **arglistPtrPtr, ItclMemberFunc *imPtr,
	const char *commandName);
MODULE_SCOPE int ItclObjectCmd(void *clientData, Tcl_Interp *interp,
	Tcl_Object oPtr, Tcl_Class clsPtr, size_t objc, Tcl_Obj *const *objv);
MODULE_SCOPE int ItclCreateObject (Tcl_Interp *interp, const char* name,
	ItclClass *iclsPtr, size_t objc, Tcl_Obj *const objv[]);
MODULE_SCOPE void ItclDeleteObjectVariablesNamespace(Tcl_Interp *interp,
	ItclObject *ioPtr);
MODULE_SCOPE void ItclDeleteClassVariablesNamespace(Tcl_Interp *interp,
	ItclClass *iclsPtr);
MODULE_SCOPE int ItclInfoInit(Tcl_Interp *interp, ItclObjectInfo *infoPtr);

MODULE_SCOPE Tcl_HashEntry *ItclResolveVarEntry(
	ItclClass* iclsPtr, const char *varName);

struct Tcl_ResolvedVarInfo;
MODULE_SCOPE int Itcl_ClassCmdResolver(Tcl_Interp *interp, const char* name,
	Tcl_Namespace *nsPtr, int flags, Tcl_Command *rPtr);
MODULE_SCOPE int Itcl_ClassVarResolver(Tcl_Interp *interp, const char* name,
	Tcl_Namespace *nsPtr, int flags, Tcl_Var *rPtr);
MODULE_SCOPE int Itcl_ClassCompiledVarResolver(Tcl_Interp *interp,
	const char* name, Tcl_Size length, Tcl_Namespace *nsPtr,
	struct Tcl_ResolvedVarInfo **rPtr);
MODULE_SCOPE int Itcl_ClassCmdResolver2(Tcl_Interp *interp, const char* name,
	Tcl_Namespace *nsPtr, int flags, Tcl_Command *rPtr);
MODULE_SCOPE int Itcl_ClassVarResolver2(Tcl_Interp *interp, const char* name,
	Tcl_Namespace *nsPtr, int flags, Tcl_Var *rPtr);
MODULE_SCOPE int ItclSetParserResolver(Tcl_Namespace *nsPtr);
MODULE_SCOPE void ItclProcErrorProc(Tcl_Interp *interp, Tcl_Obj *procNameObj);
MODULE_SCOPE int Itcl_CreateOption (Tcl_Interp *interp, ItclClass *iclsPtr,
	ItclOption *ioptPtr);
MODULE_SCOPE int ItclCreateMethodVariable(Tcl_Interp *interp,
	ItclVariable *ivPtr, Tcl_Obj* defaultPtr, Tcl_Obj* callbackPtr,
	ItclMethodVariable** imvPtrPtr);
MODULE_SCOPE int DelegationInstall(Tcl_Interp *interp, ItclObject *ioPtr,
	ItclClass *iclsPtr);
MODULE_SCOPE ItclClass *ItclNamespace2Class(Tcl_Namespace *nsPtr);
MODULE_SCOPE const char* ItclGetCommonInstanceVar(Tcl_Interp *interp,
	const char *name, const char *name2, ItclObject *contextIoPtr,
	ItclClass *contextIclsPtr);
MODULE_SCOPE int ItclCreateMethod(Tcl_Interp* interp, ItclClass *iclsPtr,
	Tcl_Obj *namePtr, const char* arglist, const char* body,
	ItclMemberFunc **imPtrPtr);
MODULE_SCOPE int Itcl_WidgetParseInit(Tcl_Interp *interp,
	ItclObjectInfo *infoPtr);
MODULE_SCOPE void ItclDeleteObjectMetadata(void *clientData);
MODULE_SCOPE void ItclDeleteClassMetadata(void *clientData);
MODULE_SCOPE void ItclDeleteArgList(ItclArgList *arglistPtr);
MODULE_SCOPE int Itcl_ClassOptionCmd(void *clientData, Tcl_Interp *interp,
	int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int DelegatedOptionsInstall(Tcl_Interp *interp,
	ItclClass *iclsPtr);
MODULE_SCOPE int Itcl_HandleDelegateOptionCmd(Tcl_Interp *interp,
	ItclObject *ioPtr, ItclClass *iclsPtr, ItclDelegatedOption **idoPtrPtr,
	Tcl_Size objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int Itcl_HandleDelegateMethodCmd(Tcl_Interp *interp,
	ItclObject *ioPtr, ItclClass *iclsPtr,
	ItclDelegatedFunction **idmPtrPtr, Tcl_Size objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int DelegateFunction(Tcl_Interp *interp, ItclObject *ioPtr,
	ItclClass *iclsPtr, Tcl_Obj *componentNamePtr,
	ItclDelegatedFunction *idmPtr);
MODULE_SCOPE int ItclInitObjectMethodVariables(Tcl_Interp *interp,
	ItclObject *ioPtr, ItclClass *iclsPtr, const char *name);
MODULE_SCOPE int InitTclOOFunctionPointers(Tcl_Interp *interp);
MODULE_SCOPE ItclOption* ItclNewOption(Tcl_Interp *interp, ItclObject *ioPtr,
	ItclClass *iclsPtr, Tcl_Obj *namePtr, const char *resourceName,
	const char *className, char *init, ItclMemberCode *mCodePtr);
MODULE_SCOPE int ItclParseOption(ItclObjectInfo *infoPtr, Tcl_Interp *interp,
	size_t objc, Tcl_Obj *const objv[], ItclClass *iclsPtr,
	ItclObject *ioPtr, ItclOption **ioptPtrPtr);
MODULE_SCOPE void ItclDestroyClassNamesp(void *cdata);
MODULE_SCOPE int ExpandDelegateAs(Tcl_Interp *interp, ItclObject *ioPtr,
	ItclClass *iclsPtr, ItclDelegatedFunction *idmPtr,
	const char *funcName, Tcl_Obj *listPtr);
MODULE_SCOPE int ItclCheckForInitializedComponents(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclObject *ioPtr);
MODULE_SCOPE int ItclCreateDelegatedFunction(Tcl_Interp *interp,
	ItclClass *iclsPtr, Tcl_Obj *methodNamePtr, ItclComponent *icPtr,
	Tcl_Obj *targetPtr, Tcl_Obj *usingPtr, Tcl_Obj *exceptionsPtr,
	ItclDelegatedFunction **idmPtrPtr);
MODULE_SCOPE void ItclDeleteDelegatedOption(char *cdata);
MODULE_SCOPE void Itcl_FinishList();
MODULE_SCOPE void ItclDeleteDelegatedFunction(ItclDelegatedFunction *idmPtr);
MODULE_SCOPE void ItclFinishEnsemble(ItclObjectInfo *infoPtr);
MODULE_SCOPE int Itcl_EnsembleDeleteCmd(void *clientData,
	Tcl_Interp *interp, int objc, Tcl_Obj *const objv[]);
MODULE_SCOPE int ItclAddClassesDictInfo(Tcl_Interp *interp, ItclClass *iclsPtr);
MODULE_SCOPE int ItclDeleteClassesDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr);
MODULE_SCOPE int ItclAddObjectsDictInfo(Tcl_Interp *interp, ItclObject *ioPtr);
MODULE_SCOPE int ItclDeleteObjectsDictInfo(Tcl_Interp *interp,
	ItclObject *ioPtr);
MODULE_SCOPE int ItclAddOptionDictInfo(Tcl_Interp *interp, ItclClass *iclsPtr,
	ItclOption *ioptPtr);
MODULE_SCOPE int ItclAddDelegatedOptionDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclDelegatedOption *idoPtr);
MODULE_SCOPE int ItclAddClassComponentDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclComponent *icPtr);
MODULE_SCOPE int ItclAddClassVariableDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclVariable *ivPtr);
MODULE_SCOPE int ItclAddClassFunctionDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclMemberFunc *imPtr);
MODULE_SCOPE int ItclAddClassDelegatedFunctionDictInfo(Tcl_Interp *interp,
	ItclClass *iclsPtr, ItclDelegatedFunction *idmPtr);
MODULE_SCOPE int ItclClassCreateObject(void *clientData, Tcl_Interp *interp,
	Tcl_Size objc, Tcl_Obj *const objv[]);

MODULE_SCOPE void ItclRestoreInfoVars(void *clientData);

MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiMyProcCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiInstallComponentCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiCallInstanceCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiGetInstanceVarCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiMyTypeMethodCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiMyMethodCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiMyTypeVarCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiMyVarCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_BiItclHullCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_ThisCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_ExtendedClassCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_TypeClassCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_AddObjectOptionCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_AddDelegatedOptionCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_AddDelegatedFunctionCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_SetComponentCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_ClassHullTypeCmd;
MODULE_SCOPE Tcl_ObjCmdProc Itcl_ClassWidgetClassCmd;

typedef int (ItclRootMethodProc)(ItclObject *ioPtr, Tcl_Interp *interp,
	int objc, Tcl_Obj *const objv[]);

MODULE_SCOPE const Tcl_MethodType itclRootMethodType;
MODULE_SCOPE ItclRootMethodProc ItclUnknownGuts;
MODULE_SCOPE ItclRootMethodProc ItclConstructGuts;
MODULE_SCOPE ItclRootMethodProc ItclInfoGuts;

#include "itcl2TclOO.h"

/*
 * Include all the private API, generated from itcl.decls.
 */

#include "itclIntDecls.h"
