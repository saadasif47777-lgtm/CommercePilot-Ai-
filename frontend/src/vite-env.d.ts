/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Deployed backend origin (e.g. https://my-service.onrender.com).
   *  Empty/undefined = same-origin, used by the Vite dev proxy. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
