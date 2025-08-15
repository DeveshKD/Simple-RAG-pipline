'use client';
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useChatStore } from '@/store/chatStore';
import { getAllInteractions, getInteractionDetails } from '@/lib/api';
import { Button } from '@/components/ui/button';

export default function Sidebar() {
  const { 
    activeInteractionId, 
    interactions, 
    setInteractions,
    setActiveInteraction,
    clearActiveInteraction 
  } = useChatStore();

  const { data: fetchedInteractions, isLoading } = useQuery({
    queryKey: ['interactions'],
    queryFn: getAllInteractions,
  });

  useEffect(() => {
    if (fetchedInteractions) {
      const sorted = [...fetchedInteractions].sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setInteractions(sorted);
    }
  }, [fetchedInteractions, setInteractions]);

  const handleSelectChat = async (id: string) => {
    try {
      const details = await getInteractionDetails(id);
      setActiveInteraction(details.id, details.messages, details.documents);
    } catch (error) {
      console.error("Failed to load interaction details", error);
    }
  };

  return (
    <aside className="w-64 h-screen bg-gray-100 dark:bg-gray-800 p-4 flex flex-col border-r dark:border-gray-700">
      <Button onClick={clearActiveInteraction} className="mb-4">
        + New Chat
      </Button>

      <h2 className="text-lg font-semibold mb-2 px-2">History</h2>
      <div className="flex-grow overflow-y-auto">
        {isLoading && <p className="text-sm text-gray-500 px-2">Loading chats...</p>}
        {interactions.length > 0 ? (
          <ul className="space-y-1">
            {interactions.map((interaction) => (
              <li key={interaction.id}>
                <Button
                  variant={activeInteractionId === interaction.id ? 'secondary' : 'ghost'}
                  className="w-full justify-start text-left truncate"
                  onClick={() => handleSelectChat(interaction.id)}
                >
                  {interaction.title}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          !isLoading && <p className="text-sm text-gray-500 px-2">No conversations yet.</p>
        )}
      </div>
    </aside>
  );
}