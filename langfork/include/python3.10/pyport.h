#ifndef Py_PYPORT_H
#define Py_PYPORT_H

#include "pyconfig.h" /* include for defines */

#include <inttypes.h>


/* Defines to build Python and its standard library:
 *
 * - Py_BUILD_CORE: Build Python core. Give access to Python internals, but
 *   should not be used by third-party modules.
 * - Py_BUILD_CORE_BUILTIN: Build a Python stdlib module as a built-in module.
 * - Py_BUILD_CORE_MODULE: Build a Python stdlib module as a dynamic library.
 *
 * Py_BUILD_CORE_BUILTIN and Py_BUILD_CORE_MODULE imply Py_BUILD_CORE.
 *
 * On Windows, Py_BUILD_CORE_MODULE exports "PyInit_xxx" symbol, whereas
 * Py_BUILD_CORE_BUILTIN does not.
 */
#if defined(Py_BUILD_CORE_BUILTIN) && !defined(Py_BUILD_CORE)
#  define Py_BUILD_CORE
#endif
#if defined(Py_BUILD_CORE_MODULE) && !defined(Py_BUILD_CORE)
#  define Py_BUILD_CORE
#endif


/**************************************************************************
Symbols and macros to supply platform-independent interfaces to basic
C language & library operations whose spellings vary across platforms.

Please try to make documentation here as clear as possible:  by definition,
the stuff here is trying to illuminate C's darkest corners.

Config #defines referenced here:

SIGNED_RIGHT_SHIFT_ZERO_FILLS
Meaning:  To be defined iff i>>j does not extend the sign bit when i is a
          signed integral type and i < 0.
Used in:  Py_ARITHMETIC_RIGHT_SHIFT

Py_DEBUG
Meaning:  Extra checks compiled in for debug mode.
Used in:  Py_SAFE_DOWNCAST

**************************************************************************/

/* typedefs for some C9X-defined synonyms for integral types.
 *
 * The names in Python are exactly the same as the C9X names, except with a
 * Py_ prefix.  Until C9X is universally implemented, this is the only way
 * to ensure that Python gets reliable names that don't conflict with names
 * in non-Python code that are playing their own tricks to define the C9X
 * names.
 *
 * NOTE: don't go nuts here!  Python has no use for *most* of the C9X
 * integral synonyms.  Only define the ones we actually need.
 */

/* long long is required. Ensure HAVE_LONG_LONG is defined for compatibility. */
#ifndef HAVE_LONG_LONG
#define HAVE_LONG_LONG 1
#endif
#ifndef PY_LONG_LONG
#define PY_LONG_LONG long long
/* If LLONG_MAX is defined in limits.h, use that. */
#define PY_LLONG_MIN LLONG_MIN
#define PY_LLONG_MAX LLONG_MAX
#define PY_ULLONG_MAX ULLONG_MAX
#endif

#define PY_UINT32_T uint32_t
#define PY_UINT64_T uint64_t

/* Signed variants of the above */
#define PY_INT32_T int32_t
#define PY_INT64_T int64_t

/* If PYLONG_BITS_IN_DIGIT is not defined then we'll use 30-bit digits if all
   the necessary integer types are available, and we're on a 64-bit platform
   (as determined by SIZEOF_VOID_P); otherwise we use 15-bit digits. */

#ifndef PYLONG_BITS_IN_DIGIT
#if SIZEOF_VOID_P >= 8
#define PYLONG_BITS_IN_DIGIT 30
#else
#define PYLONG_BITS_IN_DIGIT 15
#endif
#endif

/* uintptr_t is the C9X name for an unsigned integral type such that a
 * legitimate void* can be cast to uintptr_t and then back to void* again
 * without loss of information.  Similarly for intptr_t, wrt a signed
 * integral type.
 */
typedef uintptr_t       Py_uintptr_t;
typedef intptr_t        Py_intptr_t;

/* Py_ssize_t is a signed integral type such that sizeof(Py_ssize_t) ==
 * sizeof(size_t).  C99 doesn't define such a thing directly (size_t is an
 * unsigned integral type).  See PEP 353 for details.
 */
#ifdef HAVE_PY_SSIZE_T

#elif HAVE_SSIZE_T
typedef ssize_t         Py_ssize_t;
#elif SIZEOF_VOID_P == SIZEOF_SIZE_T
typedef Py_intptr_t     Py_ssize_t;
#else
#   error "Python needs a typedef for Py_ssize_t in pyport.h."
#endif

