import fetchPolyfill, { Response } from "cross-fetch";
import { DatapointSeries, DatapointDTO } from "./models.js";
import {
  AuthenticationError,
  AuthorizationError,
  ImpulsesError,
  NetworkError,
  NotFoundError,
  ServerError,
  ValidationError,
} from "./exceptions.js";

export interface ImpulsesClientConfig {
  url: string;
  tokenValue: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export class ImpulsesClient {
  private readonly baseUrl: string;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(config: ImpulsesClientConfig) {
    if (!config.url) {
      throw new Error("url must not be empty");
    }

    if (!config.tokenValue) {
      throw new Error("tokenValue must not be empty");
    }

    this.baseUrl = config.url.replace(/\/?$/, "");
    this.timeoutMs = config.timeoutMs ?? 3000;
    if (config.fetchImpl) {
      this.fetchImpl = config.fetchImpl;
    } else if (typeof globalThis.fetch === "function") {
      this.fetchImpl = globalThis.fetch.bind(globalThis);
    } else {
      this.fetchImpl = fetchPolyfill;
    }
    this.headers = {
      "X-Data-Token": config.tokenValue,
      "Content-Type": "application/json",
    };
  }

  async listMetricNames(): Promise<string[]> {
    const response = await this.request("/data", {
      method: "GET",
    });
    return (await response.json()) as string[];
  }

  async fetchDatapoints(metricName: string): Promise<DatapointSeries> {
    if (!metricName) {
      throw new Error("metricName must not be empty");
    }

    const response = await this.request(`/data/${encodeURIComponent(metricName)}`, {
      method: "GET",
    });
    const payload = await response.json();

    if (!Array.isArray(payload)) {
      throw new ImpulsesError(
        `Unexpected response format while fetching '${metricName}' (expected list)`
      );
    }

    return DatapointSeries.fromDTO(payload as DatapointDTO[]);
  }

  async uploadDatapoints(metricName: string, datapoints: DatapointSeries): Promise<void> {
    if (!metricName) {
      throw new Error("metricName must not be empty");
    }

    if (!datapoints) {
      throw new Error("datapoints must not be empty");
    }

    await this.request(`/data/${encodeURIComponent(metricName)}`, {
      method: "POST",
      body: JSON.stringify(datapoints.toDTO()),
    });
  }

  async deleteMetricName(metricName: string): Promise<void> {
    if (!metricName) {
      throw new Error("metricName must not be empty");
    }

    await this.request(`/data/${encodeURIComponent(metricName)}`, {
      method: "DELETE",
    });
  }

  private async request(path: string, init: RequestInit): Promise<Response> {
    const controller = new AbortController();
    const timeoutHandle = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          ...this.headers,
          ...(init.headers ?? {}),
        },
        signal: controller.signal,
      });

      await this.handleResponse(response, init.method ?? "GET", path);
      return response;
    } catch (error) {
      if (error instanceof ImpulsesError) {
        throw error;
      }

      if (error && typeof error === "object" && (error as any).name === "AbortError") {
        throw new NetworkError(`Request timed out after ${this.timeoutMs}ms`);
      }

      throw new NetworkError(
        error instanceof Error ? error.message : "Network error occurred"
      );
    } finally {
      clearTimeout(timeoutHandle);
    }
  }

  private async handleResponse(response: Response, operation: string, path: string) {
    if (response.status < 400) {
      return;
    }

    let detail: string | undefined;
    try {
      const payload = await response.json();
      detail = payload?.detail ?? JSON.stringify(payload);
    } catch (jsonError) {
      detail = response.statusText;
    }

    const errorMessage = `${operation} ${path} failed: ${detail ?? "unknown error"}`;

    switch (response.status) {
      case 401:
        throw new AuthenticationError(errorMessage);
      case 403:
        throw new AuthorizationError(errorMessage);
      case 404:
        throw new NotFoundError(errorMessage);
      case 422:
        throw new ValidationError(errorMessage);
      default:
        if (response.status >= 500) {
          throw new ServerError(errorMessage);
        }
        throw new ImpulsesError(errorMessage);
    }
  }
}
