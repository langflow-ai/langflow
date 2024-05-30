/*
 * tcl.h --
 *
 *	This header file describes the externally-visible facilities of the
 *	Tcl interpreter.
 *
 * Copyright (c) 1987-1994 The Regents of the University of California.
 * Copyright (c) 1993-1996 Lucent Technologies.
 * Copyright (c) 1994-1998 Sun Microsystems, Inc.
 * Copyright (c) 1998-2000 by Scriptics Corporation.
 * Copyright (c) 2002 by Kevin B. Kenny.  All rights reserved.
 *
 * See the file "license.terms" for information on usage and redistribution of
 * this file, and for a DISCLAIMER OF ALL WARRANTIES.
 */

#ifndef _TCL
#define _TCL

/*
 * For C++ compilers, use extern "C"
 */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * The following defines are used to indicate the various release levels.
 */

#define TCL_ALPHA_RELEASE	0
#define TCL_BETA_RELEASE	1
#define TCL_FINAL_RELEASE	2

/*
 * When version numbers change here, must also go into the following files and
 * update the version numbers:
 *
 * library/init.tcl	(1 LOC patch)
 * unix/configure.in	(2 LOC Major, 2 LOC minor, 1 LOC patch)
 * win/configure.in	(as above)
 * win/tcl.m4		(not patchlevel)
 * README.md		(sections 0 and 2, with and without separator)
 * macosx/Tcl-Common.xcconfig (not patchlevel) 1 LOC
 * win/README		(not patchlevel) (sections 0 and 2)
 * unix/tcl.spec	(1 LOC patch)
 * tools/tcl.hpj.in	(not patchlevel, for windows installer)
 */

#if !defined(TCL_MAJOR_VERSION)
#   define TCL_MAJOR_VERSION   8
#endif
#if TCL_MAJOR_VERSION != 8
#   error "This header-file is for Tcl 8 only"
#endif
#define TCL_MINOR_VERSION   6
#define TCL_RELEASE_LEVEL   TCL_FINAL_RELEASE
#define TCL_RELEASE_SERIAL  14

#define TCL_VERSION	    "8.6"
#define TCL_PATCH_LEVEL	    "8.6.14"

/*
 *----------------------------------------------------------------------------
 * The following definitions set up the proper options for Windows compilers.
 * We use this method because there is no autoconf equivalent.
 */

#ifdef _WIN32
#   ifndef __WIN32__
#	define __WIN32__
#   endif
#   ifndef WIN32
#	define WIN32
#   endif
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
 * A special definition used to allow this header file to be included from
 * windows resource files so that they can obtain version information.
 * RC_INVOKED is defined by default by the windows RC tool.
 *
 * Resource compilers don't like all the C stuff, like typedefs and function
 * declarations, that occur below, so block them out.
 */

#ifndef RC_INVOKED

/*
 * Special macro to define mutexes, that doesn't do anything if we are not
 * using threads.
 */

#ifdef TCL_THREADS
#define TCL_DECLARE_MUTEX(name) static Tcl_Mutex name;
#else
#define TCL_DECLARE_MUTEX(name)
#endif

/*
 * Tcl's public routine Tcl_FSSeek() uses the values SEEK_SET, SEEK_CUR, and
 * SEEK_END, all #define'd by stdio.h .
 *
 * Also, many extensions need stdio.h, and they've grown accustomed to tcl.h
 * providing it for them rather than #include-ing it themselves as they
 * should, so also for their sake, we keep the #include to be consistent with
 * prior Tcl releases.
 */

#include <stdio.h>

/*
 *----------------------------------------------------------------------------
 * Support for functions with a variable number of arguments.
 *
 * The following TCL_VARARGS* macros are to support old extensions
 * written for older versions of Tcl where the macros permitted
 * support for the varargs.h system as well as stdarg.h .
 *
 * New code should just directly be written to use stdarg.h conventions.
 */

#include <stdarg.h>
#if !defined(TCL_NO_DEPRECATED)
#    define TCL_VARARGS(type, name) (type name, ...)
#    define TCL_VARARGS_DEF(type, name) (type name, ...)
#    define TCL_VARARGS_START(type, name, list) (va_start(list, name), name)
#endif /* !TCL_NO_DEPRECATED */
#if defined(__GNUC__) && (__GNUC__ > 2)
#   if defined(_WIN32) && defined(__USE_MINGW_ANSI_STDIO) && __USE_MINGW_ANSI_STDIO
#	define TCL_FORMAT_PRINTF(a,b) __attribute__ ((__format__ (__MINGW_PRINTF_FORMAT, a, b)))
#   else
#	define TCL_FORMAT_PRINTF(a,b) __attribute__ ((__format__ (__printf__, a, b)))
#   endif
#   define TCL_NORETURN __attribute__ ((noreturn))
#   if defined(BUILD_tcl) || defined(BUILD_tk)
#	define TCL_NORETURN1 __attribute__ ((noreturn))
#   else
#	define TCL_NORETURN1 /* nothing */
#   endif
#else
#   define TCL_FORMAT_PRINTF(a,b)
#   if defined(_MSC_VER) && (_MSC_VER >= 1310)
#	define TCL_NORETURN _declspec(noreturn)
#   else
#	define TCL_NORETURN /* nothing */
#   endif
#   define TCL_NORETURN1 /* nothing */
#endif

/*
 * Allow a part of Tcl's API to be explicitly marked as deprecated.
 *
 * Used to make TIP 330/336 generate moans even if people use the
 * compatibility macros. Change your code, guys! We won't support you forever.
 */

#if defined(__GNUC__) && ((__GNUC__ >= 4) || ((__GNUC__ == 3) && (__GNUC_MINOR__ >= 1)))
#   if (__GNUC__ > 4) || ((__GNUC__ == 4) && (__GNUC_MINOR__ >= 5))
#	define TCL_DEPRECATED_API(msg)	__attribute__ ((__deprecated__ (msg)))
#   else
#	define TCL_DEPRECATED_API(msg)	__attribute__ ((__deprecated__))
#   endif
#else
#   define TCL_DEPRECATED_API(msg)	/* nothing portable */
#endif

/*
 *----------------------------------------------------------------------------
 * Macros used to declare a function to be exported by a DLL. Used by Windows,
 * maps to no-op declarations on non-Windows systems. The default build on
 * windows is for a DLL, which causes the DLLIMPORT and DLLEXPORT macros to be
 * nonempty. To build a static library, the macro STATIC_BUILD should be
 * defined.
 *
 * Note: when building static but linking dynamically to MSVCRT we must still
 *       correctly decorate the C library imported function.  Use CRTIMPORT
 *       for this purpose.  _DLL is defined by the compiler when linking to
 *       MSVCRT.
 */

#if (defined(_WIN32) && (defined(_MSC_VER) || (defined(__BORLANDC__) && (__BORLANDC__ >= 0x0550)) || defined(__LCC__) || defined(__WATCOMC__) || (defined(__GNUC__) && defined(__declspec))))
#   define HAVE_DECLSPEC 1
#   ifdef STATIC_BUILD
#       define DLLIMPORT
#       define DLLEXPORT
#       ifdef _DLL
#           define CRTIMPORT __declspec(dllimport)
#       else
#           define CRTIMPORT
#       endif
#   else
#       define DLLIMPORT __declspec(dllimport)
#       define DLLEXPORT __declspec(dllexport)
#       define CRTIMPORT __declspec(dllimport)
#   endif
#else
#   define DLLIMPORT
#   if defined(__GNUC__) && __GNUC__ > 3
#       define DLLEXPORT __attribute__ ((visibility("default")))
#   else
#       define DLLEXPORT
#   endif
#   define CRTIMPORT
#endif

/*
 * These macros are used to control whether functions are being declared for
 * import or export. If a function is being declared while it is being built
 * to be included in a shared library, then it should have the DLLEXPORT
 * storage class. If is being declared for use by a module that is going to
 * link against the shared library, then it should have the DLLIMPORT storage
 * class. If the symbol is being declared for a static build or for use from a
 * stub library, then the storage class should be empty.
 *
 * The convention is that a macro called BUILD_xxxx, where xxxx is the name of
 * a library we are building, is set on the compile line for sources that are
 * to be placed in the library. When this macro is set, the storage class will
 * be set to DLLEXPORT. At the end of the header file, the storage class will
 * be reset to DLLIMPORT.
 */

#undef TCL_STORAGE_CLASS
#ifdef BUILD_tcl
#   define TCL_STORAGE_CLASS DLLEXPORT
#else
#   ifdef USE_TCL_STUBS
#      define TCL_STORAGE_CLASS
#   else
#      define TCL_STORAGE_CLASS DLLIMPORT
#   endif
#endif

/*
 * The following _ANSI_ARGS_ macro is to support old extensions
 * written for older versions of Tcl where it permitted support
 * for compilers written in the pre-prototype era of C.
 *
 * New code should use prototypes.
 */

#ifndef TCL_NO_DEPRECATED
#   undef _ANSI_ARGS_
#   define _ANSI_ARGS_(x)	x
#endif

/*
 * Definitions that allow this header file to be used either with or without
 * ANSI C features.
 */

#ifndef INLINE
#   define INLINE
#endif

#ifdef NO_CONST
#   ifndef const
#      define const
#   endif
#endif
#ifndef CONST
#   define CONST const
#endif

#ifdef USE_NON_CONST
#   ifdef USE_COMPAT_CONST
#      error define at most one of USE_NON_CONST and USE_COMPAT_CONST
#   endif
#   define CONST84
#   define CONST84_RETURN
#else
#   ifdef USE_COMPAT_CONST
#      define CONST84
#      define CONST84_RETURN const
#   else
#      define CONST84 const
#      define CONST84_RETURN const
#   endif
#endif

#ifndef CONST86
#      define CONST86 CONST84
#endif

/*
 * Make sure EXTERN isn't defined elsewhere.
 */

#ifdef EXTERN
#   undef EXTERN
#endif /* EXTERN */

#ifdef __cplusplus
#   define EXTERN extern "C" TCL_STORAGE_CLASS
#else
#   define EXTERN extern TCL_STORAGE_CLASS
#endif

/*
 *----------------------------------------------------------------------------
 * The following code is copied from winnt.h. If we don't replicate it here,
 * then <windows.h> can't be included after tcl.h, since tcl.h also defines
 * VOID. This block is skipped under Cygwin and Mingw.
 */

#if defined(_WIN32) && !defined(HAVE_WINNT_IGNORE_VOID)
#ifndef VOID
#define VOID void
typedef char CHAR;
typedef short SHORT;
typedef long LONG;
#endif
#endif /* _WIN32 && !HAVE_WINNT_IGNORE_VOID */

/*
 * Macro to use instead of "void" for arguments that must have type "void *"
 * in ANSI C; maps them to type "char *" in non-ANSI systems.
 */

#ifndef __VXWORKS__
#   ifndef NO_VOID
#	define VOID void
#   else
#	define VOID char
#   endif
#endif

/*
 * Miscellaneous declarations.
 */

#ifndef _CLIENTDATA
#   ifndef NO_VOID
	typedef void *ClientData;
#   else
	typedef int *ClientData;
#   endif
#   define _CLIENTDATA
#endif

/*
 * Darwin specific configure overrides (to support fat compiles, where
 * configure runs only once for multiple architectures):
 */

#ifdef __APPLE__
#   ifdef __LP64__
#	undef TCL_WIDE_INT_TYPE
#	define TCL_WIDE_INT_IS_LONG 1
#	define TCL_CFG_DO64BIT 1
#    else /* !__LP64__ */
#	define TCL_WIDE_INT_TYPE long long
#	undef TCL_WIDE_INT_IS_LONG
#	undef TCL_CFG_DO64BIT
#    endif /* __LP64__ */
#    undef HAVE_STRUCT_STAT64
#endif /* __APPLE__ */

/* Cross-compiling 32-bit on a 64-bit platform? Then our
 * configure script does the wrong thing. Correct that here.
 */
#if defined(__GNUC__) && !defined(_WIN32) && !defined(__LP64__)
#   undef TCL_WIDE_INT_IS_LONG
#   undef TCL_WIDE_INT_TYPE
#   define TCL_WIDE_INT_TYPE long long
#endif

/*
 * Define Tcl_WideInt to be a type that is (at least) 64-bits wide, and define
 * Tcl_WideUInt to be the unsigned variant of that type (assuming that where
 * we have one, we can have the other.)
 *
 * Also defines the following macros:
 * TCL_WIDE_INT_IS_LONG - if wide ints are really longs (i.e. we're on a
 *	LP64 system such as modern Solaris or Linux ... not including Win64)
 * Tcl_WideAsLong - forgetful converter from wideInt to long.
 * Tcl_LongAsWide - sign-extending converter from long to wideInt.
 * Tcl_WideAsDouble - converter from wideInt to double.
 * Tcl_DoubleAsWide - converter from double to wideInt.
 *
 * The following invariant should hold for any long value 'longVal':
 *	longVal == Tcl_WideAsLong(Tcl_LongAsWide(longVal))
 *
 * Note on converting between Tcl_WideInt and strings. This implementation (in
 * tclObj.c) depends on the function
 * snprintf(...,"%" TCL_LL_MODIFIER "d",...).
 */

