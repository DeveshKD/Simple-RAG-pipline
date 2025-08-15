'use client';
import { useAuthStore } from "@/store/authStore";
import { logoutUser } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Button } from "./ui/button";

export default function UserProfile() {
  const { user, logout } = useAuthStore();
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (error) {
      console.error("Logout API call failed, but logging out client-side anyway:", error);
    }
    logout();
    router.push('/login');
  };

  if (!user) {
    return null;
  }

  return (
    <div className="flex items-center space-x-4">
      <p className="text-sm text-gray-500 dark:text-gray-400">{user.email}</p>
      <Button variant="outline" onClick={handleLogout}>
        Logout
      </Button>
    </div>
  );
}