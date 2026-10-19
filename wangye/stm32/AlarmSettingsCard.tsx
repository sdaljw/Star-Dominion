import { AlertTriangle, Save, Settings2, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { AlarmData, AlarmSettings } from './types';
import { countEnabledAlarmSettings, EMPTY_ALARM_SETTINGS } from './alarmSettings';

interface AlarmSettingsCardProps {
  settings: AlarmSettings;
  alarm: AlarmData | null;
  saving: boolean;
  onSave: (settings: AlarmSettings) => Promise<boolean>;
}

const SETTING_FIELDS: { key: keyof AlarmSettings; label: string; unit: string }[] = [
  { key: 'acc_x', label: '加速度 X', unit: 'g' },
  { key: 'acc_y', label: '加速度 Y', unit: 'g' },
  { key: 'angle_x', label: '姿态角 X', unit: '°' },
  { key: 'angle_y', label: '姿态角 Y', unit: '°' },
  { key: 'angle_z', label: '姿态角 Z', unit: '°' },
];

type DraftSettings = Record<keyof AlarmSettings, string>;

function toDraft(settings: AlarmSettings): DraftSettings {
  return SETTING_FIELDS.reduce<DraftSettings>((result, field) => {
    result[field.key] = settings[field.key] === null ? '' : String(settings[field.key]);
    return result;
  }, { ...Object.fromEntries(SETTING_FIELDS.map(({ key }) => [key, ''])) } as DraftSettings);
}

function isActiveAlarm(alarm: AlarmData | null): boolean {
  return Boolean(alarm && !['NORMAL', 'GREEN'].includes(alarm.level));
}

export function AlarmSettingsCard({ settings, alarm, saving, onSave }: AlarmSettingsCardProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DraftSettings>(() => toDraft(settings));
  const [error, setError] = useState('');
  const enabledCount = countEnabledAlarmSettings(settings);
  const active = isActiveAlarm(alarm);

  useEffect(() => {
    if (!open) setDraft(toDraft(settings));
  }, [open, settings]);

  useEffect(() => {
    if (!open) return undefined;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next = { ...EMPTY_ALARM_SETTINGS };
    for (const field of SETTING_FIELDS) {
      const raw = draft[field.key].trim();
      if (!raw) {
        next[field.key] = null;
        continue;
      }
      const value = Number(raw);
      if (!Number.isFinite(value) || value < 0) {
        setError(`${field.label}请输入大于等于 0 的数字`);
        return;
      }
      next[field.key] = value;
    }
    setError('');
    if (await onSave(next)) setOpen(false);
  };

  return (
    <>
      <div className={`min-w-0 rounded-lg border p-1.5 shadow-[inset_0_1px_0_rgba(120,220,255,0.05)] ${active ? 'border-rose-300/40 bg-rose-950/40' : 'border-cyan-300/10 bg-[#0a2139]/90'}`}>
        <button
          type="button"
          className="flex w-full min-w-0 flex-col text-left"
          aria-label="预警设置"
          onClick={() => { setError(''); setOpen(true); }}
        >
          <div className={`mb-0.5 flex items-center gap-1 text-[9px] font-semibold tracking-wide ${active ? 'text-rose-300' : 'text-slate-500'}`}>
            {active ? <AlertTriangle className="h-3 w-3" /> : <Settings2 className="h-3 w-3 text-cyan-300" />}
            <span className="truncate">预警设置</span>
          </div>
          <div className={`truncate font-mono text-[12px] font-semibold ${active ? 'text-rose-200' : 'text-cyan-200'}`}>
            {active ? (alarm?.message || '已触发') : enabledCount > 0 ? `已启用 ${enabledCount} 项` : '未启用'}
          </div>
        </button>
      </div>

      {open && createPortal(
        <div
          className="fixed inset-0 z-[100] flex min-h-full items-start justify-center overflow-y-auto bg-slate-950/70 p-3 sm:items-center sm:p-4"
          role="presentation"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}
        >
          <section
            className="mx-auto my-0 flex max-h-[calc(100dvh-1.5rem)] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-cyan-300/20 bg-[#06182d] shadow-2xl sm:my-2 sm:max-h-[calc(100dvh-2rem)]"
            role="dialog"
            aria-modal="true"
            aria-labelledby="alarm-settings-title"
          >
            <div className="flex shrink-0 items-start justify-between gap-3 p-4 pb-3">
              <div className="min-w-0">
                <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-cyan-300/70">Cloud alarm</p>
                <h3 id="alarm-settings-title" className="text-sm font-semibold text-slate-100">预警设置</h3>
                <p className="mt-1 text-[11px] leading-4 text-slate-400">任意一项达到阈值即报警，留空表示关闭；按绝对值判断。</p>
              </div>
              <button
                type="button"
                aria-label="关闭"
                title="关闭"
                className="inline-flex shrink-0 items-center gap-1 rounded-md border border-slate-400/20 px-2 py-1 text-xs text-slate-300 hover:bg-white/10 hover:text-slate-100"
                onClick={() => setOpen(false)}
              >
                <X className="h-4 w-4" />
                <span>关闭</span>
              </button>
            </div>
            <form className="flex min-h-0 flex-1 flex-col" onSubmit={handleSubmit}>
              <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 pb-4">
                {SETTING_FIELDS.map((field) => (
                  <label key={field.key} className="flex min-w-0 items-center gap-2 text-xs text-slate-300">
                    <span className="w-20 shrink-0">{field.label}</span>
                    <input
                      aria-label={field.label}
                      className="min-w-0 flex-1 rounded-md border border-cyan-300/15 bg-[#0a2139] px-2 py-1.5 font-mono text-xs text-slate-100 outline-none focus:border-cyan-300/60"
                      type="number"
                      min="0"
                      step="any"
                      placeholder="留空关闭"
                      value={draft[field.key]}
                      onChange={(event) => setDraft((current) => ({ ...current, [field.key]: event.target.value }))}
                    />
                    <span className="w-5 shrink-0 text-right text-[10px] text-slate-500">{field.unit}</span>
                  </label>
                ))}
                {error && <p className="text-xs text-rose-300" role="alert">{error}</p>}
              </div>
              <div className="flex shrink-0 justify-end gap-2 border-t border-cyan-300/10 bg-[#06182d] px-4 py-3">
                <button type="button" className="rounded-md border border-slate-400/20 px-3 py-1.5 text-xs text-slate-300 hover:bg-white/10" onClick={() => setOpen(false)}>取消</button>
                <button type="submit" disabled={saving} title="确定并保存设置" className="inline-flex items-center gap-1 rounded-md bg-cyan-400/15 px-3 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/25 disabled:cursor-wait disabled:opacity-50">
                  <Save className="h-3.5 w-3.5" />{saving ? '保存中…' : '确定'}
                </button>
              </div>
            </form>
          </section>
        </div>,
        document.body,
      )}
    </>
  );
}
