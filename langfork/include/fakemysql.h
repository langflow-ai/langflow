/*
 * fakemysql.h --
 *
 *	Fake definitions of the MySQL API sufficient to build tdbc::mysql
 *	without having an MySQL installation on the build system. This file
 *	comprises only data type, constant and function definitions.
 *
 * The programmers of this file believe that it contains material not
 * subject to copyright under the doctrines of scenes a faire and
 * of merger of idea and expression. Accordingly, this file is in the
 * public domain.
 *
 *-----------------------------------------------------------------------------
 */

#ifndef FAKEMYSQL_H_INCLUDED
#define FAKEMYSQL_H_INCLUDED

#include <stddef.h>

#ifndef MODULE_SCOPE
#define MODULE_SCOPE extern
#endif

MODULE_SCOPE Tcl_LoadHandle MysqlInitStubs(Tcl_Interp*);

#ifdef _WIN32
#define STDCALL __stdcall
#else
#define STDCALL /* nothing */
#endif

enum enum_field_types {
    MYSQL_TYPE_DECIMAL=0,
    MYSQL_TYPE_TINY=1,
    MYSQL_TYPE_SHORT=2,
    MYSQL_TYPE_LONG=3,
    MYSQL_TYPE_FLOAT=4,
    MYSQL_TYPE_DOUBLE=5,
    MYSQL_TYPE_NULL=6,
    MYSQL_TYPE_TIMESTAMP=7,
    MYSQL_TYPE_LONGLONG=8,
    MYSQL_TYPE_INT24=9,
    MYSQL_TYPE_DATE=10,
    MYSQL_TYPE_TIME=11,
    MYSQL_TYPE_DATETIME=12,
    MYSQL_TYPE_YEAR=13,
    MYSQL_TYPE_NEWDATE=14,
    MYSQL_TYPE_VARCHAR=15,
    MYSQL_TYPE_BIT=16,
    MYSQL_TYPE_NEWDECIMAL=246,
    MYSQL_TYPE_ENUM=247,
    MYSQL_TYPE_SET=248,
    MYSQL_TYPE_TINY_BLOB=249,
    MYSQL_TYPE_MEDIUM_BLOB=250,
    MYSQL_TYPE_LONG_BLOB=251,
    MYSQL_TYPE_BLOB=252,
    MYSQL_TYPE_VAR_STRING=253,
    MYSQL_TYPE_STRING=254,
    MYSQL_TYPE_GEOMETRY=255
};

enum mysql_option {
    MYSQL_SET_CHARSET_NAME=7,
};

enum mysql_status {
    MYSQL_STATUS_READY=0,
};

#define CLIENT_COMPRESS 	32
#define CLIENT_INTERACTIVE 1024
#define MYSQL_DATA_TRUNCATED 101
#define MYSQL_ERRMSG_SIZE 512
#define MYSQL_NO_DATA 100
#define SCRAMBLE_LENGTH 20
#define SQLSTATE_LENGTH 5

typedef struct st_list LIST;
typedef struct st_mem_root MEM_ROOT;
typedef struct st_mysql MYSQL;
typedef struct st_mysql_bind MYSQL_BIND;
typedef struct st_mysql_field MYSQL_FIELD;
typedef struct st_mysql_res MYSQL_RES;
typedef char** MYSQL_ROW;
typedef struct st_mysql_stmt MYSQL_STMT;
typedef char my_bool;
#ifndef Socket_defined
typedef int	my_socket;
#define INVALID_SOCKET -1
#endif
typedef Tcl_WideUInt my_ulonglong;
typedef struct st_net NET;
typedef struct st_used_mem USED_MEM;
typedef struct st_vio Vio;

struct st_mem_root {
  USED_MEM *free;
  USED_MEM *used;
  USED_MEM *pre_alloc;
  size_t min_malloc;
  size_t block_size;
  unsigned int block_num;
  unsigned int first_block_usage;
  void (*error_handler)(void);
};

struct st_mysql_options {
    unsigned int connect_timeout;
    unsigned int read_timeout;
    unsigned int write_timeout;
    unsigned int port;
    unsigned int protocol;
    unsigned long client_flag;
    char *host;
    char *user;
    char *password;
    char *unix_socket;
    char *db;
    struct st_dynamic_array *init_commands;
    char *my_cnf_file;
    char *my_cnf_group;
    char *charset_dir;
    char *charset_name;
    char *ssl_key;
    char *ssl_cert;
    char *ssl_ca;
    char *ssl_capath;
    char *ssl_cipher;
    char *shared_memory_base_name;
    unsigned long max_allowed_packet;
    my_bool use_ssl;
    my_bool compress,named_pipe;
    my_bool rpl_probe;
    my_bool rpl_parse;
    my_bool no_master_reads;
#if !defined(CHECK_EMBEDDED_DIFFERENCES) || defined(EMBEDDED_LIBRARY)
    my_bool separate_thread;
#endif
    enum mysql_option methods_to_use;
    char *client_ip;
    my_bool secure_auth;
    my_bool report_data_truncation;
    int (*local_infile_init)(void **, const char *, void *);
    int (*local_infile_read)(void *, char *, unsigned int);
    void (*local_infile_end)(void *);
    int (*local_infile_error)(void *, char *, unsigned int);
    void *local_infile_userdata;
    void *extension;
};

