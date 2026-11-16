import SwiftUI
import UIKit
import UserNotifications
import Security

@MainActor final class PushService: ObservableObject {
    static let shared = PushService()
    @Published var message = "Autorisez les notifications pour recevoir les nouvelles publications."
    @Published var busy = false
    @Published var denied = false

    func startOnFirstOpen() async {
        // iOS owns the authorization prompt and remembers Allow / Don't Allow.
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        if settings.authorizationStatus == .notDetermined {
            await requestPermission()
        } else {
            await refreshPermission()
        }
    }

    func refreshPermission() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        denied = settings.authorizationStatus == .denied
        if settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional {
            UIApplication.shared.registerForRemoteNotifications()
        } else if denied {
            message = "Les notifications sont désactivées dans les réglages de l’iPhone."
            if let token = UserDefaults.standard.string(forKey: "pushToken") { await register(token: token, enabled: false) }
            UIApplication.shared.unregisterForRemoteNotifications()
        }
    }

    func requestPermission() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let allowed = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
            if allowed {
                message = "Inscription auprès d’Apple en cours…"
                UIApplication.shared.registerForRemoteNotifications()
            } else { await refreshPermission() }
        } catch { message = "L’autorisation n’a pas pu être vérifiée. Réessayez." }
    }

    func register(token: String, enabled: Bool = true) async {
        do {
            let settings = await UNUserNotificationCenter.current().notificationSettings()
            let actualEnabled = enabled && (settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional)
            var request = URLRequest(url: BiningaStyle.site.appendingPathComponent("api/push/register"), timeoutInterval: 15)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONSerialization.data(withJSONObject: ["installation": try installationSecret(), "token": token, "enabled": actualEnabled])
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw URLError(.badServerResponse) }
            UserDefaults.standard.set(token, forKey: "pushToken")
            message = actualEnabled ? "Cet iPhone est inscrit aux notifications BININGA." : "Notifications désactivées."
        } catch { message = "L’inscription au serveur n’a pas abouti. Réessayez depuis cet écran." }
    }

    private func installationSecret() throws -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "fr.yaroconsulting.bininga.push", kSecAttrAccount as String: "installation"]
        var lookup = query
        lookup[kSecReturnData as String] = true
        var item: CFTypeRef?
        let status = SecItemCopyMatching(lookup as CFDictionary, &item)
        if status == errSecSuccess, let data = item as? Data, let value = String(data: data, encoding: .utf8) { return value }
        guard status == errSecItemNotFound else { throw URLError(.cannotCreateFile) }
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { throw URLError(.unknown) }
        let secret = bytes.map { String(format: "%02x", $0) }.joined()
        var insert = query
        insert[kSecValueData as String] = Data(secret.utf8)
        insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(insert as CFDictionary, nil) == errSecSuccess else { throw URLError(.cannotCreateFile) }
        return secret
    }
}

final class PushAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { @MainActor in await PushService.shared.register(token: token) }
    }
    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Task { @MainActor in PushService.shared.message = "L’inscription Apple a échoué. Vérifiez la connexion et réessayez." }
    }
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .list, .sound])
    }
}

