import Foundation

struct Publication: Decodable, Hashable {
    let title: String
    var subtitle: String?, desc: String?, text1: String?, text2: String?, quote: String?
    var image: String?, date: String?, source: String?, sourceUrl: String?
    var day: String?, month: String?, year: String?, chip: String?, cat: String?
    var bodyText: String { [subtitle, desc, text1, quote, text2].compactMap { $0 }.joined(separator: "\n\n") }
    var displayDate: String? {
        if let date, !date.isEmpty { return date }
        let parts = [day, month, year].compactMap { $0 }.filter { !$0.isEmpty }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }
    var chronology: Date? {
        EditorialDate.parse([day, month, year].compactMap { $0 }.joined(separator: " "))
            ?? EditorialDate.parse(date ?? "") ?? EditorialDate.parse(chip ?? "")
    }
    var isTerrain: Bool {
        let text = [title, subtitle, desc, cat, date].compactMap { $0 }.joined(separator: " ").folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "fr"))
        return ["ewo", "cuvette", "lebankaya"].contains { text.contains($0) }
    }
    static func recentFirst(_ items: [Publication]) -> [Publication] {
        items.enumerated().sorted {
            let a = $0.element.chronology ?? .distantPast
            let b = $1.element.chronology ?? .distantPast
            return a == b ? $0.offset < $1.offset : a > b
        }.map(\.element)
    }
}

enum EditorialDate {
    static func parse(_ raw: String) -> Date? {
        let text = raw.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: Locale(identifier: "fr")).replacingOccurrences(of: ".", with: "")
        let words = text.components(separatedBy: CharacterSet.alphanumerics.inverted).filter { !$0.isEmpty }
        guard let yi = words.firstIndex(where: { $0.count == 4 && (1900...2100).contains(Int($0) ?? 0) }), let year = Int(words[yi]) else { return nil }
        let months = ["jan":1,"janv":1,"janvier":1,"feb":2,"fev":2,"fevr":2,"fevrier":2,"mar":3,"mars":3,"avr":4,"avril":4,"mai":5,"jun":6,"juin":6,"jul":7,"juil":7,"juillet":7,"aou":8,"aout":8,"sep":9,"sept":9,"septembre":9,"oct":10,"octobre":10,"nov":11,"novembre":11,"dec":12,"decembre":12]
        var month = 1, day = 1
        if let mi = words.indices.first(where: { months[words[$0]] != nil }), let m = months[words[mi]] {
            month = m
            if mi > 0, let d = Int(words[mi-1]), (1...31).contains(d) { day = d }
        } else if yi + 2 < words.count, let m = Int(words[yi+1]), let d = Int(words[yi+2]), (1...12).contains(m), (1...31).contains(d) {
            month = m; day = d
        }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let parts = DateComponents(year: year, month: month, day: day)
        guard let result = calendar.date(from: parts), calendar.component(.day, from: result) == day else { return nil }
        return result
    }
}

struct PublicContent: Decodable {
    struct News: Decodable { var slides: [Publication]?, vedettes: [Publication]?, cards: [Publication]? }
    struct Programme: Decodable {
        struct Axis: Decodable { let title: String; var text: String?, points: [String]? }
        var heroTitle: String?, heroText: String?, axes: [Axis]?
    }
    struct Hero: Decodable { var firstName: String?, lastName: String?, role: String?, subtitle: String? }
    struct About: Decodable { var intro: String?, paragraphs: [String]? }
    struct Career: Decodable { var year: String?; let title: String; var desc: String? }
    struct Gallery: Decodable {
        struct Photo: Decodable, Hashable { var image: String?, alt: String?, title: String?, subtitle: String? }
        var grid: [Photo]?, slides: [Photo]?
    }
    struct ProgrammeSection: Decodable { var titleAccent: String?, subtitle: String? }
    let actus: News
    let programme: Programme
    var hero: Hero?, about: About?, parcours: [Career]?, gallery: Gallery?, programmeSection: ProgrammeSection?
    var fullName: String {
        let name = [hero?.firstName, hero?.lastName].compactMap { $0 }.joined(separator: " ")
        return name.isEmpty ? "Ange Aimé Wilfrid BININGA" : name
    }
    var allNews: [Publication] {
        // Keep original articles intact; remove exact repeated titles only.
        var titles = Set<String>()
        return Publication.recentFirst(((actus.vedettes ?? []) + (actus.slides ?? []) + (actus.cards ?? [])).filter {
            titles.insert($0.title.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()).inserted
        })
    }
    var terrain: [Publication] { allNews.filter(\.isTerrain) }
}

extension String {
    var editorialPlainText: String {
        replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .replacingOccurrences(of: "&amp;", with: "&")
            .replacingOccurrences(of: "&nbsp;", with: " ")
            .replacingOccurrences(of: "&#39;", with: "’")
    }
}
