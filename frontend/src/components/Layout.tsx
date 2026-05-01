import type { ReactNode } from 'react'
import Sidebar from './Sidebar'
import type { Period } from '../types'

interface Props {
  children: ReactNode
  activePeriod?: Period | null
}

export default function Layout({ children, activePeriod }: Props) {
  return (
    <>
      <Sidebar activePeriod={activePeriod} />
      <main className="main">{children}</main>
    </>
  )
}
