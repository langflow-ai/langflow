export default function Input({onChange}){
    return (
        <>
            <input
            type="text"
            className="block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            placeholder="Type a text"
            onChange={(e) => {
                onChange(e.target.value);
            }}
            />
        </>
    );
}