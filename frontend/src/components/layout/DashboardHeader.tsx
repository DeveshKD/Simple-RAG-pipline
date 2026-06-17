'use client';

import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { Menu } from 'lucide-react';

interface DashboardHeaderProps {
  activeTab?: 'chat' | 'library' | 'settings';
  onMenuClick: () => void;
}

export default function DashboardHeader({ activeTab = 'chat', onMenuClick }: DashboardHeaderProps) {
  const { user } = useAuthStore();

  const getTitle = () => {
    switch (activeTab) {
      case 'chat':
        return 'Chat Sessions';
      case 'library':
        return 'Document Library';
      case 'settings':
        return 'Settings';
      default:
        return 'Dashboard';
    }
  };

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-3 lg:px-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button
            onClick={onMenuClick}
            variant="ghost"
            size="sm"
            className="lg:hidden"
          >
            <Menu className="w-5 h-5 text-gray-500" />
          </Button>
          
          <h1 className="text-lg font-semibold text-gray-900">
            {getTitle()}
          </h1>
        </div>
        
        {/* Desktop user info */}
        <div className="hidden lg:flex items-center space-x-3">
          <span className="text-sm text-gray-600">{user?.email}</span>
        </div>
      </div>
    </div>
  );
}