import { BrowserRouter, Routes, Route } from 'react-router'
import './App.css'
import LogInPage from './pages/log-in/LogIn'

function App() {

  return (
    <BrowserRouter>
      <Routes>
        <Route path='' element={<LogInPage/>}/>
      </Routes>
    </BrowserRouter>
  )
}

export default App
