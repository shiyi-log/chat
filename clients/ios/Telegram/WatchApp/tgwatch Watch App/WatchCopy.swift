import Foundation

enum WatchCopy {
    static func localized(_ key: String) -> String {
        NSLocalizedString(key, bundle: .main, comment: "")
    }

    static func format(_ key: String, _ arguments: CVarArg...) -> String {
        String(format: localized(key), locale: Locale.current, arguments: arguments)
    }
}
