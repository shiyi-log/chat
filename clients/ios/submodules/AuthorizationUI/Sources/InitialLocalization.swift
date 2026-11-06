public enum InitialLocalization {
    public static func code(for preferredLanguages: [String]) -> String {
        return code(for: preferredLanguages, existingLanguageCode: nil)
    }

    public static func code(for preferredLanguages: [String], existingLanguageCode: String?) -> String {
        if let existingLanguageCode = existingLanguageCode, !existingLanguageCode.isEmpty {
            return existingLanguageCode
        }

        guard let firstLanguage = preferredLanguages.first else {
            return "zh-hans"
        }

        let components = firstLanguage.lowercased().split(whereSeparator: { $0 == "-" || $0 == "_" })
        guard components.first == "zh" else {
            return "zh-hans"
        }

        if components.contains("hant") || components.contains("tw") || components.contains("hk") || components.contains("mo") {
            return "zh-hant"
        }
        return "zh-hans"
    }

    public static func introResourceCode(for localizationCode: String) -> String {
        let components = localizationCode.lowercased().split(whereSeparator: { $0 == "-" || $0 == "_" })
        guard components.first == "zh" else {
            return "en"
        }

        if components.contains("hant") || components.contains("tw") || components.contains("hk") || components.contains("mo") {
            return "zh-Hant"
        }
        return "zh-Hans"
    }

    public static func startButtonTitle(for localizationCode: String) -> String {
        switch introResourceCode(for: localizationCode) {
        case "zh-Hans":
            return "开始聊天"
        case "zh-Hant":
            return "開始聊天"
        default:
            return "Start Messaging"
        }
    }
}