struct st_net {
#if !defined(CHECK_EMBEDDED_DIFFERENCES) || !defined(EMBEDDED_LIBRARY)
    Vio *vio;
    unsigned char *buff;
    unsigned char *buff_end;
    unsigned char *write_pos;
    unsigned char *read_pos;
    my_socket fd;
    unsigned long remain_in_buf;
    unsigned long length;
    unsigned long buf_length;
    unsigned long where_b;
    unsigned long max_packet;
    unsigned long max_packet_size;
    unsigned int pkt_nr;
    unsigned int compress_pkt_nr;
    unsigned int write_timeout;
    unsigned int read_timeout;
    unsigned int retry_count;
    int fcntl;
    unsigned int *return_status;
    unsigned char reading_or_writing;
    char save_char;
    my_bool unused0;
    my_bool unused;
    my_bool compress;
    my_bool unused1;
#endif
    unsigned char *query_cache_query;
    unsigned int last_errno;
    unsigned char error;
    my_bool unused2;
    my_bool return_errno;
    char last_error[MYSQL_ERRMSG_SIZE];
    char sqlstate[SQLSTATE_LENGTH+1];
    void *extension;
#if defined(MYSQL_SERVER) && !defined(EMBEDDED_LIBRARY)
    my_bool skip_big_packet;
#endif
};

/*
 * st_mysql differs between 5.0 and 5.1, but the 5.0 version is a
 * strict subset, we don't use any of the 5.1 fields, and we don't
 * ever allocate the structure ourselves.
 */

struct st_mysql {
    NET net;
    unsigned char *connector_fd;
    char *host;
    char *user;
    char *passwd;
    char *unix_socket;
    char *server_version;
    char *host_info;
    char *info;
    char *db;
    struct charset_info_st *charset;
    MYSQL_FIELD *fields;
    MEM_ROOT field_alloc;
    my_ulonglong affected_rows;
    my_ulonglong insert_id;
    my_ulonglong extra_info;
    unsigned long thread_id;
    unsigned long packet_length;
    unsigned int port;
    unsigned long client_flag;
    unsigned long server_capabilities;
    unsigned int protocol_version;
    unsigned int field_count;
    unsigned int server_status;
    unsigned int server_language;
    unsigned int warning_count;
    struct st_mysql_options options;
    enum mysql_status status;
    my_bool free_me;
    my_bool reconnect;
    char scramble[SCRAMBLE_LENGTH+1];
    my_bool rpl_pivot;
    struct st_mysql *master;
    struct st_mysql *next_slave;
    struct st_mysql* last_used_slave;
    struct st_mysql* last_used_con;
    LIST  *stmts;
    const struct st_mysql_methods *methods;
    void *thd;
    my_bool *unbuffered_fetch_owner;
    char *info_buffer;
};

/*
 * There are different version of the MYSQL_BIND structure before and after
 * MySQL 5.1. We go after the fields of the structure using accessor functions
 * so that the code in this file is compatible with both versions.
 */

struct st_mysql_bind_51 {	/* Post-5.1 */
    unsigned long* length;
    my_bool* is_null;
    void* buffer;
    my_bool* error;
    unsigned char* row_ptr;
    void (*store_param_func)(NET* net, MYSQL_BIND* param);
    void (*fetch_result)(MYSQL_BIND*, MYSQL_FIELD*, unsigned char**);
    void (*skip_result)(MYSQL_BIND*, MYSQL_FIELD*, unsigned char**);
    unsigned long buffer_length;
    unsigned long offset;
    unsigned long length_value;
    unsigned int param_number;
    unsigned int pack_length;
    enum enum_field_types buffer_type;
    my_bool error_value;
    my_bool is_unsigned;
    my_bool long_data_used;
    my_bool is_null_value;
    void* extension;
};

struct st_mysql_bind_50 {	/* Pre-5.1 */
    unsigned long* length;
    my_bool* is_null;
    void* buffer;
    my_bool* error;
    enum enum_field_types buffer_type;
    unsigned long buffer_length;
    unsigned char* row_ptr;
    unsigned long offset;
    unsigned long length_value;
    unsigned int param_number;
    unsigned int pack_length;
    my_bool error_value;
    my_bool is_unsigned;
    my_bool long_data_used;
    my_bool is_null_value;
    void (*store_param_func)(NET* net, MYSQL_BIND* param);
    void (*fetch_result)(MYSQL_BIND*, MYSQL_FIELD*, unsigned char**);
    void (*skip_result)(MYSQL_BIND*, MYSQL_FIELD*, unsigned char**);
};

/*
 * There are also different versions of the MYSQL_FIELD structure; fortunately,
 * the 5.1 version is a strict extension of the 5.0 version.
 */

struct st_mysql_field {
    char* name;
    char *org_name;
    char* table;
    char* org_table;
    char* db;
    char* catalog;
    char* def;
    unsigned long length;
    unsigned long max_length;
    unsigned int name_length;
    unsigned int org_name_length;
    unsigned int table_length;
    unsigned int org_table_length;
    unsigned int db_length;
    unsigned int catalog_length;
    unsigned int def_length;
    unsigned int flags;
    unsigned int decimals;
    unsigned int charsetnr;
    enum enum_field_types type;
};
struct st_mysql_field_50 {
    struct st_mysql_field field;
};
struct st_mysql_field_51 {
    struct st_mysql_field field;
    void* extension;
};
#define NOT_NULL_FLAG 1

#define IS_NUM(t)	((t) <= MYSQL_TYPE_INT24 || (t) == MYSQL_TYPE_YEAR || (t) == MYSQL_TYPE_NEWDECIMAL)

#define mysql_library_init mysql_server_init
#define mysql_library_end mysql_server_end

#include "mysqlStubs.h"

#endif /* not FAKEMYSQL_H_INCLUDED */
