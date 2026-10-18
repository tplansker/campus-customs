import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// FastAPI backend: run `uvicorn main:app --reload --port 8000` from backend/.
// Override with API_PORT=xxxx npm run dev if 8000 is busy.
const API_URL = `http://127.0.0.1:${process.env.API_PORT ?? '8000'}`

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': API_URL,
      '/media': API_URL,
    },
  },
})
