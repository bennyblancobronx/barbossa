import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Player from './Player'
import ToastContainer from './ToastContainer'

export default function Layout() {
  return (
    <div className="layout-dashboard">
      <Sidebar />

      <main className="main-content">
        <div className="page-content">
          <Outlet />
        </div>
      </main>

      <Player />
      <ToastContainer />
    </div>
  )
}
