import type { ApiClient, ApiResult } from "../../api/client";
import type {
  CommandResponse,
  TransactionKind,
  TransactionResponse,
} from "../../api/schema";
import { isRecord, type Validator } from "../../api/validation";

export interface MovementInput {
  readonly kind: TransactionKind;
  readonly economic_date: string;
  readonly description: string;
  readonly amount_cents: number;
  readonly account_id?: string;
  readonly category_id?: string;
  readonly destination_account_id?: string;
  readonly cash_date?: string | null;
}

export interface TransactionsApi {
  list(): Promise<ApiResult<readonly TransactionResponse[]>>;
  createDraft(input: MovementInput): Promise<ApiResult<TransactionResponse>>;
  updateDraft(
    id: string,
    input: MovementInput,
  ): Promise<ApiResult<TransactionResponse>>;
  discardDraft(id: string): Promise<ApiResult<null>>;
  postDraft(
    id: string,
    cashDate: string | null,
    key: string,
  ): Promise<ApiResult<CommandResponse>>;
  post(input: MovementInput, key: string): Promise<ApiResult<CommandResponse>>;
  reverse(
    id: string,
    input: {
      readonly economic_date: string;
      readonly cash_date: string | null;
    },
    key: string,
  ): Promise<ApiResult<CommandResponse>>;
}

const kinds = new Set(["OPENING", "INCOME", "EXPENSE", "TRANSFER", "REVERSAL"]);
const statuses = new Set(["DRAFT", "POSTED", "RECONCILED", "VOIDED"]);
const isNullableString = (value: unknown): value is string | null =>
  value === null || typeof value === "string";
const isTransaction: Validator<TransactionResponse> = (
  value,
): value is TransactionResponse =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.kind === "string" &&
  kinds.has(value.kind) &&
  typeof value.status === "string" &&
  statuses.has(value.status) &&
  typeof value.status_label === "string" &&
  typeof value.economic_date === "string" &&
  isNullableString(value.cash_date) &&
  isNullableString(value.description) &&
  (value.amount_cents === null || Number.isSafeInteger(value.amount_cents)) &&
  isNullableString(value.account_id) &&
  isNullableString(value.category_id) &&
  isNullableString(value.destination_account_id) &&
  isNullableString(value.original_transaction_id) &&
  isNullableString(value.reversal_transaction_id) &&
  isNullableString(value.corrected_original_transaction_id) &&
  isNullableString(value.replacement_transaction_id);
const transactionList: Validator<readonly TransactionResponse[]> = (
  value,
): value is readonly TransactionResponse[] =>
  Array.isArray(value) && value.every(isTransaction);
const isCommand: Validator<CommandResponse> = (
  value,
): value is CommandResponse =>
  isRecord(value) &&
  typeof value.transaction_id === "string" &&
  typeof value.status === "string" &&
  typeof value.replayed === "boolean" &&
  (value.replacement_transaction_id === null ||
    typeof value.replacement_transaction_id === "string");
const isNull: Validator<null> = (value): value is null => value === null;

function commandBody(input: MovementInput): Readonly<Record<string, unknown>> {
  const common = {
    amount_cents: input.amount_cents,
    economic_date: input.economic_date,
    description: input.description,
  };
  if (input.kind === "TRANSFER") {
    return {
      ...common,
      source_account_id: input.account_id,
      destination_account_id: input.destination_account_id,
      cash_date: input.cash_date,
    };
  }
  return {
    ...common,
    account_id: input.account_id,
    ...(input.kind === "INCOME" || input.kind === "EXPENSE"
      ? { category_id: input.category_id, cash_date: input.cash_date }
      : {}),
  };
}

export function createTransactionsApi(client: ApiClient): TransactionsApi {
  return {
    list: () =>
      client.request("/api/v1/transactions?limit=100&offset=0", {
        validate: transactionList,
      }),
    createDraft: (input) =>
      client.request("/api/v1/transactions/drafts", {
        method: "POST",
        body: { ...input },
        validate: isTransaction,
      }),
    updateDraft: (id, input) =>
      client.request(`/api/v1/transactions/drafts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { ...input },
        validate: isTransaction,
      }),
    discardDraft: (id) =>
      client.request(`/api/v1/transactions/drafts/${encodeURIComponent(id)}`, {
        method: "DELETE",
        validate: isNull,
      }),
    postDraft: (id, cashDate, key) =>
      client.request(
        `/api/v1/transactions/drafts/${encodeURIComponent(id)}/post`,
        {
          method: "POST",
          body: { cash_date: cashDate },
          idempotencyKey: key,
          validate: isCommand,
        },
      ),
    post: (input, key) =>
      client.request(
        `/api/v1/transactions/${input.kind.toLowerCase() as "opening" | "income" | "expense" | "transfer"}`,
        {
          method: "POST",
          body: commandBody(input),
          idempotencyKey: key,
          validate: isCommand,
        },
      ),
    reverse: (id, input, key) =>
      client.request(`/api/v1/transactions/${encodeURIComponent(id)}/reverse`, {
        method: "POST",
        body: input,
        idempotencyKey: key,
        validate: isCommand,
      }),
  };
}
