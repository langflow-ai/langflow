
#ifndef _TCLINT
typedef void (ProcErrorProc)(Tcl_Interp *interp, Tcl_Obj *procNameObj);
#endif

#ifndef TCL_OO_INTERNAL_H
typedef int (TclOO_PreCallProc)(void *clientData, Tcl_Interp *interp,
	Tcl_ObjectContext context, Tcl_CallFrame *framePtr, int *isFinished);
typedef int (TclOO_PostCallProc)(void *clientData, Tcl_Interp *interp,
	Tcl_ObjectContext context, Tcl_Namespace *namespacePtr, int result);
#endif

MODULE_SCOPE int Itcl_NRRunCallbacks(Tcl_Interp *interp, void *rootPtr);
MODULE_SCOPE void * Itcl_GetCurrentCallbackPtr(Tcl_Interp *interp);
MODULE_SCOPE Tcl_Method Itcl_NewProcClassMethod(Tcl_Interp *interp, Tcl_Class clsPtr,
        TclOO_PreCallProc *preCallPtr, TclOO_PostCallProc *postCallPtr,
        ProcErrorProc *errProc, void *clientData, Tcl_Obj *nameObj,
	Tcl_Obj *argsObj, Tcl_Obj *bodyObj, void **clientData2);
MODULE_SCOPE Tcl_Method Itcl_NewProcMethod(Tcl_Interp *interp, Tcl_Object oPtr,
        TclOO_PreCallProc *preCallPtr, TclOO_PostCallProc *postCallPtr,
        ProcErrorProc *errProc, void *clientData, Tcl_Obj *nameObj,
	Tcl_Obj *argsObj, Tcl_Obj *bodyObj, void **clientData2);
MODULE_SCOPE int Itcl_PublicObjectCmd(void *clientData, Tcl_Interp *interp,
        Tcl_Class clsPtr, Tcl_Size objc, Tcl_Obj *const *objv);
MODULE_SCOPE Tcl_Method Itcl_NewForwardClassMethod(Tcl_Interp *interp,
        Tcl_Class clsPtr, int flags, Tcl_Obj *nameObj, Tcl_Obj *prefixObj);
MODULE_SCOPE int Itcl_SelfCmd(void *clientData, Tcl_Interp *interp,
        int objc, Tcl_Obj *const *objv);
MODULE_SCOPE int Itcl_IsMethodCallFrame(Tcl_Interp *interp);
MODULE_SCOPE int Itcl_InvokeEnsembleMethod(Tcl_Interp *interp, Tcl_Namespace *nsPtr,
    Tcl_Obj *namePtr, Tcl_Proc *procPtr, Tcl_Size objc, Tcl_Obj *const *objv);
MODULE_SCOPE int Itcl_InvokeProcedureMethod(void *clientData, Tcl_Interp *interp,
	int objc, Tcl_Obj *const *objv);
