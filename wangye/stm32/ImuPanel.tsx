import { Activity } from 'lucide-react';
import { DeviceSelector } from './DeviceSelector';
import type { DeviceRecord, ImuData } from './types';
import { EMPTY_IMU } from './telemetry';

interface ImuPanelProps {
  devices: DeviceRecord[];
  device: DeviceRecord | null;
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
}

const AXES = ['X', 'Y', 'Z'] as const;

function ImuValue({ label, value, unit, color, progress }: { label: string; value: number; unit: string; color: string; progress: number }) {
  return (
    <div className="rounded-lg border border-cyan-300/10 bg-[#0a2139]/90 p-2">
      <div className="text-[9px] font-semibold tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-[13px] font-semibold" style={{ color }}>
        {value.toFixed(3)} <span className="text-[9px] text-slate-500">{unit}</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${Math.min(progress, 100)}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export function ImuPanel({ devices, device, selectedDeviceId, onSelectDevice }: ImuPanelProps) {
  const imu: ImuData = device?.imu || EMPTY_IMU;

  return (
    <section className="rounded-xl border border-cyan-300/15 bg-[#06182d]/88 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="mb-2 flex items-center gap-2">
        <Activity className="h-4 w-4 text-violet-300" />
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-violet-300/65">Inertial unit</p>
          <h2 className="text-sm font-semibold text-slate-100">IMU 惯性数据</h2>
        </div>
      </div>
      <div className="mb-2">
        <DeviceSelector devices={devices} value={selectedDeviceId} onChange={onSelectDevice} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {AXES.map((axis, index) => (
          <ImuValue key={`acc-${axis}`} label={`加速度 ${axis}`} value={imu.acc[index]} unit="g" color="#c4b5fd" progress={Math.abs(imu.acc[index]) * 100} />
        ))}
      </div>
      <div className="mt-2 grid grid-cols-3 gap-2">
        {AXES.map((axis, index) => {
          const angle = imu.angle[index];
          const isAlert = index < 2 && Math.abs(angle) > 5;
          return (
            <ImuValue key={`angle-${axis}`} label={`姿态角 ${axis}`} value={angle} unit="°" color={isAlert ? '#fb7185' : '#fbbf24'} progress={Math.abs(angle) / 360 * 100} />
          );
        })}
      </div>
    </section>
  );
}
