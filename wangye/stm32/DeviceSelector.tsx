import type { DeviceRecord } from './types';

interface DeviceSelectorProps {
  devices: DeviceRecord[];
  value: string | null;
  onChange: (deviceId: string) => void;
  label?: string;
}

export function DeviceSelector({ devices, value, onChange, label = '监测设备' }: DeviceSelectorProps) {
  const availableDevices = devices.filter((device) => device.online || device.device_id === value);

  return (
    <label className="flex min-w-0 flex-1 items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
      <span className="shrink-0">{label}</span>
      <select
        value={value ?? ''}
        onChange={(event) => {
          if (event.target.value) onChange(event.target.value);
        }}
        className="min-w-0 flex-1 rounded-md border border-cyan-400/25 bg-[#081b31]/95 px-2 py-1.5 text-xs font-semibold tracking-normal text-cyan-50 outline-none transition focus:border-cyan-300 focus:ring-1 focus:ring-cyan-300/40"
      >
        <option value="">{availableDevices.length ? '选择设备' : '等待在线设备'}</option>
        {availableDevices.map((device) => (
          <option key={device.device_id} value={device.device_id}>
            设备 {device.device_id} · {device.online ? '在线' : '离线'}
          </option>
        ))}
      </select>
    </label>
  );
}
