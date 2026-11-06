import { describe, expect, it } from 'vitest';
import { normalizePhoneInput } from '../src/phone';

describe('normalizePhoneInput', () => {
  it('adds the selected country code to a national number', () => {
    expect(normalizePhoneInput('138 0013 8000', '+86')).toBe('+8613800138000');
  });

  it('does not add the country code twice to an international number', () => {
    expect(normalizePhoneInput('+86 (138) 0013-8000', '+86')).toBe('+8613800138000');
  });

  it('rejects numbers outside the international length bounds', () => {
    expect(() => normalizePhoneInput('123', '+86')).toThrow('手机号位数不正确');
  });
});
