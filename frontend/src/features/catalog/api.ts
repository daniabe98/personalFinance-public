import type { ApiClient, ApiResult } from "../../api/client";
import type {
  AccountKind,
  AccountResponse,
  CategoryKind,
  CategoryResponse,
} from "../../api/schema";
import { isRecord, type Validator } from "../../api/validation";

export interface CatalogApi {
  listAccounts(
    includeArchived: boolean,
  ): Promise<ApiResult<readonly AccountResponse[]>>;
  listCategories(
    includeArchived: boolean,
  ): Promise<ApiResult<readonly CategoryResponse[]>>;
  createAccount(input: {
    readonly name: string;
    readonly kind: AccountKind;
    readonly is_reconcilable: boolean;
  }): Promise<ApiResult<AccountResponse>>;
  createCategory(input: {
    readonly name: string;
    readonly kind: CategoryKind;
  }): Promise<ApiResult<CategoryResponse>>;
  renameAccount(id: string, name: string): Promise<ApiResult<AccountResponse>>;
  renameCategory(
    id: string,
    name: string,
  ): Promise<ApiResult<CategoryResponse>>;
  setAccountArchived(
    id: string,
    archived: boolean,
  ): Promise<ApiResult<AccountResponse>>;
  setCategoryArchived(
    id: string,
    archived: boolean,
  ): Promise<ApiResult<CategoryResponse>>;
}

const isAccount: Validator<AccountResponse> = (
  value,
): value is AccountResponse =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.name === "string" &&
  (value.kind === "ASSET" || value.kind === "LIABILITY") &&
  typeof value.is_archived === "boolean" &&
  typeof value.is_reconcilable === "boolean" &&
  Number.isSafeInteger(value.balance_cents) &&
  value.currency === "EUR";

const isCategory: Validator<CategoryResponse> = (
  value,
): value is CategoryResponse =>
  isRecord(value) &&
  typeof value.id === "string" &&
  typeof value.name === "string" &&
  (value.kind === "INCOME" || value.kind === "EXPENSE") &&
  typeof value.is_archived === "boolean";

const accountList: Validator<readonly AccountResponse[]> = (
  value,
): value is readonly AccountResponse[] =>
  Array.isArray(value) && value.every(isAccount);
const categoryList: Validator<readonly CategoryResponse[]> = (
  value,
): value is readonly CategoryResponse[] =>
  Array.isArray(value) && value.every(isCategory);

export function createCatalogApi(client: ApiClient): CatalogApi {
  return {
    listAccounts: (archived) =>
      client.request(`/api/v1/accounts?include_archived=${String(archived)}`, {
        validate: accountList,
      }),
    listCategories: (archived) =>
      client.request(
        `/api/v1/categories?include_archived=${String(archived)}`,
        {
          validate: categoryList,
        },
      ),
    createAccount: (input) =>
      client.request("/api/v1/accounts", {
        method: "POST",
        body: input,
        validate: isAccount,
      }),
    createCategory: (input) =>
      client.request("/api/v1/categories", {
        method: "POST",
        body: input,
        validate: isCategory,
      }),
    renameAccount: (id, name) =>
      client.request(`/api/v1/accounts/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { name },
        validate: isAccount,
      }),
    renameCategory: (id, name) =>
      client.request(`/api/v1/categories/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: { name },
        validate: isCategory,
      }),
    setAccountArchived: (id, archived) =>
      client.request(
        `/api/v1/accounts/${encodeURIComponent(id)}/${archived ? "archive" : "unarchive"}`,
        { method: "POST", validate: isAccount },
      ),
    setCategoryArchived: (id, archived) =>
      client.request(
        `/api/v1/categories/${encodeURIComponent(id)}/${archived ? "archive" : "unarchive"}`,
        { method: "POST", validate: isCategory },
      ),
  };
}
