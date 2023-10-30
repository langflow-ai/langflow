export default function TextOutputComponent({text,emissor}:{text:string,emissor:string}){
    return(<div>
        <strong>{emissor}</strong>
        <br></br>
        <div className="break-all w-80">{text}</div>
    </div>)
}