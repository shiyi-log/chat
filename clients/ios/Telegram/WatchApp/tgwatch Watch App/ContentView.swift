import SwiftUI

struct ContentView: View {
    @Environment(TDClient.self) private var client

    var body: some View {
        switch client.authState {
        case .starting:
            LoadingView(label: "watch.state.starting")
        case .waitTdlibParameters:
            LoadingView(label: "watch.state.configuring")
        case .waitPhoneNumber:
            LoadingView(label: "watch.state.preparingQR")
        case .waitCode:
            ErrorView(message: WatchCopy.localized("watch.auth.unexpectedSMS"))
        case .waitOtherDeviceConfirmation(let link):
            QrLoginView(link: link)
        case .waitPassword(let info):
            PasswordEntryView(info: info)
        case .ready:
            if let store = client.chatList {
                ChatListView(store: store)
            } else {
                LoadingView(label: "watch.state.loading")
            }
        case .loggingOut:
            LoadingView(label: "watch.state.loggingOut")
        case .closed:
            ClosedView()
        case .failed(let message):
            ErrorView(message: message)
        }
    }
}
