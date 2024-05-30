/*
 * fakepq.h --
 *
 *	Minimal replacement for 'pq-fe.h' in the PostgreSQL client
 *	without having a PostgreSQL installation on the build system.
 *	This file comprises only data type, constant and function definitions.
 *
 * The programmers of this file believe that it contains material not
 * subject to copyright under the doctrines of scenes a faire and
 * of merger of idea and expression. Accordingly, this file is in the
 * public domain.
 *
 *-----------------------------------------------------------------------------
 */

#ifndef FAKEPQ_H_INCLUDED
#define FAKEPQ_H_INCLUDED

#ifndef MODULE_SCOPE
#define MODULE_SCOPE extern
#endif

MODULE_SCOPE Tcl_LoadHandle PostgresqlInitStubs(Tcl_Interp*);

typedef enum {
    CONNECTION_OK=0,
} ConnStatusType;
typedef enum {
    PGRES_EMPTY_QUERY=0,
    PGRES_BAD_RESPONSE=5,
    PGRES_NONFATAL_ERROR=6,
    PGRES_FATAL_ERROR=7,
} ExecStatusType;
typedef unsigned int Oid;
typedef struct pg_conn PGconn;
typedef struct pg_result PGresult;
typedef void (*PQnoticeProcessor)(void*, const PGresult*);

#define PG_DIAG_SQLSTATE 'C'
#define PG_DIAG_MESSAGE_PRIMARY 'M'

#include "pqStubs.h"

MODULE_SCOPE const pqStubDefs* pqStubs;

#endif
