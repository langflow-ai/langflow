const defaultErrorMessages ={
    deleteRLAS:"Could not remove label from record, please try again",
    addRLAS:"Could not label this record, please try again",
    deleteRecords:"Could not delete record, please try again later"
}



export class CustomError extends Error{
    constructor(message:string){
        super(message)
        Object.setPrototypeOf(this,CustomError.prototype)
    }

    getErrorMessage(): string{
        return defaultErrorMessages[this.message]?? "unknow error, please try again"
    }
}