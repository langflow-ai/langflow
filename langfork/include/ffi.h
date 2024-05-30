/* -----------------------------------------------------------------*-C-*-
   libffi 3.4.4
     - Copyright (c) 2011, 2014, 2019, 2021, 2022 Anthony Green
     - Copyright (c) 1996-2003, 2007, 2008 Red Hat, Inc.

   Permission is hereby granted, free of charge, to any person
   obtaining a copy of this software and associated documentation
   files (the ``Software''), to deal in the Software without
   restriction, including without limitation the rights to use, copy,
   modify, merge, publish, distribute, sublicense, and/or sell copies
   of the Software, and to permit persons to whom the Software is
   furnished to do so, subject to the following conditions:

   The above copyright notice and this permission notice shall be
   included in all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
   NONINFRINGEMENT.  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
   HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
   WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
   DEALINGS IN THE SOFTWARE.

   ----------------------------------------------------------------------- */

/* -------------------------------------------------------------------
   Most of the API is documented in doc/libffi.texi.

   The raw API is designed to bypass some of the argument packing and
   unpacking on architectures for which it can be avoided.  Routines
   are provided to emulate the raw API if the underlying platform
   doesn't allow faster implementation.

   More details on the raw API can be found in:

   http://gcc.gnu.org/ml/java/1999-q3/msg00138.html

   and

   http://gcc.gnu.org/ml/java/1999-q3/msg00174.html
   -------------------------------------------------------------------- */

#ifndef LIBFFI_H
#define LIBFFI_H

