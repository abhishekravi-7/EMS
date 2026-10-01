import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "@/app/shell/AppShell";
import { AuthProvider } from "@/shared/context/AuthProvider";
import { ChatbotProvider } from "@/shared/context/ChatbotContext";
import { SidebarProvider } from "@/shared/context/SidebarContext";
import "./App.css";

const MigrationWizardPage = lazy(() => import("@/features/wizard/pages/MigrationWizardPage"));
// const LandingPage = lazy(() => import("@/features/auth/pages/LandingPage"));
const SignUpPage = lazy(() => import("@/features/auth/pages/SignUpPage"));
const SignInPage = lazy(() => import("@/features/auth/pages/SignInPage"));
const ResetPasswordPage = lazy(() => import("@/features/auth/pages/ResetPasswordPage"));
const VerifyEmailPage = lazy(() => import("@/features/auth/pages/VerifyEmailPage"));
import AdminConsolePage from "@/features/admin/pages/AdminConsolePage";
import ErrorBoundary from "@/shared/components/ErrorBoundary";
const UsageDashboardPage = lazy(() => import("@/features/usage/pages/UsageDashboardPage"));

export default function App() {
  return (
    <AuthProvider>
      <SidebarProvider>
        <ChatbotProvider>
          <BrowserRouter>
            <AppShell>
              <Suspense
                fallback={
                  <div
                    style={{
                      minHeight: "60vh",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#475569",
                      fontSize: 16,
                      fontWeight: 600,
                    }}
                  >
                    Loading migration workspace...
                  </div>
                }
              >
                <Routes>
                  {/* <Route path="/" element={<LandingPage />} /> */}
                  <Route path="/signup" element={<SignUpPage />} />
                  <Route path="/signin" element={<SignInPage />} />
                  <Route path="/verify-email" element={<VerifyEmailPage />} />
                  <Route path="/reset-password" element={<ResetPasswordPage />} />
                  <Route path="/admin" element={<ErrorBoundary><AdminConsolePage /></ErrorBoundary>} />
                  <Route path="/settings" element={<ErrorBoundary><AdminConsolePage /></ErrorBoundary>} />
                  <Route path="/usage" element={<UsageDashboardPage />} />
                  <Route path="/*" element={<MigrationWizardPage />} />
                </Routes>
              </Suspense>
            </AppShell>
          </BrowserRouter>
        </ChatbotProvider>
      </SidebarProvider>
    </AuthProvider>
  );
}
