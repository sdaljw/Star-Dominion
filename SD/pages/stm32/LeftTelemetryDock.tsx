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
    <aside className="pointer-events-auto absolute inset-y-0 left-0 z-20 flex h-screen max-h-screen min-h-0 w-[min(390px,calc(100vw-24px))] flex-col gap-2 overflow-hidden border-r border-cyan-400/20 bg-[#041426]/82 p-2 shadow-[12px_0_40px_rgba(0,0,0,0.28)] backdrop-blur-xl">
      <Um980Panel devices={devices} device={device} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} />
      <ImuPanel devices={devices} device={device} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} />
      <DisplacementPanel devices={devices} selectedDeviceId={selectedDeviceId} onSelectDevice={onSelectDevice} history={displacementHistory} />
    </aside>
  );
}
