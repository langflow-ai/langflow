/*
 * fakesql.h --
 *
 *	Include file that defines the subset of SQL/CLI that TDBC
 *	uses, so that tdbc::odbc can build without an explicit ODBC
 *	dependency. It comprises only data type, constant and
 *	function declarations.
 *
 * The programmers of this file believe that it contains material not
 * subject to copyright under the doctrines of scenes a faire and
 * of merger of idea and expression. Accordingly, this file is in the
 * public domain.
 *
 *-----------------------------------------------------------------------------
 */

#ifndef FAKESQL_H_INCLUDED
#define FAKESQL_H_INCLUDED

#include <stddef.h>

#ifndef MODULE_SCOPE
#define MODULE_SCOPE extern
#endif

/* Limits */

#define SQL_MAX_DSN_LENGTH 32
#define SQL_MAX_MESSAGE_LENGTH 512

/* Fundamental data types */

#ifndef _WIN32
typedef int BOOL;
typedef unsigned int DWORD;
typedef void* HANDLE;
typedef HANDLE HWND;
typedef unsigned short WCHAR;
typedef char* LPSTR;
typedef WCHAR* LPWSTR;
typedef const char* LPCSTR;
typedef const WCHAR* LPCWSTR;
typedef unsigned short WORD;
#endif
typedef void* PVOID;
typedef short RETCODE;
typedef long SDWORD;
typedef short SWORD;
typedef unsigned short USHORT;
typedef USHORT UWORD;

/* ODBC data types */

typedef Tcl_WideInt SQLBIGINT;
typedef unsigned char SQLCHAR;
typedef double SQLDOUBLE;
typedef void* SQLHANDLE;
typedef SDWORD SQLINTEGER;
typedef PVOID SQLPOINTER;
typedef SWORD SQLSMALLINT;
typedef Tcl_WideUInt SQLUBIGINT;
typedef unsigned char SQLUCHAR;
typedef unsigned int SQLUINTEGER;
typedef UWORD SQLUSMALLINT;
typedef WCHAR SQLWCHAR;

typedef SQLSMALLINT SQLRETURN;

/* TODO - Check how the SQLLEN and SQLULEN types are handled on
 *        64-bit Unix. */

#if defined(_WIN64)
typedef Tcl_WideInt SQLLEN;
typedef Tcl_WideUInt SQLULEN;
#else
typedef SQLINTEGER SQLLEN;
typedef SQLUINTEGER SQLULEN;
#endif

/* Handle types */

typedef SQLHANDLE SQLHENV;
typedef SQLHANDLE SQLHDBC;
typedef SQLHANDLE SQLHSTMT;
typedef HWND SQLHWND;

#define SQL_HANDLE_DBC 2
#define SQL_HANDLE_ENV 1
#define SQL_HANDLE_STMT 3

/* Null handles */

#define SQL_NULL_HANDLE ((SQLHANDLE) 0)
#define SQL_NULL_HENV ((SQLHENV) 0)
#define SQL_NULL_HDBC ((SQLHDBC) 0)
#define SQL_NULL_HSTMT ((SQLHSTMT) 0)

/* SQL data types */

enum _SQL_DATATYPE {
    SQL_BIGINT = -5,
    SQL_BINARY = -2,
    SQL_BIT = -7,
    SQL_CHAR = 1,
    SQL_DATE = 9,
    SQL_DECIMAL = 3,
    SQL_DOUBLE = 8,
    SQL_FLOAT = 6,
    SQL_INTEGER = 4,
    SQL_LONGVARBINARY = -4,
    SQL_LONGVARCHAR = -1,
    SQL_NUMERIC = 2,
    SQL_REAL = 7,
    SQL_SMALLINT = 5,
    SQL_TIME = 10,
    SQL_TIMESTAMP = 11,
    SQL_TINYINT = -6,
    SQL_VARBINARY = -3,
    SQL_VARCHAR = 12,
    SQL_WCHAR = -8,
    SQL_WVARCHAR = -9,
    SQL_WLONGVARCHAR = -10,
};

/* C data types */

#define SQL_SIGNED_OFFSET (-20)

#define SQL_C_BINARY SQL_BINARY
#define SQL_C_CHAR SQL_CHAR
#define SQL_C_DOUBLE SQL_DOUBLE
#define SQL_C_LONG SQL_INTEGER
#define SQL_C_SBIGINT SQL_BIGINT + SQL_SIGNED_OFFSET
#define SQL_C_SLONG SQL_INTEGER + SQL_SIGNED_OFFSET
#define SQL_C_WCHAR SQL_WCHAR

/* Parameter transmission diretions */

#define SQL_PARAM_INPUT 1

/* Status returns */

#define    SQL_ERROR (-1)
#define    SQL_NO_DATA 100
#define	   SQL_NO_TOTAL (-4)
#define    SQL_SUCCESS 0
#define    SQL_SUCCESS_WITH_INFO 1
#define    SQL_SUCCEEDED(rc) (((rc)&(~1))==0)

/* Diagnostic fields */

