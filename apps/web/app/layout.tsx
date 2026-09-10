import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'VectoryAI',
  description: 'AI-assisted urban plan vectorization'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
