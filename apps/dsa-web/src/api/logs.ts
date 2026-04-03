import apiClient from './index';

export type OperationLogItem = {
  id: number;
  category: string;
  action: string;
  level: string;
  status: string;
  title: string;
  message: string;
  stockCode?: string | null;
  stockName?: string | null;
  taskId?: string | null;
  details?: Record<string, unknown> | null;
  createdAt?: string | null;
};

export type OperationLogPage = {
  items: OperationLogItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
};

export const logsApi = {
  async getLogs(params?: {
    page?: number;
    pageSize?: number;
    category?: string;
    status?: string;
  }): Promise<OperationLogPage> {
    const response = await apiClient.get<{
      items?: Array<{
        id: number;
        category: string;
        action: string;
        level: string;
        status: string;
        title: string;
        message: string;
        stock_code?: string | null;
        stock_name?: string | null;
        task_id?: string | null;
        details?: Record<string, unknown> | null;
        created_at?: string | null;
      }>;
      total?: number;
      page?: number;
      page_size?: number;
      total_pages?: number;
    }>('/api/v1/logs', {
      params: {
        page: params?.page,
        page_size: params?.pageSize,
        category: params?.category,
        status: params?.status,
      },
    });

    return {
      items: (response.data.items ?? []).map((item) => ({
        id: item.id,
        category: item.category,
        action: item.action,
        level: item.level,
        status: item.status,
        title: item.title,
        message: item.message,
        stockCode: item.stock_code,
        stockName: item.stock_name,
        taskId: item.task_id,
        details: item.details,
        createdAt: item.created_at,
      })),
      total: response.data.total ?? 0,
      page: response.data.page ?? 1,
      pageSize: response.data.page_size ?? 20,
      totalPages: response.data.total_pages ?? 1,
    };
  },
};
