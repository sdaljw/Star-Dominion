import { Terminal, Trash2 } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { DeviceSelector } from './DeviceSelector';
import type { DeviceRecord, LogEntry } from './types';
import { formatLogTime } from './telemetry';

interface NmeaPanelProps {
  devices: DeviceRecord[];
  selectedDeviceId: string | null;
  logs: LogEntry[];
  onSelectDevice: (deviceId: string) => void;
  onClear: () => void;
}

export function NmeaPanel({ devices, selectedDeviceId, logs, onSelectDevice, onClear }: NmeaPanelProps) {
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = logContainerRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [logs]);

  return (
    <section className="flex min-h-[250px] flex-1 flex-col overflow-hidden rounded-xl border border-cyan-300/15 bg-[#06182d]/88 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="border-b border-cyan-300/10 bg-[#0a2139]/75 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2"><Terminal className="h-4 w-4 text-cyan-300" /><div><p className="text-[10px] uppercase tracking-[0.2em] text-cyan-300/65">Raw stream</p><h2 className="text-sm font-semibold text-slate-100">NMEA 监视器</h2></div></div>
          <button type="button" onClick={onClear} className="rounded-md p-1.5 text-slate-500 transition hover:bg-rose-400/10 hover:text-rose-300" title="清空当前设备日志"><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
        <DeviceSelector devices={devices} value={selectedDeviceId} onChange={onSelectDevice} />
      </div>
      <div ref={logContainerRef} className="min-h-0 flex-1 space-y-1 overflow-y-auto p-3 font-mono text-[10px]">
        {logs.length === 0 && <p className="py-6 text-center text-xs text-slate-600">暂无当前设备数据</p>}
        {logs.map((entry) => (
          <div key={`${entry.deviceId}-${entry.seq}`} className="break-all border-l border-cyan-400/40 pl-2 leading-tight text-slate-300">
            <span className="mr-1 text-cyan-300/60">[{formatLogTime(entry.timestamp)}]</span>{entry.text}
          </div>
        ))}
      </div>
    </section>
  );
}
