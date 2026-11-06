export function normalizePhoneInput(value: string, countryCode: string): string {
  const input = value.trim();
  const digits = input.replace(/\D/g, '');
  const international = input.startsWith('+') ? digits : `${countryCode.replace(/\D/g, '')}${digits}`;

  if (international.length < 7 || international.length > 15) {
    throw new Error('手机号位数不正确');
  }

  return `+${international}`;
}
