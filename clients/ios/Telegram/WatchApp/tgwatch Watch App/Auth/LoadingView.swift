import SwiftUI

struct LoadingView: View {
    let label: String
    var body: some View {
        VStack(spacing: 8) {
            ProgressView()
            Text(verbatim: WatchCopy.localized(label))
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .accountSwitcherSheet(presentation: .sheet, logoutAffordance: .suppressed)
    }
}