/* Py_hash_t is the same size as a pointer. */
#define SIZEOF_PY_HASH_T SIZEOF_SIZE_T
typedef Py_ssize_t Py_hash_t;
/* Py_uhash_t is the unsigned equivalent needed to calculate numeric hash. */
#define SIZEOF_PY_UHASH_T SIZEOF_SIZE_T
typedef size_t Py_uhash_t;

/* Only used for compatibility with code that may not be PY_SSIZE_T_CLEAN. */
#ifdef PY_SSIZE_T_CLEAN
typedef Py_ssize_t Py_ssize_clean_t;
#else
typedef int Py_ssize_clean_t;
#endif

/* Largest possible value of size_t. */
#define PY_SIZE_MAX SIZE_MAX

/* Largest positive value of type Py_ssize_t. */
#define PY_SSIZE_T_MAX ((Py_ssize_t)(((size_t)-1)>>1))
/* Smallest negative value of type Py_ssize_t. */
#define PY_SSIZE_T_MIN (-PY_SSIZE_T_MAX-1)

/* Macro kept for backward compatibility: use "z" in new code.
 *
 * PY_FORMAT_SIZE_T is a platform-specific modifier for use in a printf
 * format to convert an argument with the width of a size_t or Py_ssize_t.
 * C99 introduced "z" for this purpose, but old MSVCs had not supported it.
 * Since MSVC supports "z" since (at least) 2015, we can just use "z"
 * for new code.
 *
 * These "high level" Python format functions interpret "z" correctly on
 * all platforms (Python interprets the format string itself, and does whatever
 * the platform C requires to convert a size_t/Py_ssize_t argument):
 *
 *     PyBytes_FromFormat
 *     PyErr_Format
 *     PyBytes_FromFormatV
 *     PyUnicode_FromFormatV
 *
 * Lower-level uses require that you interpolate the correct format modifier
 * yourself (e.g., calling printf, fprintf, sprintf, PyOS_snprintf); for
 * example,
 *
 *     Py_ssize_t index;
 *     fprintf(stderr, "index %" PY_FORMAT_SIZE_T "d sucks\n", index);
 *
 * That will expand to %zd or to something else correct for a Py_ssize_t on
 * the platform.
 */
#ifndef PY_FORMAT_SIZE_T
#   define PY_FORMAT_SIZE_T "z"
#endif

/* Py_LOCAL can be used instead of static to get the fastest possible calling
 * convention for functions that are local to a given module.
 *
 * Py_LOCAL_INLINE does the same thing, and also explicitly requests inlining,
 * for platforms that support that.
 *
 * If PY_LOCAL_AGGRESSIVE is defined before python.h is included, more
 * "aggressive" inlining/optimization is enabled for the entire module.  This
 * may lead to code bloat, and may slow things down for those reasons.  It may
 * also lead to errors, if the code relies on pointer aliasing.  Use with
 * care.
 *
 * NOTE: You can only use this for functions that are entirely local to a
 * module; functions that are exported via method tables, callbacks, etc,
 * should keep using static.
 */

#if defined(_MSC_VER)
#  if defined(PY_LOCAL_AGGRESSIVE)
   /* enable more aggressive optimization for MSVC */
   /* active in both release and debug builds - see bpo-43271 */
#  pragma optimize("gt", on)
#endif
   /* ignore warnings if the compiler decides not to inline a function */
#  pragma warning(disable: 4710)
   /* fastest possible local call under MSVC */
#  define Py_LOCAL(type) static type __fastcall
#  define Py_LOCAL_INLINE(type) static __inline type __fastcall
#else
#  define Py_LOCAL(type) static type
#  define Py_LOCAL_INLINE(type) static inline type
#endif

/* Py_MEMCPY is kept for backwards compatibility,
 * see https://bugs.python.org/issue28126 */
#define Py_MEMCPY memcpy

#include <stdlib.h>

#ifdef HAVE_IEEEFP_H
#include <ieeefp.h>  /* needed for 'finite' declaration on some platforms */
#endif

#include <math.h> /* Moved here from the math section, before extern "C" */

/********************************************
 * WRAPPER FOR <time.h> and/or <sys/time.h> *
 ********************************************/

#ifdef TIME_WITH_SYS_TIME
#include <sys/time.h>
#include <time.h>
#else /* !TIME_WITH_SYS_TIME */
#ifdef HAVE_SYS_TIME_H
#include <sys/time.h>
#else /* !HAVE_SYS_TIME_H */
#include <time.h>
#endif /* !HAVE_SYS_TIME_H */
#endif /* !TIME_WITH_SYS_TIME */


/******************************
 * WRAPPER FOR <sys/select.h> *
 ******************************/

/* NB caller must include <sys/types.h> */

