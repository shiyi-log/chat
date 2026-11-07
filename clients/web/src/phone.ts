export function normalizePhoneInput(value: string, countryCode: string): string {
  const input = value.trim();
  const digits = input.replace(/\D/g, '');
  const international = input.startsWith('+') ? digits : `${countryCode.replace(/\D/g, '')}${digits}`;
  const localTestPhone = input.startsWith('+') && /^(?:4240\d|42777)$/.test(digits);

  if ((!localTestPhone && international.length < 7) || international.length > 15) {
    throw new Error('手机号位数不正确');
  }

  return `+${international}`;
}
