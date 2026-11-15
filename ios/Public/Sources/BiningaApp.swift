import SwiftUI
import UIKit

@main struct BiningaApp: App {
    var body: some Scene { WindowGroup { Home().preferredColorScheme(.dark).tint(Color(red: 0.82, green: 0.19, blue: 0.32)) } }
}

private enum Route: Hashable { case audience, complaint, receipt(String), tracking(String) }

private struct Home: View {
    @State private var path: [Route] = []
    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section("Mes démarches") {
                    NavigationLink("Demander une audience", value: Route.audience)
                    NavigationLink("Déposer une réclamation", value: Route.complaint)
                    NavigationLink("Suivre ma demande", value: Route.tracking(""))
                }
            }.navigationTitle("BININGA")
            .navigationDestination(for: Route.self) { route in
                switch route {
                case .audience, .complaint:
                    RequestForm(complaint: route == .complaint) { code in path = [.receipt(code)] }
                case .receipt(let code):
                    List {
                        Section("Votre référence") {
                            Text(code).font(.headline.monospaced()).textSelection(.enabled)
                            Button("Copier la référence") { UIPasteboard.general.string = code }
                            NavigationLink("Suivre ma demande", value: Route.tracking(code))
                        } footer: { Text("Conservez cette référence pour consulter le dossier depuis le site ou l’application.") }
                    }.navigationTitle("Demande reçue")
                case .tracking(let code): Tracking(initial: code)
                }
            }
        }
    }
}

private struct RequestForm: View {
    let complaint: Bool
    let completed: (String) -> Void
    @State private var first = "", last = "", address = "", phone = "", email = "", reason = ""
    @State private var busy = false, error: String?
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
        }.disabled(busy).navigationBarBackButtonHidden(busy).navigationTitle(complaint ? "Réclamation" : "Audience")
    }
}

private struct Tracking: View {
    @State private var code: String
    @State private var result: Dossier?, error: String?, busy = false
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
        }.navigationTitle("Mon dossier").onChange(of:code) { result = nil; error = nil }
    }
    private func search() async {
        guard !busy else { return }; busy = true; error = nil; result = nil
        defer { busy = false }
        do { result = try await Cabinet().track(code) } catch { self.error = error.localizedDescription }
    }
}
