import type React from 'react';
import { useState, useEffect } from 'react';
import type { ParsedApiError } from '../../api/error';
import { isParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { ApiErrorAlert, EyeToggleIcon } from '../common';
import { SettingsAlert } from './SettingsAlert';

export const AuthSettingsCard: React.FC = () => {
  const { authEnabled, passwordSet, updateSettings } = useAuth();
  const [targetEnabled, setTargetEnabled] = useState(authEnabled);
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showCurrent, setShowCurrent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setTargetEnabled(authEnabled);
  }, [authEnabled]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (targetEnabled === authEnabled) {
      return;
    }

    if (targetEnabled) {
      if (!passwordSet) {
        if (!password.trim()) {
          setError('请输入新密码');
          return;
        }
        if (password.length < 6) {
          setError('密码至少 6 位');
          return;
        }
        if (password !== passwordConfirm) {
          setError('两次输入的密码不一致');
          return;
        }
      } else {
        if (!currentPassword.trim()) {
          setError('请输入当前密码以启用');
          return;
        }
      }
    } else {
      if (!currentPassword.trim()) {
        setError('请输入当前密码以停用');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const result = await updateSettings(
        targetEnabled,
        targetEnabled && !passwordSet ? password : undefined,
        targetEnabled && !passwordSet ? passwordConfirm : undefined,
        (targetEnabled && passwordSet) || !targetEnabled ? currentPassword : undefined
      );
      if (result.success) {
        setSuccess(true);
        setPassword('');
        setPasswordConfirm('');
        setCurrentPassword('');
        setTimeout(() => setSuccess(false), 4000);
      } else {
        setError(result.error ?? '更新失败');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const hasChanges = targetEnabled !== authEnabled;

  return (
    <div className="rounded-xl border border-white/8 bg-elevated/50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <label className="text-sm font-semibold text-white">管理员登录认证</label>
          <p className="mt-1 text-xs text-muted">开启后访问 Web 界面需要输入密码</p>
        </div>
        <button
          type="button"
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
            targetEnabled ? 'bg-cyan' : 'bg-white/10'
          }`}
          onClick={() => setTargetEnabled(!targetEnabled)}
          disabled={isSubmitting}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
              targetEnabled ? 'translate-x-5' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {hasChanges && (
        <form onSubmit={handleSubmit} className="mt-4 space-y-3 border-t border-white/8 pt-4">
          {targetEnabled && !passwordSet ? (
            <>
              <div>
                <label className="mb-1 block text-xs font-medium text-secondary">设置初始密码</label>
                <div className="flex items-center gap-2">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="input-terminal flex-1"
                    placeholder="输入新密码（至少 6 位）"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="btn-secondary !p-2 shrink-0"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    <EyeToggleIcon visible={showPassword} />
                  </button>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-secondary">确认新密码</label>
                <div className="flex items-center gap-2">
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    className="input-terminal flex-1"
                    placeholder="再次输入新密码"
                    value={passwordConfirm}
                    onChange={(e) => setPasswordConfirm(e.target.value)}
                    disabled={isSubmitting}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="btn-secondary !p-2 shrink-0"
                    onClick={() => setShowConfirm(!showConfirm)}
                  >
                    <EyeToggleIcon visible={showConfirm} />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div>
              <label className="mb-1 block text-xs font-medium text-secondary">
                验证当前密码
              </label>
              <div className="flex items-center gap-2">
                <input
                  type={showCurrent ? 'text' : 'password'}
                  className="input-terminal flex-1"
                  placeholder="输入当前管理员密码"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  disabled={isSubmitting}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="btn-secondary !p-2 shrink-0"
                  onClick={() => setShowCurrent(!showCurrent)}
                >
                  <EyeToggleIcon visible={showCurrent} />
                </button>
              </div>
              <p className="mt-1 text-[10px] text-muted">
                {targetEnabled ? '开启认证需要验证当前密码' : '关闭认证需要验证当前密码'}
              </p>
            </div>
          )}

          {error && (
            isParsedApiError(error) ? (
              <ApiErrorAlert error={error} className="!mt-3" />
            ) : (
              <SettingsAlert title="操作失败" message={error} variant="error" className="!mt-3" />
            )
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              className="btn-primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? '保存中...' : '确认更改'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setTargetEnabled(authEnabled);
                setError(null);
              }}
              disabled={isSubmitting}
            >
              取消
            </button>
          </div>
        </form>
      )}

      {success && !hasChanges && (
        <p className="mt-2 text-xs text-green-500">设置已成功更新</p>
      )}
    </div>
  );
};
