import { AlertCircle, Bell, CheckCircle2, Info, Trash2 } from 'lucide-react';
import { motion } from 'framer-motion';
import type { NotificationItem } from './types';

interface NotificationPanelProps {
  notifications: NotificationItem[];
  onClear: () => void;
}

const STYLE = {
  success: { border: 'border-emerald-400/20', bg: 'bg-emerald-400/10', text: 'text-emerald-200', icon: <CheckCircle2 className="h-3 w-3" /> },
  error: { border: 'border-rose-400/25', bg: 'bg-rose-400/10', text: 'text-rose-200', icon: <AlertCircle className="h-3 w-3" /> },
  warning: { border: 'border-amber-300/25', bg: 'bg-amber-300/10', text: 'text-amber-100', icon: <AlertCircle className="h-3 w-3" /> },
  info: { border: 'border-cyan-300/20', bg: 'bg-cyan-300/10', text: 'text-cyan-100', icon: <Info className="h-3 w-3" /> },
};

export function NotificationPanel({ notifications, onClear }: NotificationPanelProps) {
  return (
    <section className="flex h-[210px] min-h-[210px] flex-col rounded-xl border border-cyan-300/15 bg-[#06182d]/88 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2"><Bell className="h-4 w-4 text-cyan-300" /><h2 className="text-sm font-semibold text-slate-100">系统通知</h2></div>
        <button type="button" onClick={onClear} className="flex items-center gap-1 text-[10px] text-slate-500 transition hover:text-rose-300"><Trash2 className="h-3 w-3" />清空</button>
      </div>
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
        {notifications.length === 0 && <p className="py-5 text-center text-xs text-slate-600">暂无通知</p>}
        {notifications.map((notification, index) => {
          const style = STYLE[notification.type];
          return (
            <motion.div key={`${notification.time}-${index}`} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className={`flex gap-2 rounded-lg border ${style.border} ${style.bg} p-2 ${style.text}`}>
              <span className="mt-0.5 shrink-0">{style.icon}</span>
              <span className="shrink-0 font-mono text-[9px] text-slate-500">{notification.time}</span>
              <span className="min-w-0 text-[10px] leading-relaxed">{notification.msg}</span>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
