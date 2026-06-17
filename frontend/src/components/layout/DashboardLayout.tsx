'use client';

import { useState } from 'react';
import DashboardSidebar from './DashboardSidebar';
import DashboardHeader from './DashboardHeader';

interface DashboardLayoutProps {
  children: React.ReactNode;
  activeTab?: 'chat' | 'library' | 'settings';
}

export default function DashboardLayout({ children, activeTab = 'chat' }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="lg:fixed lg:inset-y-0 lg:left-0 lg:w-64 lg:z-40">
        <DashboardSidebar 
          activeTab={activeTab}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      {/* Main content area */}
      <div className="lg:pl-64">
        {/* Header */}
        <DashboardHeader 
          activeTab={activeTab}
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* Page content */}
        <main className="p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}