#ifdef HAVE_SYS_SELECT_H
#include <sys/select.h>
#endif /* !HAVE_SYS_SELECT_H */

/*******************************
 * stat() and fstat() fiddling *
 *******************************/

#ifdef HAVE_SYS_STAT_H
#include <sys/stat.h>
#elif defined(HAVE_STAT_H)
#include <stat.h>
#endif

#ifndef S_IFMT
/* VisualAge C/C++ Failed to Define MountType Field in sys/stat.h */
#define S_IFMT 0170000
#endif

#ifndef S_IFLNK
/* Windows doesn't define S_IFLNK but posixmodule.c maps
 * IO_REPARSE_TAG_SYMLINK to S_IFLNK */
#  define S_IFLNK 0120000
#endif

#ifndef S_ISREG
#define S_ISREG(x) (((x) & S_IFMT) == S_IFREG)
#endif

#ifndef S_ISDIR
#define S_ISDIR(x) (((x) & S_IFMT) == S_IFDIR)
#endif

#ifndef S_ISCHR
#define S_ISCHR(x) (((x) & S_IFMT) == S_IFCHR)
#endif

#ifdef __cplusplus
/* Move this down here since some C++ #include's don't like to be included
   inside an extern "C" */
extern "C" {
#endif


/* Py_ARITHMETIC_RIGHT_SHIFT
 * C doesn't define whether a right-shift of a signed integer sign-extends
 * or zero-fills.  Here a macro to force sign extension:
 * Py_ARITHMETIC_RIGHT_SHIFT(TYPE, I, J)
 *    Return I >> J, forcing sign extension.  Arithmetically, return the
 *    floor of I/2**J.
 * Requirements:
 *    I should have signed integer type.  In the terminology of C99, this can
 *    be either one of the five standard signed integer types (signed char,
 *    short, int, long, long long) or an extended signed integer type.
 *    J is an integer >= 0 and strictly less than the number of bits in the
 *    type of I (because C doesn't define what happens for J outside that
 *    range either).
 *    TYPE used to specify the type of I, but is now ignored.  It's been left
 *    in for backwards compatibility with versions <= 2.6 or 3.0.
 * Caution:
 *    I may be evaluated more than once.
 */
#ifdef SIGNED_RIGHT_SHIFT_ZERO_FILLS
#define Py_ARITHMETIC_RIGHT_SHIFT(TYPE, I, J) \
    ((I) < 0 ? -1-((-1-(I)) >> (J)) : (I) >> (J))
#else
#define Py_ARITHMETIC_RIGHT_SHIFT(TYPE, I, J) ((I) >> (J))
#endif

/* Py_FORCE_EXPANSION(X)
 * "Simply" returns its argument.  However, macro expansions within the
 * argument are evaluated.  This unfortunate trickery is needed to get
 * token-pasting to work as desired in some cases.
 */
#define Py_FORCE_EXPANSION(X) X

/* Py_SAFE_DOWNCAST(VALUE, WIDE, NARROW)
 * Cast VALUE to type NARROW from type WIDE.  In Py_DEBUG mode, this
 * assert-fails if any information is lost.
 * Caution:
 *    VALUE may be evaluated more than once.
 */
#ifdef Py_DEBUG
#define Py_SAFE_DOWNCAST(VALUE, WIDE, NARROW) \
    (assert((WIDE)(NARROW)(VALUE) == (VALUE)), (NARROW)(VALUE))
#else
#define Py_SAFE_DOWNCAST(VALUE, WIDE, NARROW) (NARROW)(VALUE)
#endif

/* Py_SET_ERRNO_ON_MATH_ERROR(x)
 * If a libm function did not set errno, but it looks like the result
 * overflowed or not-a-number, set errno to ERANGE or EDOM.  Set errno
 * to 0 before calling a libm function, and invoke this macro after,
 * passing the function result.
 * Caution:
 *    This isn't reliable.  See Py_OVERFLOWED comments.
 *    X is evaluated more than once.
 */
#if defined(__FreeBSD__) || defined(__OpenBSD__) || (defined(__hpux) && defined(__ia64))
#define _Py_SET_EDOM_FOR_NAN(X) if (isnan(X)) errno = EDOM;
#else
#define _Py_SET_EDOM_FOR_NAN(X) ;
#endif
#define Py_SET_ERRNO_ON_MATH_ERROR(X) \
    do { \
        if (errno == 0) { \
            if ((X) == Py_HUGE_VAL || (X) == -Py_HUGE_VAL) \
                errno = ERANGE; \
            else _Py_SET_EDOM_FOR_NAN(X) \
        } \
    } while(0)

/* Py_SET_ERANGE_IF_OVERFLOW(x)
 * An alias of Py_SET_ERRNO_ON_MATH_ERROR for backward-compatibility.
 */
#define Py_SET_ERANGE_IF_OVERFLOW(X) Py_SET_ERRNO_ON_MATH_ERROR(X)

/* Py_ADJUST_ERANGE1(x)
 * Py_ADJUST_ERANGE2(x, y)
 * Set errno to 0 before calling a libm function, and invoke one of these
 * macros after, passing the function result(s) (Py_ADJUST_ERANGE2 is useful
 * for functions returning complex results).  This makes two kinds of
 * adjustments to errno:  (A) If it looks like the platform libm set
 * errno=ERANGE due to underflow, clear errno. (B) If it looks like the
 * platform libm overflowed but didn't set errno, force errno to ERANGE.  In
 * effect, we're trying to force a useful implementation of C89 errno
 * behavior.
 * Caution:
 *    This isn't reliable.  See Py_OVERFLOWED comments.
 *    X and Y may be evaluated more than once.
 */
#define Py_ADJUST_ERANGE1(X)                                            \
    do {                                                                \
        if (errno == 0) {                                               \
            if ((X) == Py_HUGE_VAL || (X) == -Py_HUGE_VAL)              \
                errno = ERANGE;                                         \
        }                                                               \
        else if (errno == ERANGE && (X) == 0.0)                         \
            errno = 0;                                                  \
    } while(0)

#define Py_ADJUST_ERANGE2(X, Y)                                         \
    do {                                                                \
        if ((X) == Py_HUGE_VAL || (X) == -Py_HUGE_VAL ||                \
            (Y) == Py_HUGE_VAL || (Y) == -Py_HUGE_VAL) {                \
                        if (errno == 0)                                 \
                                errno = ERANGE;                         \
        }                                                               \
        else if (errno == ERANGE)                                       \
            errno = 0;                                                  \
    } while(0)

/*  The functions _Py_dg_strtod and _Py_dg_dtoa in Python/dtoa.c (which are
 *  required to support the short float repr introduced in Python 3.1) require
 *  that the floating-point unit that's being used for arithmetic operations
 *  on C doubles is set to use 53-bit precision.  It also requires that the
 *  FPU rounding mode is round-half-to-even, but that's less often an issue.
 *
 *  If your FPU isn't already set to 53-bit precision/round-half-to-even, and
 *  you want to make use of _Py_dg_strtod and _Py_dg_dtoa, then you should
 *
 *     #define HAVE_PY_SET_53BIT_PRECISION 1
 *
 *  and also give appropriate definitions for the following three macros:
 *
 *    _PY_SET_53BIT_PRECISION_START : store original FPU settings, and
 *        set FPU to 53-bit precision/round-half-to-even
 *    _PY_SET_53BIT_PRECISION_END : restore original FPU settings
 *    _PY_SET_53BIT_PRECISION_HEADER : any variable declarations needed to
 *        use the two macros above.
 *
 * The macros are designed to be used within a single C function: see
 * Python/pystrtod.c for an example of their use.
 */

/* get and set x87 control word for gcc/x86 */
#ifdef HAVE_GCC_ASM_FOR_X87
#define HAVE_PY_SET_53BIT_PRECISION 1
/* _Py_get/set_387controlword functions are defined in Python/pymath.c */
#define _Py_SET_53BIT_PRECISION_HEADER                          \
    unsigned short old_387controlword, new_387controlword
#define _Py_SET_53BIT_PRECISION_START                                   \
    do {                                                                \
        old_387controlword = _Py_get_387controlword();                  \
        new_387controlword = (old_387controlword & ~0x0f00) | 0x0200; \
        if (new_387controlword != old_387controlword)                   \
            _Py_set_387controlword(new_387controlword);                 \
    } while (0)
#define _Py_SET_53BIT_PRECISION_END                             \
    if (new_387controlword != old_387controlword)               \
        _Py_set_387controlword(old_387controlword)
#endif

/* get and set x87 control word for VisualStudio/x86 */
#if defined(_MSC_VER) && !defined(_WIN64) && !defined(_M_ARM) /* x87 not supported in 64-bit or ARM */
#define HAVE_PY_SET_53BIT_PRECISION 1
#define _Py_SET_53BIT_PRECISION_HEADER \
    unsigned int old_387controlword, new_387controlword, out_387controlword
/* We use the __control87_2 function to set only the x87 control word.
   The SSE control word is unaffected. */
#define _Py_SET_53BIT_PRECISION_START                                   \
    do {                                                                \
        __control87_2(0, 0, &old_387controlword, NULL);                 \
        new_387controlword =                                            \
          (old_387controlword & ~(_MCW_PC | _MCW_RC)) | (_PC_53 | _RC_NEAR); \
        if (new_387controlword != old_387controlword)                   \
            __control87_2(new_387controlword, _MCW_PC | _MCW_RC,        \
                          &out_387controlword, NULL);                   \
    } while (0)
#define _Py_SET_53BIT_PRECISION_END                                     \
    do {                                                                \
        if (new_387controlword != old_387controlword)                   \
            __control87_2(old_387controlword, _MCW_PC | _MCW_RC,        \
                          &out_387controlword, NULL);                   \
    } while (0)
#endif

#ifdef HAVE_GCC_ASM_FOR_MC68881
#define HAVE_PY_SET_53BIT_PRECISION 1
#define _Py_SET_53BIT_PRECISION_HEADER \
  unsigned int old_fpcr, new_fpcr
#define _Py_SET_53BIT_PRECISION_START                                   \
  do {                                                                  \
    __asm__ ("fmove.l %%fpcr,%0" : "=g" (old_fpcr));                    \
    /* Set double precision / round to nearest.  */                     \
    new_fpcr = (old_fpcr & ~0xf0) | 0x80;                               \
    if (new_fpcr != old_fpcr)                                           \
      __asm__ volatile ("fmove.l %0,%%fpcr" : : "g" (new_fpcr));        \
  } while (0)
#define _Py_SET_53BIT_PRECISION_END                                     \
  do {                                                                  \
    if (new_fpcr != old_fpcr)                                           \
      __asm__ volatile ("fmove.l %0,%%fpcr" : : "g" (old_fpcr));        \
  } while (0)
#endif

/* default definitions are empty */
#ifndef HAVE_PY_SET_53BIT_PRECISION
#define _Py_SET_53BIT_PRECISION_HEADER
#define _Py_SET_53BIT_PRECISION_START
#define _Py_SET_53BIT_PRECISION_END
#endif

/* If we can't guarantee 53-bit precision, don't use the code
   in Python/dtoa.c, but fall back to standard code.  This
   means that repr of a float will be long (17 sig digits).

   Realistically, there are two things that could go wrong:

   (1) doubles aren't IEEE 754 doubles, or
   (2) we're on x86 with the rounding precision set to 64-bits
       (extended precision), and we don't know how to change
       the rounding precision.
 */

#if !defined(DOUBLE_IS_LITTLE_ENDIAN_IEEE754) && \
    !defined(DOUBLE_IS_BIG_ENDIAN_IEEE754) && \
    !defined(DOUBLE_IS_ARM_MIXED_ENDIAN_IEEE754)
#define PY_NO_SHORT_FLOAT_REPR
#endif

/* double rounding is symptomatic of use of extended precision on x86.  If
   we're seeing double rounding, and we don't have any mechanism available for
   changing the FPU rounding precision, then don't use Python/dtoa.c. */
#if defined(X87_DOUBLE_ROUNDING) && !defined(HAVE_PY_SET_53BIT_PRECISION)
#define PY_NO_SHORT_FLOAT_REPR
#endif


/* Py_DEPRECATED(version)
 * Declare a variable, type, or function deprecated.
 * The macro must be placed before the declaration.
 * Usage:
 *    Py_DEPRECATED(3.3) extern int old_var;
 *    Py_DEPRECATED(3.4) typedef int T1;
 *    Py_DEPRECATED(3.8) PyAPI_FUNC(int) Py_OldFunction(void);
 */
#if defined(__GNUC__) \
    && ((__GNUC__ >= 4) || (__GNUC__ == 3) && (__GNUC_MINOR__ >= 1))
#define Py_DEPRECATED(VERSION_UNUSED) __attribute__((__deprecated__))
#elif defined(_MSC_VER)
#define Py_DEPRECATED(VERSION) __declspec(deprecated( \
                                          "deprecated in " #VERSION))
#else
#define Py_DEPRECATED(VERSION_UNUSED)
#endif

#if defined(__clang__)
#define _Py_COMP_DIAG_PUSH _Pragma("clang diagnostic push")
#define _Py_COMP_DIAG_IGNORE_DEPR_DECLS \
    _Pragma("clang diagnostic ignored \"-Wdeprecated-declarations\"")
#define _Py_COMP_DIAG_POP _Pragma("clang diagnostic pop")
#elif defined(__GNUC__) \
    && ((__GNUC__ >= 5) || (__GNUC__ == 4) && (__GNUC_MINOR__ >= 6))
#define _Py_COMP_DIAG_PUSH _Pragma("GCC diagnostic push")
#define _Py_COMP_DIAG_IGNORE_DEPR_DECLS \
    _Pragma("GCC diagnostic ignored \"-Wdeprecated-declarations\"")
#define _Py_COMP_DIAG_POP _Pragma("GCC diagnostic pop")
#elif defined(_MSC_VER)
#define _Py_COMP_DIAG_PUSH __pragma(warning(push))
#define _Py_COMP_DIAG_IGNORE_DEPR_DECLS __pragma(warning(disable: 4996))
#define _Py_COMP_DIAG_POP __pragma(warning(pop))
#else
#define _Py_COMP_DIAG_PUSH
#define _Py_COMP_DIAG_IGNORE_DEPR_DECLS
#define _Py_COMP_DIAG_POP
#endif

/* _Py_HOT_FUNCTION
 * The hot attribute on a function is used to inform the compiler that the
 * function is a hot spot of the compiled program. The function is optimized
 * more aggressively and on many target it is placed into special subsection of
 * the text section so all hot functions appears close together improving
 * locality.
 *
 * Usage:
 *    int _Py_HOT_FUNCTION x(void) { return 3; }
 *
 * Issue #28618: This attribute must not be abused, otherwise it can have a
 * negative effect on performance. Only the functions were Python spend most of
 * its time must use it. Use a profiler when running performance benchmark
 * suite to find these functions.
 */
#if defined(__GNUC__) \
    && ((__GNUC__ >= 5) || (__GNUC__ == 4) && (__GNUC_MINOR__ >= 3))
#define _Py_HOT_FUNCTION __attribute__((hot))
#else
#define _Py_HOT_FUNCTION
#endif

/* _Py_NO_INLINE
 * Disable inlining on a function. For example, it helps to reduce the C stack
 * consumption.
 *
 * Usage:
 *    int _Py_NO_INLINE x(void) { return 3; }
 */
#if defined(_MSC_VER)
#  define _Py_NO_INLINE __declspec(noinline)
#elif defined(__GNUC__) || defined(__clang__)
#  define _Py_NO_INLINE __attribute__ ((noinline))
#else
#  define _Py_NO_INLINE
#endif

/**************************************************************************
Prototypes that are missing from the standard include files on some systems
(and possibly only some versions of such systems.)

Please be conservative with adding new ones, document them and enclose them
in platform-specific #ifdefs.
**************************************************************************/

#ifdef SOLARIS
/* Unchecked */
extern int gethostname(char *, int);
#endif

#ifdef HAVE__GETPTY
#include <sys/types.h>          /* we need to import mode_t */
extern char * _getpty(int *, int, mode_t, int);
#endif

/* On QNX 6, struct termio must be declared by including sys/termio.h
   if TCGETA, TCSETA, TCSETAW, or TCSETAF are used.  sys/termio.h must
   be included before termios.h or it will generate an error. */
#if defined(HAVE_SYS_TERMIO_H) && !defined(__hpux)
#include <sys/termio.h>
#endif


/* On 4.4BSD-descendants, ctype functions serves the whole range of
 * wchar_t character set rather than single byte code points only.
 * This characteristic can break some operations of string object
 * including str.upper() and str.split() on UTF-8 locales.  This
 * workaround was provided by Tim Robbins of FreeBSD project.
 */

#if defined(__APPLE__)
#  define _PY_PORT_CTYPE_UTF8_ISSUE
#endif

#ifdef _PY_PORT_CTYPE_UTF8_ISSUE
#ifndef __cplusplus
   /* The workaround below is unsafe in C++ because
    * the <locale> defines these symbols as real functions,
    * with a slightly different signature.
    * See issue #10910
    */
#include <ctype.h>
#include <wctype.h>
#undef isalnum
#define isalnum(c) iswalnum(btowc(c))
#undef isalpha
#define isalpha(c) iswalpha(btowc(c))
#undef islower
#define islower(c) iswlower(btowc(c))
#undef isspace
#define isspace(c) iswspace(btowc(c))
#undef isupper
#define isupper(c) iswupper(btowc(c))
#undef tolower
#define tolower(c) towlower(btowc(c))
#undef toupper
#define toupper(c) towupper(btowc(c))
#endif
#endif


/* Declarations for symbol visibility.

  PyAPI_FUNC(type): Declares a public Python API function and return type
  PyAPI_DATA(type): Declares public Python data and its type
  PyMODINIT_FUNC:   A Python module init function.  If these functions are
                    inside the Python core, they are private to the core.
                    If in an extension module, it may be declared with
                    external linkage depending on the platform.

  As a number of platforms support/require "__declspec(dllimport/dllexport)",
  we support a HAVE_DECLSPEC_DLL macro to save duplication.
*/

/*
  All windows ports, except cygwin, are handled in PC/pyconfig.h.

  Cygwin is the only other autoconf platform requiring special
  linkage handling and it uses __declspec().
*/
#if defined(__CYGWIN__)
#       define HAVE_DECLSPEC_DLL
#endif

#include "exports.h"

/* only get special linkage if built as shared or platform is Cygwin */
#if defined(Py_ENABLE_SHARED) || defined(__CYGWIN__)
#       if defined(HAVE_DECLSPEC_DLL)
#               if defined(Py_BUILD_CORE) && !defined(Py_BUILD_CORE_MODULE)
#                       define PyAPI_FUNC(RTYPE) Py_EXPORTED_SYMBOL RTYPE
#                       define PyAPI_DATA(RTYPE) extern Py_EXPORTED_SYMBOL RTYPE
        /* module init functions inside the core need no external linkage */
        /* except for Cygwin to handle embedding */
#                       if defined(__CYGWIN__)
#                               define PyMODINIT_FUNC Py_EXPORTED_SYMBOL PyObject*
#                       else /* __CYGWIN__ */
#                               define PyMODINIT_FUNC PyObject*
#                       endif /* __CYGWIN__ */
#               else /* Py_BUILD_CORE */
        /* Building an extension module, or an embedded situation */
        /* public Python functions and data are imported */
        /* Under Cygwin, auto-import functions to prevent compilation */
        /* failures similar to those described at the bottom of 4.1: */
        /* http://docs.python.org/extending/windows.html#a-cookbook-approach */
#                       if !defined(__CYGWIN__)
#                               define PyAPI_FUNC(RTYPE) Py_IMPORTED_SYMBOL RTYPE
#                       endif /* !__CYGWIN__ */
#                       define PyAPI_DATA(RTYPE) extern Py_IMPORTED_SYMBOL RTYPE
        /* module init functions outside the core must be exported */
#                       if defined(__cplusplus)
#                               define PyMODINIT_FUNC extern "C" Py_EXPORTED_SYMBOL PyObject*
#                       else /* __cplusplus */
#                               define PyMODINIT_FUNC Py_EXPORTED_SYMBOL PyObject*
#                       endif /* __cplusplus */
#               endif /* Py_BUILD_CORE */
#       endif /* HAVE_DECLSPEC_DLL */
#endif /* Py_ENABLE_SHARED */

/* If no external linkage macros defined by now, create defaults */
#ifndef PyAPI_FUNC
#       define PyAPI_FUNC(RTYPE) Py_EXPORTED_SYMBOL RTYPE
#endif
#ifndef PyAPI_DATA
#       define PyAPI_DATA(RTYPE) extern Py_EXPORTED_SYMBOL RTYPE
#endif
#ifndef PyMODINIT_FUNC
#       if defined(__cplusplus)
#               define PyMODINIT_FUNC extern "C" Py_EXPORTED_SYMBOL PyObject*
#       else /* __cplusplus */
#               define PyMODINIT_FUNC Py_EXPORTED_SYMBOL PyObject*
#       endif /* __cplusplus */
#endif

/* limits.h constants that may be missing */

#ifndef INT_MAX
#define INT_MAX 2147483647
#endif

#ifndef LONG_MAX
#if SIZEOF_LONG == 4
#define LONG_MAX 0X7FFFFFFFL
#elif SIZEOF_LONG == 8
#define LONG_MAX 0X7FFFFFFFFFFFFFFFL
#else
#error "could not set LONG_MAX in pyport.h"
#endif
#endif

#ifndef LONG_MIN
#define LONG_MIN (-LONG_MAX-1)
#endif

#ifndef LONG_BIT
#define LONG_BIT (8 * SIZEOF_LONG)
#endif

#if LONG_BIT != 8 * SIZEOF_LONG
/* 04-Oct-2000 LONG_BIT is apparently (mis)defined as 64 on some recent
 * 32-bit platforms using gcc.  We try to catch that here at compile-time
 * rather than waiting for integer multiplication to trigger bogus
 * overflows.
 */
#error "LONG_BIT definition appears wrong for platform (bad gcc/glibc config?)."
#endif

#ifdef __cplusplus
}
#endif

