export default function Input({title, placeholder, onChange}){
    return (
        <>
            <div>
                <label className="block text-sm font-medium text-gray-700">
                    {title}
                </label>
                <div className="mt-1">
                    <input
                    type="text"
                    className="block w-full form-input rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    placeholder={placeholder}
                    onChange={onChange}
                    />
                </div>
            </div>
        </>
    );
}