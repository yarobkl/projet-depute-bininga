import SwiftUI
import UIKit

@main struct BiningaApp: App {
    @UIApplicationDelegateAdaptor(PushAppDelegate.self) private var pushDelegate
    @Environment(\.scenePhase) private var phase
    var body: some Scene { WindowGroup { PublicTabs().task { await PushService.shared.refreshPermission() }.onChange(of: phase) { _, value in if value == .active { Task { await PushService.shared.refreshPermission() } } }.preferredColorScheme(.light).tint(BiningaStyle.accent) } }
}

enum Route: Hashable { case audience, complaint, receipt(String), tracking(String) }

struct PublicNavigation<Content: View>: View {
    private let content: Content
    init(@ViewBuilder content: () -> Content) { self.content = content() }
    @State private var path: [Route] = []
    var body: some View {
        NavigationStack(path: $path) {
            content
            .navigationDestination(for: Route.self) { route in
                switch route {
                case .audience, .complaint:
                    RequestForm(complaint: route == .complaint) { code in path = [.receipt(code)] }
                case .receipt(let code):
                    List {
                        Section {
                            Text(code).font(.headline.monospaced()).textSelection(.enabled)
                            Button("Copier la référence") { UIPasteboard.general.string = code }
                            NavigationLink("Suivre ma demande", value: Route.tracking(code))
                        } header: { Text("Votre référence") } footer: { Text("Conservez cette référence pour consulter le dossier depuis le site ou l’application.") }
                    }.scrollContentBackground(.hidden).background(BiningaStyle.background).navigationTitle("Demande reçue")
                case .tracking(let code): Tracking(initial: code)
                }
            }
        }
        .background(BiningaStyle.background)
    }
}

private struct RequestForm: View {
    let complaint: Bool
    let completed: (String) -> Void
    @State private var first = ""
    @State private var last = ""
    @State private var address = ""
    @State private var phone = ""
    @State private var email = ""
    @State private var reason = ""
    @State private var busy = false
    @State private var error: String?
    var eligible: Bool { [first,last,address,phone,reason].allSatisfy { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } }
    var body: some View {
        Form {
            Section("Vos coordonnées") {
                TextField("Prénom",text:$first).textContentType(.givenName)
                TextField("Nom",text:$last).textContentType(.familyName)
                TextField("Adresse",text:$address).textContentType(.fullStreetAddress)
                TextField("Téléphone",text:$phone).keyboardType(.phonePad)
                TextField("Email (facultatif)",text:$email).textInputAutocapitalization(.never).keyboardType(.emailAddress)
            }
            Section(complaint ? "Description" : "Motif") { TextField("Votre demande", text:$reason,axis:.vertical).lineLimit(3...8) }
            if let error { Text(error).foregroundStyle(.red) }
            Button(busy ? "Envoi en cours…" : "Envoyer ma demande") {
                guard !busy else { return }; busy = true; error = nil
                Task {
                    defer { busy = false }
                    do {
                        let fields = ["prenom":first,"nom":last,"adresse":address,"telephone":phone,"email":email,"source":"bininga_audiences","objet":complaint ? "Réclamation" : "Demande d'audience",complaint ? "description" : "raison":reason]
                        completed(try await Cabinet().send(fields))
                    } catch { self.error = error.localizedDescription }
                }
            }.disabled(!eligible || busy)
        }.scrollContentBackground(.hidden).background(BiningaStyle.background).disabled(busy).navigationBarBackButtonHidden(busy).navigationTitle(complaint ? "Réclamation" : "Audience")
    }
}

private struct Tracking: View {
    @State private var code: String
    @State private var result: Dossier?
    @State private var error: String?
    @State private var busy = false
    init(initial: String) { _code = State(initialValue: initial) }
    var body: some View {
        Form {
            Section("Référence de suivi") {
                TextField("Numéro du dossier",text:$code).textInputAutocapitalization(.characters).autocorrectionDisabled()
                Button(busy ? "Recherche…" : "Consulter le suivi") { Task { await search() } }
                    .disabled(busy || code.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
            }.disabled(busy)
            if let error { Text(error).foregroundStyle(.red) }
            if let result {
                Section(result.status_label) {
                    ForEach(Array(result.steps.enumerated()), id: \.offset) { _, step in
                        Label(step.label,systemImage:step.done ? "checkmark.circle.fill" : "circle")
                        if let date = step.date, !date.isEmpty { Text(date).font(.footnote) }
                    }
                    if let note = result.decision_note, !note.isEmpty { Text(note) }
                }
            }
        }.scrollContentBackground(.hidden).background(BiningaStyle.background).navigationTitle("Mon dossier").onChange(of:code) { result = nil; error = nil }
    }
    private func search() async {
        guard !busy else { return }; busy = true; error = nil; result = nil
        defer { busy = false }
        do { result = try await Cabinet().track(code) } catch { self.error = error.localizedDescription }
    }
}