/*
 * Hide GCC attributes from compilers that don't support them.
 */
#if (!defined(__GNUC__) || __GNUC__ < 2 || \
     (__GNUC__ == 2 && __GNUC_MINOR__ < 7) )
#define Py_GCC_ATTRIBUTE(x)
#else
#define Py_GCC_ATTRIBUTE(x) __attribute__(x)
#endif

/*
 * Specify alignment on compilers that support it.
 */
#if defined(__GNUC__) && __GNUC__ >= 3
#define Py_ALIGNED(x) __attribute__((aligned(x)))
#else
#define Py_ALIGNED(x)
#endif

/* Eliminate end-of-loop code not reached warnings from SunPro C
 * when using do{...}while(0) macros
 */
#ifdef __SUNPRO_C
#pragma error_messages (off,E_END_OF_LOOP_CODE_NOT_REACHED)
#endif

#ifndef Py_LL
#define Py_LL(x) x##LL
#endif

#ifndef Py_ULL
#define Py_ULL(x) Py_LL(x##U)
#endif

#define Py_VA_COPY va_copy

/*
 * Convenient macros to deal with endianness of the platform. WORDS_BIGENDIAN is
 * detected by configure and defined in pyconfig.h. The code in pyconfig.h
 * also takes care of Apple's universal builds.
 */