#if !defined(TCL_WIDE_INT_TYPE)&&!defined(TCL_WIDE_INT_IS_LONG)
#   ifdef _WIN32
#	define TCL_WIDE_INT_TYPE __int64
#	ifdef __BORLANDC__
#	    define TCL_LL_MODIFIER	"L"
#	elif defined(_WIN32) && (!defined(__USE_MINGW_ANSI_STDIO) || !__USE_MINGW_ANSI_STDIO)
#	    define TCL_LL_MODIFIER	"I64"
#	else
#	    define TCL_LL_MODIFIER	"ll"
#	endif
#   elif defined(__GNUC__)
#      define TCL_WIDE_INT_TYPE long long
#      define TCL_LL_MODIFIER	"ll"
#   else /* ! _WIN32 && ! __GNUC__ */
/*
 * Don't know what platform it is and configure hasn't discovered what is
 * going on for us. Try to guess...
 */
#      include <limits.h>
#      if (INT_MAX < LONG_MAX)
#         define TCL_WIDE_INT_IS_LONG	1
#      else
#         define TCL_WIDE_INT_TYPE long long
#      endif
#   endif /* _WIN32 */
#endif /* !TCL_WIDE_INT_TYPE & !TCL_WIDE_INT_IS_LONG */
#ifdef TCL_WIDE_INT_IS_LONG
#   undef TCL_WIDE_INT_TYPE
#   define TCL_WIDE_INT_TYPE	long
#endif /* TCL_WIDE_INT_IS_LONG */

typedef TCL_WIDE_INT_TYPE		Tcl_WideInt;
typedef unsigned TCL_WIDE_INT_TYPE	Tcl_WideUInt;

#ifdef TCL_WIDE_INT_IS_LONG
#   define Tcl_WideAsLong(val)		((long)(val))
#   define Tcl_LongAsWide(val)		((long)(val))
#   define Tcl_WideAsDouble(val)	((double)((long)(val)))
#   define Tcl_DoubleAsWide(val)	((long)((double)(val)))
#   ifndef TCL_LL_MODIFIER
#      define TCL_LL_MODIFIER		"l"
#   endif /* !TCL_LL_MODIFIER */
#else /* TCL_WIDE_INT_IS_LONG */
/*
 * The next short section of defines are only done when not running on Windows
 * or some other strange platform.
 */
#   ifndef TCL_LL_MODIFIER
#      define TCL_LL_MODIFIER		"ll"
#   endif /* !TCL_LL_MODIFIER */
#   define Tcl_WideAsLong(val)		((long)((Tcl_WideInt)(val)))
#   define Tcl_LongAsWide(val)		((Tcl_WideInt)((long)(val)))
#   define Tcl_WideAsDouble(val)	((double)((Tcl_WideInt)(val)))
#   define Tcl_DoubleAsWide(val)	((Tcl_WideInt)((double)(val)))
#endif /* TCL_WIDE_INT_IS_LONG */

#ifdef _WIN32
#   ifdef __BORLANDC__
	typedef struct stati64 Tcl_StatBuf;
#   elif defined(_WIN64) || defined(_USE_64BIT_TIME_T)
	typedef struct __stat64 Tcl_StatBuf;
#   elif (defined(_MSC_VER) && (_MSC_VER < 1400)) || defined(_USE_32BIT_TIME_T)
	typedef struct _stati64	Tcl_StatBuf;
#   else
	typedef struct _stat32i64 Tcl_StatBuf;
#   endif /* _MSC_VER < 1400 */
#elif defined(__CYGWIN__)
    typedef struct {
	unsigned st_dev;
	unsigned short st_ino;
	unsigned short st_mode;
	short st_nlink;
	short st_uid;
	short st_gid;
	/* Here is a 2-byte gap */
	unsigned st_rdev;
	/* Here is a 4-byte gap */
	long long st_size;
	struct {long tv_sec;} st_atim;
	struct {long tv_sec;} st_mtim;
	struct {long tv_sec;} st_ctim;
    } Tcl_StatBuf;
#elif defined(HAVE_STRUCT_STAT64) && !defined(__APPLE__)
    typedef struct stat64 Tcl_StatBuf;
#else
    typedef struct stat Tcl_StatBuf;
#endif

/*
 *----------------------------------------------------------------------------
 * Data structures defined opaquely in this module. The definitions below just
 * provide dummy types. A few fields are made visible in Tcl_Interp
 * structures, namely those used for returning a string result from commands.
 * Direct access to the result field is discouraged in Tcl 8.0. The
 * interpreter result is either an object or a string, and the two values are
 * kept consistent unless some C code sets interp->result directly.
 * Programmers should use either the function Tcl_GetObjResult() or
 * Tcl_GetStringResult() to read the interpreter's result. See the SetResult
 * man page for details.
 *
 * Note: any change to the Tcl_Interp definition below must be mirrored in the
 * "real" definition in tclInt.h.
 *
 * Note: Tcl_ObjCmdProc functions do not directly set result and freeProc.
 * Instead, they set a Tcl_Obj member in the "real" structure that can be
 * accessed with Tcl_GetObjResult() and Tcl_SetObjResult().
 */

typedef struct Tcl_Interp
#if !defined(TCL_NO_DEPRECATED)
{
    /* TIP #330: Strongly discourage extensions from using the string
     * result. */
#ifdef USE_INTERP_RESULT
    char *result TCL_DEPRECATED_API("use Tcl_GetStringResult/Tcl_SetResult");
				/* If the last command returned a string
				 * result, this points to it. */
    void (*freeProc) (char *blockPtr)
	    TCL_DEPRECATED_API("use Tcl_GetStringResult/Tcl_SetResult");
				/* Zero means the string result is statically
				 * allocated. TCL_DYNAMIC means it was
				 * allocated with ckalloc and should be freed
				 * with ckfree. Other values give the address
				 * of function to invoke to free the result.
				 * Tcl_Eval must free it before executing next
				 * command. */
#else
    char *resultDontUse; /* Don't use in extensions! */
    void (*freeProcDontUse) (char *); /* Don't use in extensions! */
#endif
#ifdef USE_INTERP_ERRORLINE
    int errorLine TCL_DEPRECATED_API("use Tcl_GetErrorLine/Tcl_SetErrorLine");
				/* When TCL_ERROR is returned, this gives the
				 * line number within the command where the
				 * error occurred (1 if first line). */
#else
    int errorLineDontUse; /* Don't use in extensions! */
#endif
}
#endif /* !TCL_NO_DEPRECATED */
Tcl_Interp;

typedef struct Tcl_AsyncHandler_ *Tcl_AsyncHandler;
typedef struct Tcl_Channel_ *Tcl_Channel;
typedef struct Tcl_ChannelTypeVersion_ *Tcl_ChannelTypeVersion;
typedef struct Tcl_Command_ *Tcl_Command;
typedef struct Tcl_Condition_ *Tcl_Condition;
typedef struct Tcl_Dict_ *Tcl_Dict;
typedef struct Tcl_EncodingState_ *Tcl_EncodingState;
typedef struct Tcl_Encoding_ *Tcl_Encoding;
typedef struct Tcl_Event Tcl_Event;
typedef struct Tcl_InterpState_ *Tcl_InterpState;
typedef struct Tcl_LoadHandle_ *Tcl_LoadHandle;
typedef struct Tcl_Mutex_ *Tcl_Mutex;
typedef struct Tcl_Pid_ *Tcl_Pid;
typedef struct Tcl_RegExp_ *Tcl_RegExp;
typedef struct Tcl_ThreadDataKey_ *Tcl_ThreadDataKey;
typedef struct Tcl_ThreadId_ *Tcl_ThreadId;
typedef struct Tcl_TimerToken_ *Tcl_TimerToken;
typedef struct Tcl_Trace_ *Tcl_Trace;
typedef struct Tcl_Var_ *Tcl_Var;
typedef struct Tcl_ZLibStream_ *Tcl_ZlibStream;

/*
 *----------------------------------------------------------------------------
 * Definition of the interface to functions implementing threads. A function
 * following this definition is given to each call of 'Tcl_CreateThread' and
 * will be called as the main fuction of the new thread created by that call.
 */

#if defined _WIN32
typedef unsigned (__stdcall Tcl_ThreadCreateProc) (ClientData clientData);
#else
typedef void (Tcl_ThreadCreateProc) (ClientData clientData);
#endif

/*
 * Threading function return types used for abstracting away platform
 * differences when writing a Tcl_ThreadCreateProc. See the NewThread function
 * in generic/tclThreadTest.c for it's usage.
 */

#if defined _WIN32
#   define Tcl_ThreadCreateType		unsigned __stdcall
#   define TCL_THREAD_CREATE_RETURN	return 0
#else
#   define Tcl_ThreadCreateType		void
#   define TCL_THREAD_CREATE_RETURN
#endif

/*
 * Definition of values for default stacksize and the possible flags to be
 * given to Tcl_CreateThread.
 */

#define TCL_THREAD_STACK_DEFAULT (0)    /* Use default size for stack. */
#define TCL_THREAD_NOFLAGS	 (0000) /* Standard flags, default
					 * behaviour. */
#define TCL_THREAD_JOINABLE	 (0001) /* Mark the thread as joinable. */

/*
 * Flag values passed to Tcl_StringCaseMatch.
 */

#define TCL_MATCH_NOCASE	(1<<0)

/*
 * Flag values passed to Tcl_GetRegExpFromObj.
 */

#define	TCL_REG_BASIC		000000	/* BREs (convenience). */
#define	TCL_REG_EXTENDED	000001	/* EREs. */
#define	TCL_REG_ADVF		000002	/* Advanced features in EREs. */
#define	TCL_REG_ADVANCED	000003	/* AREs (which are also EREs). */
#define	TCL_REG_QUOTE		000004	/* No special characters, none. */
#define	TCL_REG_NOCASE		000010	/* Ignore case. */
#define	TCL_REG_NOSUB		000020	/* Don't care about subexpressions. */
#define	TCL_REG_EXPANDED	000040	/* Expanded format, white space &
					 * comments. */
#define	TCL_REG_NLSTOP		000100  /* \n doesn't match . or [^ ] */
#define	TCL_REG_NLANCH		000200  /* ^ matches after \n, $ before. */
#define	TCL_REG_NEWLINE		000300  /* Newlines are line terminators. */
#define	TCL_REG_CANMATCH	001000  /* Report details on partial/limited
					 * matches. */

/*
 * Flags values passed to Tcl_RegExpExecObj.
 */

#define	TCL_REG_NOTBOL	0001	/* Beginning of string does not match ^.  */
#define	TCL_REG_NOTEOL	0002	/* End of string does not match $. */

/*
 * Structures filled in by Tcl_RegExpInfo. Note that all offset values are
 * relative to the start of the match string, not the beginning of the entire
 * string.
 */

typedef struct Tcl_RegExpIndices {
    long start;			/* Character offset of first character in
				 * match. */
    long end;			/* Character offset of first character after
				 * the match. */
} Tcl_RegExpIndices;

typedef struct Tcl_RegExpInfo {
    int nsubs;			/* Number of subexpressions in the compiled
				 * expression. */
    Tcl_RegExpIndices *matches;	/* Array of nsubs match offset pairs. */
    long extendStart;		/* The offset at which a subsequent match
				 * might begin. */
    long reserved;		/* Reserved for later use. */
} Tcl_RegExpInfo;

/*
 * Picky compilers complain if this typdef doesn't appear before the struct's
 * reference in tclDecls.h.
 */

typedef Tcl_StatBuf *Tcl_Stat_;
typedef struct stat *Tcl_OldStat_;

/*
 *----------------------------------------------------------------------------
 * When a TCL command returns, the interpreter contains a result from the
 * command. Programmers are strongly encouraged to use one of the functions
 * Tcl_GetObjResult() or Tcl_GetStringResult() to read the interpreter's
 * result. See the SetResult man page for details. Besides this result, the
 * command function returns an integer code, which is one of the following:
 *
 * TCL_OK		Command completed normally; the interpreter's result
 *			contains the command's result.
 * TCL_ERROR		The command couldn't be completed successfully; the
 *			interpreter's result describes what went wrong.
 * TCL_RETURN		The command requests that the current function return;
 *			the interpreter's result contains the function's
 *			return value.
 * TCL_BREAK		The command requests that the innermost loop be
 *			exited; the interpreter's result is meaningless.
 * TCL_CONTINUE		Go on to the next iteration of the current loop; the
 *			interpreter's result is meaningless.
 */

#define TCL_OK			0
#define TCL_ERROR		1
#define TCL_RETURN		2
#define TCL_BREAK		3
#define TCL_CONTINUE		4

#define TCL_RESULT_SIZE		200

/*
 *----------------------------------------------------------------------------
 * Flags to control what substitutions are performed by Tcl_SubstObj():
 */

#define TCL_SUBST_COMMANDS	001
#define TCL_SUBST_VARIABLES	002
#define TCL_SUBST_BACKSLASHES	004
#define TCL_SUBST_ALL		007

/*
 * Argument descriptors for math function callbacks in expressions:
 */

typedef enum {
    TCL_INT, TCL_DOUBLE, TCL_EITHER, TCL_WIDE_INT
} Tcl_ValueType;

typedef struct Tcl_Value {
    Tcl_ValueType type;		/* Indicates intValue or doubleValue is valid,
				 * or both. */
    long intValue;		/* Integer value. */
    double doubleValue;		/* Double-precision floating value. */
    Tcl_WideInt wideValue;	/* Wide (min. 64-bit) integer value. */
} Tcl_Value;

/*
 * Forward declaration of Tcl_Obj to prevent an error when the forward
 * reference to Tcl_Obj is encountered in the function types declared below.
 */

