// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AlarmSettingsCard } from './AlarmSettingsCard';
import { EMPTY_ALARM_SETTINGS } from './alarmSettings';

describe('AlarmSettingsCard', () => {
  afterEach(() => cleanup());

  it('keeps close and confirm actions visible in a viewport-sized dialog', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(true);
    render(<AlarmSettingsCard settings={EMPTY_ALARM_SETTINGS} alarm={null} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole('button', { name: '预警设置' }));
    const dialog = screen.getByRole('dialog');

    expect(dialog.className).toContain('max-h-[calc(100dvh-2rem)]');
    expect(dialog.className).toContain('overflow-hidden');
    expect(screen.getByRole('button', { name: '关闭' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '取消' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '确定' })).toBeTruthy();

    await user.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    await user.click(screen.getByRole('button', { name: '预警设置' }));
    await user.click(screen.getByRole('button', { name: '关闭' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    await user.click(screen.getByRole('button', { name: '预警设置' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens the five global threshold fields and saves blank values as disabled', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(true);
    render(<AlarmSettingsCard settings={EMPTY_ALARM_SETTINGS} alarm={null} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole('button', { name: '预警设置' }));
    expect(screen.getByRole('dialog')).toBeTruthy();

    await user.type(screen.getByRole('spinbutton', { name: '加速度 X' }), '0.8');
    await user.click(screen.getByRole('button', { name: '确定' }));

    expect(onSave).toHaveBeenCalledWith({
      acc_x: 0.8,
      acc_y: null,
      angle_x: null,
      angle_y: null,
      angle_z: null,
    });
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
