import { Crosshair, RadioTower } from 'lucide-react';
import { DisplacementPanel } from './DisplacementPanel';
import { ImuPanel } from './ImuPanel';
import { Um980Panel } from './Um980Panel';
import type { DeviceRecord, DisplacementPoint } from './types';

interface LeftTelemetryDockProps {
  devices: DeviceRecord[];
  device: DeviceRecord | null;
  selectedDeviceId: string | null;
  onSelectDevice: (deviceId: string) => void;
  displacementHistory: DisplacementPoint[];
}

export function LeftTelemetryDock({ devices, device, selectedDeviceId, onSelectDevice, displacementHistory }: LeftTelemetryDockProps) {
  return (
    <aside className="pointer-events-auto absolute inset-y-0 left-0 z-20 flex w-[min(390px,calc(100vw-24px))] flex-col gap-3 overflow-y-auto border-r border-cyan-400/20 bg-[#041426]/82 p-3 shadow-[12px_0_40px_rgba(0,0,0,0.28)] backdrop-blur-xl">
      <div className="flex items-center justify-between px-1 py-1">
        <div className="flex items-center gap-2">
          <div className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 p-2 text-cyan-300"><Crosshair className="h-4 w-4" /></div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.25em] text-cyan-300/60">Telemetry deck</p>
            <h1 className="text-base font-semibold tracking-wide text-slate-100">边坡监测数据</h1>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-slate-400"><RadioTower className="h-3.5 w-3.5 text-emerald-300" />{devices.filter((item) => item.online).length}/{devices.length}</div>
      </div>
      <Um980Panel devices={devices} device={device} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} />
      <ImuPanel devices={devices} device={device} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} />
      <DisplacementPanel devices={devices} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} history={displacementHistory} />
    </aside>
  );
}