struct Tcl_Obj;

/*
 *----------------------------------------------------------------------------
 * Function types defined by Tcl:
 */

typedef int (Tcl_AppInitProc) (Tcl_Interp *interp);
typedef int (Tcl_AsyncProc) (ClientData clientData, Tcl_Interp *interp,
	int code);
typedef void (Tcl_ChannelProc) (ClientData clientData, int mask);
typedef void (Tcl_CloseProc) (ClientData data);
typedef void (Tcl_CmdDeleteProc) (ClientData clientData);
typedef int (Tcl_CmdProc) (ClientData clientData, Tcl_Interp *interp,
	int argc, CONST84 char *argv[]);
typedef void (Tcl_CmdTraceProc) (ClientData clientData, Tcl_Interp *interp,
	int level, char *command, Tcl_CmdProc *proc,
	ClientData cmdClientData, int argc, CONST84 char *argv[]);
typedef int (Tcl_CmdObjTraceProc) (ClientData clientData, Tcl_Interp *interp,
	int level, const char *command, Tcl_Command commandInfo, int objc,
	struct Tcl_Obj *const *objv);
typedef void (Tcl_CmdObjTraceDeleteProc) (ClientData clientData);
typedef void (Tcl_DupInternalRepProc) (struct Tcl_Obj *srcPtr,
	struct Tcl_Obj *dupPtr);
typedef int (Tcl_EncodingConvertProc) (ClientData clientData, const char *src,
	int srcLen, int flags, Tcl_EncodingState *statePtr, char *dst,
	int dstLen, int *srcReadPtr, int *dstWrotePtr, int *dstCharsPtr);
typedef void (Tcl_EncodingFreeProc) (ClientData clientData);
typedef int (Tcl_EventProc) (Tcl_Event *evPtr, int flags);
typedef void (Tcl_EventCheckProc) (ClientData clientData, int flags);
typedef int (Tcl_EventDeleteProc) (Tcl_Event *evPtr, ClientData clientData);
typedef void (Tcl_EventSetupProc) (ClientData clientData, int flags);
typedef void (Tcl_ExitProc) (ClientData clientData);
typedef void (Tcl_FileProc) (ClientData clientData, int mask);
typedef void (Tcl_FileFreeProc) (ClientData clientData);
typedef void (Tcl_FreeInternalRepProc) (struct Tcl_Obj *objPtr);
typedef void (Tcl_FreeProc) (char *blockPtr);
typedef void (Tcl_IdleProc) (ClientData clientData);
typedef void (Tcl_InterpDeleteProc) (ClientData clientData,
	Tcl_Interp *interp);
typedef int (Tcl_MathProc) (ClientData clientData, Tcl_Interp *interp,
	Tcl_Value *args, Tcl_Value *resultPtr);
typedef void (Tcl_NamespaceDeleteProc) (ClientData clientData);
typedef int (Tcl_ObjCmdProc) (ClientData clientData, Tcl_Interp *interp,
	int objc, struct Tcl_Obj *const *objv);
typedef int (Tcl_PackageInitProc) (Tcl_Interp *interp);
typedef int (Tcl_PackageUnloadProc) (Tcl_Interp *interp, int flags);
typedef void (Tcl_PanicProc) (const char *format, ...);
typedef void (Tcl_TcpAcceptProc) (ClientData callbackData, Tcl_Channel chan,
	char *address, int port);
typedef void (Tcl_TimerProc) (ClientData clientData);
typedef int (Tcl_SetFromAnyProc) (Tcl_Interp *interp, struct Tcl_Obj *objPtr);
typedef void (Tcl_UpdateStringProc) (struct Tcl_Obj *objPtr);
typedef char * (Tcl_VarTraceProc) (ClientData clientData, Tcl_Interp *interp,
	CONST84 char *part1, CONST84 char *part2, int flags);
typedef void (Tcl_CommandTraceProc) (ClientData clientData, Tcl_Interp *interp,
	const char *oldName, const char *newName, int flags);
typedef void (Tcl_CreateFileHandlerProc) (int fd, int mask, Tcl_FileProc *proc,
	ClientData clientData);
typedef void (Tcl_DeleteFileHandlerProc) (int fd);
typedef void (Tcl_AlertNotifierProc) (ClientData clientData);
typedef void (Tcl_ServiceModeHookProc) (int mode);
typedef ClientData (Tcl_InitNotifierProc) (void);
typedef void (Tcl_FinalizeNotifierProc) (ClientData clientData);
typedef void (Tcl_MainLoopProc) (void);

/*
 *----------------------------------------------------------------------------
 * The following structure represents a type of object, which is a particular
 * internal representation for an object plus a set of functions that provide
 * standard operations on objects of that type.
 */

typedef struct Tcl_ObjType {
    const char *name;		/* Name of the type, e.g. "int". */
    Tcl_FreeInternalRepProc *freeIntRepProc;
				/* Called to free any storage for the type's
				 * internal rep. NULL if the internal rep does
				 * not need freeing. */
    Tcl_DupInternalRepProc *dupIntRepProc;
				/* Called to create a new object as a copy of
				 * an existing object. */
    Tcl_UpdateStringProc *updateStringProc;
				/* Called to update the string rep from the
				 * type's internal representation. */
    Tcl_SetFromAnyProc *setFromAnyProc;
				/* Called to convert the object's internal rep
				 * to this type. Frees the internal rep of the
				 * old type. Returns TCL_ERROR on failure. */
} Tcl_ObjType;

/*
 * One of the following structures exists for each object in the Tcl system.
 * An object stores a value as either a string, some internal representation,
 * or both.
 */

typedef struct Tcl_Obj {
    int refCount;		/* When 0 the object will be freed. */
    char *bytes;		/* This points to the first byte of the
				 * object's string representation. The array
				 * must be followed by a null byte (i.e., at
				 * offset length) but may also contain
				 * embedded null characters. The array's
				 * storage is allocated by ckalloc. NULL means
				 * the string rep is invalid and must be
				 * regenerated from the internal rep.  Clients
				 * should use Tcl_GetStringFromObj or
				 * Tcl_GetString to get a pointer to the byte
				 * array as a readonly value. */
    int length;			/* The number of bytes at *bytes, not
				 * including the terminating null. */
    const Tcl_ObjType *typePtr;	/* Denotes the object's type. Always
				 * corresponds to the type of the object's
				 * internal rep. NULL indicates the object has
				 * no internal rep (has no type). */
    union {			/* The internal representation: */
	long longValue;		/*   - an long integer value. */
	double doubleValue;	/*   - a double-precision floating value. */
	void *otherValuePtr;	/*   - another, type-specific value,
	                       not used internally any more. */
	Tcl_WideInt wideValue;	/*   - a long long value. */
	struct {		/*   - internal rep as two pointers.
				 *     the main use of which is a bignum's
				 *     tightly packed fields, where the alloc,
				 *     used and signum flags are packed into
				 *     ptr2 with everything else hung off ptr1. */
	    void *ptr1;
	    void *ptr2;
	} twoPtrValue;
	struct {		/*   - internal rep as a pointer and a long,
	                       not used internally any more. */
	    void *ptr;
	    unsigned long value;
	} ptrAndLongRep;
    } internalRep;
} Tcl_Obj;

/*
 * Macros to increment and decrement a Tcl_Obj's reference count, and to test
 * whether an object is shared (i.e. has reference count > 1). Note: clients
 * should use Tcl_DecrRefCount() when they are finished using an object, and
 * should never call TclFreeObj() directly. TclFreeObj() is only defined and
 * made public in tcl.h to support Tcl_DecrRefCount's macro definition.
 */

void		Tcl_IncrRefCount(Tcl_Obj *objPtr);
void		Tcl_DecrRefCount(Tcl_Obj *objPtr);
int		Tcl_IsShared(Tcl_Obj *objPtr);

/*
 *----------------------------------------------------------------------------
 * The following structure contains the state needed by Tcl_SaveResult. No-one
 * outside of Tcl should access any of these fields. This structure is
 * typically allocated on the stack.
 */

typedef struct Tcl_SavedResult {
    char *result;
    Tcl_FreeProc *freeProc;
    Tcl_Obj *objResultPtr;
    char *appendResult;
    int appendAvl;
    int appendUsed;
    char resultSpace[TCL_RESULT_SIZE+1];
} Tcl_SavedResult;

/*
 *----------------------------------------------------------------------------
 * The following definitions support Tcl's namespace facility. Note: the first
 * five fields must match exactly the fields in a Namespace structure (see
 * tclInt.h).
 */

typedef struct Tcl_Namespace {
    char *name;			/* The namespace's name within its parent
				 * namespace. This contains no ::'s. The name
				 * of the global namespace is "" although "::"
				 * is an synonym. */
    char *fullName;		/* The namespace's fully qualified name. This
				 * starts with ::. */
    ClientData clientData;	/* Arbitrary value associated with this
				 * namespace. */
    Tcl_NamespaceDeleteProc *deleteProc;
				/* Function invoked when deleting the
				 * namespace to, e.g., free clientData. */
    struct Tcl_Namespace *parentPtr;
				/* Points to the namespace that contains this
				 * one. NULL if this is the global
				 * namespace. */
} Tcl_Namespace;

/*
 *----------------------------------------------------------------------------
 * The following structure represents a call frame, or activation record. A
 * call frame defines a naming context for a procedure call: its local scope
 * (for local variables) and its namespace scope (used for non-local
 * variables; often the global :: namespace). A call frame can also define the
 * naming context for a namespace eval or namespace inscope command: the
 * namespace in which the command's code should execute. The Tcl_CallFrame
 * structures exist only while procedures or namespace eval/inscope's are
 * being executed, and provide a Tcl call stack.
 *
 * A call frame is initialized and pushed using Tcl_PushCallFrame and popped
 * using Tcl_PopCallFrame. Storage for a Tcl_CallFrame must be provided by the
 * Tcl_PushCallFrame caller, and callers typically allocate them on the C call
 * stack for efficiency. For this reason, Tcl_CallFrame is defined as a
 * structure and not as an opaque token. However, most Tcl_CallFrame fields
 * are hidden since applications should not access them directly; others are
 * declared as "dummyX".
 *
 * WARNING!! The structure definition must be kept consistent with the
 * CallFrame structure in tclInt.h. If you change one, change the other.
 */

typedef struct Tcl_CallFrame {
    Tcl_Namespace *nsPtr;
    int dummy1;
    int dummy2;
    void *dummy3;
    void *dummy4;
    void *dummy5;
    int dummy6;
    void *dummy7;
    void *dummy8;
    int dummy9;
    void *dummy10;
    void *dummy11;
    void *dummy12;
    void *dummy13;
} Tcl_CallFrame;

/*
 *----------------------------------------------------------------------------
 * Information about commands that is returned by Tcl_GetCommandInfo and
 * passed to Tcl_SetCommandInfo. objProc is an objc/objv object-based command
 * function while proc is a traditional Tcl argc/argv string-based function.
 * Tcl_CreateObjCommand and Tcl_CreateCommand ensure that both objProc and
 * proc are non-NULL and can be called to execute the command. However, it may
 * be faster to call one instead of the other. The member isNativeObjectProc
 * is set to 1 if an object-based function was registered by
 * Tcl_CreateObjCommand, and to 0 if a string-based function was registered by
 * Tcl_CreateCommand. The other function is typically set to a compatibility
 * wrapper that does string-to-object or object-to-string argument conversions
 * then calls the other function.
 */

typedef struct Tcl_CmdInfo {
    int isNativeObjectProc;	/* 1 if objProc was registered by a call to
				 * Tcl_CreateObjCommand; 0 otherwise.
				 * Tcl_SetCmdInfo does not modify this
				 * field. */
    Tcl_ObjCmdProc *objProc;	/* Command's object-based function. */
    ClientData objClientData;	/* ClientData for object proc. */
    Tcl_CmdProc *proc;		/* Command's string-based function. */
    ClientData clientData;	/* ClientData for string proc. */
    Tcl_CmdDeleteProc *deleteProc;
				/* Function to call when command is
				 * deleted. */
    ClientData deleteData;	/* Value to pass to deleteProc (usually the
				 * same as clientData). */
    Tcl_Namespace *namespacePtr;/* Points to the namespace that contains this
				 * command. Note that Tcl_SetCmdInfo will not
				 * change a command's namespace; use
				 * TclRenameCommand or Tcl_Eval (of 'rename')
				 * to do that. */
} Tcl_CmdInfo;

/*
 *----------------------------------------------------------------------------
 * The structure defined below is used to hold dynamic strings. The only
 * fields that clients should use are string and length, accessible via the
 * macros Tcl_DStringValue and Tcl_DStringLength.
 */

#define TCL_DSTRING_STATIC_SIZE 200
typedef struct Tcl_DString {
    char *string;		/* Points to beginning of string: either
				 * staticSpace below or a malloced array. */
    int length;			/* Number of non-NULL characters in the
				 * string. */
    int spaceAvl;		/* Total number of bytes available for the
				 * string and its terminating NULL char. */
    char staticSpace[TCL_DSTRING_STATIC_SIZE];
				/* Space to use in common case where string is
				 * small. */
} Tcl_DString;

#define Tcl_DStringLength(dsPtr) ((dsPtr)->length)
#define Tcl_DStringValue(dsPtr) ((dsPtr)->string)
#define Tcl_DStringTrunc Tcl_DStringSetLength

