import SwiftUI

private struct CareerPosition: PreferenceKey {
    static var defaultValue: [Int: CGFloat] = [:]
    static func reduce(value: inout [Int: CGFloat], nextValue: () -> [Int: CGFloat]) {
        value.merge(nextValue(), uniquingKeysWith: { _, new in new })
    }
}

struct CareerTimeline: View {
    let steps: [PublicContent.Career]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var current = 0
    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 24) {
                Text("Son parcours").font(.largeTitle.bold()).accessibilityAddTraits(.isHeader)
                Text("Les étapes de son engagement").font(.subheadline).foregroundStyle(BiningaStyle.secondary)
                ForEach(Array(steps.enumerated()), id: \.offset) { index, step in
                    HStack(alignment: .top, spacing: 16) {
                        VStack(spacing: 0) {
                            Circle().fill(index <= current ? BiningaStyle.accent : BiningaStyle.border)
                                .frame(width: 12, height: 12)
                                .padding(.top, 6)
                            Rectangle().fill(BiningaStyle.border).frame(width: 2)
                        }.frame(width: 16).accessibilityHidden(true)
                        VStack(alignment: .leading, spacing: 12) {
                            if let year = step.year {
                                Text(year).font(.subheadline.weight(.semibold)).foregroundStyle(BiningaStyle.accent)
                            }
                            Text(step.title.editorialPlainText).font(.title2.bold())
                                .fixedSize(horizontal: false, vertical: true).accessibilityAddTraits(.isHeader)
                            if let text = step.desc { Text(text.editorialPlainText).font(.body).lineSpacing(5) }
                        }
                        .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                        .background(BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 20))
                    }
                    .background {
                        GeometryReader { geometry in
                            Color.clear.preference(key: CareerPosition.self,
                                value: [index: geometry.frame(in: .named("career-scroll")).midY])
                        }
                    }
                    .scrollTransition(.interactive, axis: .vertical) { content, phase in
                        content.opacity(reduceMotion || phase.isIdentity ? 1 : 0.8)
                            .offset(y: reduceMotion || phase.isIdentity ? 0 : 8)
                    }
                }
                if steps.isEmpty { ContentUnavailableView("Parcours indisponible", systemImage: "person.text.rectangle") }
            }
            .padding(.leading, 20).padding(.trailing, 32).padding(.vertical, 20)
            .frame(maxWidth: 700).frame(maxWidth: .infinity)
        }
        .coordinateSpace(name: "career-scroll")
        .onPreferenceChange(CareerPosition.self) { positions in
            if let closest = positions.min(by: { abs($0.value - 240) < abs($1.value - 240) }) {
                current = closest.key
            }
        }
        .overlay(alignment: .trailing) {
            GeometryReader { geometry in
                ZStack(alignment: .top) {
                    Capsule().fill(BiningaStyle.border)
                    Capsule().fill(LinearGradient(colors: [BiningaStyle.accent.opacity(0.35), BiningaStyle.accent], startPoint: .top, endPoint: .bottom))
                        .frame(height: geometry.size.height * CGFloat(current + 1) / CGFloat(max(steps.count, 1)))
                        .animation(reduceMotion ? nil : .easeOut(duration: 0.25), value: current)
                }
            }.frame(width: 3).padding(.vertical, 24).padding(.trailing, 10).allowsHitTesting(false).accessibilityHidden(true)
        }
        .background(BiningaStyle.background)
        .navigationTitle("Son parcours").navigationBarTitleDisplayMode(.inline)
    }
}
