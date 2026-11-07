import SwiftUI

struct ClosedView: View {
    var body: some View {
        VStack(spacing: 8) {
            Text("watch.session.loggedOut")
                .font(.headline)
            Text("watch.session.relaunch")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .accountSwitcherSheet(presentation: .sheet, logoutAffordance: .suppressed)
    }
}