/*
 * Definitions for the maximum number of digits of precision that may be
 * specified in the "tcl_precision" variable, and the number of bytes of
 * buffer space required by Tcl_PrintDouble.
 */

#define TCL_MAX_PREC		17
#define TCL_DOUBLE_SPACE	(TCL_MAX_PREC+10)

/*
 * Definition for a number of bytes of buffer space sufficient to hold the
 * string representation of an integer in base 10 (assuming the existence of
 * 64-bit integers).
 */

#define TCL_INTEGER_SPACE	24

/*
 * Flag values passed to Tcl_ConvertElement.
 * TCL_DONT_USE_BRACES forces it not to enclose the element in braces, but to
 *	use backslash quoting instead.
 * TCL_DONT_QUOTE_HASH disables the default quoting of the '#' character. It
 *	is safe to leave the hash unquoted when the element is not the first
 *	element of a list, and this flag can be used by the caller to indicate
 *	that condition.
 */

#define TCL_DONT_USE_BRACES	1
#define TCL_DONT_QUOTE_HASH	8

/*
 * Flag that may be passed to Tcl_GetIndexFromObj to force it to disallow
 * abbreviated strings.
 */

#define TCL_EXACT	1

/*
 *----------------------------------------------------------------------------
 * Flag values passed to Tcl_RecordAndEval, Tcl_EvalObj, Tcl_EvalObjv.
 * WARNING: these bit choices must not conflict with the bit choices for
 * evalFlag bits in tclInt.h!
 *
 * Meanings:
 *	TCL_NO_EVAL:		Just record this command
 *	TCL_EVAL_GLOBAL:	Execute script in global namespace
 *	TCL_EVAL_DIRECT:	Do not compile this script
 *	TCL_EVAL_INVOKE:	Magical Tcl_EvalObjv mode for aliases/ensembles
 *				o Run in iPtr->lookupNsPtr or global namespace
 *				o Cut out of error traces
 *				o Don't reset the flags controlling ensemble
 *				  error message rewriting.
 *	TCL_CANCEL_UNWIND:	Magical Tcl_CancelEval mode that causes the
 *				stack for the script in progress to be
 *				completely unwound.
 *	TCL_EVAL_NOERR:	Do no exception reporting at all, just return
 *				as the caller will report.
 */

#define TCL_NO_EVAL		0x010000
#define TCL_EVAL_GLOBAL		0x020000
#define TCL_EVAL_DIRECT		0x040000
#define TCL_EVAL_INVOKE		0x080000
#define TCL_CANCEL_UNWIND	0x100000
#define TCL_EVAL_NOERR          0x200000

/*
 * Special freeProc values that may be passed to Tcl_SetResult (see the man
 * page for details):
 */

#define TCL_VOLATILE		((Tcl_FreeProc *) 1)
#define TCL_STATIC		((Tcl_FreeProc *) 0)
#define TCL_DYNAMIC		((Tcl_FreeProc *) 3)

/*
 * Flag values passed to variable-related functions.
 * WARNING: these bit choices must not conflict with the bit choice for
 * TCL_CANCEL_UNWIND, above.
 */

#define TCL_GLOBAL_ONLY		 1
#define TCL_NAMESPACE_ONLY	 2
#define TCL_APPEND_VALUE	 4
#define TCL_LIST_ELEMENT	 8
#define TCL_TRACE_READS		 0x10
#define TCL_TRACE_WRITES	 0x20
#define TCL_TRACE_UNSETS	 0x40
#define TCL_TRACE_DESTROYED	 0x80
#define TCL_INTERP_DESTROYED	 0x100
#define TCL_LEAVE_ERR_MSG	 0x200
#define TCL_TRACE_ARRAY		 0x800
#ifndef TCL_REMOVE_OBSOLETE_TRACES
/* Required to support old variable/vdelete/vinfo traces. */
#define TCL_TRACE_OLD_STYLE	 0x1000
#endif
/* Indicate the semantics of the result of a trace. */
#define TCL_TRACE_RESULT_DYNAMIC 0x8000
#define TCL_TRACE_RESULT_OBJECT  0x10000

/*
 * Flag values for ensemble commands.
 */

#define TCL_ENSEMBLE_PREFIX 0x02/* Flag value to say whether to allow
				 * unambiguous prefixes of commands or to
				 * require exact matches for command names. */

/*
 * Flag values passed to command-related functions.
 */

#define TCL_TRACE_RENAME	0x2000
#define TCL_TRACE_DELETE	0x4000

#define TCL_ALLOW_INLINE_COMPILATION 0x20000

/*
 * The TCL_PARSE_PART1 flag is deprecated and has no effect. The part1 is now
 * always parsed whenever the part2 is NULL. (This is to avoid a common error
 * when converting code to use the new object based APIs and forgetting to
 * give the flag)
 */

#if !defined(TCL_NO_DEPRECATED)
#   define TCL_PARSE_PART1	0x400
#endif /* !TCL_NO_DEPRECATED */

/*
 * Types for linked variables:
 */

#define TCL_LINK_INT		1
#define TCL_LINK_DOUBLE		2
#define TCL_LINK_BOOLEAN	3
#define TCL_LINK_STRING		4
#define TCL_LINK_WIDE_INT	5
#define TCL_LINK_CHAR		6
#define TCL_LINK_UCHAR		7
#define TCL_LINK_SHORT		8
#define TCL_LINK_USHORT		9
#define TCL_LINK_UINT		10
#define TCL_LINK_LONG		11
#define TCL_LINK_ULONG		12
#define TCL_LINK_FLOAT		13
#define TCL_LINK_WIDE_UINT	14
#define TCL_LINK_READ_ONLY	0x80

/*
 *----------------------------------------------------------------------------
 * Forward declarations of Tcl_HashTable and related types.
 */

typedef struct Tcl_HashKeyType Tcl_HashKeyType;
typedef struct Tcl_HashTable Tcl_HashTable;
typedef struct Tcl_HashEntry Tcl_HashEntry;

typedef unsigned (Tcl_HashKeyProc) (Tcl_HashTable *tablePtr, void *keyPtr);
typedef int (Tcl_CompareHashKeysProc) (void *keyPtr, Tcl_HashEntry *hPtr);
typedef Tcl_HashEntry * (Tcl_AllocHashEntryProc) (Tcl_HashTable *tablePtr,
	void *keyPtr);
typedef void (Tcl_FreeHashEntryProc) (Tcl_HashEntry *hPtr);

/*
 * This flag controls whether the hash table stores the hash of a key, or
 * recalculates it. There should be no reason for turning this flag off as it
 * is completely binary and source compatible unless you directly access the
 * bucketPtr member of the Tcl_HashTableEntry structure. This member has been
 * removed and the space used to store the hash value.
 */

#ifndef TCL_HASH_KEY_STORE_HASH
#   define TCL_HASH_KEY_STORE_HASH 1
#endif

/*
 * Structure definition for an entry in a hash table. No-one outside Tcl
 * should access any of these fields directly; use the macros defined below.
 */

struct Tcl_HashEntry {
    Tcl_HashEntry *nextPtr;	/* Pointer to next entry in this hash bucket,
				 * or NULL for end of chain. */
    Tcl_HashTable *tablePtr;	/* Pointer to table containing entry. */
#if TCL_HASH_KEY_STORE_HASH
    void *hash;			/* Hash value, stored as pointer to ensure
				 * that the offsets of the fields in this
				 * structure are not changed. */
#else
    Tcl_HashEntry **bucketPtr;	/* Pointer to bucket that points to first
				 * entry in this entry's chain: used for
				 * deleting the entry. */
#endif
    ClientData clientData;	/* Application stores something here with
				 * Tcl_SetHashValue. */
    union {			/* Key has one of these forms: */
	char *oneWordValue;	/* One-word value for key. */
	Tcl_Obj *objPtr;	/* Tcl_Obj * key value. */
	int words[1];		/* Multiple integer words for key. The actual
				 * size will be as large as necessary for this
				 * table's keys. */
	char string[1];		/* String for key. The actual size will be as
				 * large as needed to hold the key. */
    } key;			/* MUST BE LAST FIELD IN RECORD!! */
};

/*
 * Flags used in Tcl_HashKeyType.
 *
 * TCL_HASH_KEY_RANDOMIZE_HASH -
 *				There are some things, pointers for example
 *				which don't hash well because they do not use
 *				the lower bits. If this flag is set then the
 *				hash table will attempt to rectify this by
 *				randomising the bits and then using the upper
 *				N bits as the index into the table.
 * TCL_HASH_KEY_SYSTEM_HASH -	If this flag is set then all memory internally
 *                              allocated for the hash table that is not for an
 *                              entry will use the system heap.
 */

#define TCL_HASH_KEY_RANDOMIZE_HASH 0x1
#define TCL_HASH_KEY_SYSTEM_HASH    0x2

/*
 * Structure definition for the methods associated with a hash table key type.
 */

#define TCL_HASH_KEY_TYPE_VERSION 1
struct Tcl_HashKeyType {
    int version;		/* Version of the table. If this structure is
				 * extended in future then the version can be
				 * used to distinguish between different
				 * structures. */
    int flags;			/* Flags, see above for details. */
    Tcl_HashKeyProc *hashKeyProc;
				/* Calculates a hash value for the key. If
				 * this is NULL then the pointer itself is
				 * used as a hash value. */
    Tcl_CompareHashKeysProc *compareKeysProc;
				/* Compares two keys and returns zero if they
				 * do not match, and non-zero if they do. If
				 * this is NULL then the pointers are
				 * compared. */
    Tcl_AllocHashEntryProc *allocEntryProc;
				/* Called to allocate memory for a new entry,
				 * i.e. if the key is a string then this could
				 * allocate a single block which contains
				 * enough space for both the entry and the
				 * string. Only the key field of the allocated
				 * Tcl_HashEntry structure needs to be filled
				 * in. If something else needs to be done to
				 * the key, i.e. incrementing a reference
				 * count then that should be done by this
				 * function. If this is NULL then Tcl_Alloc is
				 * used to allocate enough space for a
				 * Tcl_HashEntry and the key pointer is
				 * assigned to key.oneWordValue. */
    Tcl_FreeHashEntryProc *freeEntryProc;
				/* Called to free memory associated with an
				 * entry. If something else needs to be done
				 * to the key, i.e. decrementing a reference
				 * count then that should be done by this
				 * function. If this is NULL then Tcl_Free is
				 * used to free the Tcl_HashEntry. */
};

/*
 * Structure definition for a hash table.  Must be in tcl.h so clients can
 * allocate space for these structures, but clients should never access any
 * fields in this structure.
 */

#define TCL_SMALL_HASH_TABLE 4
struct Tcl_HashTable {
    Tcl_HashEntry **buckets;	/* Pointer to bucket array. Each element
				 * points to first entry in bucket's hash
				 * chain, or NULL. */
    Tcl_HashEntry *staticBuckets[TCL_SMALL_HASH_TABLE];
				/* Bucket array used for small tables (to
				 * avoid mallocs and frees). */
    int numBuckets;		/* Total number of buckets allocated at
				 * **bucketPtr. */
    int numEntries;		/* Total number of entries present in
				 * table. */
    int rebuildSize;		/* Enlarge table when numEntries gets to be
				 * this large. */
    int downShift;		/* Shift count used in hashing function.
				 * Designed to use high-order bits of
				 * randomized keys. */
    int mask;			/* Mask value used in hashing function. */
    int keyType;		/* Type of keys used in this table. It's
				 * either TCL_CUSTOM_KEYS, TCL_STRING_KEYS,
				 * TCL_ONE_WORD_KEYS, or an integer giving the
				 * number of ints that is the size of the
				 * key. */
    Tcl_HashEntry *(*findProc) (Tcl_HashTable *tablePtr, const char *key);
    Tcl_HashEntry *(*createProc) (Tcl_HashTable *tablePtr, const char *key,
	    int *newPtr);
    const Tcl_HashKeyType *typePtr;
				/* Type of the keys used in the
				 * Tcl_HashTable. */
};

/*
 * Structure definition for information used to keep track of searches through
 * hash tables:
 */

typedef struct Tcl_HashSearch {
    Tcl_HashTable *tablePtr;	/* Table being searched. */
    int nextIndex;		/* Index of next bucket to be enumerated after
				 * present one. */
    Tcl_HashEntry *nextEntryPtr;/* Next entry to be enumerated in the current
				 * bucket. */
} Tcl_HashSearch;

/*
 * Acceptable key types for hash tables:
 *
 * TCL_STRING_KEYS:		The keys are strings, they are copied into the
 *				entry.
 * TCL_ONE_WORD_KEYS:		The keys are pointers, the pointer is stored
 *				in the entry.
 * TCL_CUSTOM_TYPE_KEYS:	The keys are arbitrary types which are copied
 *				into the entry.
 * TCL_CUSTOM_PTR_KEYS:		The keys are pointers to arbitrary types, the
 *				pointer is stored in the entry.
 *
 * While maintaining binary compatibility the above have to be distinct values
 * as they are used to differentiate between old versions of the hash table
 * which don't have a typePtr and new ones which do. Once binary compatibility
 * is discarded in favour of making more wide spread changes TCL_STRING_KEYS
 * can be the same as TCL_CUSTOM_TYPE_KEYS, and TCL_ONE_WORD_KEYS can be the
 * same as TCL_CUSTOM_PTR_KEYS because they simply determine how the key is
 * accessed from the entry and not the behaviour.
 */

