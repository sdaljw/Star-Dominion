import { AlertTriangle, ArrowDownRight, Gauge, Ruler } from 'lucide-react';
import { motion } from 'framer-motion';
import type { AlarmData, DeviceRecord } from './types';

interface AlertStackProps {
  devices: Record<string, DeviceRecord>;
}

const LEVELS: Record<string, { label: string; color: string; border: string; bg: string }> = {
  RED: { label: '红色预警', color: '#fb7185', border: 'border-rose-400/45', bg: 'bg-rose-950/90' },
  ORANGE: { label: '橙色预警', color: '#fb923c', border: 'border-orange-400/45', bg: 'bg-orange-950/90' },
  YELLOW: { label: '黄色预警', color: '#facc15', border: 'border-yellow-300/45', bg: 'bg-yellow-950/90' },
};

const SEVERITY: Record<string, number> = { RED: 0, ORANGE: 1, YELLOW: 2 };

function isActiveAlarm(alarm: AlarmData | null): alarm is AlarmData {
  return Boolean(alarm && !['NORMAL', 'GREEN'].includes(alarm.level));
}

export function AlertStack({ devices }: AlertStackProps) {
  const alarms = Object.values(devices)
    .filter((device) => isActiveAlarm(device.alarm))
    .sort((a, b) => (SEVERITY[a.alarm?.level || 'YELLOW'] ?? 3) - (SEVERITY[b.alarm?.level || 'YELLOW'] ?? 3));

  if (alarms.length === 0) return null;

  return (
    <div className="pointer-events-none absolute top-5 z-30 flex w-[300px] flex-col gap-2" style={{ left: 'calc(min(390px, 100vw - 24px) + 12px)' }}>
      {alarms.map((device) => {
        const alarm = device.alarm as AlarmData;
        const style = LEVELS[alarm.level] || LEVELS.YELLOW;
        return (
          <motion.div key={device.device_id} initial={{ opacity: 0, x: -18, scale: 0.98 }} animate={{ opacity: 1, x: 0, scale: 1 }} className={`pointer-events-auto rounded-xl border ${style.border} ${style.bg} p-3 shadow-[0_10px_30px_rgba(0,0,0,0.28)] backdrop-blur-xl`}>
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" style={{ color: style.color }} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold" style={{ color: style.color }}>{style.label}</span>
                  <span className="font-mono text-[10px] text-slate-400">设备 {device.device_id}</span>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] text-slate-300">
                  <span className="flex items-center gap-1"><Gauge className="h-3 w-3" />风险 {alarm.score.toFixed(1)}</span>
                  <span className="flex items-center gap-1"><Ruler className="h-3 w-3" />位移 {alarm.D.toFixed(2)} mm</span>
                  <span className="flex items-center gap-1"><ArrowDownRight className="h-3 w-3" />倾角 {alarm.tilt.toFixed(2)}°</span>
                  <span>速率 {alarm.V.toFixed(2)} mm/min</span>
                </div>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
