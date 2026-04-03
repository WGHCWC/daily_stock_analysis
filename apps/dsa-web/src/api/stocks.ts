import apiClient from './index';

export type ExtractItem = {
  code?: string | null;
  name?: string | null;
  confidence: string;
};

export type ExtractFromImageResponse = {
  codes: string[];
  items?: ExtractItem[];
  rawText?: string;
};

export type WatchlistItem = {
  code: string;
  name: string;
  addedAt?: string | null;
  addedPrice?: number | null;
  currentPrice?: number | null;
  gainPercent?: number | null;
  updatedAt?: string | null;
};

export type WatchlistBatchResult = {
  code: string;
  status: 'success' | 'error';
  message: string;
  item?: WatchlistItem;
};

export type WatchlistBatchTask = {
  taskId: string;
  status: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  total: number;
  completed: number;
  results: WatchlistBatchResult[];
  errorMessage?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  finishedAt?: string | null;
};

export const stocksApi = {
  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; items?: ExtractItem[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      items: data.items,
      rawText: data.raw_text,
    };
  },

  async parseImport(file?: File, text?: string): Promise<ExtractFromImageResponse> {
    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
      const response = await apiClient.post('/api/v1/stocks/parse-import', formData, { headers });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    if (text) {
      const response = await apiClient.post('/api/v1/stocks/parse-import', { text });
      const data = response.data as { codes?: string[]; items?: ExtractItem[] };
      return { codes: data.codes ?? [], items: data.items };
    }
    throw new Error('请提供文件或粘贴文本');
  },

  async getWatchlist(refresh = false): Promise<WatchlistItem[]> {
    const response = await apiClient.get<{
      items?: Array<{
        code: string;
        name: string;
        added_at?: string | null;
        added_price?: number | null;
        current_price?: number | null;
        gain_percent?: number | null;
        updated_at?: string | null;
      }>;
    }>('/api/v1/stocks/watchlist', {
      params: refresh ? { refresh: true } : undefined,
    });

    return (response.data.items ?? []).map((item) => ({
      code: item.code,
      name: item.name,
      addedAt: item.added_at,
      addedPrice: item.added_price,
      currentPrice: item.current_price,
      gainPercent: item.gain_percent,
      updatedAt: item.updated_at,
    }));
  },

  async addWatchlistStock(payload: { code: string; name?: string }): Promise<WatchlistItem> {
    const response = await apiClient.post<{
      item: {
        code: string;
        name: string;
        added_at?: string | null;
        added_price?: number | null;
        current_price?: number | null;
        gain_percent?: number | null;
        updated_at?: string | null;
      };
    }>('/api/v1/stocks/watchlist', payload);

    const item = response.data.item;
    return {
      code: item.code,
      name: item.name,
      addedAt: item.added_at,
      addedPrice: item.added_price,
      currentPrice: item.current_price,
      gainPercent: item.gain_percent,
      updatedAt: item.updated_at,
    };
  },

  async startWatchlistBatchAdd(payload: { codes: string[]; name?: string }): Promise<WatchlistBatchTask> {
    const response = await apiClient.post<{
      task_id: string;
      status: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
      total: number;
      completed: number;
      results?: Array<{
        code: string;
        status: 'success' | 'error';
        message: string;
        item?: {
          code: string;
          name: string;
          added_at?: string | null;
          added_price?: number | null;
          current_price?: number | null;
          gain_percent?: number | null;
          updated_at?: string | null;
        };
      }>;
      error_message?: string | null;
      created_at?: string | null;
      updated_at?: string | null;
      finished_at?: string | null;
    }>('/api/v1/stocks/watchlist/batch', payload);

    return {
      taskId: response.data.task_id,
      status: response.data.status,
      total: response.data.total,
      completed: response.data.completed,
      results: (response.data.results ?? []).map((result) => ({
        code: result.code,
        status: result.status,
        message: result.message,
        item: result.item ? {
          code: result.item.code,
          name: result.item.name,
          addedAt: result.item.added_at,
          addedPrice: result.item.added_price,
          currentPrice: result.item.current_price,
          gainPercent: result.item.gain_percent,
          updatedAt: result.item.updated_at,
        } : undefined,
      })),
      errorMessage: response.data.error_message,
      createdAt: response.data.created_at,
      updatedAt: response.data.updated_at,
      finishedAt: response.data.finished_at,
    };
  },

  async getWatchlistBatchTask(taskId: string): Promise<WatchlistBatchTask> {
    const response = await apiClient.get<{
      task_id: string;
      status: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
      total: number;
      completed: number;
      results?: Array<{
        code: string;
        status: 'success' | 'error';
        message: string;
        item?: {
          code: string;
          name: string;
          added_at?: string | null;
          added_price?: number | null;
          current_price?: number | null;
          gain_percent?: number | null;
          updated_at?: string | null;
        };
      }>;
      error_message?: string | null;
      created_at?: string | null;
      updated_at?: string | null;
      finished_at?: string | null;
    }>(`/api/v1/stocks/watchlist/batch/${encodeURIComponent(taskId)}`);

    return {
      taskId: response.data.task_id,
      status: response.data.status,
      total: response.data.total,
      completed: response.data.completed,
      results: (response.data.results ?? []).map((result) => ({
        code: result.code,
        status: result.status,
        message: result.message,
        item: result.item ? {
          code: result.item.code,
          name: result.item.name,
          addedAt: result.item.added_at,
          addedPrice: result.item.added_price,
          currentPrice: result.item.current_price,
          gainPercent: result.item.gain_percent,
          updatedAt: result.item.updated_at,
        } : undefined,
      })),
      errorMessage: response.data.error_message,
      createdAt: response.data.created_at,
      updatedAt: response.data.updated_at,
      finishedAt: response.data.finished_at,
    };
  },

  async cancelWatchlistBatchTask(taskId: string): Promise<WatchlistBatchTask> {
    const response = await apiClient.post<{
      task_id: string;
      status: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
      total: number;
      completed: number;
      results?: WatchlistBatchResult[];
      error_message?: string | null;
      created_at?: string | null;
      updated_at?: string | null;
      finished_at?: string | null;
    }>(`/api/v1/stocks/watchlist/batch/${encodeURIComponent(taskId)}/cancel`);

    return {
      taskId: response.data.task_id,
      status: response.data.status,
      total: response.data.total,
      completed: response.data.completed,
      results: response.data.results ?? [],
      errorMessage: response.data.error_message,
      createdAt: response.data.created_at,
      updatedAt: response.data.updated_at,
      finishedAt: response.data.finished_at,
    };
  },

  async deleteWatchlistStock(code: string): Promise<void> {
    await apiClient.delete(`/api/v1/stocks/watchlist/${encodeURIComponent(code)}`);
  },
};