#define TCL_STRING_KEYS		(0)
#define TCL_ONE_WORD_KEYS	(1)
#define TCL_CUSTOM_TYPE_KEYS	(-2)
#define TCL_CUSTOM_PTR_KEYS	(-1)

/*
 * Structure definition for information used to keep track of searches through
 * dictionaries. These fields should not be accessed by code outside
 * tclDictObj.c
 */

typedef struct {
    void *next;			/* Search position for underlying hash
				 * table. */
    int epoch;			/* Epoch marker for dictionary being searched,
				 * or -1 if search has terminated. */
    Tcl_Dict dictionaryPtr;	/* Reference to dictionary being searched. */
} Tcl_DictSearch;

/*
 *----------------------------------------------------------------------------
 * Flag values to pass to Tcl_DoOneEvent to disable searches for some kinds of
 * events:
 */

#define TCL_DONT_WAIT		(1<<1)
#define TCL_WINDOW_EVENTS	(1<<2)
#define TCL_FILE_EVENTS		(1<<3)
#define TCL_TIMER_EVENTS	(1<<4)
#define TCL_IDLE_EVENTS		(1<<5)	/* WAS 0x10 ???? */
#define TCL_ALL_EVENTS		(~TCL_DONT_WAIT)

/*
 * The following structure defines a generic event for the Tcl event system.
 * These are the things that are queued in calls to Tcl_QueueEvent and
 * serviced later by Tcl_DoOneEvent. There can be many different kinds of
 * events with different fields, corresponding to window events, timer events,
 * etc. The structure for a particular event consists of a Tcl_Event header
 * followed by additional information specific to that event.
 */

struct Tcl_Event {
    Tcl_EventProc *proc;	/* Function to call to service this event. */
    struct Tcl_Event *nextPtr;	/* Next in list of pending events, or NULL. */
};

/*
 * Positions to pass to Tcl_QueueEvent:
 */

typedef enum {
    TCL_QUEUE_TAIL, TCL_QUEUE_HEAD, TCL_QUEUE_MARK
} Tcl_QueuePosition;

/*
 * Values to pass to Tcl_SetServiceMode to specify the behavior of notifier
 * event routines.
 */

#define TCL_SERVICE_NONE 0
#define TCL_SERVICE_ALL 1

/*
 * The following structure keeps is used to hold a time value, either as an
 * absolute time (the number of seconds from the epoch) or as an elapsed time.
 * On Unix systems the epoch is Midnight Jan 1, 1970 GMT.
 */

typedef struct Tcl_Time {
    long sec;			/* Seconds. */
    long usec;			/* Microseconds. */
} Tcl_Time;

typedef void (Tcl_SetTimerProc) (CONST86 Tcl_Time *timePtr);
typedef int (Tcl_WaitForEventProc) (CONST86 Tcl_Time *timePtr);

/*
 * TIP #233 (Virtualized Time)
 */

typedef void (Tcl_GetTimeProc)   (Tcl_Time *timebuf, ClientData clientData);
typedef void (Tcl_ScaleTimeProc) (Tcl_Time *timebuf, ClientData clientData);

/*
 *----------------------------------------------------------------------------
 * Bits to pass to Tcl_CreateFileHandler and Tcl_CreateChannelHandler to
 * indicate what sorts of events are of interest:
 */

#define TCL_READABLE		(1<<1)
#define TCL_WRITABLE		(1<<2)
#define TCL_EXCEPTION		(1<<3)

/*
 * Flag values to pass to Tcl_OpenCommandChannel to indicate the disposition
 * of the stdio handles. TCL_STDIN, TCL_STDOUT, TCL_STDERR, are also used in
 * Tcl_GetStdChannel.
 */

#define TCL_STDIN		(1<<1)
#define TCL_STDOUT		(1<<2)
#define TCL_STDERR		(1<<3)
#define TCL_ENFORCE_MODE	(1<<4)

/*
 * Bits passed to Tcl_DriverClose2Proc to indicate which side of a channel
 * should be closed.
 */

#define TCL_CLOSE_READ		(1<<1)
#define TCL_CLOSE_WRITE		(1<<2)

/*
 * Value to use as the closeProc for a channel that supports the close2Proc
 * interface.
 */

#define TCL_CLOSE2PROC		((Tcl_DriverCloseProc *) 1)

/*
 * Channel version tag. This was introduced in 8.3.2/8.4.
 */

#define TCL_CHANNEL_VERSION_1	((Tcl_ChannelTypeVersion) 0x1)
#define TCL_CHANNEL_VERSION_2	((Tcl_ChannelTypeVersion) 0x2)
#define TCL_CHANNEL_VERSION_3	((Tcl_ChannelTypeVersion) 0x3)
#define TCL_CHANNEL_VERSION_4	((Tcl_ChannelTypeVersion) 0x4)
#define TCL_CHANNEL_VERSION_5	((Tcl_ChannelTypeVersion) 0x5)

/*
 * TIP #218: Channel Actions, Ids for Tcl_DriverThreadActionProc.
 */

#define TCL_CHANNEL_THREAD_INSERT (0)
#define TCL_CHANNEL_THREAD_REMOVE (1)

/*
 * Typedefs for the various operations in a channel type:
 */

typedef int	(Tcl_DriverBlockModeProc) (ClientData instanceData, int mode);
typedef int	(Tcl_DriverCloseProc) (ClientData instanceData,
			Tcl_Interp *interp);
typedef int	(Tcl_DriverClose2Proc) (ClientData instanceData,
			Tcl_Interp *interp, int flags);
typedef int	(Tcl_DriverInputProc) (ClientData instanceData, char *buf,
			int toRead, int *errorCodePtr);
typedef int	(Tcl_DriverOutputProc) (ClientData instanceData,
			CONST84 char *buf, int toWrite, int *errorCodePtr);
typedef int	(Tcl_DriverSeekProc) (ClientData instanceData, long offset,
			int mode, int *errorCodePtr);
typedef int	(Tcl_DriverSetOptionProc) (ClientData instanceData,
			Tcl_Interp *interp, const char *optionName,
			const char *value);
typedef int	(Tcl_DriverGetOptionProc) (ClientData instanceData,
			Tcl_Interp *interp, CONST84 char *optionName,
			Tcl_DString *dsPtr);
typedef void	(Tcl_DriverWatchProc) (ClientData instanceData, int mask);
typedef int	(Tcl_DriverGetHandleProc) (ClientData instanceData,
			int direction, ClientData *handlePtr);
typedef int	(Tcl_DriverFlushProc) (ClientData instanceData);
typedef int	(Tcl_DriverHandlerProc) (ClientData instanceData,
			int interestMask);
typedef Tcl_WideInt (Tcl_DriverWideSeekProc) (ClientData instanceData,
			Tcl_WideInt offset, int mode, int *errorCodePtr);
/*
 * TIP #218, Channel Thread Actions
 */
typedef void	(Tcl_DriverThreadActionProc) (ClientData instanceData,
			int action);
/*
 * TIP #208, File Truncation (etc.)
 */
typedef int	(Tcl_DriverTruncateProc) (ClientData instanceData,
			Tcl_WideInt length);

/*
 * struct Tcl_ChannelType:
 *
 * One such structure exists for each type (kind) of channel. It collects
 * together in one place all the functions that are part of the specific
 * channel type.
 *
 * It is recommend that the Tcl_Channel* functions are used to access elements
 * of this structure, instead of direct accessing.
 */

typedef struct Tcl_ChannelType {
    const char *typeName;	/* The name of the channel type in Tcl
				 * commands. This storage is owned by channel
				 * type. */
    Tcl_ChannelTypeVersion version;
				/* Version of the channel type. */
    Tcl_DriverCloseProc *closeProc;
				/* Function to call to close the channel, or
				 * TCL_CLOSE2PROC if the close2Proc should be
				 * used instead. */
    Tcl_DriverInputProc *inputProc;
				/* Function to call for input on channel. */
    Tcl_DriverOutputProc *outputProc;
				/* Function to call for output on channel. */
    Tcl_DriverSeekProc *seekProc;
				/* Function to call to seek on the channel.
				 * May be NULL. */
    Tcl_DriverSetOptionProc *setOptionProc;
				/* Set an option on a channel. */
    Tcl_DriverGetOptionProc *getOptionProc;
				/* Get an option from a channel. */
    Tcl_DriverWatchProc *watchProc;
				/* Set up the notifier to watch for events on
				 * this channel. */
    Tcl_DriverGetHandleProc *getHandleProc;
				/* Get an OS handle from the channel or NULL
				 * if not supported. */
    Tcl_DriverClose2Proc *close2Proc;
				/* Function to call to close the channel if
				 * the device supports closing the read &
				 * write sides independently. */
    Tcl_DriverBlockModeProc *blockModeProc;
				/* Set blocking mode for the raw channel. May
				 * be NULL. */
    /*
     * Only valid in TCL_CHANNEL_VERSION_2 channels or later.
     */
    Tcl_DriverFlushProc *flushProc;
				/* Function to call to flush a channel. May be
				 * NULL. */
    Tcl_DriverHandlerProc *handlerProc;
				/* Function to call to handle a channel event.
				 * This will be passed up the stacked channel
				 * chain. */
    /*
     * Only valid in TCL_CHANNEL_VERSION_3 channels or later.
     */
    Tcl_DriverWideSeekProc *wideSeekProc;
				/* Function to call to seek on the channel
				 * which can handle 64-bit offsets. May be
				 * NULL, and must be NULL if seekProc is
				 * NULL. */
    /*
     * Only valid in TCL_CHANNEL_VERSION_4 channels or later.
     * TIP #218, Channel Thread Actions.
     */
    Tcl_DriverThreadActionProc *threadActionProc;
				/* Function to call to notify the driver of
				 * thread specific activity for a channel. May
				 * be NULL. */
    /*
     * Only valid in TCL_CHANNEL_VERSION_5 channels or later.
     * TIP #208, File Truncation.
     */
    Tcl_DriverTruncateProc *truncateProc;
				/* Function to call to truncate the underlying
				 * file to a particular length. May be NULL if
				 * the channel does not support truncation. */
} Tcl_ChannelType;

/*
 * The following flags determine whether the blockModeProc above should set
 * the channel into blocking or nonblocking mode. They are passed as arguments
 * to the blockModeProc function in the above structure.
 */

#define TCL_MODE_BLOCKING	0	/* Put channel into blocking mode. */
#define TCL_MODE_NONBLOCKING	1	/* Put channel into nonblocking
					 * mode. */

/*
 *----------------------------------------------------------------------------
 * Enum for different types of file paths.
 */

typedef enum Tcl_PathType {
    TCL_PATH_ABSOLUTE,
    TCL_PATH_RELATIVE,
    TCL_PATH_VOLUME_RELATIVE
} Tcl_PathType;

/*
 * The following structure is used to pass glob type data amongst the various
 * glob routines and Tcl_FSMatchInDirectory.
 */

typedef struct Tcl_GlobTypeData {
    int type;			/* Corresponds to bcdpfls as in 'find -t'. */
    int perm;			/* Corresponds to file permissions. */
    Tcl_Obj *macType;		/* Acceptable Mac type. */
    Tcl_Obj *macCreator;	/* Acceptable Mac creator. */
} Tcl_GlobTypeData;

/*
 * Type and permission definitions for glob command.
 */

#define TCL_GLOB_TYPE_BLOCK		(1<<0)
#define TCL_GLOB_TYPE_CHAR		(1<<1)
#define TCL_GLOB_TYPE_DIR		(1<<2)
#define TCL_GLOB_TYPE_PIPE		(1<<3)
#define TCL_GLOB_TYPE_FILE		(1<<4)
#define TCL_GLOB_TYPE_LINK		(1<<5)
#define TCL_GLOB_TYPE_SOCK		(1<<6)
#define TCL_GLOB_TYPE_MOUNT		(1<<7)

#define TCL_GLOB_PERM_RONLY		(1<<0)
#define TCL_GLOB_PERM_HIDDEN		(1<<1)
#define TCL_GLOB_PERM_R			(1<<2)
#define TCL_GLOB_PERM_W			(1<<3)
#define TCL_GLOB_PERM_X			(1<<4)

/*
 * Flags for the unload callback function.
 */

#define TCL_UNLOAD_DETACH_FROM_INTERPRETER	(1<<0)
#define TCL_UNLOAD_DETACH_FROM_PROCESS		(1<<1)

/*
 * Typedefs for the various filesystem operations:
 */

typedef int (Tcl_FSStatProc) (Tcl_Obj *pathPtr, Tcl_StatBuf *buf);
typedef int (Tcl_FSAccessProc) (Tcl_Obj *pathPtr, int mode);
typedef Tcl_Channel (Tcl_FSOpenFileChannelProc) (Tcl_Interp *interp,
	Tcl_Obj *pathPtr, int mode, int permissions);
typedef int (Tcl_FSMatchInDirectoryProc) (Tcl_Interp *interp, Tcl_Obj *result,
	Tcl_Obj *pathPtr, const char *pattern, Tcl_GlobTypeData *types);
typedef Tcl_Obj * (Tcl_FSGetCwdProc) (Tcl_Interp *interp);
typedef int (Tcl_FSChdirProc) (Tcl_Obj *pathPtr);
typedef int (Tcl_FSLstatProc) (Tcl_Obj *pathPtr, Tcl_StatBuf *buf);
typedef int (Tcl_FSCreateDirectoryProc) (Tcl_Obj *pathPtr);
typedef int (Tcl_FSDeleteFileProc) (Tcl_Obj *pathPtr);
typedef int (Tcl_FSCopyDirectoryProc) (Tcl_Obj *srcPathPtr,
	Tcl_Obj *destPathPtr, Tcl_Obj **errorPtr);
