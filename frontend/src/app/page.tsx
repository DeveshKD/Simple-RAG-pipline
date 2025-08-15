import Sidebar from "@/components/Sidebar";
import UserProfile from "@/components/UserProfile";
import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="flex h-screen bg-white dark:bg-gray-900 text-black dark:text-white">
      <Sidebar />
      <main className="flex-1 flex flex-col">
        <header className="p-4 border-b dark:border-gray-700 flex justify-between items-center">
          <h1 className="text-2xl font-bold">RAG Application</h1>
          <UserProfile />
        </header>
        <ChatWindow />
      </main>
    </div>
  );
}