import Foundation

@main struct CitizenProbe {
    static func main() async throws {
        let client = Cabinet(base: URL(string: "http://127.0.0.1:18080")!)
        let args = CommandLine.arguments
        if args[1] == "create" {
            let ref = try await client.send(["source":"bininga_audiences","objet":"Demande d'audience","prenom":"Mobile","nom":"Test","telephone":"000000000","adresse":"Adresse fictive","raison":"Test isolé"])
            print(ref)
        } else {
            let result = try await client.track(args[2])
            guard result.status_label == args[3], result.steps.first?.done == true else { throw URLError(.cannotParseResponse) }
            print(result.status_label)
        }
    }
}