typedef int (Tcl_FSCopyFileProc) (Tcl_Obj *srcPathPtr, Tcl_Obj *destPathPtr);
typedef int (Tcl_FSRemoveDirectoryProc) (Tcl_Obj *pathPtr, int recursive,
	Tcl_Obj **errorPtr);
typedef int (Tcl_FSRenameFileProc) (Tcl_Obj *srcPathPtr, Tcl_Obj *destPathPtr);
typedef void (Tcl_FSUnloadFileProc) (Tcl_LoadHandle loadHandle);
typedef Tcl_Obj * (Tcl_FSListVolumesProc) (void);
/* We have to declare the utime structure here. */
struct utimbuf;
typedef int (Tcl_FSUtimeProc) (Tcl_Obj *pathPtr, struct utimbuf *tval);
typedef int (Tcl_FSNormalizePathProc) (Tcl_Interp *interp, Tcl_Obj *pathPtr,
	int nextCheckpoint);
typedef int (Tcl_FSFileAttrsGetProc) (Tcl_Interp *interp, int index,
	Tcl_Obj *pathPtr, Tcl_Obj **objPtrRef);
typedef const char *CONST86 * (Tcl_FSFileAttrStringsProc) (Tcl_Obj *pathPtr,
	Tcl_Obj **objPtrRef);
typedef int (Tcl_FSFileAttrsSetProc) (Tcl_Interp *interp, int index,
	Tcl_Obj *pathPtr, Tcl_Obj *objPtr);
typedef Tcl_Obj * (Tcl_FSLinkProc) (Tcl_Obj *pathPtr, Tcl_Obj *toPtr,
	int linkType);
typedef int (Tcl_FSLoadFileProc) (Tcl_Interp *interp, Tcl_Obj *pathPtr,
	Tcl_LoadHandle *handlePtr, Tcl_FSUnloadFileProc **unloadProcPtr);
typedef int (Tcl_FSPathInFilesystemProc) (Tcl_Obj *pathPtr,
	ClientData *clientDataPtr);
typedef Tcl_Obj * (Tcl_FSFilesystemPathTypeProc) (Tcl_Obj *pathPtr);
typedef Tcl_Obj * (Tcl_FSFilesystemSeparatorProc) (Tcl_Obj *pathPtr);
typedef void (Tcl_FSFreeInternalRepProc) (ClientData clientData);
typedef ClientData (Tcl_FSDupInternalRepProc) (ClientData clientData);
typedef Tcl_Obj * (Tcl_FSInternalToNormalizedProc) (ClientData clientData);
typedef ClientData (Tcl_FSCreateInternalRepProc) (Tcl_Obj *pathPtr);

typedef struct Tcl_FSVersion_ *Tcl_FSVersion;

/*
 *----------------------------------------------------------------------------
 * Data structures related to hooking into the filesystem
 */

/*
 * Filesystem version tag.  This was introduced in 8.4.
 */

#define TCL_FILESYSTEM_VERSION_1	((Tcl_FSVersion) 0x1)

/*
 * struct Tcl_Filesystem:
 *
 * One such structure exists for each type (kind) of filesystem. It collects
 * together the functions that form the interface for a particulr the
 * filesystem. Tcl always accesses the filesystem through one of these
 * structures.
 *
 * Not all entries need be non-NULL; any which are NULL are simply ignored.
 * However, a complete filesystem should provide all of these functions. The
 * explanations in the structure show the importance of each function.
 */

typedef struct Tcl_Filesystem {
    const char *typeName;	/* The name of the filesystem. */
    int structureLength;	/* Length of this structure, so future binary
				 * compatibility can be assured. */
    Tcl_FSVersion version;	/* Version of the filesystem type. */
    Tcl_FSPathInFilesystemProc *pathInFilesystemProc;
				/* Determines whether the pathname is in this
				 * filesystem. This is the most important
				 * filesystem function. */
    Tcl_FSDupInternalRepProc *dupInternalRepProc;
				/* Duplicates the internal handle of the node.
				 * If it is NULL, the filesystem is less
				 * performant. */
    Tcl_FSFreeInternalRepProc *freeInternalRepProc;
				/* Frees the internal handle of the node.  NULL
				 * only if there is no need to free resources
				 * used for the internal handle. */
    Tcl_FSInternalToNormalizedProc *internalToNormalizedProc;
				/* Converts the internal handle to a normalized
				 * path.  NULL if the filesystem creates nodes
				 * having no pathname. */
    Tcl_FSCreateInternalRepProc *createInternalRepProc;
				/* Creates an internal handle for a pathname.
				 * May be NULL if pathnames have no internal
				 * handle or if pathInFilesystemProc always
				 * immediately creates an internal
				 * representation for pathnames in the
				 * filesystem. */
    Tcl_FSNormalizePathProc *normalizePathProc;
				/* Normalizes a path.  Should be implemented if
				 * the filesystems supports multiple paths to
				 * the same node. */
    Tcl_FSFilesystemPathTypeProc *filesystemPathTypeProc;
				/* Determines the type of a path in this
				 * filesystem. May be NULL. */
    Tcl_FSFilesystemSeparatorProc *filesystemSeparatorProc;
				/* Produces the separator character(s) for this
				 * filesystem. Must not be NULL. */
    Tcl_FSStatProc *statProc;	/* Called by 'Tcl_FSStat()'.  Provided by any
				 * reasonable filesystem. */
    Tcl_FSAccessProc *accessProc;
				/* Called by 'Tcl_FSAccess()'.  Implemented by
				 * any reasonable filesystem. */
    Tcl_FSOpenFileChannelProc *openFileChannelProc;
				/* Called by 'Tcl_FSOpenFileChannel()'.
				 * Provided by any reasonable filesystem. */
    Tcl_FSMatchInDirectoryProc *matchInDirectoryProc;
				/* Called by 'Tcl_FSMatchInDirectory()'.  NULL
				 * if the filesystem does not support glob or
				 * recursive copy. */
    Tcl_FSUtimeProc *utimeProc;	/* Called by 'Tcl_FSUtime()', by 'file
				 *  mtime' to set (not read) times, 'file
				 *  atime', and the open-r/open-w/fcopy variant
				 *  of 'file copy'. */
    Tcl_FSLinkProc *linkProc;	/* Called by 'Tcl_FSLink()'. NULL if reading or
				 *  creating links is not supported. */
    Tcl_FSListVolumesProc *listVolumesProc;
				/* Lists filesystem volumes added by this
				 * filesystem. NULL if the filesystem does not
				 * use volumes. */
    Tcl_FSFileAttrStringsProc *fileAttrStringsProc;
				/* List all valid attributes strings.  NULL if
				 * the filesystem does not support the 'file
				 * attributes' command.  Can be used to attach
				 * arbitrary additional data to files in a
				 * filesystem. */
    Tcl_FSFileAttrsGetProc *fileAttrsGetProc;
				/* Called by 'Tcl_FSFileAttrsGet()' and by
				 * 'file attributes'. */
    Tcl_FSFileAttrsSetProc *fileAttrsSetProc;
				/* Called by 'Tcl_FSFileAttrsSet()' and by
				 * 'file attributes'.  */
    Tcl_FSCreateDirectoryProc *createDirectoryProc;
				/* Called by 'Tcl_FSCreateDirectory()'.  May be
				 * NULL if the filesystem is read-only. */
    Tcl_FSRemoveDirectoryProc *removeDirectoryProc;
				/* Called by 'Tcl_FSRemoveDirectory()'.  May be
				 * NULL if the filesystem is read-only. */
    Tcl_FSDeleteFileProc *deleteFileProc;
				/* Called by 'Tcl_FSDeleteFile()' May be NULL
				 * if the filesystem is is read-only. */
    Tcl_FSCopyFileProc *copyFileProc;
				/* Called by 'Tcl_FSCopyFile()'.  If NULL, for
				 * a copy operation at the script level (not
				 * C) Tcl uses open-r, open-w and fcopy. */
    Tcl_FSRenameFileProc *renameFileProc;
				/* Called by 'Tcl_FSRenameFile()'. If NULL, for
				 * a rename operation at the script level (not
				 * C) Tcl performs a copy operation followed
				 * by a delete operation. */
    Tcl_FSCopyDirectoryProc *copyDirectoryProc;
				/* Called by 'Tcl_FSCopyDirectory()'. If NULL,
				 * for a copy operation at the script level
				 * (not C) Tcl recursively creates directories
				 * and copies files. */
    Tcl_FSLstatProc *lstatProc;	/* Called by 'Tcl_FSLstat()'. If NULL, Tcl
				 * attempts to use 'statProc' instead. */
    Tcl_FSLoadFileProc *loadFileProc;
				/* Called by 'Tcl_FSLoadFile()'. If NULL, Tcl
				 * performs a copy to a temporary file in the
				 * native filesystem and then calls
				 * Tcl_FSLoadFile() on that temporary copy. */
    Tcl_FSGetCwdProc *getCwdProc;
				/* Called by 'Tcl_FSGetCwd()'.  Normally NULL.
				 * Usually only called once:  If 'getcwd' is
				 * called before 'chdir' is ever called. */
    Tcl_FSChdirProc *chdirProc;	/* Called by 'Tcl_FSChdir()'.  For a virtual
				 * filesystem, chdirProc just returns zero
				 * (success) if the pathname is a valid
				 * directory, and some other value otherwise.
				 * For A real filesystem, chdirProc performs
				 * the correct action, e.g.  calls the system
				 * 'chdir' function. If not implemented, then
				 * 'cd' and 'pwd' fail for a pathname in this
				 * filesystem. On success Tcl stores the
				 * pathname for use by GetCwd.  If NULL, Tcl
				 * performs records the pathname as the new
				 * current directory if it passes a series of
				 * directory access checks. */
} Tcl_Filesystem;

/*
 * The following definitions are used as values for the 'linkAction' flag to
 * Tcl_FSLink, or the linkProc of any filesystem. Any combination of flags can
 * be given. For link creation, the linkProc should create a link which
 * matches any of the types given.
 *
 * TCL_CREATE_SYMBOLIC_LINK -	Create a symbolic or soft link.
 * TCL_CREATE_HARD_LINK -	Create a hard link.
 */

#define TCL_CREATE_SYMBOLIC_LINK	0x01
#define TCL_CREATE_HARD_LINK		0x02

/*
 *----------------------------------------------------------------------------
 * The following structure represents the Notifier functions that you can
 * override with the Tcl_SetNotifier call.
 */

typedef struct Tcl_NotifierProcs {
    Tcl_SetTimerProc *setTimerProc;
    Tcl_WaitForEventProc *waitForEventProc;
    Tcl_CreateFileHandlerProc *createFileHandlerProc;
    Tcl_DeleteFileHandlerProc *deleteFileHandlerProc;
    Tcl_InitNotifierProc *initNotifierProc;
    Tcl_FinalizeNotifierProc *finalizeNotifierProc;
    Tcl_AlertNotifierProc *alertNotifierProc;
    Tcl_ServiceModeHookProc *serviceModeHookProc;
} Tcl_NotifierProcs;

/*
 *----------------------------------------------------------------------------
 * The following data structures and declarations are for the new Tcl parser.
 *
 * For each word of a command, and for each piece of a word such as a variable
 * reference, one of the following structures is created to describe the
 * token.
 */

typedef struct Tcl_Token {
    int type;			/* Type of token, such as TCL_TOKEN_WORD; see
				 * below for valid types. */
    const char *start;		/* First character in token. */
    int size;			/* Number of bytes in token. */
    int numComponents;		/* If this token is composed of other tokens,
				 * this field tells how many of them there are
				 * (including components of components, etc.).
				 * The component tokens immediately follow
				 * this one. */
} Tcl_Token;

