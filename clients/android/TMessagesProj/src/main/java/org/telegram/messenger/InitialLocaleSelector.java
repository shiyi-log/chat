package org.telegram.messenger;

/** The first launch uses bundled Chinese; an existing supported user choice always wins. */
public final class InitialLocaleSelector {
    private InitialLocaleSelector() {
    }

    public static String select(String savedLanguage, boolean savedLanguageAvailable) {
        return savedLanguage != null && savedLanguageAvailable ? savedLanguage : "zh_cn";
    }
}
