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

export const logsApi = {
  async getLogs(params?: {
    limit?: number;
    category?: string;
    status?: string;
  }): Promise<OperationLogItem[]> {
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
    }>('/api/v1/logs', { params });

    return (response.data.items ?? []).map((item) => ({
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
    }));
  },
};