/*
 * Type values defined for Tcl_Token structures. These values are defined as
 * mask bits so that it's easy to check for collections of types.
 *
 * TCL_TOKEN_WORD -		The token describes one word of a command,
 *				from the first non-blank character of the word
 *				(which may be " or {) up to but not including
 *				the space, semicolon, or bracket that
 *				terminates the word. NumComponents counts the
 *				total number of sub-tokens that make up the
 *				word. This includes, for example, sub-tokens
 *				of TCL_TOKEN_VARIABLE tokens.
 * TCL_TOKEN_SIMPLE_WORD -	This token is just like TCL_TOKEN_WORD except
 *				that the word is guaranteed to consist of a
 *				single TCL_TOKEN_TEXT sub-token.
 * TCL_TOKEN_TEXT -		The token describes a range of literal text
 *				that is part of a word. NumComponents is
 *				always 0.
 * TCL_TOKEN_BS -		The token describes a backslash sequence that
 *				must be collapsed. NumComponents is always 0.
 * TCL_TOKEN_COMMAND -		The token describes a command whose result
 *				must be substituted into the word. The token
 *				includes the enclosing brackets. NumComponents
 *				is always 0.
 * TCL_TOKEN_VARIABLE -		The token describes a variable substitution,
 *				including the dollar sign, variable name, and
 *				array index (if there is one) up through the
 *				right parentheses. NumComponents tells how
 *				many additional tokens follow to represent the
 *				variable name. The first token will be a
 *				TCL_TOKEN_TEXT token that describes the
 *				variable name. If the variable is an array
 *				reference then there will be one or more
 *				additional tokens, of type TCL_TOKEN_TEXT,
 *				TCL_TOKEN_BS, TCL_TOKEN_COMMAND, and
 *				TCL_TOKEN_VARIABLE, that describe the array
 *				index; numComponents counts the total number
 *				of nested tokens that make up the variable
 *				reference, including sub-tokens of
 *				TCL_TOKEN_VARIABLE tokens.
 * TCL_TOKEN_SUB_EXPR -		The token describes one subexpression of an
 *				expression, from the first non-blank character
 *				of the subexpression up to but not including
 *				the space, brace, or bracket that terminates
 *				the subexpression. NumComponents counts the
 *				total number of following subtokens that make
 *				up the subexpression; this includes all
 *				subtokens for any nested TCL_TOKEN_SUB_EXPR
 *				tokens. For example, a numeric value used as a
 *				primitive operand is described by a
 *				TCL_TOKEN_SUB_EXPR token followed by a
 *				TCL_TOKEN_TEXT token. A binary subexpression
 *				is described by a TCL_TOKEN_SUB_EXPR token
 *				followed by the TCL_TOKEN_OPERATOR token for
 *				the operator, then TCL_TOKEN_SUB_EXPR tokens
 *				for the left then the right operands.
 * TCL_TOKEN_OPERATOR -		The token describes one expression operator.
 *				An operator might be the name of a math
 *				function such as "abs". A TCL_TOKEN_OPERATOR
 *				token is always preceded by one
 *				TCL_TOKEN_SUB_EXPR token for the operator's
 *				subexpression, and is followed by zero or more
 *				TCL_TOKEN_SUB_EXPR tokens for the operator's
 *				operands. NumComponents is always 0.
 * TCL_TOKEN_EXPAND_WORD -	This token is just like TCL_TOKEN_WORD except
 *				that it marks a word that began with the
 *				literal character prefix "{*}". This word is
 *				marked to be expanded - that is, broken into
 *				words after substitution is complete.
 */

#define TCL_TOKEN_WORD		1
#define TCL_TOKEN_SIMPLE_WORD	2
#define TCL_TOKEN_TEXT		4
#define TCL_TOKEN_BS		8
#define TCL_TOKEN_COMMAND	16
#define TCL_TOKEN_VARIABLE	32
#define TCL_TOKEN_SUB_EXPR	64
#define TCL_TOKEN_OPERATOR	128
#define TCL_TOKEN_EXPAND_WORD	256

/*
 * Parsing error types. On any parsing error, one of these values will be
 * stored in the error field of the Tcl_Parse structure defined below.
 */

#define TCL_PARSE_SUCCESS		0
#define TCL_PARSE_QUOTE_EXTRA		1
#define TCL_PARSE_BRACE_EXTRA		2
#define TCL_PARSE_MISSING_BRACE		3
#define TCL_PARSE_MISSING_BRACKET	4
#define TCL_PARSE_MISSING_PAREN		5
#define TCL_PARSE_MISSING_QUOTE		6
#define TCL_PARSE_MISSING_VAR_BRACE	7
#define TCL_PARSE_SYNTAX		8
#define TCL_PARSE_BAD_NUMBER		9

/*
 * A structure of the following type is filled in by Tcl_ParseCommand. It
 * describes a single command parsed from an input string.
 */

#define NUM_STATIC_TOKENS 20

typedef struct Tcl_Parse {
    const char *commentStart;	/* Pointer to # that begins the first of one
				 * or more comments preceding the command. */
    int commentSize;		/* Number of bytes in comments (up through
				 * newline character that terminates the last
				 * comment). If there were no comments, this
				 * field is 0. */
    const char *commandStart;	/* First character in first word of
				 * command. */
    int commandSize;		/* Number of bytes in command, including first
				 * character of first word, up through the
				 * terminating newline, close bracket, or
				 * semicolon. */
    int numWords;		/* Total number of words in command. May be
				 * 0. */
    Tcl_Token *tokenPtr;	/* Pointer to first token representing the
				 * words of the command. Initially points to
				 * staticTokens, but may change to point to
				 * malloc-ed space if command exceeds space in
				 * staticTokens. */
    int numTokens;		/* Total number of tokens in command. */
    int tokensAvailable;	/* Total number of tokens available at
				 * *tokenPtr. */
    int errorType;		/* One of the parsing error types defined
				 * above. */

    /*
     * The fields below are intended only for the private use of the parser.
     * They should not be used by functions that invoke Tcl_ParseCommand.
     */

    const char *string;		/* The original command string passed to
				 * Tcl_ParseCommand. */
    const char *end;		/* Points to the character just after the last
				 * one in the command string. */
    Tcl_Interp *interp;		/* Interpreter to use for error reporting, or
				 * NULL. */
    const char *term;		/* Points to character in string that
				 * terminated most recent token. Filled in by
				 * ParseTokens. If an error occurs, points to
				 * beginning of region where the error
				 * occurred (e.g. the open brace if the close
				 * brace is missing). */
    int incomplete;		/* This field is set to 1 by Tcl_ParseCommand
				 * if the command appears to be incomplete.
				 * This information is used by
				 * Tcl_CommandComplete. */
    Tcl_Token staticTokens[NUM_STATIC_TOKENS];
				/* Initial space for tokens for command. This
				 * space should be large enough to accommodate
				 * most commands; dynamic space is allocated
				 * for very large commands that don't fit
				 * here. */
} Tcl_Parse;

/*
 *----------------------------------------------------------------------------
 * The following structure represents a user-defined encoding. It collects
 * together all the functions that are used by the specific encoding.
 */

typedef struct Tcl_EncodingType {
    const char *encodingName;	/* The name of the encoding, e.g. "euc-jp".
				 * This name is the unique key for this
				 * encoding type. */
    Tcl_EncodingConvertProc *toUtfProc;
				/* Function to convert from external encoding
				 * into UTF-8. */
    Tcl_EncodingConvertProc *fromUtfProc;
				/* Function to convert from UTF-8 into
				 * external encoding. */
    Tcl_EncodingFreeProc *freeProc;
				/* If non-NULL, function to call when this
				 * encoding is deleted. */
    ClientData clientData;	/* Arbitrary value associated with encoding
				 * type. Passed to conversion functions. */
    int nullSize;		/* Number of zero bytes that signify
				 * end-of-string in this encoding. This number
				 * is used to determine the source string
				 * length when the srcLen argument is
				 * negative. Must be 1 or 2. */
} Tcl_EncodingType;

/*
 * The following definitions are used as values for the conversion control
 * flags argument when converting text from one character set to another:
 *
 * TCL_ENCODING_START -		Signifies that the source buffer is the first
 *				block in a (potentially multi-block) input
 *				stream. Tells the conversion function to reset
 *				to an initial state and perform any
 *				initialization that needs to occur before the
 *				first byte is converted. If the source buffer
 *				contains the entire input stream to be
 *				converted, this flag should be set.
 * TCL_ENCODING_END -		Signifies that the source buffer is the last
 *				block in a (potentially multi-block) input
 *				stream. Tells the conversion routine to
 *				perform any finalization that needs to occur
 *				after the last byte is converted and then to
 *				reset to an initial state. If the source
 *				buffer contains the entire input stream to be
 *				converted, this flag should be set.
 * TCL_ENCODING_STOPONERROR -	If set, the converter returns immediately upon
 *				encountering an invalid byte sequence or a
 *				source character that has no mapping in the
 *				target encoding. If clear, the converter
 *				substitues the problematic character(s) with
 *				one or more "close" characters in the
 *				destination buffer and then continues to
 *				convert the source.
 * TCL_ENCODING_NO_TERMINATE - 	If set, Tcl_ExternalToUtf does not append a
 *				terminating NUL byte.  Since it does not need
 *				an extra byte for a terminating NUL, it fills
 *				all dstLen bytes with encoded UTF-8 content if
 *				needed.  If clear, a byte is reserved in the
 *				dst space for NUL termination, and a
 *				terminating NUL is appended.
 * TCL_ENCODING_CHAR_LIMIT -	If set and dstCharsPtr is not NULL, then
 *				Tcl_ExternalToUtf takes the initial value of
 *				*dstCharsPtr as a limit of the maximum number
 *				of chars to produce in the encoded UTF-8
 *				content.  Otherwise, the number of chars
 *				produced is controlled only by other limiting
 *				factors.
 */

#define TCL_ENCODING_START		0x01
#define TCL_ENCODING_END		0x02
#define TCL_ENCODING_STOPONERROR	0x04
#define TCL_ENCODING_NO_TERMINATE	0x08
#define TCL_ENCODING_CHAR_LIMIT		0x10

/*
 * The following definitions are the error codes returned by the conversion
 * routines:
 *
 * TCL_OK -			All characters were converted.
 * TCL_CONVERT_NOSPACE -	The output buffer would not have been large
 *				enough for all of the converted data; as many
 *				characters as could fit were converted though.
 * TCL_CONVERT_MULTIBYTE -	The last few bytes in the source string were
 *				the beginning of a multibyte sequence, but
 *				more bytes were needed to complete this
 *				sequence. A subsequent call to the conversion
 *				routine should pass the beginning of this
 *				unconverted sequence plus additional bytes
 *				from the source stream to properly convert the
 *				formerly split-up multibyte sequence.
 * TCL_CONVERT_SYNTAX -		The source stream contained an invalid
 *				character sequence. This may occur if the
 *				input stream has been damaged or if the input
 *				encoding method was misidentified. This error
 *				is reported only if TCL_ENCODING_STOPONERROR
 *				was specified.
 * TCL_CONVERT_UNKNOWN -	The source string contained a character that
 *				could not be represented in the target
 *				encoding. This error is reported only if
 *				TCL_ENCODING_STOPONERROR was specified.
 */

#define TCL_CONVERT_MULTIBYTE	(-1)
#define TCL_CONVERT_SYNTAX	(-2)
#define TCL_CONVERT_UNKNOWN	(-3)
#define TCL_CONVERT_NOSPACE	(-4)

/*
 * The maximum number of bytes that are necessary to represent a single
 * Unicode character in UTF-8. The valid values should be 3, 4 or 6. If 3 or
 * 4, then Tcl_UniChar must be 2-bytes in size (UCS-2) (the default). If 6,
 * then Tcl_UniChar must be 4-bytes in size (UCS-4). At this time UCS-2 mode
 * is the default and recommended mode. UCS-4 is experimental and not
 * recommended. It works for the core, but most extensions expect UCS-2.
 */

#ifndef TCL_UTF_MAX
#define TCL_UTF_MAX		3
#endif

/*
 * This represents a Unicode character. Any changes to this should also be
 * reflected in regcustom.h.
 */

#if TCL_UTF_MAX > 4
    /*
     * unsigned int isn't 100% accurate as it should be a strict 4-byte value.
     * The size of this value must be reflected correctly in regcustom.h.
     * XXX: Tcl is currently UCS-2 and planning UTF-16 for the Unicode
     * XXX: string rep that Tcl_UniChar represents.  Changing the size
     * XXX: of Tcl_UniChar is /not/ supported.
     */
typedef unsigned int Tcl_UniChar;
#else
typedef unsigned short Tcl_UniChar;
#endif

/*
 *----------------------------------------------------------------------------
 * TIP #59: The following structure is used in calls 'Tcl_RegisterConfig' to
 * provide the system with the embedded configuration data.
 */

typedef struct Tcl_Config {
    const char *key;		/* Configuration key to register. ASCII
				 * encoded, thus UTF-8. */
    const char *value;		/* The value associated with the key. System
				 * encoding. */
} Tcl_Config;

/*
 *----------------------------------------------------------------------------
 * Flags for TIP#143 limits, detailing which limits are active in an
 * interpreter. Used for Tcl_{Add,Remove}LimitHandler type argument.
 */

#define TCL_LIMIT_COMMANDS	0x01
#define TCL_LIMIT_TIME		0x02

/*
 * Structure containing information about a limit handler to be called when a
 * command- or time-limit is exceeded by an interpreter.
 */

typedef void (Tcl_LimitHandlerProc) (ClientData clientData, Tcl_Interp *interp);
typedef void (Tcl_LimitHandlerDeleteProc) (ClientData clientData);

/*
 *----------------------------------------------------------------------------
 * Override definitions for libtommath.
 */

typedef struct mp_int mp_int;
#define MP_INT_DECLARED
typedef unsigned int mp_digit;
#define MP_DIGIT_DECLARED

/*
 *----------------------------------------------------------------------------
 * Definitions needed for Tcl_ParseArgvObj routines.
 * Based on tkArgv.c.
 * Modifications from the original are copyright (c) Sam Bromley 2006
 */

typedef struct {
    int type;			/* Indicates the option type; see below. */
    const char *keyStr;		/* The key string that flags the option in the
				 * argv array. */
    void *srcPtr;		/* Value to be used in setting dst; usage
				 * depends on type.*/
    void *dstPtr;		/* Address of value to be modified; usage
				 * depends on type.*/
    const char *helpStr;	/* Documentation message describing this
				 * option. */
    ClientData clientData;	/* Word to pass to function callbacks. */
} Tcl_ArgvInfo;

/*
 * Legal values for the type field of a Tcl_ArgInfo: see the user
 * documentation for details.
 */

#define TCL_ARGV_CONSTANT	15
#define TCL_ARGV_INT		16
#define TCL_ARGV_STRING		17
#define TCL_ARGV_REST		18
#define TCL_ARGV_FLOAT		19
#define TCL_ARGV_FUNC		20
#define TCL_ARGV_GENFUNC	21
#define TCL_ARGV_HELP		22
#define TCL_ARGV_END		23