enum _SQL_DIAG {
    SQL_DIAG_NUMBER = 2,
    SQL_DIAG_SQLSTATE = 4
};

/* Transaction isolation levels */

#define SQL_TXN_READ_COMMITTED 2
#define SQL_TXN_READ_UNCOMMITTED 1
#define SQL_TXN_REPEATABLE_READ 4
#define SQL_TXN_SERIALIZABLE 8

/* Access modes */

#define SQL_MODE_READ_ONLY 1UL
#define SQL_MODE_READ_WRITE 0UL

/* ODBC properties */

#define SQL_ACCESS_MODE 101
#define SQL_AUTOCOMMIT 102
#define SQL_TXN_ISOLATION 108

/* ODBC attributes */

#define SQL_ATTR_ACCESS_MODE SQL_ACCESS_MODE
#define SQL_ATTR_CONNECTION_TIMEOUT 113
#define SQL_ATTR_ODBC_VERSION 200
#define SQL_ATTR_TXN_ISOLATION SQL_TXN_ISOLATION
#define SQL_ATTR_AUTOCOMMIT SQL_AUTOCOMMIT

/* Nullable? */

#define SQL_NULLABLE_UNKNOWN 2

/* Placeholder for length of missing data */

#define SQL_NULL_DATA (-1)

/* ODBC versions */

#define SQL_OV_ODBC3 3UL
#define SQL_ODBC_VER 10

/* SQLDriverConnect flags */

#define SQL_DRIVER_COMPLETE_REQUIRED 3
#define SQL_DRIVER_NOPROMPT 0

/* SQLGetTypeInfo flags */

#define SQL_ALL_TYPES 0

/* Transaction actions */

#define SQL_COMMIT 0
#define SQL_ROLLBACK 1

/* Data source fetch flags */

#define SQL_FETCH_FIRST 2
#define SQL_FETCH_FIRST_SYSTEM 32
#define SQL_FETCH_FIRST_USER 31
#define SQL_FETCH_NEXT 1

/* ODBCINST actions */

#define  ODBC_ADD_DSN     1
#define  ODBC_CONFIG_DSN  2
#define  ODBC_REMOVE_DSN  3
#define ODBC_ADD_SYS_DSN 4
#define ODBC_CONFIG_SYS_DSN 5
#define ODBC_REMOVE_SYS_DSN 6

/* ODBCINST errors */

#define ODBC_ERROR_GENERAL_ERR 1
#define ODBC_ERROR_INVALID_BUFF_LEN 2
#define ODBC_ERROR_INVALID_HWND 3
#define ODBC_ERROR_INVALID_STR 4
#define ODBC_ERROR_INVALID_REQUEST_TYPE 5
#define ODBC_ERROR_COMPONENT_NOT_FOUND 6
#define ODBC_ERROR_INVALID_NAME 7
#define ODBC_ERROR_INVALID_KEYWORD_VALUE 8
#define ODBC_ERROR_INVALID_DSN 9
#define ODBC_ERROR_INVALID_INF 10
#define ODBC_ERROR_REQUEST_FAILED 11
#define ODBC_ERROR_INVALID_PATH 12
#define ODBC_ERROR_LOAD_LIB_FAILED 13
#define ODBC_ERROR_INVALID_PARAM_SEQUENCE 14
#define ODBC_ERROR_INVALID_LOG_FILE 15
#define ODBC_ERROR_USER_CANCELED 16
#define ODBC_ERROR_USAGE_UPDATE_FAILED 17
#define ODBC_ERROR_CREATE_DSN_FAILED 18
#define ODBC_ERROR_WRITING_SYSINFO_FAILED 19
#define ODBC_ERROR_REMOVE_DSN_FAILED 20
#define ODBC_ERROR_OUT_OF_MEM 21
#define ODBC_ERROR_OUTPUT_STRING_TRUNCATED 22

/* ODBC client library entry points */

#ifdef _WIN32
#define SQL_API __stdcall
#define INSTAPI __stdcall
#else
#define SQL_API /* nothing */
#define INSTAPI /* nothing */
#endif

#include "odbcStubs.h"
MODULE_SCOPE const odbcStubDefs* odbcStubs;

/*
 * Additional entry points in ODBCINST - all of these are optional
 * and resolved with Tcl_FindSymbol, not directly in Tcl_LoadLibrary.
 */

MODULE_SCOPE BOOL (INSTAPI* SQLConfigDataSourceW)(HWND, WORD, LPCWSTR,
						  LPCWSTR);
MODULE_SCOPE BOOL (INSTAPI* SQLConfigDataSource)(HWND, WORD, LPCSTR, LPCSTR);
MODULE_SCOPE BOOL (INSTAPI* SQLInstallerErrorW)(WORD, DWORD*, LPWSTR, WORD,
						WORD*);
MODULE_SCOPE BOOL (INSTAPI* SQLInstallerError)(WORD, DWORD*, LPSTR, WORD,
					       WORD*);

/*
 * Function that initialises the stubs
 */

MODULE_SCOPE Tcl_LoadHandle OdbcInitStubs(Tcl_Interp*, Tcl_LoadHandle*);

#endif
