'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useApp } from '@/components/providers';
export default function Home() { const router = useRouter(); const { session } = useApp(); useEffect(() => { if (session?.authenticated) router.replace('/dashboard/'); }, [session, router]); return <div className="page-loading">Opening your private workspace…</div>; }
