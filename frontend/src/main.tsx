import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './app/App'
import './style.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 1500 } } })
const root = document.getElementById('root')
if (!root) throw new Error('Application root is missing')

createRoot(root).render(<StrictMode><QueryClientProvider client={queryClient}>
  <BrowserRouter><App /></BrowserRouter>
</QueryClientProvider></StrictMode>)
