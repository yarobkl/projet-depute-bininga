import Foundation

struct Dossier: Decodable {
    struct Step: Decodable { let label: String; let done: Bool; let date: String? }
    let status_label: String
    let steps: [Step]
    let decision_note: String?
}

struct Cabinet {
    var base = URL(string: "https://projet-depute-bininga.vercel.app")!
    var session: URLSession = .shared

    struct Receipt: Decodable { let ok: Bool; let tracking_code: String? }
    struct Failure: LocalizedError { let errorDescription: String? }

    func request<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200..<300).contains(http.statusCode) else {
            let message = http.statusCode == 404 ? "Référence introuvable." : "Le service est indisponible (\(http.statusCode))."
            throw Failure(errorDescription: message)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    func send(_ fields: [String: String]) async throws -> String {
        var req = URLRequest(url: base.appendingPathComponent("api/contact"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(fields)
        let reply: Receipt = try await request(req)
        guard reply.ok, let code = reply.tracking_code, !code.isEmpty else {
            throw Failure(errorDescription: "Le serveur n’a pas confirmé le numéro de suivi.")
        }
        return code
    }

    func track(_ code: String) async throws -> Dossier {
        let url = base.appendingPathComponent("api/dossier").appending(queryItems: [
            URLQueryItem(name: "code", value: code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased())
        ])
        return try await request(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
    }
}
