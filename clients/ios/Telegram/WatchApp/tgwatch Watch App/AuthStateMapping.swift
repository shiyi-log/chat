import Foundation
import TDShim

func mapAuthState(_ s: AuthorizationState) -> AuthState {
    switch s {
    case .authorizationStateWaitTdlibParameters:
        return .waitTdlibParameters
    case .authorizationStateWaitPhoneNumber:
        return .waitPhoneNumber
    case .authorizationStateWaitCode(let payload):
        return .waitCode(info: codeInfo(from: payload.codeInfo))
    case .authorizationStateReady:
        return .ready
    case .authorizationStateLoggingOut:
        return .loggingOut
    case .authorizationStateClosing:
        return .loggingOut
    case .authorizationStateClosed:
        return .closed
    case .authorizationStateWaitPassword(let payload):
        return .waitPassword(info: PasswordInfo(
            hint: payload.passwordHint,
            hasRecoveryEmail: payload.hasRecoveryEmailAddress
        ))
    case .authorizationStateWaitEmailAddress, .authorizationStateWaitEmailCode:
        return .failed(WatchCopy.localized("watch.auth.emailUnsupported"))
    case .authorizationStateWaitOtherDeviceConfirmation(let payload):
        return .waitOtherDeviceConfirmation(link: payload.link)
    case .authorizationStateWaitRegistration:
        return .failed(WatchCopy.localized("watch.auth.registrationUnsupported"))
    case .authorizationStateWaitPremiumPurchase:
        return .failed(WatchCopy.localized("watch.auth.premiumUnsupported"))
    case .unsupported:
        return .failed(WatchCopy.localized("watch.auth.stateUnsupported"))
    }
}

private func codeInfo(from info: AuthenticationCodeInfo) -> CodeInfo {
    CodeInfo(
        phoneNumber: info.phoneNumber,
        codeLength: codeLength(from: info.type),
        typeDescription: typeDescription(from: info.type)
    )
}

private func codeLength(from type: AuthenticationCodeType) -> Int? {
    switch type {
    case .authenticationCodeTypeSms(let p): return p.length
    case .authenticationCodeTypeTelegramMessage(let p): return p.length
    case .authenticationCodeTypeCall(let p): return p.length
    case .authenticationCodeTypeMissedCall(let p): return p.length
    default: return nil
    }
}

private func typeDescription(from type: AuthenticationCodeType) -> String {
    switch type {
    case .authenticationCodeTypeSms: return "SMS"
    case .authenticationCodeTypeTelegramMessage:
        return WatchCopy.localized("watch.auth.type.appMessage")
    case .authenticationCodeTypeCall:
        return WatchCopy.localized("watch.auth.type.phoneCall")
    case .authenticationCodeTypeMissedCall:
        return WatchCopy.localized("watch.auth.type.missedCall")
    case .authenticationCodeTypeFlashCall:
        return WatchCopy.localized("watch.auth.type.flashCall")
    case .authenticationCodeTypeFragment:
        return WatchCopy.localized("watch.auth.type.fragment")
    case .authenticationCodeTypeFirebaseAndroid, .authenticationCodeTypeFirebaseIos:
        return WatchCopy.localized("watch.auth.type.appPush")
    case .authenticationCodeTypeSmsWord, .authenticationCodeTypeSmsPhrase:
        return "SMS"
    case .unsupported:
        return WatchCopy.localized("watch.auth.type.code")
    }
}
