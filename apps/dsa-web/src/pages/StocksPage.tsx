import type React from 'react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiErrorAlert, ConfirmDialog } from '../components/common';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { stocksApi, type WatchlistBatchTask, type WatchlistItem } from '../api/stocks';

const WATCHLIST_BATCH_TASK_STORAGE_KEY = 'dsa_watchlist_batch_task_id';

const formatDate = (value?: string | null): string => {
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
  }).format(date);
};

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
  }).format(date);
};

const formatPrice = (value?: number | null): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  return value.toFixed(2);
};

const formatGain = (value?: number | null): string => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
};

const splitBatchCodes = (rawValue: string): string[] => (
  rawValue
    .split(/[,\n，]+/)
    .map((item) => item.trim())
    .filter(Boolean)
);

const mergeWatchlistItems = (previousItems: WatchlistItem[], nextItems: WatchlistItem[]): WatchlistItem[] => {
  const merged = new Map(previousItems.map((item) => [item.code, item]));
  nextItems.forEach((item) => {
    merged.set(item.code, item);
  });
  return Array.from(merged.values());
};

const StocksPage: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingCode, setDeletingCode] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<ParsedApiError | null>(null);
  const [actionError, setActionError] = useState<ParsedApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<WatchlistItem | null>(null);
  const [addTask, setAddTask] = useState<WatchlistBatchTask | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);

  useEffect(() => {
    void loadWatchlist();
  }, []);

  useEffect(() => {
    const storedTaskId = window.localStorage.getItem(WATCHLIST_BATCH_TASK_STORAGE_KEY);
    if (storedTaskId) {
      setActiveTaskId(storedTaskId);
    }
  }, []);

  useEffect(() => {
    if (!successMessage) {
      return;
    }
    const timer = window.setTimeout(() => setSuccessMessage(null), 3200);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  useEffect(() => {
    if (!activeTaskId) {
      return;
    }

    let cancelled = false;
    let finishHandled = false;
    let timer: number | null = null;

    const pollTask = async () => {
      try {
        const task = await stocksApi.getWatchlistBatchTask(activeTaskId);
        if (cancelled) {
          return;
        }

        setAddTask(task);

        if ((task.status === 'completed' || task.status === 'cancelled') && !finishHandled) {
          finishHandled = true;
          setActiveTaskId(null);
          window.localStorage.removeItem(WATCHLIST_BATCH_TASK_STORAGE_KEY);
          if (timer !== null) {
            window.clearInterval(timer);
            timer = null;
          }
          const addedItems = task.results
            .filter((result) => result.status === 'success' && result.item)
            .map((result) => result.item as WatchlistItem);
          if (addedItems.length > 0) {
            setItems((previousItems) => mergeWatchlistItems(previousItems, addedItems));
          }
          return;
        }

        if (task.status === 'failed' && !finishHandled) {
          finishHandled = true;
          setActiveTaskId(null);
          window.localStorage.removeItem(WATCHLIST_BATCH_TASK_STORAGE_KEY);
          if (timer !== null) {
            window.clearInterval(timer);
            timer = null;
          }
          if (task.errorMessage) {
            setActionError(getParsedApiError(task.errorMessage));
          }
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setActionError(getParsedApiError(error));
        setAddTask(null);
        setActiveTaskId(null);
        window.localStorage.removeItem(WATCHLIST_BATCH_TASK_STORAGE_KEY);
        if (timer !== null) {
          window.clearInterval(timer);
          timer = null;
        }
      }
    };

    timer = window.setInterval(() => {
      void pollTask();
    }, 1200);
    void pollTask();

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearInterval(timer);
      }
    };
  }, [activeTaskId]);

  const loadWatchlist = async (forceRefresh = false) => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const nextItems = await stocksApi.getWatchlist(forceRefresh);
      setItems(nextItems);
    } catch (error) {
      setLoadError(getParsedApiError(error));
    } finally {
      setIsLoading(false);
    }
  };

  const totalCount = items.length;
  const gainItems = items.filter((item) => typeof item.gainPercent === 'number');
  const averageGain = gainItems.length
    ? gainItems.reduce((sum, item) => sum + Number(item.gainPercent ?? 0), 0) / gainItems.length
    : null;
  const bestItem = [...items]
    .filter((item) => typeof item.gainPercent === 'number')
    .sort((a, b) => Number(b.gainPercent ?? -Infinity) - Number(a.gainPercent ?? -Infinity))[0];

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError(null);
    setSuccessMessage(null);

    const rawCodes = splitBatchCodes(code);
    if (rawCodes.length === 0) {
      setActionError(getParsedApiError('请输入至少一个股票代码'));
      return;
    }

    const singleName = rawCodes.length === 1 ? name.trim() || undefined : undefined;

    void (async () => {
      try {
        const task = await stocksApi.startWatchlistBatchAdd({
          codes: rawCodes,
          name: singleName,
        });
        setCode('');
        setName('');
        setIsAddModalOpen(false);
        setAddTask(task);
        setActiveTaskId(task.taskId);
        window.localStorage.setItem(WATCHLIST_BATCH_TASK_STORAGE_KEY, task.taskId);
      } catch (error) {
        setActionError(getParsedApiError(error));
      }
    })();
  };

  const handleConfirmDelete = async () => {
    if (!pendingDelete) {
      return;
    }

    setActionError(null);
    setDeletingCode(pendingDelete.code);
    try {
      await stocksApi.deleteWatchlistStock(pendingDelete.code);
      setSuccessMessage(`${pendingDelete.code} 已从自选股移除`);
      setPendingDelete(null);
      await loadWatchlist();
    } catch (error) {
      setActionError(getParsedApiError(error));
    } finally {
      setDeletingCode(null);
    }
  };

  const handleAnalyze = (item: WatchlistItem) => {
    navigate(`/?stock=${encodeURIComponent(item.code)}&analyze=1`);
  };

  const handleCancelAddTask = () => {
    if (!activeTaskId || !addTask || (addTask.status !== 'running' && addTask.status !== 'cancelling')) {
      return;
    }

    setActionError(null);
    void (async () => {
      try {
        const task = await stocksApi.cancelWatchlistBatchTask(activeTaskId);
        setAddTask(task);
      } catch (error) {
        setActionError(getParsedApiError(error));
      }
    })();
  };

  const isAddJobRunning = addTask?.status === 'running' || addTask?.status === 'cancelling';
  const addProgress = {
    completed: addTask?.completed ?? 0,
    total: addTask?.total ?? 0,
  };
  const failedResults = (addTask?.results ?? []).filter((result) => result.status === 'error');
  const shouldShowAddPanel = Boolean(
    isAddJobRunning
    || failedResults.length > 0
    || addTask?.status === 'failed'
    || addTask?.status === 'cancelled'
  );

  return (
    <div className="min-h-screen px-4 pb-6 pt-4 md:px-6">
      <section className="relative overflow-hidden rounded-[28px] border border-cyan/15 bg-card/85 p-5 shadow-[0_20px_80px_rgba(0,212,255,0.08)] backdrop-blur-sm">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(0,212,255,0.18),transparent_34%),radial-gradient(circle_at_left,rgba(111,97,241,0.12),transparent_28%)]" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan/80">Watchlist Desk</p>
            <h1 className="mt-3 text-3xl font-semibold text-white md:text-4xl">股票管理</h1>
            <p className="mt-3 text-sm leading-6 text-secondary">
              这里是新的自选股工作台。新增、删除会实时同步回原来的 <code>STOCK_LIST</code>，
              旧配置入口和新页面始终保持一致。涨跌幅默认走缓存，仅在手动刷新或各市场收盘后自动更新。
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 lg:min-w-[420px]">
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">持仓池数量</div>
              <div className="mt-2 text-2xl font-semibold text-white">{totalCount}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">平均涨幅</div>
              <div className={`mt-2 text-2xl font-semibold ${averageGain !== null && averageGain >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {formatGain(averageGain)}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-elevated/70 p-4">
              <div className="text-xs uppercase tracking-[0.2em] text-muted">领先股票</div>
              <div className="mt-2 text-lg font-semibold text-white">{bestItem?.name ?? '--'}</div>
              <div className="text-sm text-secondary">{bestItem ? `${bestItem.code} · ${formatGain(bestItem.gainPercent)}` : '暂无数据'}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <div className="rounded-3xl border border-white/8 bg-card/70 p-5 backdrop-blur-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">自选股列表</h2>
              <p className="mt-1 text-sm text-secondary">展示名称、代码、添加日期、添加后涨幅和缓存更新时间。</p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  setActionError(null);
                  setIsAddModalOpen(true);
                }}
                disabled={Boolean(isAddJobRunning)}
              >
                {isAddJobRunning ? '后台添加中...' : '新增股票'}
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void loadWatchlist(true)}
                disabled={isLoading || Boolean(deletingCode)}
              >
                手动刷新
              </button>
            </div>
          </div>

          {loadError ? <ApiErrorAlert error={loadError} className="mb-4" /> : null}
          {actionError ? <ApiErrorAlert error={actionError} className="mb-4" /> : null}
          {successMessage ? (
            <div className="mb-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
              {successMessage}
            </div>
          ) : null}

          {shouldShowAddPanel ? (
            <div className="mb-4 rounded-2xl border border-white/8 bg-elevated/45 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-white">
                    {addTask?.status === 'cancelling'
                      ? '正在取消后台添加'
                      : addTask?.status === 'running'
                        ? '股票正在后台添加'
                        : addTask?.status === 'cancelled'
                          ? '后台添加已取消'
                          : addTask?.status === 'failed'
                            ? '后台任务执行失败'
                            : '添加失败代码'}
                  </div>
                  <div className="mt-1 text-xs text-secondary">
                    {addProgress.total > 0
                      ? `已处理 ${addProgress.completed} / ${addProgress.total}`
                      : '暂无添加任务'}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(addTask?.status === 'running' || addTask?.status === 'cancelling') ? (
                    <button
                      type="button"
                      className="rounded-xl border border-amber-500/20 px-3 py-2 text-sm text-amber-200 transition hover:bg-amber-500/10 disabled:cursor-not-allowed disabled:opacity-60"
                      onClick={handleCancelAddTask}
                      disabled={addTask?.status === 'cancelling'}
                    >
                      {addTask?.status === 'cancelling' ? '取消中...' : '取消后台添加'}
                    </button>
                  ) : null}
                  {failedResults.length > 0 || addTask?.status === 'failed' || addTask?.status === 'cancelled' ? (
                    <button
                      type="button"
                      className="rounded-xl border border-white/10 px-3 py-2 text-sm text-secondary transition hover:border-white/20 hover:text-white"
                      onClick={() => {
                        setAddTask(null);
                        setActiveTaskId(null);
                        window.localStorage.removeItem(WATCHLIST_BATCH_TASK_STORAGE_KEY);
                      }}
                    >
                      清空结果
                    </button>
                  ) : null}
                </div>
              </div>

              {addProgress.total > 0 ? (
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/6">
                  <div
                    className="h-full rounded-full bg-cyan transition-all"
                    style={{ width: `${Math.min(100, (addProgress.completed / Math.max(addProgress.total, 1)) * 100)}%` }}
                  />
                </div>
              ) : null}

              {failedResults.length > 0 ? (
                <div className="mt-4 max-h-52 space-y-2 overflow-y-auto pr-1">
                  {failedResults.map((result) => (
                    <div
                      key={`${result.code}-${result.status}-${result.message}`}
                      className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200"
                    >
                      <span className="font-mono">{result.code}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              {addTask?.status === 'failed' && addTask.errorMessage ? (
                <div className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                  {addTask.errorMessage}
                </div>
              ) : null}

              {addTask?.status === 'cancelled' ? (
                <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
                  后台添加已取消，未开始的股票不会继续处理。
                </div>
              ) : null}
            </div>
          ) : null}

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="h-20 animate-pulse rounded-2xl border border-white/8 bg-elevated/40" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-white/10 bg-elevated/30 px-6 py-10 text-center text-sm text-secondary">
              还没有自选股，点击右上角“新增股票”试试看。
            </div>
          ) : (
            <>
              <div className="hidden overflow-hidden rounded-2xl border border-white/8 lg:block">
                <table className="min-w-full divide-y divide-white/8 text-left text-sm">
                  <thead className="bg-elevated/60 text-muted">
                    <tr>
                      <th className="px-4 py-3 font-medium">股票名称</th>
                      <th className="px-4 py-3 font-medium">代码</th>
                      <th className="px-4 py-3 font-medium">添加日期</th>
                      <th className="px-4 py-3 font-medium">添加价</th>
                      <th className="px-4 py-3 font-medium">现价</th>
                      <th className="px-4 py-3 font-medium">添加后涨幅</th>
                      <th className="px-4 py-3 font-medium">缓存更新</th>
                      <th className="px-4 py-3 font-medium text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/6">
                    {items.map((item) => (
                      <tr key={item.code} className="bg-card/40 transition hover:bg-elevated/60">
                        <td className="px-4 py-4">
                          <div className="font-medium text-white">{item.name}</div>
                        </td>
                        <td className="px-4 py-4 font-mono text-secondary">{item.code}</td>
                        <td className="px-4 py-4 text-secondary">{formatDate(item.addedAt)}</td>
                        <td className="px-4 py-4 text-secondary">{formatPrice(item.addedPrice)}</td>
                        <td className="px-4 py-4 text-secondary">{formatPrice(item.currentPrice)}</td>
                        <td className={`px-4 py-4 font-medium ${Number(item.gainPercent ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {formatGain(item.gainPercent)}
                        </td>
                        <td className="px-4 py-4 text-secondary">{formatDateTime(item.updatedAt)}</td>
                        <td className="px-4 py-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button
                              type="button"
                              className="rounded-xl border border-cyan/20 px-3 py-2 text-sm text-cyan transition hover:bg-cyan/10"
                              onClick={() => handleAnalyze(item)}
                              disabled={Boolean(deletingCode)}
                            >
                              分析
                            </button>
                            <button
                              type="button"
                              className="rounded-xl border border-rose-500/20 px-3 py-2 text-sm text-rose-300 transition hover:bg-rose-500/10"
                              onClick={() => setPendingDelete(item)}
                              disabled={Boolean(deletingCode)}
                            >
                              删除
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-1 gap-3 lg:hidden">
                {items.map((item) => (
                  <div key={item.code} className="rounded-2xl border border-white/8 bg-elevated/40 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-base font-semibold text-white">{item.name}</div>
                        <div className="mt-1 font-mono text-sm text-secondary">{item.code}</div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="rounded-xl border border-cyan/20 px-3 py-2 text-sm text-cyan transition hover:bg-cyan/10"
                          onClick={() => handleAnalyze(item)}
                          disabled={Boolean(deletingCode)}
                        >
                          分析
                        </button>
                        <button
                          type="button"
                          className="rounded-xl border border-rose-500/20 px-3 py-2 text-sm text-rose-300 transition hover:bg-rose-500/10"
                          onClick={() => setPendingDelete(item)}
                          disabled={Boolean(deletingCode)}
                        >
                          删除
                        </button>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-xl bg-card/70 p-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted">添加日期</div>
                        <div className="mt-2 text-white">{formatDate(item.addedAt)}</div>
                      </div>
                      <div className="rounded-xl bg-card/70 p-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted">添加后涨幅</div>
                        <div className={`mt-2 font-semibold ${Number(item.gainPercent ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {formatGain(item.gainPercent)}
                        </div>
                      </div>
                      <div className="rounded-xl bg-card/70 p-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted">添加价</div>
                        <div className="mt-2 text-white">{formatPrice(item.addedPrice)}</div>
                      </div>
                      <div className="rounded-xl bg-card/70 p-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted">现价</div>
                        <div className="mt-2 text-white">{formatPrice(item.currentPrice)}</div>
                      </div>
                      <div className="col-span-2 rounded-xl bg-card/70 p-3">
                        <div className="text-xs uppercase tracking-[0.2em] text-muted">缓存更新</div>
                        <div className="mt-2 text-white">{formatDateTime(item.updatedAt)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </section>

      {isAddModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-4 backdrop-blur-sm"
          onClick={() => setIsAddModalOpen(false)}
        >
          <div
            className="w-full max-w-lg rounded-[28px] border border-white/10 bg-card/95 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.45)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-cyan/80">Quick Add</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">新增股票</h3>
                <p className="mt-2 text-sm leading-6 text-secondary">
                  支持单个或批量输入代码，多个股票可用英文逗号、中文逗号或换行分隔；名称只在单只股票时生效。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsAddModalOpen(false)}
                className="dock-item !h-10 !w-10 shrink-0"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="mb-2 block text-sm text-secondary">股票代码</span>
                <textarea
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder="例如 600519,300750,HK00700 或一行一个"
                  className="min-h-[120px] w-full rounded-2xl border border-white/10 bg-elevated/70 px-4 py-3 text-white outline-none transition focus:border-cyan/40"
                />
              </label>

              <label className="block">
                <span className="mb-2 block text-sm text-secondary">股票名称（可选）</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="例如 贵州茅台"
                  className="w-full rounded-2xl border border-white/10 bg-elevated/70 px-4 py-3 text-white outline-none transition focus:border-cyan/40"
                />
              </label>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  className="rounded-xl border border-white/10 px-4 py-3 text-sm text-secondary transition hover:border-white/20 hover:text-white"
                  onClick={() => setIsAddModalOpen(false)}
                >
                  取消
                </button>
                <button type="submit" className="btn-primary">
                  后台添加
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title="删除自选股"
        message={pendingDelete ? `确认删除 ${pendingDelete.name}（${pendingDelete.code}）吗？这会同步更新原有的自选股配置。` : ''}
        confirmText={deletingCode ? '删除中...' : '确认删除'}
        cancelText="取消"
        isDanger
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => {
          if (!deletingCode) {
            setPendingDelete(null);
          }
        }}
      />
    </div>
  );
};

export default StocksPage;
