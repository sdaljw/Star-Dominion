export interface AlarmDisplacement {
  E: number;
  N: number;
  U: number;
}

export interface ParsedAlarmPayload extends AlarmDisplacement {
  level: string;
  score: number;
  D: number;
  V: number;
  tilt: number;
  accDyn: number;
  q: number;
  sats: number;
}

const NUM_RE = '[-+]?\\d+(?:\\.\\d+)?';

export function parseAlarmPayload(payload: string): ParsedAlarmPayload | null {
  const level = payload.match(/level=(\w+)/)?.[1];
  if (!level) return null;

  const get = (key: string) => {
    const match = payload.match(new RegExp(`${key}=(${NUM_RE})`));
    return match ? Number(match[1]) : 0;
  };

  return {
    level,
    score: get('score'),
    D: get('D'),
    V: get('V'),
    E: get('E'),
    N: get('N'),
    U: get('U'),
    tilt: get('tilt'),
    accDyn: get('accDyn'),
    q: Number(payload.match(/q=(\d+)/)?.[1] || 0),
    sats: Number(payload.match(/sats=(\d+)/)?.[1] || 0),
  };
}

export function alarmToDisplacementPoint(
  alarm: AlarmDisplacement,
  time: string,
): { time: string; x: number; y: number; z: number } {
  return { time, x: alarm.E / 1000, y: alarm.N / 1000, z: alarm.U / 1000 };
}
