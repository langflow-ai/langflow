import { useContext, useState } from 'react'
import {
    BellIcon,
    MoonIcon,
    SunIcon,
  } from '@heroicons/react/24/outline'
import { alertContext } from '../../contexts/alertContext'
import { useLayer } from 'react-laag'
import AlertDropdown from '../../alerts/alertDropDown'
import { darkContext } from '../../contexts/darkContext'

export default function Header(){
  const {notificationCenter, setNotificationCenter} = useContext(alertContext)
  const [isOpen,setIsOpen] = useState(false)
  const {layerProps,renderLayer, triggerProps} = useLayer({
    isOpen,
    placement: "left-start",
    auto:true,
    onOutsideClick:()=>setIsOpen(false),
    preferX: "left",
    triggerOffset: 10,
    containerOffset: 12,
    arrowOffset: 4,
  })
  const {dark, setDark} = useContext(darkContext);
    return (
    <header className="relative flex h-16 w-full shrink-0 items-center bg-white dark:bg-gray-800">
        {/* Desktop nav area */}
        <div className="flex min-w-0 flex-1  flex-row-reverse items-center justify-between">
          <div className="ml-10 flex shrink-0 items-center space-x-10 pr-4">
            <div className="flex items-center space-x-8">
              <span className="inline-flex gap-6">
                <button className="text-gray-400 hover:text-gray-500 " onClick={()=>{setDark(!dark)}}>
                  {dark ?
                    <SunIcon className="h-6 w-6" />
                  :
                    <MoonIcon className="h-6 w-6" />
                  }
                </button>
                <button type="button" {...triggerProps} className="-mx-1 rounded-full p-1 text-gray-400 hover:text-gray-500 relative" onClick={()=>{setNotificationCenter(false);setIsOpen(true)}}>
                  <span className="sr-only">View notifications</span>
                  {notificationCenter&&<div className='absolute top-[2px] w-2 h-2 rounded-full bg-red-600 right-[7px]'></div>}
                  
                  <BellIcon className="h-6 w-6" aria-hidden="true" />
                </button>{renderLayer(<div {...layerProps}><AlertDropdown closeFunction={()=>setIsOpen(false)} open={isOpen}></AlertDropdown></div>)}
              </span>
              </div>
            </div>
          </div>
        </header>
    )
}