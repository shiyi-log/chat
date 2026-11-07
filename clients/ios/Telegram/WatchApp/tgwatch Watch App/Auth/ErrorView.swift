import SwiftUI

struct ErrorView: View {
    @Environment(TDClient.self) private var client
    let message: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("watch.error.title")
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.vertical, 8)
            if client.useTestDc {
                Text("watch.environment.test")
                    .font(.caption2.weight(.semibold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.yellow.opacity(0.25), in: Capsule())
                    .foregroundStyle(.yellow)
                    .accessibilityIdentifier("dcTestBadge")
            }
            Text(verbatim: message)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
        .accountSwitcherSheet(presentation: .sheet, logoutAffordance: .suppressed)
    }
}
