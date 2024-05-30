
#ifndef Py_PYTHREAD_H
#define Py_PYTHREAD_H

typedef void *PyThread_type_lock;

#ifdef __cplusplus
extern "C" {
#endif

/* Return status codes for Python lock acquisition.  Chosen for maximum
 * backwards compatibility, ie failure -> 0, success -> 1.  */
typedef enum PyLockStatus {
    PY_LOCK_FAILURE = 0,
    PY_LOCK_ACQUIRED = 1,
    PY_LOCK_INTR
} PyLockStatus;

#ifndef Py_LIMITED_API
#define PYTHREAD_INVALID_THREAD_ID ((unsigned long)-1)
#endif

PyAPI_FUNC(void) PyThread_init_thread(void);
PyAPI_FUNC(unsigned long) PyThread_start_new_thread(void (*)(void *), void *);
PyAPI_FUNC(void) _Py_NO_RETURN PyThread_exit_thread(void);
PyAPI_FUNC(unsigned long) PyThread_get_thread_ident(void);

#if defined(__APPLE__) || defined(__linux__) || defined(__FreeBSD__) || defined(__OpenBSD__) || defined(__NetBSD__) || defined(_WIN32) || defined(_AIX)
#define PY_HAVE_THREAD_NATIVE_ID
PyAPI_FUNC(unsigned long) PyThread_get_thread_native_id(void);
#endif

PyAPI_FUNC(PyThread_type_lock) PyThread_allocate_lock(void);
PyAPI_FUNC(void) PyThread_free_lock(PyThread_type_lock);
PyAPI_FUNC(int) PyThread_acquire_lock(PyThread_type_lock, int);
#define WAIT_LOCK       1
#define NOWAIT_LOCK     0

#ifndef Py_LIMITED_API
#ifdef HAVE_FORK
/* Private function to reinitialize a lock at fork in the child process.
   Reset the lock to the unlocked state.
   Return 0 on success, return -1 on error. */
PyAPI_FUNC(int) _PyThread_at_fork_reinit(PyThread_type_lock *lock);
#endif  /* HAVE_FORK */
#endif  /* !Py_LIMITED_API */

/* PY_TIMEOUT_T is the integral type used to specify timeouts when waiting
   on a lock (see PyThread_acquire_lock_timed() below).
   PY_TIMEOUT_MAX is the highest usable value (in microseconds) of that
   type, and depends on the system threading API.

   NOTE: this isn't the same value as `_thread.TIMEOUT_MAX`.  The _thread
   module exposes a higher-level API, with timeouts expressed in seconds
   and floating-point numbers allowed.
*/
#define PY_TIMEOUT_T long long

#if defined(_POSIX_THREADS)
   /* PyThread_acquire_lock_timed() uses _PyTime_FromNanoseconds(us * 1000),
      convert microseconds to nanoseconds. */
#  define PY_TIMEOUT_MAX (LLONG_MAX / 1000)
#elif defined (NT_THREADS)
   /* In the NT API, the timeout is a DWORD and is expressed in milliseconds */
#  if 0xFFFFFFFFLL * 1000 < LLONG_MAX
#    define PY_TIMEOUT_MAX (0xFFFFFFFFLL * 1000)
#  else
#    define PY_TIMEOUT_MAX LLONG_MAX
#  endif
#else
#  define PY_TIMEOUT_MAX LLONG_MAX
#endif


/* If microseconds == 0, the call is non-blocking: it returns immediately
   even when the lock can't be acquired.
   If microseconds > 0, the call waits up to the specified duration.
   If microseconds < 0, the call waits until success (or abnormal failure)

   microseconds must be less than PY_TIMEOUT_MAX. Behaviour otherwise is
   undefined.

   If intr_flag is true and the acquire is interrupted by a signal, then the
   call will return PY_LOCK_INTR.  The caller may reattempt to acquire the
   lock.
*/
PyAPI_FUNC(PyLockStatus) PyThread_acquire_lock_timed(PyThread_type_lock,
                                                     PY_TIMEOUT_T microseconds,
                                                     int intr_flag);

PyAPI_FUNC(void) PyThread_release_lock(PyThread_type_lock);

PyAPI_FUNC(size_t) PyThread_get_stacksize(void);
PyAPI_FUNC(int) PyThread_set_stacksize(size_t);

#if !defined(Py_LIMITED_API) || Py_LIMITED_API+0 >= 0x03030000
PyAPI_FUNC(PyObject*) PyThread_GetInfo(void);
#endif


/* Thread Local Storage (TLS) API
   TLS API is DEPRECATED.  Use Thread Specific Storage (TSS) API.

   The existing TLS API has used int to represent TLS keys across all
   platforms, but it is not POSIX-compliant.  Therefore, the new TSS API uses
   opaque data type to represent TSS keys to be compatible (see PEP 539).
*/
Py_DEPRECATED(3.7) PyAPI_FUNC(int) PyThread_create_key(void);
Py_DEPRECATED(3.7) PyAPI_FUNC(void) PyThread_delete_key(int key);
Py_DEPRECATED(3.7) PyAPI_FUNC(int) PyThread_set_key_value(int key,
                                                          void *value);
Py_DEPRECATED(3.7) PyAPI_FUNC(void *) PyThread_get_key_value(int key);
Py_DEPRECATED(3.7) PyAPI_FUNC(void) PyThread_delete_key_value(int key);

/* Cleanup after a fork */
Py_DEPRECATED(3.7) PyAPI_FUNC(void) PyThread_ReInitTLS(void);


#if !defined(Py_LIMITED_API) || Py_LIMITED_API+0 >= 0x03070000
/* New in 3.7 */
/* Thread Specific Storage (TSS) API */

typedef struct _Py_tss_t Py_tss_t;  /* opaque */

#ifndef Py_LIMITED_API
#if defined(_POSIX_THREADS)
    /* Darwin needs pthread.h to know type name the pthread_key_t. */
#   include <pthread.h>
#   define NATIVE_TSS_KEY_T     pthread_key_t
#elif defined(NT_THREADS)
    /* In Windows, native TSS key type is DWORD,
       but hardcode the unsigned long to avoid errors for include directive.
    */
#   define NATIVE_TSS_KEY_T     unsigned long
#else
#   error "Require native threads. See https://bugs.python.org/issue31370"
#endif

/* When Py_LIMITED_API is not defined, the type layout of Py_tss_t is
   exposed to allow static allocation in the API clients.  Even in this case,
   you must handle TSS keys through API functions due to compatibility.
*/
struct _Py_tss_t {
    int _is_initialized;
    NATIVE_TSS_KEY_T _key;
};

#undef NATIVE_TSS_KEY_T

/* When static allocation, you must initialize with Py_tss_NEEDS_INIT. */
#define Py_tss_NEEDS_INIT   {0}
#endif  /* !Py_LIMITED_API */

PyAPI_FUNC(Py_tss_t *) PyThread_tss_alloc(void);
PyAPI_FUNC(void) PyThread_tss_free(Py_tss_t *key);

/* The parameter key must not be NULL. */
PyAPI_FUNC(int) PyThread_tss_is_created(Py_tss_t *key);
PyAPI_FUNC(int) PyThread_tss_create(Py_tss_t *key);
PyAPI_FUNC(void) PyThread_tss_delete(Py_tss_t *key);
PyAPI_FUNC(int) PyThread_tss_set(Py_tss_t *key, void *value);
PyAPI_FUNC(void *) PyThread_tss_get(Py_tss_t *key);
#endif  /* New in 3.7 */

#ifdef __cplusplus
}
#endif

#endif /* !Py_PYTHREAD_H */
