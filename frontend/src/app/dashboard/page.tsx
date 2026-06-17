'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useInteractionStore } from '@/store/interactionStore';
import { useDocumentStore } from '@/store/documentStore';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Plus, 
  MessageSquare, 
  FileText, 
  Upload, 
  Search, 
  Calendar,
  Trash2,
  MoreHorizontal,
  BookOpen
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export default function DashboardPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const { 
    interactions, 
    isLoading, 
    error, 
    fetchInteractions, 
    deleteInteraction,
    createInteractionWithDocument,
    clearError 
  } = useInteractionStore();

  const router = useRouter();

  useEffect(() => {
    fetchInteractions();
  }, [fetchInteractions]);

  const filteredInteractions = interactions.filter(interaction =>
    interaction.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateWithDocument = async () => {
    if (!uploadFile) return;

    setIsUploading(true);
    clearError();

    const interactionId = await createInteractionWithDocument(uploadFile);
    
    if (interactionId) {
      setShowUploadDialog(false);
      setUploadFile(null);
      router.push(`/dashboard/chat/${interactionId}`);
    }
    
    setIsUploading(false);
  };

  const handleDeleteInteraction = async (interactionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (confirm('Are you sure you want to delete this chat session? This action cannot be undone.')) {
      await deleteInteraction(interactionId);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <DashboardLayout activeTab="chat">
      <div className="max-w-7xl mx-auto">
        {/* Header Section */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Chat Sessions</h2>
              <p className="text-gray-600">Start new conversations or continue existing ones</p>
            </div>
            <Button
              onClick={() => setShowUploadDialog(true)}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-md hover:shadow-lg transition-all duration-200"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Chat with Document
            </Button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Alert className="mb-6 border-red-200 bg-red-50">
            <AlertDescription className="text-red-800">
              {typeof error === 'string' ? error : 'An error occurred'}
            </AlertDescription>
          </Alert>
        )}

        {/* Search Bar */}
        <div className="mb-6">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              placeholder="Search chat sessions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-white border-gray-200 shadow-sm"
            />
          </div>
        </div>

        {/* Upload Dialog */}
        {showUploadDialog && (
          <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
            <Card className="w-full max-w-md">
              <CardHeader>
                <CardTitle>Start New Chat with Document</CardTitle>
                <CardDescription>
                  Upload a document to begin a new conversation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                  <input
                    type="file"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="hidden"
                    id="file-upload"
                    accept=".pdf,.txt,.csv,.doc,.docx"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-600">
                      {uploadFile ? uploadFile.name : 'Click to select file'}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Supports PDF, TXT, CSV, DOC, DOCX
                    </p>
                  </label>
                </div>
                
                <div className="flex space-x-3">
                  <Button
                    onClick={() => {
                      setShowUploadDialog(false);
                      setUploadFile(null);
                    }}
                    variant="outline"
                    className="flex-1"
                    disabled={isUploading}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateWithDocument}
                    disabled={!uploadFile || isUploading}
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                  >
                    {isUploading ? (
                      <div className="flex items-center">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Creating...
                      </div>
                    ) : (
                      'Create Chat'
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Content */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="p-4">
                  <div className="h-4 bg-gray-200 rounded mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-2/3"></div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : filteredInteractions.length === 0 ? (
          <div className="text-center py-12">
            <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {searchTerm ? 'No matching chat sessions' : 'No chat sessions yet'}
            </h3>
            <p className="text-gray-600 mb-6">
              {searchTerm 
                ? 'Try adjusting your search terms' 
                : 'Upload a document to start your first conversation'
              }
            </p>
            {!searchTerm && (
              <Button
                onClick={() => setShowUploadDialog(true)}
                className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
              >
                <Plus className="w-4 h-4 mr-2" />
                Start First Chat
              </Button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredInteractions.map((interaction) => (
              <Card 
                key={interaction.id}
                className="hover:shadow-md transition-shadow cursor-pointer group"
                onClick={() => router.push(`/dashboard/chat/${interaction.id}`)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-base font-medium text-gray-900 truncate group-hover:text-blue-700 transition-colors">
                        {interaction.title}
                      </CardTitle>
                      <CardDescription className="flex items-center mt-1">
                        <Calendar className="w-3 h-3 mr-1" />
                        {formatDate(interaction.created_at)}
                      </CardDescription>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                        <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={(e) => handleDeleteInteraction(interaction.id, e)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="flex items-center text-sm text-gray-500">
                    <MessageSquare className="w-4 h-4 mr-1" />
                    Click to continue conversation
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Quick Stats */}
        <div className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <MessageSquare className="w-8 h-8 text-blue-600" />
                <div className="ml-3">
                  <p className="text-2xl font-semibold text-gray-900">{interactions.length}</p>
                  <p className="text-sm text-gray-600">Total Chats</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center">
                <FileText className="w-8 h-8 text-green-600" />
                <div className="ml-3">
                  <p className="text-2xl font-semibold text-gray-900">-</p>
                  <p className="text-sm text-gray-600">Documents</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="lg:col-span-2">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Quick Actions</p>
                  <p className="text-xs text-gray-600">Get started quickly</p>
                </div>
                <div className="flex space-x-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => router.push('/dashboard/library')}
                  >
                    <BookOpen className="w-4 h-4 mr-1" />
                    Library
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setShowUploadDialog(true)}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    <Plus className="w-4 h-4 mr-1" />
                    New Chat
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}