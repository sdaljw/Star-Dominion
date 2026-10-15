// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AlarmSettingsCard } from './AlarmSettingsCard';
import { EMPTY_ALARM_SETTINGS } from './alarmSettings';

describe('AlarmSettingsCard', () => {
  it('opens the five global threshold fields and saves blank values as disabled', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(true);
    render(<AlarmSettingsCard settings={EMPTY_ALARM_SETTINGS} alarm={null} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole('button', { name: '预警设置' }));
    expect(screen.getByRole('dialog')).toBeTruthy();

    await user.type(screen.getByRole('spinbutton', { name: '加速度 X' }), '0.8');
    await user.click(screen.getByRole('button', { name: '保存设置' }));

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
