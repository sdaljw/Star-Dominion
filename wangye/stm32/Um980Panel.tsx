import type { ReactNode } from 'react';
import { Activity, MapPin, Satellite, Thermometer, Waves } from 'lucide-react';
import { DeviceSelector } from './DeviceSelector';
import type { DeviceRecord } from './types';
import { formatDataAge } from './telemetry';

interface Um980PanelProps {
  devices: DeviceRecord[];
  device: DeviceRecord | null;
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
}

interface MetricCardProps {
  label: string;
  value: string;
  accent: string;
  icon: ReactNode;
}

function MetricCard({ label, value, accent, icon }: MetricCardProps) {
  return (
    <div className="min-w-0 rounded-lg border border-cyan-300/10 bg-[#0a2139]/90 p-2.5 shadow-[inset_0_1px_0_rgba(120,220,255,0.05)]">
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold tracking-wide text-slate-500">
        {icon}
        <span className="truncate">{label}</span>
      </div>
      <div className="truncate font-mono text-[13px] font-semibold" style={{ color: accent }}>{value}</div>
    </div>
  );
}

export function Um980Panel({ devices, device, selectedDeviceId, onSelectDevice }: Um980PanelProps) {
  const metrics = [
    { label: '经度', value: device?.longitude === null || device?.longitude === undefined ? '--' : `${device.longitude.toFixed(7)}°`, accent: '#67e8f9', icon: <MapPin className="h-3 w-3 text-cyan-300" /> },
    { label: '纬度', value: device?.latitude === null || device?.latitude === undefined ? '--' : `${device.latitude.toFixed(7)}°`, accent: '#67e8f9', icon: <MapPin className="h-3 w-3 text-cyan-300" /> },
    { label: '海拔', value: device?.altitude === null || device?.altitude === undefined ? '--' : `${device.altitude.toFixed(2)} m`, accent: '#a5f3fc', icon: <Activity className="h-3 w-3 text-cyan-300" /> },
    { label: '定位状态', value: device?.quality || '--', accent: '#bef264', icon: <Activity className="h-3 w-3 text-lime-300" /> },
    { label: '卫星数', value: device ? `${device.satellites} 颗` : '--', accent: '#fde68a', icon: <Satellite className="h-3 w-3 text-amber-300" /> },
    { label: '温度', value: device?.temperature === null || device?.temperature === undefined ? '--' : `${device.temperature.toFixed(1)} °C`, accent: '#fdba74', icon: <Thermometer className="h-3 w-3 text-orange-300" /> },
    { label: '湿度', value: device?.humidity === null || device?.humidity === undefined ? '--' : `${device.humidity.toFixed(1)} %RH`, accent: '#93c5fd', icon: <Waves className="h-3 w-3 text-blue-300" /> },
  ];

  return (
    <section className="rounded-xl border border-cyan-300/15 bg-[#06182d]/88 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300/70">GNSS receiver</p>
          <h2 className="text-sm font-semibold text-slate-100">UM980 定位数据</h2>
        </div>
        <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold ${device?.online ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' : 'border-slate-500/30 bg-slate-500/10 text-slate-400'}`}>
          {device ? (device.online ? '在线' : '离线') : '未选择'}
        </span>
      </div>
      <div className="mb-2 flex items-center gap-2">
        <DeviceSelector devices={devices} value={selectedDeviceId} onChange={onSelectDevice} />
        <span className="shrink-0 text-[10px] text-slate-500">{device ? formatDataAge(device.data_age_ms) : '--'}</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {metrics.slice(0, 3).map((metric) => <MetricCard key={metric.label} {...metric} />)}
      </div>
      <div className="mt-2 grid grid-cols-4 gap-2">
        {metrics.slice(3).map((metric) => <MetricCard key={metric.label} {...metric} />)}
      </div>
    </section>
  );
}
