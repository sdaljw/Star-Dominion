import { Send, Terminal } from 'lucide-react';
import { useState } from 'react';
import { DeviceSelector } from './DeviceSelector';
import type { DeviceRecord } from './types';

interface CommandPanelProps {
  devices: DeviceRecord[];
  selectedDeviceId: string | null;
  selectedDevice: DeviceRecord | null;
  onSelectDevice: (deviceId: string) => void;
  onSendCommand: (value: string, label?: string) => Promise<boolean>;
}

const PRESET_COMMANDS = [
  ['0', '重设当前 RTK 固定解位置为参考点'],
  ['1', '系统初始化'],
  ['2', '流动站配置'],
  ['3', '开启 GPGGA 1 秒输出'],
  ['4', '开启 GPGGA 0.5 秒输出'],
  ['5', '关闭 GPGGA'],
  ['6', '开启星历'],
  ['7', '关闭星历'],
  ['8', '开启原始数据'],
  ['9', '关闭原始数据'],
] as const;

export function CommandPanel({ devices, selectedDeviceId, selectedDevice, onSelectDevice, onSendCommand }: CommandPanelProps) {
  const [command, setCommand] = useState('');
  const canSend = Boolean(selectedDevice?.online);

  const send = async () => {
    const value = command.trim();
    if (!value || !canSend) return;
    if (await onSendCommand(value, value)) setCommand('');
  };

  return (
    <section className="rounded-xl border border-cyan-300/15 bg-[#06182d]/88 p-3 shadow-[0_10px_30px_rgba(0,0,0,0.24)] backdrop-blur-xl">
      <div className="mb-2 flex items-center gap-2">
        <Send className="h-4 w-4 text-cyan-300" />
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-300/65">Remote control</p>
          <h2 className="text-sm font-semibold text-slate-100">指令下发</h2>
        </div>
      </div>
      <div className="mb-2">
        <DeviceSelector devices={devices} value={selectedDeviceId} onChange={onSelectDevice} />
      </div>
      <div className="mb-2 rounded-lg border border-cyan-300/10 bg-[#0a2139]/75 px-2.5 py-2 text-[10px] text-slate-400">
        当前目标：<span className="font-mono text-cyan-200">{selectedDevice ? `设备 ${selectedDevice.device_id}` : '未选择设备'}</span>
        <span className={`ml-2 ${canSend ? 'text-emerald-300' : 'text-slate-500'}`}>{canSend ? '可发送' : '设备离线'}</span>
      </div>
      <select
        value=""
        disabled={!canSend}
        onChange={(event) => {
          const selected = PRESET_COMMANDS.find(([value]) => value === event.target.value);
          if (!selected) return;
          void onSendCommand(selected[0], `${selected[0]}: ${selected[1]}`);
          event.currentTarget.value = '';
        }}
        className="mb-2 w-full rounded-lg border border-cyan-300/15 bg-[#0a2139] px-2.5 py-2 text-xs text-slate-200 outline-none focus:border-cyan-300/60 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="">选择预设指令</option>
        {PRESET_COMMANDS.map(([value, label]) => <option key={value} value={value}>{value}：{label}</option>)}
      </select>
      <textarea
        value={command}
        onChange={(event) => setCommand(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            void send();
          }
        }}
        disabled={!canSend}
        placeholder={canSend ? '输入自定义指令，回车发送…' : '选择在线设备后可发送'}
        className="h-16 w-full resize-none rounded-lg border border-cyan-300/15 bg-[#0a2139] p-2.5 font-mono text-xs text-slate-200 outline-none placeholder:text-slate-600 focus:border-cyan-300/60 disabled:cursor-not-allowed disabled:opacity-50"
      />
      <button onClick={() => void send()} disabled={!command.trim() || !canSend} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-cyan-300/30 bg-cyan-400/15 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-400/25 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800/60 disabled:text-slate-600">
        <Terminal className="h-3.5 w-3.5" />发送指令
      </button>
    </section>
  );
}
