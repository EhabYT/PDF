import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Providers } from '@/components/providers';
export const metadata: Metadata = { title: 'OmniFix Private Scanner', description: 'Private, local document scanning and enhancement. Your originals always stay yours.', manifest: '/manifest.webmanifest', appleWebApp: { capable: true, statusBarStyle: 'default', title: 'OmniFix' }, icons: { icon: '/icons/icon-192.png', apple: '/icons/icon-192.png' } };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover', themeColor: '#6c5ce7' };
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en" suppressHydrationWarning><body><Providers>{children}</Providers></body></html>; }
