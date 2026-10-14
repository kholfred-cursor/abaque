import type { RouteObject } from "react-router";
import { DashboardPage } from "./admin/DashboardPage";
import { EvaluationLayout } from "./admin/evaluations/EvaluationLayout";
import { EvaluationSettingsPage } from "./admin/evaluations/EvaluationSettingsPage";
import { ItemsEditorPage } from "./admin/evaluations/ItemsEditorPage";
import { VersionsPage } from "./admin/evaluations/VersionsPage";
import { ForgotPasswordPage } from "./admin/ForgotPasswordPage";
import { LoginPage } from "./admin/LoginPage";
import { ResetPasswordPage } from "./admin/ResetPasswordPage";
import { SessionsPage } from "./admin/SessionsPage";
import { SignupPage } from "./admin/SignupPage";
import { VerifyEmailPage } from "./admin/VerifyEmailPage";
import { TokensPage } from "./dev/TokensPage";
import { NotFoundPage } from "./NotFoundPage";
import { RequireAuth } from "./shared/auth/RequireAuth";
import { AppLayout } from "./shared/ui/Layout";
import { VotePlaceholderPage } from "./vote/VotePlaceholderPage";

export function buildRoutes(dev: boolean): RouteObject[] {
  const protectedChildren: RouteObject[] = [
    { index: true, element: <DashboardPage /> },
    { path: "compte/sessions", element: <SessionsPage /> },
    {
      path: "evaluations/:evaluationId",
      element: <EvaluationLayout />,
      children: [
        { index: true, element: <EvaluationSettingsPage /> },
        { path: "items", element: <ItemsEditorPage /> },
        { path: "versions", element: <VersionsPage /> },
      ],
    },
  ];
  if (dev) protectedChildren.push({ path: "dev/tokens", element: <TokensPage /> });
  return [
    { path: "/connexion", element: <LoginPage /> },
    { path: "/inscription", element: <SignupPage /> },
    { path: "/verifier-email", element: <VerifyEmailPage /> },
    { path: "/mot-de-passe-oublie", element: <ForgotPasswordPage /> },
    { path: "/reinitialiser", element: <ResetPasswordPage /> },
    { path: "/v/:slug", element: <VotePlaceholderPage /> },
    {
      path: "/",
      element: (
        <RequireAuth>
          <AppLayout />
        </RequireAuth>
      ),
      children: protectedChildren,
    },
    { path: "*", element: <NotFoundPage /> },
  ];
}
