#ifndef ITCL_USE_MODIFIED_TCL_H
/* this is just to provide the definition. This struct is only used if
 * infoPtr->useOldResolvers == 0 which is not the default
 */
#define FRAME_HAS_RESOLVER 0x100
typedef Tcl_Command (Tcl_CmdAliasProc)(Tcl_Interp *interp,
        Tcl_Namespace *nsPtr, const char *cmdName,
        void *clientData);
typedef Tcl_Var (Tcl_VarAliasProc)(Tcl_Interp *interp,
        Tcl_Namespace *nsPtr, const char *varName,
        void *clientData);

#ifndef _TCL_RESOLVE_DEFINED
typedef struct Tcl_Resolve {
    Tcl_VarAliasProc *varProcPtr;
    Tcl_CmdAliasProc *cmdProcPtr;
    void *clientData;
} Tcl_Resolve;
#define _TCL_RESOLVE_DEFINED 1
#endif
#endif

#ifndef _TCLINT
struct Tcl_ResolvedVarInfo;

typedef Tcl_Var (Tcl_ResolveRuntimeVarProc)(Tcl_Interp *interp,
	struct Tcl_ResolvedVarInfo *vinfoPtr);

typedef void (Tcl_ResolveVarDeleteProc)(struct Tcl_ResolvedVarInfo *vinfoPtr);

/*
 * The following structure encapsulates the routines needed to resolve a
 * variable reference at runtime. Any variable specific state will typically
 * be appended to this structure.
 */

typedef struct Tcl_ResolvedVarInfo {
    Tcl_ResolveRuntimeVarProc *fetchProc;
    Tcl_ResolveVarDeleteProc *deleteProc;
} Tcl_ResolvedVarInfo;

typedef int (Tcl_ResolveCompiledVarProc) (Tcl_Interp *interp,
	const char *name, Tcl_Size length, Tcl_Namespace *context,
	Tcl_ResolvedVarInfo **rPtr);

typedef int (Tcl_ResolveVarProc) (Tcl_Interp *interp, const char *name,
	Tcl_Namespace *context, int flags, Tcl_Var *rPtr);

typedef int (Tcl_ResolveCmdProc) (Tcl_Interp *interp, const char *name,
	Tcl_Namespace *context, int flags, Tcl_Command *rPtr);

typedef struct Tcl_ResolverInfo {
    Tcl_ResolveCmdProc *cmdResProc;
				/* Procedure handling command name
				 * resolution. */
    Tcl_ResolveVarProc *varResProc;
				/* Procedure handling variable name resolution
				 * for variables that can only be handled at
				 * runtime. */
    Tcl_ResolveCompiledVarProc *compiledVarResProc;
				/* Procedure handling variable name resolution
				 * at compile time. */
} Tcl_ResolverInfo;
#endif


/* here come the definitions for code which should be migrated to Tcl core */
/* these functions DO NOT exist and are not published */
#ifndef _TCL_PROC_DEFINED
typedef struct Tcl_Proc_ *Tcl_Proc;
#define _TCL_PROC_DEFINED 1
#endif

MODULE_SCOPE Tcl_Var Tcl_NewNamespaceVar(Tcl_Interp *interp, Tcl_Namespace *nsPtr,
	const char *varName);
MODULE_SCOPE void Itcl_PreserveVar(Tcl_Var var);
MODULE_SCOPE void Itcl_ReleaseVar(Tcl_Var var);
MODULE_SCOPE int Itcl_IsCallFrameArgument(Tcl_Interp *interp, const char *name);
MODULE_SCOPE size_t Itcl_GetCallVarFrameObjc(Tcl_Interp *interp);
MODULE_SCOPE Tcl_Obj *const * Itcl_GetCallVarFrameObjv(Tcl_Interp *interp);
#define Tcl_SetNamespaceResolver _Tcl_SetNamespaceResolver
MODULE_SCOPE int _Tcl_SetNamespaceResolver(Tcl_Namespace *nsPtr,
        struct Tcl_Resolve *resolvePtr);