#ifdef WORDS_BIGENDIAN
#  define PY_BIG_ENDIAN 1
#  define PY_LITTLE_ENDIAN 0
#else
#  define PY_BIG_ENDIAN 0
#  define PY_LITTLE_ENDIAN 1
#endif

#ifdef Py_BUILD_CORE
/*
 * Macros to protect CRT calls against instant termination when passed an
 * invalid parameter (issue23524).
 */
#if defined _MSC_VER && _MSC_VER >= 1900

extern _invalid_parameter_handler _Py_silent_invalid_parameter_handler;
#define _Py_BEGIN_SUPPRESS_IPH { _invalid_parameter_handler _Py_old_handler = \
    _set_thread_local_invalid_parameter_handler(_Py_silent_invalid_parameter_handler);
#define _Py_END_SUPPRESS_IPH _set_thread_local_invalid_parameter_handler(_Py_old_handler); }

#else

#define _Py_BEGIN_SUPPRESS_IPH
#define _Py_END_SUPPRESS_IPH

#endif /* _MSC_VER >= 1900 */
#endif /* Py_BUILD_CORE */

#ifdef __ANDROID__
   /* The Android langinfo.h header is not used. */
#  undef HAVE_LANGINFO_H
#  undef CODESET
#endif

/* Maximum value of the Windows DWORD type */
#define PY_DWORD_MAX 4294967295U

