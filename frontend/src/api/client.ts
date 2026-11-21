export interface ApiErrorPayload {
  detail: string;
  code: string;
  errors?: Record<string, string[] | Record<string, unknown>>;
  status: number;
}

export class ApiError extends Error {
  public readonly code: string;
  public readonly errors?: ApiErrorPayload["errors"];
  public readonly status: number;

  constructor(payload: ApiErrorPayload) {
    super(payload.detail);
    this.name = "ApiError";
    this.code = payload.code;
    this.errors = payload.errors;
    this.status = payload.status;
  }
}

export interface TokenStorage {
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  setTokens(tokens: { access: string; refresh?: string }): void;
  clearTokens(): void;
}

export function createMemoryTokenStorage(): TokenStorage {
  let accessToken: string | null = null;
  let refreshToken: string | null = null;
  return {
    getAccessToken: () => accessToken,
    getRefreshToken: () => refreshToken,
    setTokens: ({ access, refresh }) => {
      accessToken = access;
      if (refresh) refreshToken = refresh;
    },
    clearTokens: () => {
      accessToken = null;
      refreshToken = null;
    },
  };
}

export interface AuthTokensResponse {
  access: string;
  refresh: string;
  user_code: string;
}

export interface SportItem {
  id: number;
  name: string;
}

export interface ProfilePayload {
  last_name?: string;
  first_name?: string;
  middle_name?: string;
  sex?: "male" | "female";
  birth_date?: string;
  sport?: number | null;
  sport_custom?: string;
  sport_name?: string;
  start_age_any?: number;
  start_age_sport?: number;
  trainings_per_week?: number;
  hours_per_week?: number | string;
  season_period?: "rest" | "preparation" | "camp" | "competition";
  age?: number;
  total_experience?: number | null;
  sport_experience?: number | null;
  is_complete?: boolean;
}

export interface ProfileChangeItem {
  field: string;
  old_value: string;
  new_value: string;
  changed_at: string;
}

export interface AssessmentCompleteRequest {
  client_uuid: string;
  filled_at?: string;
  answers: Record<string, unknown>;
}

export interface ReminderSettingsPayload {
  notify_time: string;
  timezone: string;
  due_date?: string | null;
}

export interface SportApiClientOptions {
  baseUrl: string;
  storage?: TokenStorage;
  onUnauthorized?: () => void;
}

export class SportApiClient {
  private readonly baseUrl: string;
  private readonly storage: TokenStorage;
  private readonly onUnauthorized?: () => void;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(options: SportApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.storage = options.storage ?? createMemoryTokenStorage();
    this.onUnauthorized = options.onUnauthorized;
  }

