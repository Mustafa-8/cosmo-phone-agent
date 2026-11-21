import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import PhoneCall from './voice/PhoneCall.jsx'

// /?phone (or a ?room=... link) opens the two-phone call; everything else is the normal website.
const params = new URLSearchParams(window.location.search)
const Page = params.has('phone') || params.has('room') ? PhoneCall : App

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
