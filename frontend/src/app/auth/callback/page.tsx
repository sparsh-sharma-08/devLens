"use client";

import { useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setTokens } from "@/lib/api";
import { Zap, Loader2 } from "lucide-react";
import { Suspense } from "react";

/**
 * Auth Callback Page
 * Receives access_token and refresh_token from the GitHub OAuth backend callback,
 * stores them, and redirects to the dashboard.
 *
 * The backend returns to /auth/callback?access_token=...&refresh_token=...&username=...&avatar_url=...
 */
function CallbackInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const accessToken = searchParams.get("access_token");
    const refreshToken = searchParams.get("refresh_token");

    if (accessToken && refreshToken) {
      setTokens(accessToken, refreshToken);

      const user = {
        id: searchParams.get("user_id") || "",
        username: searchParams.get("username") || "",
        avatar_url: searchParams.get("avatar_url") || null,
        email: null,
      };
      sessionStorage.setItem("devlens_user", JSON.stringify(user));

      router.replace("/dashboard");
    } else {
      // OAuth failed — go back to landing
      router.replace("/?error=auth_failed");
    }
  }, [searchParams, router]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 24,
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: 16,
          background: "linear-gradient(135deg, var(--primary), var(--accent))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Zap size={32} color="white" />
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "center", marginBottom: 8 }}>
          <Loader2 size={20} color="var(--primary)" className="animate-spin" />
          <span style={{ fontSize: "1.1rem", fontWeight: 600 }}>Signing you in…</span>
        </div>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
          Completing GitHub authentication
        </p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense>
      <CallbackInner />
    </Suspense>
  );
}