  private buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>): string {
    const cleanPath = path.startsWith("/") ? path : `/${path}`;
    const url = new URL(`${this.baseUrl}${cleanPath}`);
    if (query) {
      for (const [key, val] of Object.entries(query)) {
        if (val !== undefined && val !== null && val !== "") {
          url.searchParams.set(key, String(val));
        }
      }
    }
    return url.toString();
  }

  private async parseError(res: Response): Promise<ApiError> {
    let raw: unknown = null;
    try {
      raw = await res.json();
    } catch {

    }
    if (raw && typeof raw === "object") {
      const obj = raw as Record<string, unknown>;
      return new ApiError({
        detail: typeof obj.detail === "string" ? obj.detail : res.statusText || "Ошибка запроса",
        code: typeof obj.code === "string" ? obj.code : `http_${res.status}`,
        errors:
          obj.errors && typeof obj.errors === "object"
            ? (obj.errors as ApiErrorPayload["errors"])
            : undefined,
        status: res.status,
      });
    }
    return new ApiError({
      detail: res.statusText || "Ошибка запроса",
      code: `http_${res.status}`,
      status: res.status,
    });
  }

  private async refreshAccessToken(): Promise<string | null> {
    const refresh = this.storage.getRefreshToken();
    if (!refresh) return null;

    if (!this.refreshPromise) {
      this.refreshPromise = (async () => {
        try {
          const res = await fetch(this.buildUrl("/api/auth/token/refresh/"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh }),
          });
          if (!res.ok) {
            this.storage.clearTokens();
            this.onUnauthorized?.();
            return null;
          }
          const data = (await res.json()) as { access: string; refresh?: string };
          this.storage.setTokens({ access: data.access, refresh: data.refresh ?? refresh });
          return data.access;
        } catch {
          return null;
        } finally {
          this.refreshPromise = null;
        }
      })();
    }

    return this.refreshPromise;
  }

  public async request<T>(
    path: string,
    options: {
      method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
      query?: Record<string, string | number | boolean | undefined | null>;
      body?: unknown;
      auth?: boolean;
      retryOn401?: boolean;
    } = {}
  ): Promise<T> {
    const {
      method = "GET",
      query,
      body,
      auth = true,
      retryOn401 = true,
    } = options;

    const headers: Record<string, string> = {};
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (auth) {
      const token = this.storage.getAccessToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    const res = await fetch(this.buildUrl(path, query), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401 && auth && retryOn401) {
      const nextAccess = await this.refreshAccessToken();
      if (nextAccess) {
        return this.request<T>(path, { ...options, retryOn401: false });
      }
    }

    if (!res.ok) {
      throw await this.parseError(res);
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return (await res.json()) as T;
  }

  getPublicSettings() {
    return this.request<{ version: number; data: Record<string, unknown> }>("/api/settings/", {
      auth: false,
    });
  }

  registerStart(payload: { contact: string; birth_date: string; consent: boolean }) {
    return this.request<{ detail: string; resend_in: number; debug_code?: string }>(
      "/api/auth/register/start/",
      { method: "POST", body: payload, auth: false }
    );
  }

  async registerVerify(payload: { contact: string; code: string; password: string }) {
    const data = await this.request<AuthTokensResponse>("/api/auth/register/verify/", {
      method: "POST",
      body: payload,
      auth: false,
    });
    this.storage.setTokens({ access: data.access, refresh: data.refresh });
    return data;
  }

  async login(payload: { contact: string; password: string }) {
    const data = await this.request<AuthTokensResponse>("/api/auth/login/", {
      method: "POST",
      body: payload,
      auth: false,
    });
    this.storage.setTokens({ access: data.access, refresh: data.refresh });
    return data;
  }

  loginOtpStart(contact: string) {
    return this.request<{ detail: string; resend_in: number; debug_code?: string }>(
      "/api/auth/login/otp/start/",
      { method: "POST", body: { contact }, auth: false }
    );
  }

  async loginOtpVerify(payload: { contact: string; code: string }) {
    const data = await this.request<AuthTokensResponse>("/api/auth/login/otp/verify/", {
      method: "POST",
      body: payload,
      auth: false,
    });
    this.storage.setTokens({ access: data.access, refresh: data.refresh });
    return data;
  }

  passwordResetStart(contact: string) {
    return this.request<{ detail: string; resend_in: number; debug_code?: string }>(
      "/api/auth/password-reset/start/",
      { method: "POST", body: { contact }, auth: false }
    );
  }

  passwordResetConfirm(payload: { contact: string; code: string; new_password: string }) {
    return this.request<{ detail: string }>("/api/auth/password-reset/confirm/", {
      method: "POST",
      body: payload,
      auth: false,
    });
  }

  async logout() {
    const refresh = this.storage.getRefreshToken();
    try {
      await this.request<void>("/api/auth/logout/", {
        method: "POST",
        body: refresh ? { refresh } : {},
      });
    } finally {
      this.storage.clearTokens();
    }
  }

  getAccountInfo() {
    return this.request<{
      user_code: string;
      consent_given_at: string | null;
      policy_version: string | null;
    }>("/api/account/");
  }

  async deleteAccount(password: string) {
    await this.request<void>("/api/account/", { method: "DELETE", body: { password } });
    this.storage.clearTokens();
  }

  async revokeConsent(password: string) {
    await this.request<void>("/api/account/consent/revoke/", {
      method: "POST",
      body: { password },
    });
    this.storage.clearTokens();
  }

  getSports(q?: string) {
    return this.request<SportItem[]>("/api/sports/", { query: { q } });
  }

  getProfile() {
    return this.request<ProfilePayload>("/api/profile/");
  }

  updateProfile(payload: ProfilePayload, method: "PUT" | "PATCH" = "PATCH") {
    return this.request<ProfilePayload>("/api/profile/", { method, body: payload });
  }

  setSeasonPeriod(
    season_period: "rest" | "preparation" | "camp" | "competition",
    method: "PUT" | "PATCH" = "PUT"
  ) {
    return this.request<{ season_period: string }>("/api/profile/season/", {
      method,
      body: { season_period },
    });
  }

  getProfileHistory() {
    return this.request<ProfileChangeItem[]>("/api/profile/history/");
  }

  getHome() {
    return this.request<Record<string, unknown>>("/api/home/");
  }

  getAssessments(params?: { from?: string; to?: string }) {
    return this.request<Record<string, unknown>[]>("/api/assessments/", { query: params });
  }

  getAssessmentDetail(id: string) {
    return this.request<Record<string, unknown>>(`/api/assessments/${id}/`);
  }

  createAssessment(payload: AssessmentCompleteRequest) {
    return this.request<Record<string, unknown>>("/api/assessments/", {
      method: "POST",
      body: payload,
    });
  }

  getDraft() {
    return this.request<{ data: Record<string, unknown>; updated_at: string; expires_at: string }>(
      "/api/assessments/draft/"
    );
  }

  saveDraft(data: Record<string, unknown>) {
    return this.request<{ updated_at: string; expires_at: string }>("/api/assessments/draft/", {
      method: "PUT",
      body: { data },
    });
  }

  deleteDraft() {
    return this.request<void>("/api/assessments/draft/", { method: "DELETE" });
  }

  getExportData(params?: { from?: string; to?: string; include_name?: boolean }) {
    return this.request<Record<string, unknown>>("/api/export/data/", {
      query: {
        from: params?.from,
        to: params?.to,
        include_name: params?.include_name ? 1 : undefined,
      },
    });
  }

  getReminderSettings() {
    return this.request<ReminderSettingsPayload>("/api/reminders/settings/");
  }

  updateReminderSettings(payload: { notify_time: string; timezone: string }) {
    return this.request<ReminderSettingsPayload>("/api/reminders/settings/", {
      method: "PUT",
      body: payload,
    });
  }

  registerDevice(payload: { token: string; platform: "ios" | "android" | "web" }) {
    return this.request<void>("/api/devices/", { method: "POST", body: payload });
  }

  removeDevice(token: string) {
    return this.request<void>("/api/devices/", { method: "DELETE", body: { token } });
  }
}