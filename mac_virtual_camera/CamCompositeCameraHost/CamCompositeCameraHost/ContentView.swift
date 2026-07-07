//
//  ContentView.swift
//  CamCompositeCameraHost
//
import SwiftUI
import SystemExtensions
import Combine

struct ContentView: View {
    @StateObject private var extensionManager = CameraExtensionManager()

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "video.badge.checkmark")
                .imageScale(.large)
                .font(.system(size: 42))

            Text("CamComposite Camera Host")
                .font(.title2)
                .fontWeight(.semibold)

            Text(extensionManager.statusMessage)
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .frame(maxWidth: 420)

            Button("Activate Camera Extension") {
                extensionManager.activate()
            }
            .buttonStyle(.borderedProminent)

            Button("Deactivate Camera Extension") {
                extensionManager.deactivate()
            }
            .buttonStyle(.bordered)
        }
        .padding(32)
        .frame(width: 520, height: 320)
    }
}

final class CameraExtensionManager: NSObject, ObservableObject, OSSystemExtensionRequestDelegate {
    @Published var statusMessage = "Ready to activate the CamComposite camera extension."

    private let extensionBundleIdentifier =
        "com.ashishkarigar.CamCompositeCameraHost.CamCompositeCameraExtension"

    func activate() {
        statusMessage = "Requesting camera extension activation..."

        let request = OSSystemExtensionRequest.activationRequest(
            forExtensionWithIdentifier: extensionBundleIdentifier,
            queue: .main
        )

        request.delegate = self
        OSSystemExtensionManager.shared.submitRequest(request)
    }

    func deactivate() {
        statusMessage = "Requesting camera extension deactivation..."

        let request = OSSystemExtensionRequest.deactivationRequest(
            forExtensionWithIdentifier: extensionBundleIdentifier,
            queue: .main
        )

        request.delegate = self
        OSSystemExtensionManager.shared.submitRequest(request)
    }

    func request(
        _ request: OSSystemExtensionRequest,
        actionForReplacingExtension existing: OSSystemExtensionProperties,
        withExtension extension: OSSystemExtensionProperties
    ) -> OSSystemExtensionRequest.ReplacementAction {
        statusMessage = "Replacing existing camera extension..."
        return .replace
    }

    func requestNeedsUserApproval(_ request: OSSystemExtensionRequest) {
        statusMessage = "macOS needs approval. Open System Settings and approve the CamComposite camera extension."
    }

    func request(
        _ request: OSSystemExtensionRequest,
        didFinishWithResult result: OSSystemExtensionRequest.Result
    ) {
        switch result {
        case .completed:
            statusMessage = "Camera extension activated."
        case .willCompleteAfterReboot:
            statusMessage = "Camera extension will finish activation after reboot."
        @unknown default:
            statusMessage = "Camera extension finished with an unknown result."
        }
    }

    func request(
        _ request: OSSystemExtensionRequest,
        didFailWithError error: Error
    ) {
        statusMessage = "Camera extension request failed: \(error.localizedDescription)"
    }
}

#Preview {
    ContentView()
}
