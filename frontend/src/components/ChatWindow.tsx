'use client';
import { useState, useEffect, useRef } from 'react';
import { useChatStore } from '@/store/chatStore';
import { postQuery, uploadDocument } from '@/lib/api';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { useQueryClient } from '@tanstack/react-query';

export default function ChatWindow() {
  const { 
    activeInteractionId, 
    messages, 
    documents, 
    addMessage, 
    setActiveInteraction 
  } = useChatStore();

  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const queryClient = useQueryClient();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTo({ top: scrollAreaRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeInteractionId) return;

    const userMessage = { id: crypto.randomUUID(), role: 'user' as const, content: input, timestamp: new Date().toISOString() };
    addMessage(userMessage);
    const currentInput = input;
    setInput('');
    setIsSending(true);

    try {
      const response = await postQuery(activeInteractionId, currentInput);
      const assistantMessage = { id: crypto.randomUUID(), role: 'assistant' as const, content: response.synthesized_answer, timestamp: new Date().toISOString() };
      addMessage(assistantMessage);
    } catch (error) {
      console.error("Failed to send message:", error);
      const errorMessage = { id: crypto.randomUUID(), role: 'assistant' as const, content: 'Sorry, I encountered an error. Please try again.', timestamp: new Date().toISOString() };
      addMessage(errorMessage);
    } finally {
      setIsSending(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsSending(true);
    try {
      const response = await uploadDocument(file, null);
      if (response && response.interaction_state) {
        const { interaction_state } = response;
        setActiveInteraction(interaction_state.id, interaction_state.messages, interaction_state.documents);
        await queryClient.invalidateQueries({ queryKey: ['interactions'] });
      }
    } catch (error) {
      console.error("File upload failed", error);
    } finally {
      setIsSending(false);
    }
  };

  if (!activeInteractionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
        <h2 className="text-2xl font-semibold mb-2">Start a new chat</h2>
        <p className="text-gray-500 mb-4">Upload a document to begin the conversation.</p>
        <div className="w-full max-w-sm">
          <input
            type="file"
            id="file-upload"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) {
                handleFileUpload(e.target.files[0]);
              }
            }}
            disabled={isSending}
          />
          <Button onClick={() => document.getElementById('file-upload')?.click()} disabled={isSending} className="w-full">
            {isSending ? 'Processing...' : 'Upload Document'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      <header className="p-4 border-b dark:border-gray-700">
        <h3 className="font-semibold">Sources for this chat:</h3>
        <div className="flex flex-wrap gap-2 mt-1">
        {documents.map(doc => (
          <span key={doc.id} className="text-xs bg-gray-200 dark:bg-gray-700 px-2 py-1 rounded-full">
            {doc.filename}
          </span>
        ))}
        </div>
      </header>
      <ScrollArea className="flex-grow p-4" ref={scrollAreaRef}>
        <div className="pr-4"> {/* Add padding to prevent scrollbar overlap */}
          {messages.map((message) => (
            <div key={message.id} className={`mb-4 flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-prose p-3 rounded-lg shadow-md ${message.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-700'}`}>
                <p>{message.content}</p>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="p-4 border-t dark:border-gray-700">
        <form onSubmit={handleSendMessage} className="flex space-x-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about the document(s)..."
            disabled={isSending}
          />
          <Button type="submit" disabled={isSending}>
            {isSending ? 'Sending...' : 'Send'}
          </Button>
        </form>
      </div>
    </div>
  );
}