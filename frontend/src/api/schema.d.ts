/* Generated from frontend/openapi.json. Do not edit by hand. */

export interface SessionPrincipal {
  readonly user_id: string;
  readonly space_id: string;
  readonly username: string;
}

export interface SessionResponse extends SessionPrincipal {
  readonly csrf_token: string;
}

export interface LoginResponse {
  readonly csrf_token: string;
  readonly expires_at: string;
  readonly user_id: string;
  readonly space_id: string;
}

export interface ProblemResponse {
  readonly code: string;
  readonly detail: string;
  readonly status: number;
  readonly title: string;
}

export type AccountKind = "ASSET" | "LIABILITY" | "EQUITY";

export type CategoryKind = "INCOME" | "EXPENSE";

export type TransactionKind =
  "OPENING" | "INCOME" | "EXPENSE" | "TRANSFER" | "REVERSAL";

export type TransactionStatus = "DRAFT" | "POSTED" | "RECONCILED" | "VOIDED";

export interface AccountResponse {
  readonly id: string;
  readonly name: string;
  readonly kind: AccountKind;
  readonly is_archived: boolean;
  readonly is_reconcilable: boolean;
  readonly balance_cents: number;
  readonly currency: "EUR";
}

export interface CategoryResponse {
  readonly id: string;
  readonly name: string;
  readonly kind: CategoryKind;
  readonly is_archived: boolean;
}

export interface CommandResponse {
  readonly transaction_id: string;
  readonly status: string;
  readonly replayed: boolean;
  readonly replacement_transaction_id: string | null;
}

export interface TransactionResponse {
  readonly id: string;
  readonly kind: TransactionKind;
  readonly status: TransactionStatus;
  readonly status_label: string;
  readonly economic_date: string;
  readonly cash_date: string | null;
  readonly description: string | null;
  readonly amount_cents: number | null;
  readonly account_id: string | null;
  readonly category_id: string | null;
  readonly destination_account_id: string | null;
  readonly original_transaction_id: string | null;
  readonly reversal_transaction_id: string | null;
  readonly corrected_original_transaction_id: string | null;
  readonly replacement_transaction_id: string | null;
}
