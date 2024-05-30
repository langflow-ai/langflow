#ifndef Py_CPYTHON_FILEUTILS_H
#  error "this header file must not be included directly"
#endif

typedef enum {
    _Py_ERROR_UNKNOWN=0,
    _Py_ERROR_STRICT,
    _Py_ERROR_SURROGATEESCAPE,
    _Py_ERROR_REPLACE,
    _Py_ERROR_IGNORE,
    _Py_ERROR_BACKSLASHREPLACE,
    _Py_ERROR_SURROGATEPASS,
    _Py_ERROR_XMLCHARREFREPLACE,
    _Py_ERROR_OTHER
} _Py_error_handler;

PyAPI_FUNC(_Py_error_handler) _Py_GetErrorHandler(const char *errors);

PyAPI_FUNC(int) _Py_DecodeLocaleEx(
    const char *arg,
    wchar_t **wstr,
    size_t *wlen,
    const char **reason,
    int current_locale,
    _Py_error_handler errors);

PyAPI_FUNC(int) _Py_EncodeLocaleEx(
    const wchar_t *text,
    char **str,
    size_t *error_pos,
    const char **reason,
    int current_locale,
    _Py_error_handler errors);

PyAPI_FUNC(char*) _Py_EncodeLocaleRaw(
    const wchar_t *text,
    size_t *error_pos);

PyAPI_FUNC(PyObject *) _Py_device_encoding(int);

#if defined(MS_WINDOWS) || defined(__APPLE__)
    /* On Windows, the count parameter of read() is an int (bpo-9015, bpo-9611).
       On macOS 10.13, read() and write() with more than INT_MAX bytes
       fail with EINVAL (bpo-24658). */
#   define _PY_READ_MAX  INT_MAX
#   define _PY_WRITE_MAX INT_MAX
#else
    /* write() should truncate the input to PY_SSIZE_T_MAX bytes,
       but it's safer to do it ourself to have a portable behaviour */
#   define _PY_READ_MAX  PY_SSIZE_T_MAX
#   define _PY_WRITE_MAX PY_SSIZE_T_MAX
#endif

#ifdef MS_WINDOWS
struct _Py_stat_struct {
    unsigned long st_dev;
    uint64_t st_ino;
    unsigned short st_mode;
    int st_nlink;
    int st_uid;
    int st_gid;
    unsigned long st_rdev;
    __int64 st_size;
    time_t st_atime;
    int st_atime_nsec;
    time_t st_mtime;
    int st_mtime_nsec;
    time_t st_ctime;
    int st_ctime_nsec;
    unsigned long st_file_attributes;
    unsigned long st_reparse_tag;
};
#else
#  define _Py_stat_struct stat
#endif

PyAPI_FUNC(int) _Py_fstat(
    int fd,
    struct _Py_stat_struct *status);

PyAPI_FUNC(int) _Py_fstat_noraise(
    int fd,
    struct _Py_stat_struct *status);

PyAPI_FUNC(int) _Py_stat(
    PyObject *path,
    struct stat *status);

PyAPI_FUNC(int) _Py_open(
    const char *pathname,
    int flags);

PyAPI_FUNC(int) _Py_open_noraise(
    const char *pathname,
    int flags);

PyAPI_FUNC(FILE *) _Py_wfopen(
    const wchar_t *path,
    const wchar_t *mode);

PyAPI_FUNC(FILE*) _Py_fopen_obj(
    PyObject *path,
    const char *mode);

PyAPI_FUNC(Py_ssize_t) _Py_read(
    int fd,
    void *buf,
    size_t count);

PyAPI_FUNC(Py_ssize_t) _Py_write(
    int fd,
    const void *buf,
    size_t count);

PyAPI_FUNC(Py_ssize_t) _Py_write_noraise(
    int fd,
    const void *buf,
    size_t count);

#ifdef HAVE_READLINK
PyAPI_FUNC(int) _Py_wreadlink(
    const wchar_t *path,
    wchar_t *buf,
    /* Number of characters of 'buf' buffer
       including the trailing NUL character */
    size_t buflen);
#endif

#ifdef HAVE_REALPATH
PyAPI_FUNC(wchar_t*) _Py_wrealpath(
    const wchar_t *path,
    wchar_t *resolved_path,
    /* Number of characters of 'resolved_path' buffer
       including the trailing NUL character */
    size_t resolved_path_len);
#endif

#ifndef MS_WINDOWS
PyAPI_FUNC(int) _Py_isabs(const wchar_t *path);
#endif

PyAPI_FUNC(int) _Py_abspath(const wchar_t *path, wchar_t **abspath_p);

PyAPI_FUNC(wchar_t*) _Py_wgetcwd(
    wchar_t *buf,
    /* Number of characters of 'buf' buffer
       including the trailing NUL character */
    size_t buflen);

PyAPI_FUNC(int) _Py_get_inheritable(int fd);

PyAPI_FUNC(int) _Py_set_inheritable(int fd, int inheritable,
                                    int *atomic_flag_works);

PyAPI_FUNC(int) _Py_set_inheritable_async_safe(int fd, int inheritable,
                                               int *atomic_flag_works);

PyAPI_FUNC(int) _Py_dup(int fd);

#ifndef MS_WINDOWS
PyAPI_FUNC(int) _Py_get_blocking(int fd);

PyAPI_FUNC(int) _Py_set_blocking(int fd, int blocking);
#else   /* MS_WINDOWS */
PyAPI_FUNC(void*) _Py_get_osfhandle_noraise(int fd);

PyAPI_FUNC(void*) _Py_get_osfhandle(int fd);

PyAPI_FUNC(int) _Py_open_osfhandle_noraise(void *handle, int flags);

PyAPI_FUNC(int) _Py_open_osfhandle(void *handle, int flags);
#endif  /* MS_WINDOWS */
