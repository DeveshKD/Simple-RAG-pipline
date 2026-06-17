'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  MessageSquare, 
  BookOpen, 
  LogOut, 
  X,
  User,
  Settings
} from 'lucide-react';

interface DashboardSidebarProps {
  activeTab?: 'chat' | 'library' | 'settings';
  isOpen: boolean;
  onClose: () => void;
}

export default function DashboardSidebar({ activeTab = 'chat', isOpen, onClose }: DashboardSidebarProps) {
  const { user, logout } = useAuthStore();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/auth/login');
  };

  const navigation = [
    { name: 'Chat', href: '/dashboard', icon: MessageSquare, key: 'chat' },
    { name: 'Library', href: '/dashboard/library', icon: BookOpen, key: 'library' },
    { name: 'Settings', href: '/dashboard/settings', icon: Settings, key: 'settings' },
  ];

  return (
    <>
      {/* Mobile sidebar backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out
        lg:translate-x-0 lg:static lg:inset-0
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <span className="font-semibold text-gray-900">DocRAG</span>
            </div>
            <button
              onClick={onClose}
              className="lg:hidden p-1 rounded-md hover:bg-gray-100"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-2">
            {navigation.map((item) => {
              const isActive = activeTab === item.key;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`
                    flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                    ${isActive 
                      ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-600' 
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                    }
                  `}
                  onClick={onClose}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center">
                <User className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {user?.email || 'User'}
                </p>
                <p className="text-xs text-gray-500">Active</p>
              </div>
            </div>
            <Button
              onClick={handleLogout}
              variant="outline"
              size="sm"
              className="w-full justify-start text-gray-700 hover:text-red-700 hover:border-red-300"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}