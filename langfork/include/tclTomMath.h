/* LibTomMath, multiple-precision integer library -- Tom St Denis */
/* SPDX-License-Identifier: Unlicense */

#ifndef BN_H_
#define BN_H_

#ifndef MODULE_SCOPE
#define MODULE_SCOPE extern
#endif



#ifdef __cplusplus
extern "C" {
#endif

/* MS Visual C++ doesn't have a 128bit type for words, so fall back to 32bit MPI's (where words are 64bit) */
#if (defined(_WIN32) || defined(__LLP64__) || defined(__e2k__) || defined(__LCC__)) && !defined(MP_64BIT)
#   define MP_32BIT
#endif

/* detect 64-bit mode if possible */
#if defined(NEVER)
#   if !(defined(MP_32BIT) || defined(MP_16BIT) || defined(MP_8BIT))
#      if defined(__GNUC__)
/* we support 128bit integers only via: __attribute__((mode(TI))) */
#         define MP_64BIT
#      else
/* otherwise we fall back to MP_32BIT even on 64bit platforms */
#         define MP_32BIT
#      endif
#   endif
#endif

#ifdef MP_DIGIT_BIT
#   error Defining MP_DIGIT_BIT is disallowed, use MP_8/16/31/32/64BIT
#endif

/* some default configurations.
 *
 * A "mp_digit" must be able to hold MP_DIGIT_BIT + 1 bits
 * A "mp_word" must be able to hold 2*MP_DIGIT_BIT + 1 bits
 *
 * At the very least a mp_digit must be able to hold 7 bits
 * [any size beyond that is ok provided it doesn't overflow the data type]
 */

#ifdef MP_8BIT
#ifndef MP_DIGIT_DECLARED
typedef unsigned char        mp_digit;
#define MP_DIGIT_DECLARED
#endif
#ifndef MP_WORD_DECLARED
typedef unsigned short       private_mp_word;
#define MP_WORD_DECLARED
#endif
#   define MP_SIZEOF_MP_DIGIT 1
#   ifdef MP_DIGIT_BIT
#      error You must not define MP_DIGIT_BIT when using MP_8BIT
#   endif
#elif defined(MP_16BIT)
#ifndef MP_DIGIT_DECLARED
typedef unsigned short       mp_digit;
#define MP_DIGIT_DECLARED
#endif
#ifndef MP_WORD_DECLARED
typedef unsigned int         private_mp_word;
#define MP_WORD_DECLARED
#endif
#   define MP_SIZEOF_MP_DIGIT 2
#   ifdef MP_DIGIT_BIT
#      error You must not define MP_DIGIT_BIT when using MP_16BIT
#   endif
#elif defined(MP_64BIT)
/* for GCC only on supported platforms */
#ifndef MP_DIGIT_DECLARED
typedef unsigned long long   mp_digit;
#define MP_DIGIT_DECLARED
#endif
typedef unsigned long        private_mp_word __attribute__((mode(TI)));
#   define MP_DIGIT_BIT 60
#else
/* this is the default case, 28-bit digits */

/* this is to make porting into LibTomCrypt easier :-) */
#ifndef MP_DIGIT_DECLARED
typedef unsigned int         mp_digit;
#define MP_DIGIT_DECLARED
#endif
#ifndef MP_WORD_DECLARED
#ifdef _WIN32
typedef unsigned __int64   private_mp_word;
#else
typedef unsigned long long   private_mp_word;
#endif
#define MP_WORD_DECLARED
#endif

#   ifdef MP_31BIT
/*
 * This is an extension that uses 31-bit digits.
 * Please be aware that not all functions support this size, especially s_mp_mul_digs_fast
 * will be reduced to work on small numbers only:
 * Up to 8 limbs, 248 bits instead of up to 512 limbs, 15872 bits with MP_28BIT.
 */
#      define MP_DIGIT_BIT 31
#   else
/* default case is 28-bit digits, defines MP_28BIT as a handy macro to test */
#      define MP_DIGIT_BIT 28
#      define MP_28BIT
#   endif
#endif

/* otherwise the bits per digit is calculated automatically from the size of a mp_digit */
#ifndef MP_DIGIT_BIT
#   define MP_DIGIT_BIT (((CHAR_BIT * MP_SIZEOF_MP_DIGIT) - 1))  /* bits per digit */
#endif

#define MP_MASK          ((((mp_digit)1)<<((mp_digit)MP_DIGIT_BIT))-((mp_digit)1))
#define MP_DIGIT_MAX     MP_MASK

/* Primality generation flags */
#define MP_PRIME_BBS      0x0001 /* BBS style prime */
#define MP_PRIME_SAFE     0x0002 /* Safe prime (p-1)/2 == prime */
#define MP_PRIME_2MSB_ON  0x0008 /* force 2nd MSB to 1 */

#define LTM_PRIME_BBS      (MP_DEPRECATED_PRAGMA("LTM_PRIME_BBS has been deprecated, use MP_PRIME_BBS") MP_PRIME_BBS)
#define LTM_PRIME_SAFE     (MP_DEPRECATED_PRAGMA("LTM_PRIME_SAFE has been deprecated, use MP_PRIME_SAFE") MP_PRIME_SAFE)
#define LTM_PRIME_2MSB_ON  (MP_DEPRECATED_PRAGMA("LTM_PRIME_2MSB_ON has been deprecated, use MP_PRIME_2MSB_ON") MP_PRIME_2MSB_ON)

#ifdef MP_USE_ENUMS
typedef enum {
   MP_ZPOS = 0,   /* positive */
   MP_NEG = 1     /* negative */
} mp_sign;
typedef enum {
   MP_LT = -1,    /* less than */
   MP_EQ = 0,     /* equal */
   MP_GT = 1      /* greater than */
} mp_ord;
typedef enum {
   MP_NO = 0,
   MP_YES = 1
} mp_bool;
typedef enum {
   MP_OKAY  = 0,   /* no error */
   MP_ERR   = -1,  /* unknown error */
   MP_MEM   = -2,  /* out of mem */
   MP_VAL   = -3,  /* invalid input */
   MP_ITER  = -4,  /* maximum iterations reached */
   MP_BUF   = -5   /* buffer overflow, supplied buffer too small */
} mp_err;
typedef enum {
   MP_LSB_FIRST = -1,
   MP_MSB_FIRST =  1
} mp_order;
typedef enum {
   MP_LITTLE_ENDIAN  = -1,
   MP_NATIVE_ENDIAN  =  0,
   MP_BIG_ENDIAN     =  1
} mp_endian;
#else
typedef int mp_sign;
#define MP_ZPOS       0   /* positive integer */
#define MP_NEG        1   /* negative */
typedef int mp_ord;
#define MP_LT        -1   /* less than */
#define MP_EQ         0   /* equal to */
#define MP_GT         1   /* greater than */
typedef int mp_bool;
#define MP_YES        1
#define MP_NO         0
typedef int mp_err;
#define MP_OKAY       0   /* no error */
#define MP_ERR        -1  /* unknown error */
#define MP_MEM        -2  /* out of mem */
#define MP_VAL        -3  /* invalid input */
#define MP_RANGE      (MP_DEPRECATED_PRAGMA("MP_RANGE has been deprecated in favor of MP_VAL") MP_VAL)
#define MP_ITER       -4  /* maximum iterations reached */
#define MP_BUF        -5  /* buffer overflow, supplied buffer too small */
typedef int mp_order;
#define MP_LSB_FIRST -1
#define MP_MSB_FIRST  1
typedef int mp_endian;
#define MP_LITTLE_ENDIAN  -1
#define MP_NATIVE_ENDIAN  0
#define MP_BIG_ENDIAN     1
#endif

/* tunable cutoffs */

#ifndef MP_FIXED_CUTOFFS
extern int
KARATSUBA_MUL_CUTOFF,
KARATSUBA_SQR_CUTOFF,
TOOM_MUL_CUTOFF,
TOOM_SQR_CUTOFF;
#endif

/* define this to use lower memory usage routines (exptmods mostly) */
/* #define MP_LOW_MEM */

/* default precision */
#ifndef MP_PREC
#   ifndef MP_LOW_MEM
#      define MP_PREC 32        /* default digits of precision */
#   elif defined(MP_8BIT)
#      define MP_PREC 16        /* default digits of precision */
#   else
#      define MP_PREC 8         /* default digits of precision */
#   endif
#endif

/* size of comba arrays, should be at least 2 * 2**(BITS_PER_WORD - BITS_PER_DIGIT*2) */
#define PRIVATE_MP_WARRAY (int)(1 << (((CHAR_BIT * sizeof(private_mp_word)) - (2 * MP_DIGIT_BIT)) + 1))

#if defined(__GNUC__) && __GNUC__ >= 4
#   define MP_NULL_TERMINATED __attribute__((sentinel))
#else
#   define MP_NULL_TERMINATED
#endif

/*
 * MP_WUR - warn unused result
 * ---------------------------
 *
 * The result of functions annotated with MP_WUR must be
 * checked and cannot be ignored.
 *
 * Most functions in libtommath return an error code.
 * This error code must be checked in order to prevent crashes or invalid
 * results.
 *
 * If you still want to avoid the error checks for quick and dirty programs
 * without robustness guarantees, you can `#define MP_WUR` before including
 * tommath.h, disabling the warnings.
 */
#ifndef MP_WUR
#  if defined(__GNUC__) && __GNUC__ >= 4
#     define MP_WUR __attribute__((warn_unused_result))
#  else
#     define MP_WUR
#  endif
#endif

#if defined(__GNUC__) && (__GNUC__ * 100 + __GNUC_MINOR__ >= 405)
#  define MP_DEPRECATED(x) __attribute__((deprecated("replaced by " #x)))
#elif defined(_MSC_VER) && _MSC_VER >= 1500
#  define MP_DEPRECATED(x) __declspec(deprecated("replaced by " #x))
#else
#  define MP_DEPRECATED(x)
#endif

#ifndef MP_NO_DEPRECATED_PRAGMA
#if defined(__GNUC__) && (__GNUC__ * 100 + __GNUC_MINOR__ >= 301)
#  define PRIVATE_MP_DEPRECATED_PRAGMA(s) _Pragma(#s)
#  define MP_DEPRECATED_PRAGMA(s) PRIVATE_MP_DEPRECATED_PRAGMA(GCC warning s)
#elif defined(_MSC_VER) && _MSC_VER >= 1500
#  define MP_DEPRECATED_PRAGMA(s) __pragma(message(s))
#endif
#endif

#ifndef MP_DEPRECATED_PRAGMA
#  define MP_DEPRECATED_PRAGMA(s)
#endif

#define DIGIT_BIT   MP_DIGIT_BIT
#define USED(m)    ((m)->used)
#define DIGIT(m,k) ((m)->dp[(k)])
#define SIGN(m)    ((m)->sign)

/* the infamous mp_int structure */
#ifndef MP_INT_DECLARED
#define MP_INT_DECLARED
typedef struct mp_int mp_int;
#endif
struct mp_int {
   int used, alloc;
   mp_sign sign;
   mp_digit *dp;
};

/* callback for mp_prime_random, should fill dst with random bytes and return how many read [upto len] */
typedef int private_mp_prime_callback(unsigned char *dst, int len, void *dat);
typedef private_mp_prime_callback MP_DEPRECATED(mp_rand_source) ltm_prime_callback;

/* error code to char* string */
/*
const char *mp_error_to_string(mp_err code) MP_WUR;
*/

/* ---> init and deinit bignum functions <--- */
/* init a bignum */
/*
mp_err mp_init(mp_int *a) MP_WUR;
*/

/* free a bignum */
/*
void mp_clear(mp_int *a);
*/

/* init a null terminated series of arguments */
/*
mp_err mp_init_multi(mp_int *mp, ...) MP_NULL_TERMINATED MP_WUR;
*/

/* clear a null terminated series of arguments */
/*
void mp_clear_multi(mp_int *mp, ...) MP_NULL_TERMINATED;
*/

/* exchange two ints */
/*
void mp_exch(mp_int *a, mp_int *b);
*/

/* shrink ram required for a bignum */
/*
mp_err mp_shrink(mp_int *a) MP_WUR;
*/

/* grow an int to a given size */
/*
mp_err mp_grow(mp_int *a, int size) MP_WUR;
*/

/* init to a given number of digits */
/*
mp_err mp_init_size(mp_int *a, int size) MP_WUR;
*/

/* ---> Basic Manipulations <--- */
#define mp_iszero(a) (((a)->used == 0) ? MP_YES : MP_NO)
#define mp_isodd(a)  (((a)->used != 0 && (((a)->dp[0] & 1) == 1)) ? MP_YES : MP_NO)
#define mp_iseven(a) (((a)->used == 0 || (((a)->dp[0] & 1) == 0)) ? MP_YES : MP_NO)
#define mp_isneg(a)  (((a)->sign != MP_ZPOS) ? MP_YES : MP_NO)

/* set to zero */
/*
void mp_zero(mp_int *a);
*/

/* get and set doubles */
/*
double mp_get_double(const mp_int *a) MP_WUR;
*/
/*
mp_err mp_set_double(mp_int *a, double b) MP_WUR;
*/

/* get integer, set integer and init with integer (int32_t) */
#ifndef MP_NO_STDINT
/*
int32_t mp_get_i32(const mp_int *a) MP_WUR;
*/
/*
void mp_set_i32(mp_int *a, int32_t b);
*/
/*
mp_err mp_init_i32(mp_int *a, int32_t b) MP_WUR;
*/

/* get integer, set integer and init with integer, behaves like two complement for negative numbers (uint32_t) */
#define mp_get_u32(a) ((uint32_t)mp_get_i32(a))
/*
void mp_set_u32(mp_int *a, uint32_t b);
*/
/*
mp_err mp_init_u32(mp_int *a, uint32_t b) MP_WUR;
*/

/* get integer, set integer and init with integer (int64_t) */
/*
int64_t mp_get_i64(const mp_int *a) MP_WUR;
*/
/*
void mp_set_i64(mp_int *a, int64_t b);
*/
/*
mp_err mp_init_i64(mp_int *a, int64_t b) MP_WUR;
*/

/* get integer, set integer and init with integer, behaves like two complement for negative numbers (uint64_t) */
#define mp_get_u64(a) ((uint64_t)mp_get_i64(a))
/*
void mp_set_u64(mp_int *a, uint64_t b);
*/
/*
mp_err mp_init_u64(mp_int *a, uint64_t b) MP_WUR;
*/

/* get magnitude */
/*
uint32_t mp_get_mag_u32(const mp_int *a) MP_WUR;
*/
/*
uint64_t mp_get_mag_u64(const mp_int *a) MP_WUR;
*/
#endif
/*
unsigned long mp_get_mag_ul(const mp_int *a) MP_WUR;
*/
/*
Tcl_WideUInt mp_get_mag_ull(const mp_int *a) MP_WUR;
*/

/* get integer, set integer (long) */
/*
long mp_get_l(const mp_int *a) MP_WUR;
*/
/*
void mp_set_l(mp_int *a, long b);
*/
/*
mp_err mp_init_l(mp_int *a, long b) MP_WUR;
*/

/* get integer, set integer (unsigned long) */
#define mp_get_ul(a) ((unsigned long)mp_get_l(a))
/*
void mp_set_ul(mp_int *a, unsigned long b);
*/
/*
mp_err mp_init_ul(mp_int *a, unsigned long b) MP_WUR;
*/

/* get integer, set integer (Tcl_WideInt) */
/*
Tcl_WideInt mp_get_ll(const mp_int *a) MP_WUR;
*/
/*
void mp_set_ll(mp_int *a, Tcl_WideInt b);
*/
/*
mp_err mp_init_ll(mp_int *a, Tcl_WideInt b) MP_WUR;
*/

/* get integer, set integer (Tcl_WideUInt) */
#define mp_get_ull(a) ((Tcl_WideUInt)mp_get_ll(a))
/*
void mp_set_ull(mp_int *a, Tcl_WideUInt b);
*/
/*
mp_err mp_init_ull(mp_int *a, Tcl_WideUInt b) MP_WUR;
*/

/* set to single unsigned digit, up to MP_DIGIT_MAX */
/*
void mp_set(mp_int *a, mp_digit b);
*/
/*
mp_err mp_init_set(mp_int *a, mp_digit b) MP_WUR;
*/

/* get integer, set integer and init with integer (deprecated) */
/*
MP_DEPRECATED(mp_get_mag_u32/mp_get_u32) unsigned long mp_get_int(const mp_int *a) MP_WUR;
*/
/*
MP_DEPRECATED(mp_get_mag_ul/mp_get_ul) unsigned long mp_get_long(const mp_int *a) MP_WUR;
*/
/*
MP_DEPRECATED(mp_get_mag_ull/mp_get_ull) Tcl_WideUInt mp_get_long_long(const mp_int *a) MP_WUR;
*/
/*
MP_DEPRECATED(mp_set_ul) mp_err mp_set_int(mp_int *a, unsigned long b);
*/
/*
MP_DEPRECATED(mp_set_ul) mp_err mp_set_long(mp_int *a, unsigned long b);
*/
/*
MP_DEPRECATED(mp_set_ull) mp_err mp_set_long_long(mp_int *a, Tcl_WideUInt b);
*/
/*
MP_DEPRECATED(mp_init_ul) mp_err mp_init_set_int(mp_int *a, unsigned long b) MP_WUR;
*/

/* copy, b = a */
/*
mp_err mp_copy(const mp_int *a, mp_int *b) MP_WUR;
*/

/* inits and copies, a = b */
/*
mp_err mp_init_copy(mp_int *a, const mp_int *b) MP_WUR;
*/

/* trim unused digits */
/*
void mp_clamp(mp_int *a);
*/

/* export binary data */
/*
MP_DEPRECATED(mp_pack) mp_err mp_export(void *rop, size_t *countp, int order, size_t size,
                                        int endian, size_t nails, const mp_int *op) MP_WUR;
*/

/* import binary data */
/*
MP_DEPRECATED(mp_unpack) mp_err mp_import(mp_int *rop, size_t count, int order,
      size_t size, int endian, size_t nails,
      const void *op) MP_WUR;
*/

/* unpack binary data */
/*
mp_err mp_unpack(mp_int *rop, size_t count, mp_order order, size_t size, mp_endian endian,
                 size_t nails, const void *op) MP_WUR;
*/

/* pack binary data */
/*
size_t mp_pack_count(const mp_int *a, size_t nails, size_t size) MP_WUR;
*/
/*
mp_err mp_pack(void *rop, size_t maxcount, size_t *written, mp_order order, size_t size,
               mp_endian endian, size_t nails, const mp_int *op) MP_WUR;
*/

/* ---> digit manipulation <--- */

/* right shift by "b" digits */
/*
void mp_rshd(mp_int *a, int b);
*/

/* left shift by "b" digits */
/*
mp_err mp_lshd(mp_int *a, int b) MP_WUR;
*/

/* c = a / 2**b, implemented as c = a >> b */
/*
mp_err mp_div_2d(const mp_int *a, int b, mp_int *c, mp_int *d) MP_WUR;
*/

/* b = a/2 */
/*
mp_err mp_div_2(const mp_int *a, mp_int *b) MP_WUR;
*/

/* a/3 => 3c + d == a */
/*
mp_err mp_div_3(const mp_int *a, mp_int *c, mp_digit *d) MP_WUR;
*/

/* c = a * 2**b, implemented as c = a << b */
/*
mp_err mp_mul_2d(const mp_int *a, int b, mp_int *c) MP_WUR;
*/

/* b = a*2 */
/*
mp_err mp_mul_2(const mp_int *a, mp_int *b) MP_WUR;
*/

/* c = a mod 2**b */
/*
mp_err mp_mod_2d(const mp_int *a, int b, mp_int *c) MP_WUR;
*/

/* computes a = 2**b */
/*
mp_err mp_2expt(mp_int *a, int b) MP_WUR;
*/

/* Counts the number of lsbs which are zero before the first zero bit */
/*
int mp_cnt_lsb(const mp_int *a) MP_WUR;
*/

/* I Love Earth! */

/* makes a pseudo-random mp_int of a given size */
/*
mp_err mp_rand(mp_int *a, int digits) MP_WUR;
*/
/* makes a pseudo-random small int of a given size */
/*
MP_DEPRECATED(mp_rand) mp_err mp_rand_digit(mp_digit *r) MP_WUR;
*/
/* use custom random data source instead of source provided the platform */
/*
void mp_rand_source(mp_err(*source)(void *out, size_t size));
*/

#ifdef MP_PRNG_ENABLE_LTM_RNG
/* A last resort to provide random data on systems without any of the other
 * implemented ways to gather entropy.
 * It is compatible with `rng_get_bytes()` from libtomcrypt so you could
 * provide that one and then set `ltm_rng = rng_get_bytes;` */
extern unsigned long (*ltm_rng)(unsigned char *out, unsigned long outlen, void (*callback)(void));
extern void (*ltm_rng_callback)(void);
#endif

/* ---> binary operations <--- */

/* Checks the bit at position b and returns MP_YES
 * if the bit is 1, MP_NO if it is 0 and MP_VAL
 * in case of error
 */
/*
MP_DEPRECATED(s_mp_get_bit) int mp_get_bit(const mp_int *a, int b) MP_WUR;
*/

/* c = a XOR b (two complement) */
/*
MP_DEPRECATED(mp_xor) mp_err mp_tc_xor(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/
/*
mp_err mp_xor(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = a OR b (two complement) */
/*
MP_DEPRECATED(mp_or) mp_err mp_tc_or(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/
/*
mp_err mp_or(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = a AND b (two complement) */
/*
MP_DEPRECATED(mp_and) mp_err mp_tc_and(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/
/*
mp_err mp_and(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* b = ~a (bitwise not, two complement) */
/*
mp_err mp_complement(const mp_int *a, mp_int *b) MP_WUR;
*/

/* right shift with sign extension */
/*
MP_DEPRECATED(mp_signed_rsh) mp_err mp_tc_div_2d(const mp_int *a, int b, mp_int *c) MP_WUR;
*/
/*
mp_err mp_signed_rsh(const mp_int *a, int b, mp_int *c) MP_WUR;
*/

/* ---> Basic arithmetic <--- */

/* b = -a */
/*
mp_err mp_neg(const mp_int *a, mp_int *b) MP_WUR;
*/

/* b = |a| */
/*
mp_err mp_abs(const mp_int *a, mp_int *b) MP_WUR;
*/

/* compare a to b */
/*
mp_ord mp_cmp(const mp_int *a, const mp_int *b) MP_WUR;
*/

/* compare |a| to |b| */
/*
mp_ord mp_cmp_mag(const mp_int *a, const mp_int *b) MP_WUR;
*/

/* c = a + b */
/*
mp_err mp_add(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = a - b */
/*
mp_err mp_sub(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = a * b */
/*
mp_err mp_mul(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* b = a*a  */
/*
mp_err mp_sqr(const mp_int *a, mp_int *b) MP_WUR;
*/

/* a/b => cb + d == a */
/*
mp_err mp_div(const mp_int *a, const mp_int *b, mp_int *c, mp_int *d) MP_WUR;
*/

/* c = a mod b, 0 <= c < b  */
/*
mp_err mp_mod(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* Increment "a" by one like "a++". Changes input! */
/*
mp_err mp_incr(mp_int *a) MP_WUR;
*/

/* Decrement "a" by one like "a--". Changes input! */
/*
mp_err mp_decr(mp_int *a) MP_WUR;
*/

/* ---> single digit functions <--- */

/* compare against a single digit */
/*
mp_ord mp_cmp_d(const mp_int *a, mp_digit b) MP_WUR;
*/

/* c = a + b */
/*
mp_err mp_add_d(const mp_int *a, mp_digit b, mp_int *c) MP_WUR;
*/

/* c = a - b */
/*
mp_err mp_sub_d(const mp_int *a, mp_digit b, mp_int *c) MP_WUR;
*/

/* c = a * b */
/*
mp_err mp_mul_d(const mp_int *a, mp_digit b, mp_int *c) MP_WUR;
*/

/* a/b => cb + d == a */
/*
mp_err mp_div_d(const mp_int *a, mp_digit b, mp_int *c, mp_digit *d) MP_WUR;
*/

/* c = a mod b, 0 <= c < b  */
/*
mp_err mp_mod_d(const mp_int *a, mp_digit b, mp_digit *c) MP_WUR;
*/

/* ---> number theory <--- */

/* d = a + b (mod c) */
/*
mp_err mp_addmod(const mp_int *a, const mp_int *b, const mp_int *c, mp_int *d) MP_WUR;
*/

/* d = a - b (mod c) */
/*
mp_err mp_submod(const mp_int *a, const mp_int *b, const mp_int *c, mp_int *d) MP_WUR;
*/

/* d = a * b (mod c) */
/*
mp_err mp_mulmod(const mp_int *a, const mp_int *b, const mp_int *c, mp_int *d) MP_WUR;
*/

/* c = a * a (mod b) */
/*
mp_err mp_sqrmod(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = 1/a (mod b) */
/*
mp_err mp_invmod(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* c = (a, b) */
/*
mp_err mp_gcd(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* produces value such that U1*a + U2*b = U3 */
/*
mp_err mp_exteuclid(const mp_int *a, const mp_int *b, mp_int *U1, mp_int *U2, mp_int *U3) MP_WUR;
*/

/* c = [a, b] or (a*b)/(a, b) */
/*
mp_err mp_lcm(const mp_int *a, const mp_int *b, mp_int *c) MP_WUR;
*/

/* finds one of the b'th root of a, such that |c|**b <= |a|
 *
 * returns error if a < 0 and b is even
 */
/*
mp_err mp_root_u32(const mp_int *a, unsigned int b, mp_int *c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_root_u32) mp_err mp_n_root(const mp_int *a, mp_digit b, mp_int *c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_root_u32) mp_err mp_n_root_ex(const mp_int *a, mp_digit b, mp_int *c, int fast) MP_WUR;
*/

/* special sqrt algo */
/*
mp_err mp_sqrt(const mp_int *arg, mp_int *ret) MP_WUR;
*/

/* special sqrt (mod prime) */
/*
mp_err mp_sqrtmod_prime(const mp_int *n, const mp_int *prime, mp_int *ret) MP_WUR;
*/

/* is number a square? */
/*
mp_err mp_is_square(const mp_int *arg, mp_bool *ret) MP_WUR;
*/

/* computes the jacobi c = (a | n) (or Legendre if b is prime)  */
/*
MP_DEPRECATED(mp_kronecker) mp_err mp_jacobi(const mp_int *a, const mp_int *n, int *c) MP_WUR;
*/

/* computes the Kronecker symbol c = (a | p) (like jacobi() but with {a,p} in Z */
/*
mp_err mp_kronecker(const mp_int *a, const mp_int *p, int *c) MP_WUR;
*/

/* used to setup the Barrett reduction for a given modulus b */
/*
mp_err mp_reduce_setup(mp_int *a, const mp_int *b) MP_WUR;
*/

/* Barrett Reduction, computes a (mod b) with a precomputed value c
 *
 * Assumes that 0 < x <= m*m, note if 0 > x > -(m*m) then you can merely
 * compute the reduction as -1 * mp_reduce(mp_abs(x)) [pseudo code].
 */
/*
mp_err mp_reduce(mp_int *x, const mp_int *m, const mp_int *mu) MP_WUR;
*/

/* setups the montgomery reduction */
/*
mp_err mp_montgomery_setup(const mp_int *n, mp_digit *rho) MP_WUR;
*/

/* computes a = B**n mod b without division or multiplication useful for
 * normalizing numbers in a Montgomery system.
 */
/*
mp_err mp_montgomery_calc_normalization(mp_int *a, const mp_int *b) MP_WUR;
*/

/* computes x/R == x (mod N) via Montgomery Reduction */
/*
mp_err mp_montgomery_reduce(mp_int *x, const mp_int *n, mp_digit rho) MP_WUR;
*/

/* returns 1 if a is a valid DR modulus */
/*
mp_bool mp_dr_is_modulus(const mp_int *a) MP_WUR;
*/

/* sets the value of "d" required for mp_dr_reduce */
/*
void mp_dr_setup(const mp_int *a, mp_digit *d);
*/

/* reduces a modulo n using the Diminished Radix method */
/*
mp_err mp_dr_reduce(mp_int *x, const mp_int *n, mp_digit k) MP_WUR;
*/

/* returns true if a can be reduced with mp_reduce_2k */
/*
mp_bool mp_reduce_is_2k(const mp_int *a) MP_WUR;
*/

/* determines k value for 2k reduction */
/*
mp_err mp_reduce_2k_setup(const mp_int *a, mp_digit *d) MP_WUR;
*/

/* reduces a modulo b where b is of the form 2**p - k [0 <= a] */
/*
mp_err mp_reduce_2k(mp_int *a, const mp_int *n, mp_digit d) MP_WUR;
*/

/* returns true if a can be reduced with mp_reduce_2k_l */
/*
mp_bool mp_reduce_is_2k_l(const mp_int *a) MP_WUR;
*/

/* determines k value for 2k reduction */
/*
mp_err mp_reduce_2k_setup_l(const mp_int *a, mp_int *d) MP_WUR;
*/

/* reduces a modulo b where b is of the form 2**p - k [0 <= a] */
/*
mp_err mp_reduce_2k_l(mp_int *a, const mp_int *n, const mp_int *d) MP_WUR;
*/

/* Y = G**X (mod P) */
/*
mp_err mp_exptmod(const mp_int *G, const mp_int *X, const mp_int *P, mp_int *Y) MP_WUR;
*/

/* ---> Primes <--- */

/* number of primes */
#ifdef MP_8BIT
#  define PRIVATE_MP_PRIME_TAB_SIZE 31
#else
#  define PRIVATE_MP_PRIME_TAB_SIZE 256
#endif
#define PRIME_SIZE (MP_DEPRECATED_PRAGMA("PRIME_SIZE has been made internal") PRIVATE_MP_PRIME_TAB_SIZE)

/* table of first PRIME_SIZE primes */
#if defined(BUILD_tcl) || !defined(_WIN32)
MODULE_SCOPE const mp_digit ltm_prime_tab[PRIVATE_MP_PRIME_TAB_SIZE];
#endif

/* result=1 if a is divisible by one of the first PRIME_SIZE primes */
/*
MP_DEPRECATED(mp_prime_is_prime) mp_err mp_prime_is_divisible(const mp_int *a, mp_bool *result) MP_WUR;
*/

/* performs one Fermat test of "a" using base "b".
 * Sets result to 0 if composite or 1 if probable prime
 */
/*
mp_err mp_prime_fermat(const mp_int *a, const mp_int *b, mp_bool *result) MP_WUR;
*/

/* performs one Miller-Rabin test of "a" using base "b".
 * Sets result to 0 if composite or 1 if probable prime
 */
/*
mp_err mp_prime_miller_rabin(const mp_int *a, const mp_int *b, mp_bool *result) MP_WUR;
*/

/* This gives [for a given bit size] the number of trials required
 * such that Miller-Rabin gives a prob of failure lower than 2^-96
 */
/*
int mp_prime_rabin_miller_trials(int size) MP_WUR;
*/

/* performs one strong Lucas-Selfridge test of "a".
 * Sets result to 0 if composite or 1 if probable prime
 */
/*
mp_err mp_prime_strong_lucas_selfridge(const mp_int *a, mp_bool *result) MP_WUR;
*/

/* performs one Frobenius test of "a" as described by Paul Underwood.
 * Sets result to 0 if composite or 1 if probable prime
 */
/*
mp_err mp_prime_frobenius_underwood(const mp_int *N, mp_bool *result) MP_WUR;
*/

/* performs t random rounds of Miller-Rabin on "a" additional to
 * bases 2 and 3.  Also performs an initial sieve of trial
 * division.  Determines if "a" is prime with probability
 * of error no more than (1/4)**t.
 * Both a strong Lucas-Selfridge to complete the BPSW test
 * and a separate Frobenius test are available at compile time.
 * With t<0 a deterministic test is run for primes up to
 * 318665857834031151167461. With t<13 (abs(t)-13) additional
 * tests with sequential small primes are run starting at 43.
 * Is Fips 186.4 compliant if called with t as computed by
 * mp_prime_rabin_miller_trials();
 *
 * Sets result to 1 if probably prime, 0 otherwise
 */
/*
mp_err mp_prime_is_prime(const mp_int *a, int t, mp_bool *result) MP_WUR;
*/

/* finds the next prime after the number "a" using "t" trials
 * of Miller-Rabin.
 *
 * bbs_style = 1 means the prime must be congruent to 3 mod 4
 */
/*
mp_err mp_prime_next_prime(mp_int *a, int t, int bbs_style) MP_WUR;
*/

/* makes a truly random prime of a given size (bytes),
 * call with bbs = 1 if you want it to be congruent to 3 mod 4
 *
 * You have to supply a callback which fills in a buffer with random bytes.  "dat" is a parameter you can
 * have passed to the callback (e.g. a state or something).  This function doesn't use "dat" itself
 * so it can be NULL
 *
 * The prime generated will be larger than 2^(8*size).
 */
#define mp_prime_random(a, t, size, bbs, cb, dat) (MP_DEPRECATED_PRAGMA("mp_prime_random has been deprecated, use mp_prime_rand instead") mp_prime_random_ex(a, t, ((size) * 8) + 1, (bbs==1)?MP_PRIME_BBS:0, cb, dat))

/* makes a truly random prime of a given size (bits),
 *
 * Flags are as follows:
 *
 *   MP_PRIME_BBS      - make prime congruent to 3 mod 4
 *   MP_PRIME_SAFE     - make sure (p-1)/2 is prime as well (implies MP_PRIME_BBS)
 *   MP_PRIME_2MSB_ON  - make the 2nd highest bit one
 *
 * You have to supply a callback which fills in a buffer with random bytes.  "dat" is a parameter you can
 * have passed to the callback (e.g. a state or something).  This function doesn't use "dat" itself
 * so it can be NULL
 *
 */
/*
MP_DEPRECATED(mp_prime_rand) mp_err mp_prime_random_ex(mp_int *a, int t, int size, int flags,
      private_mp_prime_callback cb, void *dat) MP_WUR;
*/
/*
mp_err mp_prime_rand(mp_int *a, int t, int size, int flags) MP_WUR;
*/

/* Integer logarithm to integer base */
/*
mp_err mp_log_u32(const mp_int *a, unsigned int base, unsigned int *c) MP_WUR;
*/

/* c = a**b */
/*
mp_err mp_expt_u32(const mp_int *a, unsigned int b, mp_int *c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_expt_u32) mp_err mp_expt_d(const mp_int *a, mp_digit b, mp_int *c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_expt_u32) mp_err mp_expt_d_ex(const mp_int *a, mp_digit b, mp_int *c, int fast) MP_WUR;
*/

/* ---> radix conversion <--- */
/*
int mp_count_bits(const mp_int *a) MP_WUR;
*/


/*
MP_DEPRECATED(mp_ubin_size) int mp_unsigned_bin_size(const mp_int *a) MP_WUR;
*/
/*
MP_DEPRECATED(mp_from_ubin) mp_err mp_read_unsigned_bin(mp_int *a, const unsigned char *b, int c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_ubin) mp_err mp_to_unsigned_bin(const mp_int *a, unsigned char *b) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_ubin) mp_err mp_to_unsigned_bin_n(const mp_int *a, unsigned char *b, unsigned long *outlen) MP_WUR;
*/

/*
MP_DEPRECATED(mp_sbin_size) int mp_signed_bin_size(const mp_int *a) MP_WUR;
*/
/*
MP_DEPRECATED(mp_from_sbin) mp_err mp_read_signed_bin(mp_int *a, const unsigned char *b, int c) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_sbin) mp_err mp_to_signed_bin(const mp_int *a,  unsigned char *b) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_sbin) mp_err mp_to_signed_bin_n(const mp_int *a, unsigned char *b, unsigned long *outlen) MP_WUR;
*/

/*
size_t mp_ubin_size(const mp_int *a) MP_WUR;
*/
/*
mp_err mp_from_ubin(mp_int *a, const unsigned char *buf, size_t size) MP_WUR;
*/
/*
mp_err mp_to_ubin(const mp_int *a, unsigned char *buf, size_t maxlen, size_t *written) MP_WUR;
*/

/*
size_t mp_sbin_size(const mp_int *a) MP_WUR;
*/
/*
mp_err mp_from_sbin(mp_int *a, const unsigned char *buf, size_t size) MP_WUR;
*/
/*
mp_err mp_to_sbin(const mp_int *a, unsigned char *buf, size_t maxlen, size_t *written) MP_WUR;
*/

/*
mp_err mp_read_radix(mp_int *a, const char *str, int radix) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_radix) mp_err mp_toradix(const mp_int *a, char *str, int radix) MP_WUR;
*/
/*
MP_DEPRECATED(mp_to_radix) mp_err mp_toradix_n(const mp_int *a, char *str, int radix, int maxlen) MP_WUR;
*/
/*
mp_err mp_to_radix(const mp_int *a, char *str, size_t maxlen, size_t *written, int radix) MP_WUR;
*/
/*
mp_err mp_radix_size(const mp_int *a, int radix, int *size) MP_WUR;
*/

#ifndef MP_NO_FILE
/*
mp_err mp_fread(mp_int *a, int radix, FILE *stream) MP_WUR;
*/
/*
mp_err mp_fwrite(const mp_int *a, int radix, FILE *stream) MP_WUR;
*/
#endif

#define mp_read_raw(mp, str, len) (MP_DEPRECATED_PRAGMA("replaced by mp_read_signed_bin") mp_read_signed_bin((mp), (str), (len)))
#define mp_raw_size(mp)           (MP_DEPRECATED_PRAGMA("replaced by mp_signed_bin_size") mp_signed_bin_size(mp))
#define mp_toraw(mp, str)         (MP_DEPRECATED_PRAGMA("replaced by mp_to_signed_bin") mp_to_signed_bin((mp), (str)))
#define mp_read_mag(mp, str, len) (MP_DEPRECATED_PRAGMA("replaced by mp_read_unsigned_bin") mp_read_unsigned_bin((mp), (str), (len))
#define mp_mag_size(mp)           (MP_DEPRECATED_PRAGMA("replaced by mp_unsigned_bin_size") mp_unsigned_bin_size(mp))
#define mp_tomag(mp, str)         (MP_DEPRECATED_PRAGMA("replaced by mp_to_unsigned_bin") mp_to_unsigned_bin((mp), (str)))

#define mp_tobinary(M, S)  (MP_DEPRECATED_PRAGMA("replaced by mp_to_binary")  mp_toradix((M), (S), 2))
#define mp_tooctal(M, S)   (MP_DEPRECATED_PRAGMA("replaced by mp_to_octal")   mp_toradix((M), (S), 8))
#define mp_todecimal(M, S) (MP_DEPRECATED_PRAGMA("replaced by mp_to_decimal") mp_toradix((M), (S), 10))
#define mp_tohex(M, S)     (MP_DEPRECATED_PRAGMA("replaced by mp_to_hex")     mp_toradix((M), (S), 16))

#define mp_to_binary(M, S, N)  mp_to_radix((M), (S), (N), NULL, 2)
#define mp_to_octal(M, S, N)   mp_to_radix((M), (S), (N), NULL, 8)
#define mp_to_decimal(M, S, N) mp_to_radix((M), (S), (N), NULL, 10)
#define mp_to_hex(M, S, N)     mp_to_radix((M), (S), (N), NULL, 16)

#ifdef __cplusplus
}
#endif

#include "tclTomMathDecls.h"

#endif
