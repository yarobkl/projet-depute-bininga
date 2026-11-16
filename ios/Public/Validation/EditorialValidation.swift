
func require(_ condition: @autoclosure () -> Bool, _ message: String) {
    guard condition() else { fatalError(message) }
}
let march = EditorialDate.parse("📅 9 mars 2026 · Axe Lebankaya")!
let february = EditorialDate.parse("18 Février 2026, Paris")!
let december = EditorialDate.parse("12 Décembre 2025")!
require(march > february && february > december, "French dates must sort newest first")
require(EditorialDate.parse("2026-03-09") == march, "ISO dates must work")
require(EditorialDate.parse("31 février 2026") == nil, "Impossible dates must be rejected")
require(EditorialDate.parse("Portrait officiel") == nil, "An undated portrait must not get an invented date")
let card = Publication(title: "Action à Ewo", day: "09", month: "Mars", year: "2026")
require(card.chronology == march && card.isTerrain, "Structured dates and terrain classification must work")
let undated = Publication(title: "Sans date")
let previous = Publication(title: "Ancienne", date: "12 déc. 2025")
let sorted = Publication.recentFirst([undated, previous, card])
require(sorted.map(\.title) == [card.title, previous.title, undated.title], "Undated articles belong last")
let data = try Data(contentsOf: URL(fileURLWithPath: "Sources/PublicContent.json"))
let bundled = try JSONDecoder().decode(PublicContent.self, from: data)
require(!bundled.fullName.isEmpty, "Full name must decode")
require(!(bundled.programme.axes ?? []).isEmpty, "Programme must decode")
require(!(bundled.parcours ?? []).isEmpty, "Career must decode")
require(!(bundled.gallery?.slides ?? []).isEmpty, "Gallery must decode")
print("Editorial validation passed: dates, stable chronology, native programme, career and gallery")
