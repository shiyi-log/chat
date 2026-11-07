import Foundation
import TDShim

func humanMessage(_ error: Swift.Error) -> String {
    if let tdErr = error as? TDError {
        return humanMessageForTdLibCode(tdErr.message)
    }
    return (error as? LocalizedError)?.errorDescription ?? WatchCopy.localized("watch.error.unknown")
}

/// Maps a TDLib error from `checkAuthenticationPassword` to one of three
/// user-facing messages for the 2-step verification screen. Unlike
/// `humanMessage`, unknown codes collapse to a generic message rather than
/// passing the raw code through.
func passwordSubmitErrorMessage(_ error: Swift.Error) -> String {
    guard let tdErr = error as? TDError else {
        return WatchCopy.localized("watch.error.unknown")
    }
    if tdErr.message == "PASSWORD_HASH_INVALID" {
        return WatchCopy.localized("watch.error.incorrectPassword")
    }
    if let flood = floodWaitMessage(tdErr.message) {
        return flood
    }
    return WatchCopy.localized("watch.error.unknown")
}

private func humanMessageForTdLibCode(_ code: String) -> String {
    switch code {
    case "PHONE_NUMBER_INVALID":
        return WatchCopy.localized("watch.error.phoneInvalid")
    case "PHONE_CODE_INVALID":
        return WatchCopy.localized("watch.error.codeInvalid")
    case "PHONE_CODE_EXPIRED":
        return WatchCopy.localized("watch.error.codeExpired")
    case "FIRSTNAME_INVALID":
        return WatchCopy.localized("watch.error.firstNameInvalid")
    case "LASTNAME_INVALID":
        return WatchCopy.localized("watch.error.lastNameInvalid")
    default:
        return floodWaitMessage(code) ?? WatchCopy.localized("watch.error.unknown")
    }
}

/// Formats a `FLOOD_WAIT_<seconds>` code into a wait message, or `nil` if the
/// code is not a flood-wait code.
private func floodWaitMessage(_ code: String) -> String? {
    guard code.hasPrefix("FLOOD_WAIT_") else { return nil }
    let suffix = code.dropFirst("FLOOD_WAIT_".count)
    if let seconds = Int(suffix), seconds > 0 {
        return WatchCopy.format("watch.error.floodWait", seconds)
    }
    return WatchCopy.localized("watch.error.floodWaitLater")
}
