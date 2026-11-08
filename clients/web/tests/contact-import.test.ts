import { describe, expect, it } from 'vitest';
import { normalizeContactPhone, resolveImportedContactUser } from '../src/contact-import';

describe('normalizeContactPhone', () => {
  it('sends international contacts in the digits-only format used by the local server', () => {
    expect(normalizeContactPhone('+1 (202) 555-0103', '+86')).toBe('12025550103');
    expect(normalizeContactPhone('+42777', '+86')).toBe('42777');
  });
});

describe('resolveImportedContactUser', () => {
  it('selects the user linked to the submitted contact when results contain other users', () => {
    const target = { id: 42, firstName: 'Lin' };

    expect(resolveImportedContactUser({
      imported: [{ clientId: '1', userId: 42 }],
      users: [{ id: 7, firstName: 'Other' }, target],
    }, 1)).toBe(target);
  });

  it('does not select an unrelated user when the submitted phone was not imported', () => {
    expect(resolveImportedContactUser({
      imported: [],
      users: [{ id: 7, firstName: 'Other' }],
    }, 1)).toBeNull();
  });
});
