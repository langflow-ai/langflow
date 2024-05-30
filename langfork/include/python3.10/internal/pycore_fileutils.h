#ifndef Py_INTERNAL_FILEUTILS_H
#define Py_INTERNAL_FILEUTILS_H
#ifdef __cplusplus
extern "C" {
#endif

#ifndef Py_BUILD_CORE
#  error "Py_BUILD_CORE must be defined to include this header"
#endif

#include <locale.h>   /* struct lconv */

PyAPI_DATA(int) _Py_HasFileSystemDefaultEncodeErrors;

PyAPI_FUNC(int) _Py_DecodeUTF8Ex(
    const char *arg,
    Py_ssize_t arglen,
    wchar_t **wstr,
    size_t *wlen,
    const char **reason,
    _Py_error_handler errors);

PyAPI_FUNC(int) _Py_EncodeUTF8Ex(
    const wchar_t *text,
    char **str,
    size_t *error_pos,
    const char **reason,
    int raw_malloc,
    _Py_error_handler errors);

PyAPI_FUNC(wchar_t*) _Py_DecodeUTF8_surrogateescape(
    const char *arg,
    Py_ssize_t arglen,
    size_t *wlen);

PyAPI_FUNC(int) _Py_GetForceASCII(void);

/* Reset "force ASCII" mode (if it was initialized).

   This function should be called when Python changes the LC_CTYPE locale,
   so the "force ASCII" mode can be detected again on the new locale
   encoding. */
PyAPI_FUNC(void) _Py_ResetForceASCII(void);


PyAPI_FUNC(int) _Py_GetLocaleconvNumeric(
    struct lconv *lc,
    PyObject **decimal_point,
    PyObject **thousands_sep);

PyAPI_FUNC(void) _Py_closerange(int first, int last);

PyAPI_FUNC(wchar_t*) _Py_GetLocaleEncoding(void);
PyAPI_FUNC(PyObject*) _Py_GetLocaleEncodingObject(void);

#ifdef HAVE_NON_UNICODE_WCHAR_T_REPRESENTATION
extern int _Py_LocaleUsesNonUnicodeWchar(void);

extern wchar_t* _Py_DecodeNonUnicodeWchar(
    const wchar_t* native,
    Py_ssize_t size);

extern int _Py_EncodeNonUnicodeWchar_InPlace(
    wchar_t* unicode,
    Py_ssize_t size);
#endif

#ifdef __cplusplus
}
#endif
#endif /* !Py_INTERNAL_FILEUTILS_H */
