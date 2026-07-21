/** @type {import('next').NextConfig} */
const isElectronBuild = process.env.ELECTRON_BUILD === 'true'

const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  // Static export for Electron production packaging.
  // Note: Next.js API routes (app/api/**) are excluded from static exports.
  // In Electron production, all backend communication goes through FastAPI (localhost:8000).
  // Dev mode (next dev) is unaffected — API routes still work normally during development.
  ...(isElectronBuild && {
    output: 'export',
    // Electron loads static files via file:// — relative paths required
    assetPrefix: './',
    trailingSlash: true,
  }),
}

export default nextConfig
