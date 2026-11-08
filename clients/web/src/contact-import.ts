import { normalizePhoneInput } from './phone';

type ContactId = number | string | { toString(): string };

export function normalizeContactPhone(value: string, countryCode: string): string {
  return normalizePhoneInput(value, countryCode).slice(1);
}

export function resolveImportedContactUser<T extends { id: number }>(
  result: {
    imported: Array<{ clientId: ContactId; userId: ContactId }>;
    users: T[];
  },
  clientId: ContactId,
): T | null {
  const imported = result.imported.find((contact) => String(contact.clientId) === String(clientId));
  if (!imported) return null;
  return result.users.find((user) => String(user.id) === String(imported.userId)) ?? null;
}
