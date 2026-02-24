import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Web3Provider } from '@/components/Web3Provider';
import { Layout } from '@/components/Layout';
import HomePage from '@/pages/HomePage';
import VaultsPage from '@/pages/VaultsPage';
import VaultDetailPage from '@/pages/VaultDetailPage';
import AdminLoginPage from '@/pages/AdminLoginPage';
import AdminVaultsPage from '@/pages/AdminVaultsPage';
import '@/App.css';

function App() {
  return (
    <Web3Provider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="vaults" element={<VaultsPage />} />
            <Route path="vaults/:id" element={<VaultDetailPage />} />
            <Route path="admin/login" element={<AdminLoginPage />} />
            <Route path="admin/vaults" element={<AdminVaultsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </Web3Provider>
  );
}

export default App;
