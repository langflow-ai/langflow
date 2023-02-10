import {
  BoltIcon,
  Cog6ToothIcon,
  HomeIcon,
  LightBulbIcon,
  RocketLaunchIcon,
  TableCellsIcon,
} from '@heroicons/react/24/outline'


export const sidebarNavigation = [
  { name: 'Home', href: '/', icon: HomeIcon, current: true },
  { name: 'Table', href: '/table/', icon: TableCellsIcon, current: false },
  //{ name: 'Train', href: '#', icon: BoltIcon, current: false },
  //{ name: 'Model Details', href: '#', icon: LightBulbIcon, current: false },
  //{ name: 'Deploy', href: '#', icon: RocketLaunchIcon, current: false },
  { name: 'Settings', href: '/settings/', icon: Cog6ToothIcon, current: false },
]
