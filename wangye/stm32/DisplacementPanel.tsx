import { BarChart3 } from 'lucide-react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { DeviceSelector } from './DeviceSelector';
import type { DeviceRecord, DisplacementPoint } from './types';

interface DisplacementPanelProps {
  devices: DeviceRecord[];
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
  history: DisplacementPoint[];
}

const SERIES = [
  { key: 'x', label: 'X 东 / 西', color: '#22d3ee' },
  { key: 'y', label: 'Y 南 / 北', color: '#34d399' },
  { key: 'z', label: 'Z 高程', color: '#fb923c' },
] as const;

export function DisplacementPanel({ devices, selectedDeviceId, onSelectDevice, history }: DisplacementPanelProps) {
  return (
    <section className="rounded-xl border border-cyan-300/15 bg-[#06182d]/88 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="mb-2 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-cyan-300" />
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300/65">Movement trend</p>
          <h2 className="text-sm font-semibold text-slate-100">XYZ 三轴位移变化</h2>
        </div>
      </div>
      <div className="mb-2">
        <DeviceSelector devices={devices} value={selectedDeviceId} onChange={onSelectDevice} />
      </div>
      <div className="space-y-2">
        {SERIES.map((series) => {
          const latest = history.length ? history[history.length - 1][series.key] : 0;
          return (
            <div key={series.key} className="rounded-lg border border-cyan-300/10 bg-[#0a2139]/90 p-2">
              <div className="mb-1 flex items-center justify-between">
                <div className="flex items-center gap-2 text-[10px] font-semibold text-slate-400">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: series.color }} />
                  {series.label}
                </div>
                <span className="font-mono text-[10px]" style={{ color: series.color }}>{latest.toFixed(3)} m</span>
              </div>
              <div className="h-[58px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e405c" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis stroke="#64748b" fontSize={8} tickLine={false} axisLine={false} width={25} />
                    <Tooltip contentStyle={{ backgroundColor: '#071b31', border: '1px solid #1d5a76', borderRadius: '8px', fontSize: '10px', color: '#e2e8f0' }} />
                    <Line type="monotone" dataKey={series.key} stroke={series.color} strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
