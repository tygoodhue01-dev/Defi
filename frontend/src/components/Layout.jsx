import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { Footer } from '@/components/Footer';
import { Toaster } from '@/components/ui/sonner';

export function Layout({ children }) {
  return (
    <div className="min-h-screen flex flex-col bg-background pattern-dots">
      <Navbar />
      <main className="flex-1">
        {children || <Outlet />}
      </main>
      <Footer />
      <Toaster position="top-right" richColors />
    </div>
  );
}
