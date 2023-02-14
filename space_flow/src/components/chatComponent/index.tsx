import {
  ChatBubbleBottomCenterTextIcon,
  PaperAirplaneIcon,
  XMarkIcon,
} from "@heroicons/react/24/outline";

export default function Chat({}) {
  return (
    <>
      <div className="w-[400px] absolute bottom-0 right-6">
        <div className="border h-full rounded-xl rounded-b-none bg-white shadow">
          <div className="flex justify-between items-center px-5 py-3 border-b">
            <div className="flex gap-3 text-xl font-medium items-center">
              <ChatBubbleBottomCenterTextIcon className="h-8 w-8 mt-1 text-blue-600" />
              Chat
            </div>
            <XMarkIcon className="h-6 w-6 text-gray-600" />
          </div>
          <div className="w-full h-[400px] flex gap-3 mb-auto overflow-y-auto flex-col bg-gray-50 p-3 py-5">
            <div className="w-full text-start">
              <div className="text-start inline-block bg-gray-200 rounded-xl p-3 overflow-hidden w-fit max-w-[280px] px-5 text-sm font-normal rounded-tl-none">
                Lorem Ipsum is simply dummy text of the printing and typesetting
                industry.
              </div>
            </div>
            <div className="w-full text-end">
              <div className="text-start inline-block bg-blue-600 rounded-xl p-3 overflow-hidden w-fit max-w-[280px] px-5 text-sm text-white font-normal rounded-tr-none">
                Lorem Ipsum has been the industry's standard dummy text ever
                since the 1500s
              </div>
            </div>
          </div>
          <div className="w-full bg-white border-t flex items-center justify-between p-3">
            <div className="relative w-full mt-1 rounded-md shadow-sm">
              <input
                type="text"
                className="form-input block w-full rounded-md border-gray-300 pr-10 sm:text-sm"
                placeholder="Send a message..."
              />
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <button>
                <PaperAirplaneIcon
                  className="h-5 w-5 text-gray-400 hover:text-gray-600"
                  aria-hidden="true"
                />
                </button>
                
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
