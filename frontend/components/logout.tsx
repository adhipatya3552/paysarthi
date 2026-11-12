"use client";
import { useRouter } from "next/navigation";
import { SignOut } from "@phosphor-icons/react";

export default function LogoutButton() {
  const router = useRouter();
  return (
    <button
      onClick={() => {
        localStorage.removeItem("ps_token");
        router.push("/login");
      }}
      className="flex w-full items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-white/60 hover:bg-white/10 hover:text-white active:scale-[0.98] transition text-left"
    >
      <SignOut size={18} /> Log out
    </button>
  );
}
