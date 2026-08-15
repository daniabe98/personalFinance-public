import { useMemo } from "react";
import { RouterProvider } from "react-router-dom";

import { type ApiClient, type ApiResult, createApiClient } from "./api/client";
import { type AuthApi, createAuthApi } from "./features/auth/api";
import {
  type ReconciliationAccount,
  type ReconciliationApi,
  ReconciliationPage,
} from "./features/reconciliation/page";
import type { ReconciliationCandidate } from "./features/reconciliation/entry-list";
import type {
  DetailCatalogItem,
  MovementDetail,
} from "./features/reports/movement-detail-dialog";
import { type ReportsApi, ReportsSummary } from "./features/reports/summary";
import { type SettingsApi, SettingsPage } from "./features/settings/page";
import { createIdempotencyKey } from "./lib/idempotency-key";
import { type ControlRoutePages, createAppRouter } from "./router";

type ViewResult<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly message: string };

function viewResult<T>(result: ApiResult<T>): ViewResult<T> {
  return result.ok
    ? { ok: true, data: result.data }
    : { ok: false, message: result.error.message };
}

function reconciliationApi(client: ApiClient): ReconciliationApi {
  return {
    async accounts() {
      return viewResult(
        await client.request<readonly ReconciliationAccount[]>(
          "/api/v1/accounts?include_archived=false",
        ),
      );
    },
    async candidates(accountId, cutoffDate) {
      const path =
        `/api/v1/reconciliations/candidates?account_id=${encodeURIComponent(accountId)}` +
        `&cutoff_date=${encodeURIComponent(cutoffDate)}`;
      return viewResult(
        await client.request<readonly ReconciliationCandidate[]>(
          path as `/api/v1/${string}`,
        ),
      );
    },
    async preview(request) {
      return viewResult(
        await client.request("/api/v1/reconciliations/preview", {
          method: "POST",
          body: { ...request },
        }),
      );
    },
    async complete(request) {
      return viewResult(
        await client.request("/api/v1/reconciliations", {
          method: "POST",
          body: { ...request },
          idempotencyKey: createIdempotencyKey(),
        }),
      );
    },
  };
}

function reportsApi(client: ApiClient): ReportsApi {
  return {
    async economic(start, end) {
      return viewResult(
        await client.request(
          `/api/v1/reports/economic?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`,
        ),
      );
    },
    async cash(start, end) {
      return viewResult(
        await client.request(
          `/api/v1/reports/cash-flow?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`,
        ),
      );
    },
    async netWorth(asOf) {
      return viewResult(
        await client.request(
          `/api/v1/reports/net-worth?as_of=${encodeURIComponent(asOf)}`,
        ),
      );
    },
    async transaction(transactionId) {
      const result = await client.request<MovementDetail>(
        `/api/v1/transactions/${encodeURIComponent(transactionId)}`,
      );
      if (!result.ok && result.error.status === 404) {
        return { ok: true, data: null };
      }
      return viewResult<MovementDetail | null>(result);
    },
    async accounts() {
      return viewResult(
        await client.request<readonly DetailCatalogItem[]>(
          "/api/v1/accounts?include_archived=true",
        ),
      );
    },
    async categories() {
      return viewResult(
        await client.request<readonly DetailCatalogItem[]>(
          "/api/v1/categories?include_archived=true",
        ),
      );
    },
  };
}

function settingsApi(client: ApiClient): SettingsApi {
  return {
    async backupStatus() {
      return viewResult(await client.request("/api/v1/recovery/backup-status"));
    },
    async auditEvents(cursor) {
      const query =
        cursor === undefined ? "" : `?cursor=${encodeURIComponent(cursor)}`;
      return viewResult(await client.request(`/api/v1/audit/events${query}`));
    },
  };
}

function currentInterval(): {
  readonly startDate: string;
  readonly endDate: string;
} {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return {
    startDate: `${year}-${month}-01`,
    endDate: `${year}-${month}-${day}`,
  };
}

function browserRuntime(): {
  readonly authApi: AuthApi;
  readonly controlPages: ControlRoutePages;
} {
  let csrfToken: string | null = null;
  const client = createApiClient({ getCsrfToken: () => csrfToken });
  const base = createAuthApi(client);
  const authApi: AuthApi = {
    async session() {
      const result = await base.session();
      if (result.ok) csrfToken = result.csrfToken;
      return result;
    },
    async login(username, password) {
      const result = await base.login(username, password);
      if (result.ok) csrfToken = result.csrfToken;
      return result;
    },
    async logout() {
      const result = await base.logout();
      csrfToken = null;
      return result;
    },
  };
  const reconciliation = reconciliationApi(client);
  const reports = reportsApi(client);
  const settings = settingsApi(client);
  return {
    authApi,
    controlPages: {
      summary: () => (
        <ReportsSummary
          api={reports}
          initialInterval={currentInterval()}
          autoLoad={false}
        />
      ),
      reconciliation: () => <ReconciliationPage api={reconciliation} />,
      settings: () => <SettingsPage api={settings} />,
    },
  };
}

export function App({
  authApi,
  controlPages,
}: {
  readonly authApi?: AuthApi;
  readonly controlPages?: ControlRoutePages;
}): React.JSX.Element {
  const runtime = useMemo(() => browserRuntime(), []);
  const router = useMemo(
    () =>
      createAppRouter({
        authApi: authApi ?? runtime.authApi,
        controlPages: controlPages ?? runtime.controlPages,
      }),
    [authApi, controlPages, runtime],
  );
  return <RouterProvider router={router} />;
}