/* This macro used to tell whether Python was built with multithreading
 * enabled.  Now multithreading is always enabled, but keep the macro
 * for compatibility.
 */
#ifndef WITH_THREAD
#  define WITH_THREAD
#endif

/* Check that ALT_SOABI is consistent with Py_TRACE_REFS:
   ./configure --with-trace-refs should must be used to define Py_TRACE_REFS */
#if defined(ALT_SOABI) && defined(Py_TRACE_REFS)
#  error "Py_TRACE_REFS ABI is not compatible with release and debug ABI"
#endif

#if defined(__ANDROID__) || defined(__VXWORKS__)
   // Use UTF-8 as the locale encoding, ignore the LC_CTYPE locale.
   // See _Py_GetLocaleEncoding(), PyUnicode_DecodeLocale()
   // and PyUnicode_EncodeLocale().
#  define _Py_FORCE_UTF8_LOCALE
#endif

#if defined(_Py_FORCE_UTF8_LOCALE) || defined(__APPLE__)
   // Use UTF-8 as the filesystem encoding.
   // See PyUnicode_DecodeFSDefaultAndSize(), PyUnicode_EncodeFSDefault(),
   // Py_DecodeLocale() and Py_EncodeLocale().
#  define _Py_FORCE_UTF8_FS_ENCODING
#endif

/* Mark a function which cannot return. Example:
   PyAPI_FUNC(void) _Py_NO_RETURN PyThread_exit_thread(void);

   XLC support is intentionally omitted due to bpo-40244 */
#ifndef _Py_NO_RETURN
#if defined(__clang__) || \
    (defined(__GNUC__) && \
     ((__GNUC__ >= 3) || \
      (__GNUC__ == 2) && (__GNUC_MINOR__ >= 5)))
#  define _Py_NO_RETURN __attribute__((__noreturn__))
#elif defined(_MSC_VER)
#  define _Py_NO_RETURN __declspec(noreturn)
#else
#  define _Py_NO_RETURN
#endif
#endif


// Preprocessor check for a builtin preprocessor function. Always return 0
// if __has_builtin() macro is not defined.
//
// __has_builtin() is available on clang and GCC 10.
#ifdef __has_builtin
#  define _Py__has_builtin(x) __has_builtin(x)
#else
#  define _Py__has_builtin(x) 0
#endif


#endif /* Py_PYPORT_H */
