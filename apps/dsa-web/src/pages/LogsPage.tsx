import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { ApiErrorAlert } from '../components/common';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { logsApi, type OperationLogItem } from '../api/logs';

const LOGS_PAGE_SIZE = 20;

const formatDateTime = (value?: string | null): string => {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
};

const statusTone = (status: string): string => {
  if (status === 'success') {
    return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300';
  }
  if (status === 'partial') {
    return 'border-amber-500/20 bg-amber-500/10 text-amber-200';
  }
  if (status === 'error') {
    return 'border-rose-500/20 bg-rose-500/10 text-rose-200';
  }
  return 'border-white/10 bg-white/5 text-secondary';
};

const levelTone = (level: string): string => {
  if (level === 'error') {
    return 'text-rose-300';
  }
  if (level === 'warning') {
    return 'text-amber-200';
  }
  return 'text-cyan';
};

const LogsPage: React.FC = () => {
  const [items, setItems] = useState<OperationLogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [category, setCategory] = useState('all');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const loadLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await logsApi.getLogs({
        page,
        pageSize: LOGS_PAGE_SIZE,
        category: category === 'all' ? undefined : category,
        status: status === 'all' ? undefined : status,
      });
      setItems(result.items);
      setTotal(result.total);
      setTotalPages(result.totalPages);
    } catch (loadError) {
      setError(getParsedApiError(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [category, page, status]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    setPage(1);
  }, [category, status]);

  const successCount = items.filter((item) => item.status === 'success').length;
  const errorCount = items.filter((item) => item.status === 'error').length;
  const partialCount = items.filter((item) => item.status === 'partial').length;

  return (
    <div className="min-h-screen px-4 pb-6 pt-4 md:px-6">
      <section className="relative overflow-hidden rounded-[28px] border border-cyan/15 bg-card/85 p-5 shadow-[0_20px_80px_rgba(0,212,255,0.08)] backdrop-blur-sm">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(0,212,255,0.18),transparent_34%),radial-gradient(circle_at_left,rgba(111,97,241,0.12),transparent_28%)]" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan/80">Global Journal</p>
            <h1 className="mt-3 text-3xl font-semibold text-white md:text-4xl">全局日志</h1>
            <p className="mt-3 text-sm leading-6 text-secondary">
              这里集中展示 Web 端重要操作日志，数据持久化保存在后端数据库中。股票批量新增的逐条结果和汇总结果都会在这里留档。
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:min-w-[420px]">
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">日志总数</div>
              <div className="mt-2 text-2xl font-semibold text-white">{total}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">当前页成功 / 部分</div>
              <div className="mt-2 text-2xl font-semibold text-emerald-300">{successCount} / {partialCount}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">当前页失败</div>
              <div className="mt-2 text-2xl font-semibold text-rose-300">{errorCount}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <div className="rounded-3xl border border-white/8 bg-card/70 p-5 backdrop-blur-sm">
          <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">日志流水</h2>
              <p className="mt-1 text-sm text-secondary">按时间倒序展示日志，分页浏览，每页最多 20 条。</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="rounded-xl border border-white/10 bg-elevated/70 px-3 py-2 text-sm text-white outline-none"
              >
                <option value="all">全部分类</option>
                <option value="watchlist">自选股</option>
              </select>
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="rounded-xl border border-white/10 bg-elevated/70 px-3 py-2 text-sm text-white outline-none"
              >
                <option value="all">全部状态</option>
                <option value="success">成功</option>
                <option value="partial">部分成功</option>
                <option value="error">失败</option>
              </select>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void loadLogs()}
                disabled={isLoading}
              >
                刷新日志
              </button>
            </div>
          </div>

          {error ? <ApiErrorAlert error={error} className="mb-4" /> : null}

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <div key={index} className="h-28 animate-pulse rounded-2xl border border-white/8 bg-elevated/40" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-elevated/30 px-6 py-10 text-center text-sm text-secondary">
              当前筛选条件下还没有日志。
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <article key={item.id} className="rounded-2xl border border-white/8 bg-elevated/35 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2.5 py-1 text-xs ${statusTone(item.status)}`}>
                          {item.status}
                        </span>
                        <span className={`text-xs uppercase tracking-[0.25em] ${levelTone(item.level)}`}>
                          {item.level}
                        </span>
                        <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs text-secondary">
                          {item.category} / {item.action}
                        </span>
                      </div>
                      <h3 className="mt-3 text-base font-semibold text-white">{item.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-secondary">{item.message}</p>
                    </div>
                    <div className="shrink-0 text-sm text-secondary lg:text-right">
                      <div>{formatDateTime(item.createdAt)}</div>
                      {item.stockCode ? <div className="mt-1 font-mono">{item.stockCode}</div> : null}
                      {item.stockName ? <div className="mt-1">{item.stockName}</div> : null}
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs text-secondary">
                    {item.taskId ? (
                      <span className="rounded-full border border-white/10 px-2.5 py-1 font-mono">
                        task: {item.taskId}
                      </span>
                    ) : null}
                  </div>

                  {item.details ? (
                    <details className="mt-4 rounded-xl border border-white/8 bg-card/50 p-3">
                      <summary className="cursor-pointer text-sm text-white">查看明细</summary>
                      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all text-xs leading-6 text-secondary">
                        {JSON.stringify(item.details, null, 2)}
                      </pre>
                    </details>
                  ) : null}
                </article>
              ))}
            </div>
          )}

          {!isLoading && total > 0 ? (
            <div className="mt-4 flex flex-col gap-3 border-t border-white/8 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-secondary">
                第 {page} / {Math.max(totalPages, 1)} 页，每页 {LOGS_PAGE_SIZE} 条，共 {total} 条
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={isLoading || page <= 1}
                >
                  上一页
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                  disabled={isLoading || page >= totalPages}
                >
                  下一页
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
};

export default LogsPage;
