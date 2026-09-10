const isGitHubPagesBuild = process.env.GITHUB_ACTIONS === 'true';
const basePath = isGitHubPagesBuild ? '/VectorAI' : '';

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  basePath,
  assetPrefix: basePath ? `${basePath}/` : '',
  images: {
    unoptimized: true
  }
};

export default nextConfig;