#ifdef __cplusplus
extern "C" {
#endif

/* Specify which architecture libffi is configured for. */
#ifndef X86_64
#define X86_64
#endif

/* ---- System configuration information --------------------------------- */

/* If these change, update src/mips/ffitarget.h. */
#define FFI_TYPE_VOID       0
#define FFI_TYPE_INT        1
#define FFI_TYPE_FLOAT      2
#define FFI_TYPE_DOUBLE     3
#if 1
#define FFI_TYPE_LONGDOUBLE 4
#else
#define FFI_TYPE_LONGDOUBLE FFI_TYPE_DOUBLE
#endif
#define FFI_TYPE_UINT8      5
#define FFI_TYPE_SINT8      6
#define FFI_TYPE_UINT16     7
#define FFI_TYPE_SINT16     8
#define FFI_TYPE_UINT32     9
#define FFI_TYPE_SINT32     10
#define FFI_TYPE_UINT64     11
#define FFI_TYPE_SINT64     12
#define FFI_TYPE_STRUCT     13
#define FFI_TYPE_POINTER    14
#define FFI_TYPE_COMPLEX    15

/* This should always refer to the last type code (for sanity checks).  */
#define FFI_TYPE_LAST       FFI_TYPE_COMPLEX

#include <ffitarget.h>

#ifndef LIBFFI_ASM

#if defined(_MSC_VER) && !defined(__clang__)
#define __attribute__(X)
#endif

#include <stddef.h>
#include <limits.h>

/* LONG_LONG_MAX is not always defined (not if STRICT_ANSI, for example).
   But we can find it either under the correct ANSI name, or under GNU
   C's internal name.  */

#define FFI_64_BIT_MAX 9223372036854775807

#ifdef LONG_LONG_MAX
# define FFI_LONG_LONG_MAX LONG_LONG_MAX
#else
# ifdef LLONG_MAX
#  define FFI_LONG_LONG_MAX LLONG_MAX
#  ifdef _AIX52 /* or newer has C99 LLONG_MAX */
#   undef FFI_64_BIT_MAX
#   define FFI_64_BIT_MAX 9223372036854775807LL
#  endif /* _AIX52 or newer */
# else
#  ifdef __GNUC__
#   define FFI_LONG_LONG_MAX __LONG_LONG_MAX__
#  endif
#  ifdef _AIX /* AIX 5.1 and earlier have LONGLONG_MAX */
#   ifndef __PPC64__
#    if defined (__IBMC__) || defined (__IBMCPP__)
#     define FFI_LONG_LONG_MAX LONGLONG_MAX
#    endif
#   endif /* __PPC64__ */
#   undef  FFI_64_BIT_MAX
#   define FFI_64_BIT_MAX 9223372036854775807LL
#  endif
# endif
#endif

/* The closure code assumes that this works on pointers, i.e. a size_t
   can hold a pointer.  */

typedef struct _ffi_type
{
  size_t size;
  unsigned short alignment;
  unsigned short type;
  struct _ffi_type **elements;
} ffi_type;

/* Need minimal decorations for DLLs to work on Windows.  GCC has
   autoimport and autoexport.  Always mark externally visible symbols
   as dllimport for MSVC clients, even if it means an extra indirection
   when using the static version of the library.
   Besides, as a workaround, they can define FFI_BUILDING if they
   *know* they are going to link with the static library.  */
#if defined _MSC_VER
# if defined FFI_BUILDING_DLL /* Building libffi.DLL with msvcc.sh */
#  define FFI_API __declspec(dllexport)
# elif !defined FFI_BUILDING  /* Importing libffi.DLL */
#  define FFI_API __declspec(dllimport)
# else                        /* Building/linking static library */
#  define FFI_API
# endif
#else
# define FFI_API
#endif

/* The externally visible type declarations also need the MSVC DLL
   decorations, or they will not be exported from the object file.  */
#if defined LIBFFI_HIDE_BASIC_TYPES
# define FFI_EXTERN FFI_API
#else
# define FFI_EXTERN extern FFI_API
#endif

#ifndef LIBFFI_HIDE_BASIC_TYPES
#if SCHAR_MAX == 127
# define ffi_type_uchar                ffi_type_uint8
# define ffi_type_schar                ffi_type_sint8
#else
 #error "char size not supported"
#endif

#if SHRT_MAX == 32767
# define ffi_type_ushort       ffi_type_uint16
# define ffi_type_sshort       ffi_type_sint16
#elif SHRT_MAX == 2147483647
# define ffi_type_ushort       ffi_type_uint32
# define ffi_type_sshort       ffi_type_sint32
#else
 #error "short size not supported"
#endif

#if INT_MAX == 32767
# define ffi_type_uint         ffi_type_uint16
# define ffi_type_sint         ffi_type_sint16
#elif INT_MAX == 2147483647
# define ffi_type_uint         ffi_type_uint32
# define ffi_type_sint         ffi_type_sint32
#elif INT_MAX == 9223372036854775807
# define ffi_type_uint         ffi_type_uint64
# define ffi_type_sint         ffi_type_sint64
#else
 #error "int size not supported"
#endif

#if LONG_MAX == 2147483647
# if FFI_LONG_LONG_MAX != FFI_64_BIT_MAX
 #error "no 64-bit data type supported"
# endif
#elif LONG_MAX != FFI_64_BIT_MAX
 #error "long size not supported"
#endif

#if LONG_MAX == 2147483647
# define ffi_type_ulong        ffi_type_uint32
# define ffi_type_slong        ffi_type_sint32
#elif LONG_MAX == FFI_64_BIT_MAX
# define ffi_type_ulong        ffi_type_uint64
# define ffi_type_slong        ffi_type_sint64
#else
 #error "long size not supported"
#endif

/* These are defined in types.c.  */
FFI_EXTERN ffi_type ffi_type_void;
FFI_EXTERN ffi_type ffi_type_uint8;
FFI_EXTERN ffi_type ffi_type_sint8;
FFI_EXTERN ffi_type ffi_type_uint16;
FFI_EXTERN ffi_type ffi_type_sint16;
FFI_EXTERN ffi_type ffi_type_uint32;
FFI_EXTERN ffi_type ffi_type_sint32;
FFI_EXTERN ffi_type ffi_type_uint64;
FFI_EXTERN ffi_type ffi_type_sint64;
FFI_EXTERN ffi_type ffi_type_float;
FFI_EXTERN ffi_type ffi_type_double;
FFI_EXTERN ffi_type ffi_type_pointer;

#if 1
FFI_EXTERN ffi_type ffi_type_longdouble;
#else
#define ffi_type_longdouble ffi_type_double
#endif

#ifdef FFI_TARGET_HAS_COMPLEX_TYPE
FFI_EXTERN ffi_type ffi_type_complex_float;
FFI_EXTERN ffi_type ffi_type_complex_double;
#if 1
FFI_EXTERN ffi_type ffi_type_complex_longdouble;
#else
#define ffi_type_complex_longdouble ffi_type_complex_double
#endif
#endif
#endif /* LIBFFI_HIDE_BASIC_TYPES */

typedef enum {
  FFI_OK = 0,
  FFI_BAD_TYPEDEF,
  FFI_BAD_ABI,
  FFI_BAD_ARGTYPE
} ffi_status;

typedef struct {
  ffi_abi abi;
  unsigned nargs;
  ffi_type **arg_types;
  ffi_type *rtype;
  unsigned bytes;
  unsigned flags;
#ifdef FFI_EXTRA_CIF_FIELDS
  FFI_EXTRA_CIF_FIELDS;
#endif
} ffi_cif;

/* ---- Definitions for the raw API -------------------------------------- */

#ifndef FFI_SIZEOF_ARG
# if LONG_MAX == 2147483647
#  define FFI_SIZEOF_ARG        4
# elif LONG_MAX == FFI_64_BIT_MAX
#  define FFI_SIZEOF_ARG        8
# endif
#endif

#ifndef FFI_SIZEOF_JAVA_RAW
#  define FFI_SIZEOF_JAVA_RAW FFI_SIZEOF_ARG
#endif

typedef union {
  ffi_sarg  sint;
  ffi_arg   uint;
  float	    flt;
  char      data[FFI_SIZEOF_ARG];
  void*     ptr;
} ffi_raw;

#if FFI_SIZEOF_JAVA_RAW == 4 && FFI_SIZEOF_ARG == 8
/* This is a special case for mips64/n32 ABI (and perhaps others) where
   sizeof(void *) is 4 and FFI_SIZEOF_ARG is 8.  */
typedef union {
  signed int	sint;
  unsigned int	uint;
  float		flt;
  char		data[FFI_SIZEOF_JAVA_RAW];
  void*		ptr;
} ffi_java_raw;
#else
typedef ffi_raw ffi_java_raw;
#endif


FFI_API
void ffi_raw_call (ffi_cif *cif,
		   void (*fn)(void),
		   void *rvalue,
		   ffi_raw *avalue);

FFI_API void ffi_ptrarray_to_raw (ffi_cif *cif, void **args, ffi_raw *raw);
FFI_API void ffi_raw_to_ptrarray (ffi_cif *cif, ffi_raw *raw, void **args);
FFI_API size_t ffi_raw_size (ffi_cif *cif);

/* This is analogous to the raw API, except it uses Java parameter
   packing, even on 64-bit machines.  I.e. on 64-bit machines longs
   and doubles are followed by an empty 64-bit word.  */

#if !FFI_NATIVE_RAW_API
FFI_API
void ffi_java_raw_call (ffi_cif *cif,
			void (*fn)(void),
			void *rvalue,
			ffi_java_raw *avalue) __attribute__((deprecated));
#endif

FFI_API
void ffi_java_ptrarray_to_raw (ffi_cif *cif, void **args, ffi_java_raw *raw) __attribute__((deprecated));
FFI_API
void ffi_java_raw_to_ptrarray (ffi_cif *cif, ffi_java_raw *raw, void **args) __attribute__((deprecated));
FFI_API
size_t ffi_java_raw_size (ffi_cif *cif) __attribute__((deprecated));

/* ---- Definitions for closures ----------------------------------------- */

#if FFI_CLOSURES

#ifdef _MSC_VER
__declspec(align(8))
#endif
typedef struct {
#if 0
  void *trampoline_table;
  void *trampoline_table_entry;
#else
  union {
    char tramp[FFI_TRAMPOLINE_SIZE];
    void *ftramp;
  };
#endif
  ffi_cif   *cif;
  void     (*fun)(ffi_cif*,void*,void**,void*);
  void      *user_data;
#if defined(_MSC_VER) && defined(_M_IX86)
  void      *padding;
#endif
} ffi_closure
#ifdef __GNUC__
    __attribute__((aligned (8)))
#endif
    ;

#ifndef __GNUC__
# ifdef __sgi
#  pragma pack 0
# endif
#endif

FFI_API void *ffi_closure_alloc (size_t size, void **code);
FFI_API void ffi_closure_free (void *);

#if defined(PA_LINUX) || defined(PA_HPUX)
#define FFI_CLOSURE_PTR(X) ((void *)((unsigned int)(X) | 2))
#define FFI_RESTORE_PTR(X) ((void *)((unsigned int)(X) & ~3))
#else
#define FFI_CLOSURE_PTR(X) (X)
#define FFI_RESTORE_PTR(X) (X)
#endif

FFI_API ffi_status
ffi_prep_closure (ffi_closure*,
		  ffi_cif *,
		  void (*fun)(ffi_cif*,void*,void**,void*),
		  void *user_data)
#if defined(__GNUC__) && (((__GNUC__ * 100) + __GNUC_MINOR__) >= 405)
  __attribute__((deprecated ("use ffi_prep_closure_loc instead")))
#elif defined(__GNUC__) && __GNUC__ >= 3
  __attribute__((deprecated))
#endif
  ;

FFI_API ffi_status
ffi_prep_closure_loc (ffi_closure*,
		      ffi_cif *,
		      void (*fun)(ffi_cif*,void*,void**,void*),
		      void *user_data,
		      void *codeloc);

#ifdef __sgi
# pragma pack 8
#endif
typedef struct {
#if 0
  void *trampoline_table;
  void *trampoline_table_entry;
#else
  char tramp[FFI_TRAMPOLINE_SIZE];
#endif
  ffi_cif   *cif;

#if !FFI_NATIVE_RAW_API

  /* If this is enabled, then a raw closure has the same layout
     as a regular closure.  We use this to install an intermediate
     handler to do the translation, void** -> ffi_raw*.  */

  void     (*translate_args)(ffi_cif*,void*,void**,void*);
  void      *this_closure;

#endif

  void     (*fun)(ffi_cif*,void*,ffi_raw*,void*);
  void      *user_data;

} ffi_raw_closure;

typedef struct {
#if 0
  void *trampoline_table;
  void *trampoline_table_entry;
#else
  char tramp[FFI_TRAMPOLINE_SIZE];
#endif

  ffi_cif   *cif;

#if !FFI_NATIVE_RAW_API

  /* If this is enabled, then a raw closure has the same layout
     as a regular closure.  We use this to install an intermediate
     handler to do the translation, void** -> ffi_raw*.  */

  void     (*translate_args)(ffi_cif*,void*,void**,void*);
  void      *this_closure;

#endif

  void     (*fun)(ffi_cif*,void*,ffi_java_raw*,void*);
  void      *user_data;

} ffi_java_raw_closure;

FFI_API ffi_status
ffi_prep_raw_closure (ffi_raw_closure*,
		      ffi_cif *cif,
		      void (*fun)(ffi_cif*,void*,ffi_raw*,void*),
		      void *user_data);

FFI_API ffi_status
ffi_prep_raw_closure_loc (ffi_raw_closure*,
			  ffi_cif *cif,
			  void (*fun)(ffi_cif*,void*,ffi_raw*,void*),
			  void *user_data,
			  void *codeloc);

#if !FFI_NATIVE_RAW_API
FFI_API ffi_status
ffi_prep_java_raw_closure (ffi_java_raw_closure*,
		           ffi_cif *cif,
		           void (*fun)(ffi_cif*,void*,ffi_java_raw*,void*),
		           void *user_data) __attribute__((deprecated));

FFI_API ffi_status
ffi_prep_java_raw_closure_loc (ffi_java_raw_closure*,
			       ffi_cif *cif,
			       void (*fun)(ffi_cif*,void*,ffi_java_raw*,void*),
			       void *user_data,
			       void *codeloc) __attribute__((deprecated));
#endif

#endif /* FFI_CLOSURES */

#if FFI_GO_CLOSURES

typedef struct {
  void      *tramp;
  ffi_cif   *cif;
  void     (*fun)(ffi_cif*,void*,void**,void*);
} ffi_go_closure;

FFI_API ffi_status ffi_prep_go_closure (ffi_go_closure*, ffi_cif *,
				void (*fun)(ffi_cif*,void*,void**,void*));

FFI_API void ffi_call_go (ffi_cif *cif, void (*fn)(void), void *rvalue,
		  void **avalue, void *closure);

#endif /* FFI_GO_CLOSURES */

/* ---- Public interface definition -------------------------------------- */

FFI_API
ffi_status ffi_prep_cif(ffi_cif *cif,
			ffi_abi abi,
			unsigned int nargs,
			ffi_type *rtype,
			ffi_type **atypes);

FFI_API
ffi_status ffi_prep_cif_var(ffi_cif *cif,
			    ffi_abi abi,
			    unsigned int nfixedargs,
			    unsigned int ntotalargs,
			    ffi_type *rtype,
			    ffi_type **atypes);

FFI_API
void ffi_call(ffi_cif *cif,
	      void (*fn)(void),
	      void *rvalue,
	      void **avalue);

FFI_API
ffi_status ffi_get_struct_offsets (ffi_abi abi, ffi_type *struct_type,
				   size_t *offsets);

/* Useful for eliminating compiler warnings.  */
#define FFI_FN(f) ((void (*)(void))f)

/* ---- Definitions shared with assembly code ---------------------------- */

#endif

#ifdef __cplusplus
}
#endif

#endif
