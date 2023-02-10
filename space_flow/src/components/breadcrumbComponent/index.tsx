import { ChevronRightIcon, HomeIcon } from '@heroicons/react/20/solid'
import { useContext } from 'react';
import { Link } from 'react-router-dom'
import { locationContext } from '../../contexts/locationContext';

const breadcrumbNameMap: { [key: string]: string } = {
  '/settings': 'Settings',
  '/settings/general': 'General',
  '/settings/general/main': 'Main',
  '/table': 'Table',
};


function getPages(atual){
  let pages = [];
  for(let i = 2; i <= atual.length; i++){
    let to = '/' + atual.slice(1,i).join('/');
    pages.push({ name: breadcrumbNameMap[to], href: to })
  }
  return (pages);
  
}

export default function Breadcrumb(){
  let {atual} = useContext(locationContext);
    return (
        <div>
            <nav className="flex ml-2" aria-label="Breadcrumb">
              <ol className="flex items-center space-x-4">
                <li>
                  <div>
                    <Link to='/' className="text-gray-400 hover:text-gray-500">
                      <HomeIcon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                      <span className="sr-only">Home</span>
                    </Link>
                  </div>
                </li>
                  {getPages(atual).map((page) => (
                    <li key={page.href}>
                      <div className="flex items-center">
                        <ChevronRightIcon className="h-5 w-5 flex-shrink-0 text-gray-400" aria-hidden="true" />
                        <a
                          href={page.href}
                          className="ml-4 text-sm font-medium text-gray-500 hover:text-gray-700"
                        >
                          {page.name}
                        </a>
                      </div>
                    </li>
                  ))}
              </ol>
            </nav>
        </div>
    )
}