/*
 * Types of callback functions for the TCL_ARGV_FUNC and TCL_ARGV_GENFUNC
 * argument types:
 */

typedef int (Tcl_ArgvFuncProc)(ClientData clientData, Tcl_Obj *objPtr,
	void *dstPtr);
typedef int (Tcl_ArgvGenFuncProc)(ClientData clientData, Tcl_Interp *interp,
	int objc, Tcl_Obj *const *objv, void *dstPtr);

/*
 * Shorthand for commonly used argTable entries.
 */

#define TCL_ARGV_AUTO_HELP \
    {TCL_ARGV_HELP,	"-help",	NULL,	NULL, \
	    "Print summary of command-line options and abort", NULL}
#define TCL_ARGV_AUTO_REST \
    {TCL_ARGV_REST,	"--",		NULL,	NULL, \
	    "Marks the end of the options", NULL}
#define TCL_ARGV_TABLE_END \
    {TCL_ARGV_END, NULL, NULL, NULL, NULL, NULL}

/*
 *----------------------------------------------------------------------------
 * Definitions needed for Tcl_Zlib routines. [TIP #234]
 *
 * Constants for the format flags describing what sort of data format is
 * desired/expected for the Tcl_ZlibDeflate, Tcl_ZlibInflate and
 * Tcl_ZlibStreamInit functions.
 */

#define TCL_ZLIB_FORMAT_RAW	1
#define TCL_ZLIB_FORMAT_ZLIB	2
#define TCL_ZLIB_FORMAT_GZIP	4
#define TCL_ZLIB_FORMAT_AUTO	8

/*
 * Constants that describe whether the stream is to operate in compressing or
 * decompressing mode.
 */

#define TCL_ZLIB_STREAM_DEFLATE	16
#define TCL_ZLIB_STREAM_INFLATE	32

/*
 * Constants giving compression levels. Use of TCL_ZLIB_COMPRESS_DEFAULT is
 * recommended.
 */

#define TCL_ZLIB_COMPRESS_NONE	0
#define TCL_ZLIB_COMPRESS_FAST	1
#define TCL_ZLIB_COMPRESS_BEST	9
#define TCL_ZLIB_COMPRESS_DEFAULT (-1)

/*
 * Constants for types of flushing, used with Tcl_ZlibFlush.
 */

#define TCL_ZLIB_NO_FLUSH	0
#define TCL_ZLIB_FLUSH		2
#define TCL_ZLIB_FULLFLUSH	3
#define TCL_ZLIB_FINALIZE	4

/*
 *----------------------------------------------------------------------------
 * Definitions needed for the Tcl_LoadFile function. [TIP #416]
 */

#define TCL_LOAD_GLOBAL 1
#define TCL_LOAD_LAZY 2

/*
 *----------------------------------------------------------------------------
 * Single public declaration for NRE.
 */

typedef int (Tcl_NRPostProc) (ClientData data[], Tcl_Interp *interp,
				int result);

/*
 *----------------------------------------------------------------------------
 * The following constant is used to test for older versions of Tcl in the
 * stubs tables.
 */

#define TCL_STUB_MAGIC		((int) 0xFCA3BACF)

/*
 * The following function is required to be defined in all stubs aware
 * extensions. The function is actually implemented in the stub library, not
 * the main Tcl library, although there is a trivial implementation in the
 * main library in case an extension is statically linked into an application.
 */

const char *		Tcl_InitStubs(Tcl_Interp *interp, const char *version,
			    int exact);
const char *		TclTomMathInitializeStubs(Tcl_Interp *interp,
			    const char *version, int epoch, int revision);

/*
 * When not using stubs, make it a macro.
 */

#ifndef USE_TCL_STUBS
#define Tcl_InitStubs(interp, version, exact) \
    Tcl_PkgInitStubsCheck(interp, version, exact)
#endif

/*
 * Public functions that are not accessible via the stubs table.
 * Tcl_GetMemoryInfo is needed for AOLserver. [Bug 1868171]
 */

#define Tcl_Main(argc, argv, proc) Tcl_MainEx(argc, argv, proc, \
	    ((Tcl_CreateInterp)()))
EXTERN void		Tcl_MainEx(int argc, char **argv,
			    Tcl_AppInitProc *appInitProc, Tcl_Interp *interp);
EXTERN const char *	Tcl_PkgInitStubsCheck(Tcl_Interp *interp,
			    const char *version, int exact);
EXTERN void		Tcl_GetMemoryInfo(Tcl_DString *dsPtr);

/*
 *----------------------------------------------------------------------------
 * Include the public function declarations that are accessible via the stubs
 * table.
 */

#include "tclDecls.h"

/*
 * Include platform specific public function declarations that are accessible
 * via the stubs table. Make all TclOO symbols MODULE_SCOPE (which only
 * has effect on building it as a shared library). See ticket [3010352].
 */

#if defined(BUILD_tcl)
#   undef TCLAPI
#   define TCLAPI MODULE_SCOPE
#endif

#include "tclPlatDecls.h"

/*
 *----------------------------------------------------------------------------
 * The following declarations either map ckalloc and ckfree to malloc and
 * free, or they map them to functions with all sorts of debugging hooks
 * defined in tclCkalloc.c.
 */

#ifdef TCL_MEM_DEBUG

#   define ckalloc(x) \
    ((void *) Tcl_DbCkalloc((unsigned)(x), __FILE__, __LINE__))
#   define ckfree(x) \
    Tcl_DbCkfree((char *)(x), __FILE__, __LINE__)
#   define ckrealloc(x,y) \
    ((void *) Tcl_DbCkrealloc((char *)(x), (unsigned)(y), __FILE__, __LINE__))
#   define attemptckalloc(x) \
    ((void *) Tcl_AttemptDbCkalloc((unsigned)(x), __FILE__, __LINE__))
#   define attemptckrealloc(x,y) \
    ((void *) Tcl_AttemptDbCkrealloc((char *)(x), (unsigned)(y), __FILE__, __LINE__))

#else /* !TCL_MEM_DEBUG */

/*
 * If we are not using the debugging allocator, we should call the Tcl_Alloc,
 * et al. routines in order to guarantee that every module is using the same
 * memory allocator both inside and outside of the Tcl library.
 */

#   define ckalloc(x) \
    ((void *) Tcl_Alloc((unsigned)(x)))
#   define ckfree(x) \
    Tcl_Free((char *)(x))
#   define ckrealloc(x,y) \
    ((void *) Tcl_Realloc((char *)(x), (unsigned)(y)))
#   define attemptckalloc(x) \
    ((void *) Tcl_AttemptAlloc((unsigned)(x)))
#   define attemptckrealloc(x,y) \
    ((void *) Tcl_AttemptRealloc((char *)(x), (unsigned)(y)))
#   undef  Tcl_InitMemory
#   define Tcl_InitMemory(x)
#   undef  Tcl_DumpActiveMemory
#   define Tcl_DumpActiveMemory(x)
#   undef  Tcl_ValidateAllMemory
#   define Tcl_ValidateAllMemory(x,y)

#endif /* !TCL_MEM_DEBUG */

#ifdef TCL_MEM_DEBUG
#   define Tcl_IncrRefCount(objPtr) \
	Tcl_DbIncrRefCount(objPtr, __FILE__, __LINE__)
#   define Tcl_DecrRefCount(objPtr) \
	Tcl_DbDecrRefCount(objPtr, __FILE__, __LINE__)
#   define Tcl_IsShared(objPtr) \
	Tcl_DbIsShared(objPtr, __FILE__, __LINE__)
#else
#   define Tcl_IncrRefCount(objPtr) \
	++(objPtr)->refCount
    /*
     * Use do/while0 idiom for optimum correctness without compiler warnings.
     * https://wiki.c2.com/?TrivialDoWhileLoop
     */
#   define Tcl_DecrRefCount(objPtr) \
	do { \
	    Tcl_Obj *_objPtr = (objPtr); \
	    if (_objPtr->refCount-- <= 1) { \
		TclFreeObj(_objPtr); \
	    } \
	} while(0)
#   define Tcl_IsShared(objPtr) \
	((objPtr)->refCount > 1)
#endif

/*
 * Macros and definitions that help to debug the use of Tcl objects. When
 * TCL_MEM_DEBUG is defined, the Tcl_New declarations are overridden to call
 * debugging versions of the object creation functions.
 */

#ifdef TCL_MEM_DEBUG
#  undef  Tcl_NewBignumObj
#  define Tcl_NewBignumObj(val) \
     Tcl_DbNewBignumObj(val, __FILE__, __LINE__)
#  undef  Tcl_NewBooleanObj
#  define Tcl_NewBooleanObj(val) \
     Tcl_DbNewBooleanObj(val, __FILE__, __LINE__)
#  undef  Tcl_NewByteArrayObj
#  define Tcl_NewByteArrayObj(bytes, len) \
     Tcl_DbNewByteArrayObj(bytes, len, __FILE__, __LINE__)
#  undef  Tcl_NewDoubleObj
#  define Tcl_NewDoubleObj(val) \
     Tcl_DbNewDoubleObj(val, __FILE__, __LINE__)
#  undef  Tcl_NewIntObj
#  define Tcl_NewIntObj(val) \
     Tcl_DbNewLongObj(val, __FILE__, __LINE__)
#  undef  Tcl_NewListObj
#  define Tcl_NewListObj(objc, objv) \
     Tcl_DbNewListObj(objc, objv, __FILE__, __LINE__)
#  undef  Tcl_NewLongObj
#  define Tcl_NewLongObj(val) \
     Tcl_DbNewLongObj(val, __FILE__, __LINE__)
#  undef  Tcl_NewObj
#  define Tcl_NewObj() \
     Tcl_DbNewObj(__FILE__, __LINE__)
#  undef  Tcl_NewStringObj
#  define Tcl_NewStringObj(bytes, len) \
     Tcl_DbNewStringObj(bytes, len, __FILE__, __LINE__)
#  undef  Tcl_NewWideIntObj
#  define Tcl_NewWideIntObj(val) \
     Tcl_DbNewWideIntObj(val, __FILE__, __LINE__)
#endif /* TCL_MEM_DEBUG */

/*
 *----------------------------------------------------------------------------
 * Macros for clients to use to access fields of hash entries:
 */

#define Tcl_GetHashValue(h) ((h)->clientData)
#define Tcl_SetHashValue(h, value) ((h)->clientData = (ClientData) (value))
#define Tcl_GetHashKey(tablePtr, h) \
	((void *) (((tablePtr)->keyType == TCL_ONE_WORD_KEYS || \
		    (tablePtr)->keyType == TCL_CUSTOM_PTR_KEYS) \
		   ? (h)->key.oneWordValue \
		   : (h)->key.string))

/*
 * Macros to use for clients to use to invoke find and create functions for
 * hash tables:
 */

#undef  Tcl_FindHashEntry
#define Tcl_FindHashEntry(tablePtr, key) \
	(*((tablePtr)->findProc))(tablePtr, (const char *)(key))
#undef  Tcl_CreateHashEntry
#define Tcl_CreateHashEntry(tablePtr, key, newPtr) \
	(*((tablePtr)->createProc))(tablePtr, (const char *)(key), newPtr)

/*
 *----------------------------------------------------------------------------
 * Macros that eliminate the overhead of the thread synchronization functions
 * when compiling without thread support.
 */

#ifndef TCL_THREADS
#undef  Tcl_MutexLock
#define Tcl_MutexLock(mutexPtr)
#undef  Tcl_MutexUnlock
#define Tcl_MutexUnlock(mutexPtr)
#undef  Tcl_MutexFinalize
#define Tcl_MutexFinalize(mutexPtr)
#undef  Tcl_ConditionNotify
#define Tcl_ConditionNotify(condPtr)
#undef  Tcl_ConditionWait
#define Tcl_ConditionWait(condPtr, mutexPtr, timePtr)
#undef  Tcl_ConditionFinalize
#define Tcl_ConditionFinalize(condPtr)
#endif /* TCL_THREADS */

/*
 *----------------------------------------------------------------------------
 * Deprecated Tcl functions:
 */

#ifndef TCL_NO_DEPRECATED
/*
 * These function have been renamed. The old names are deprecated, but we
 * define these macros for backwards compatibility.
 */

#   define Tcl_Ckalloc		Tcl_Alloc
#   define Tcl_Ckfree		Tcl_Free
#   define Tcl_Ckrealloc	Tcl_Realloc
#   define Tcl_Return		Tcl_SetResult
#   define Tcl_TildeSubst	Tcl_TranslateFileName
#if !defined(__APPLE__) /* On OSX, there is a conflict with "mach/mach.h" */
#   define panic		Tcl_Panic
#endif
#   define panicVA		Tcl_PanicVA
#endif /* !TCL_NO_DEPRECATED */

/*
 *----------------------------------------------------------------------------
 * Convenience declaration of Tcl_AppInit for backwards compatibility. This
 * function is not *implemented* by the tcl library, so the storage class is
 * neither DLLEXPORT nor DLLIMPORT.
 */

extern Tcl_AppInitProc Tcl_AppInit;

#endif /* RC_INVOKED */

/*
 * end block for C++
 */

#ifdef __cplusplus
}
#endif

#endif /* _TCL */

/*
 * Local Variables:
 * mode: c
 * c-basic-offset: 4
 * fill-column: 78
 * End:
 */
