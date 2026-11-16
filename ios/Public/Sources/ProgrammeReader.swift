import SwiftUI

struct ProgrammeReader: View {
    let programme: PublicContent.Programme
    var section: PublicContent.ProgrammeSection?
    private var axes: [PublicContent.Programme.Axis] { programme.axes ?? [] }
    private let symbols = ["building.columns", "briefcase", "road.lanes", "graduationcap", "cross.case", "leaf"]
    private var readingMinutes: Int {
        let text = ([programme.heroText ?? ""] + axes.map { [$0.title, $0.text ?? "", ($0.points ?? []).joined(separator: " ")].joined(separator: " ") }).joined(separator: " ")
        return max(1, Int(ceil(Double(text.split(whereSeparator: { $0.isWhitespace }).count) / 180)))
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    VStack(alignment: .leading, spacing: 14) {
                        Label(section?.titleAccent ?? "LE PROGRAMME", systemImage: "book.closed")
                            .font(.subheadline.weight(.semibold)).foregroundStyle(BiningaStyle.accent)
                        Text((programme.heroTitle ?? "Le programme").editorialPlainText)
                            .font(.largeTitle.bold()).tracking(-0.6).fixedSize(horizontal: false, vertical: true)
                            .accessibilityAddTraits(.isHeader)
                        if let intro = programme.heroText, !intro.isEmpty {
                            Text(intro.editorialPlainText).font(.title3).lineSpacing(4).foregroundStyle(BiningaStyle.secondary)
                        }
                        Label("\(axes.count) axes · \(readingMinutes) min de lecture", systemImage: "clock")
                            .font(.caption).foregroundStyle(BiningaStyle.secondary)
                    }
                    if axes.isEmpty {
                        ContentUnavailableView("Programme à venir", systemImage: "book.closed", description: Text("Le programme sera disponible ici dès sa publication."))
                    } else {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Sommaire").font(.headline).padding(.bottom, 8)
                            ForEach(axes.indices, id: \.self) { index in
                                Button {
                                    proxy.scrollTo(index, anchor: .top)
                                } label: {
                                    HStack(spacing: 12) {
                                        Text(String(format: "%02d", index + 1)).font(.caption.monospacedDigit()).foregroundStyle(BiningaStyle.secondary)
                                        Text(axes[index].title).font(.subheadline.weight(.medium)).multilineTextAlignment(.leading)
                                        Spacer(minLength: 4)
                                        Image(systemName: "arrow.down").font(.caption)
                                    }.frame(minHeight: 44)
                                }.buttonStyle(.plain).foregroundStyle(BiningaStyle.accent)
                                if index < axes.count - 1 { Divider() }
                            }
                        }.padding(20).background(BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 20))
                        ForEach(axes.indices, id: \.self) { index in
                            chapter(axes[index], index: index).id(index)
                        }
                    }
                    ShareLink(item: URL(string: "#programme", relativeTo: BiningaStyle.site)!.absoluteURL) {
                        Label("Partager le programme", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity, minHeight: 44)
                    }.buttonStyle(.bordered).tint(BiningaStyle.accent)
                }
                .padding(.horizontal, 20).padding(.top, 16).padding(.bottom, 28)
                .frame(maxWidth: 680).frame(maxWidth: .infinity)
            }
            .background(BiningaStyle.background)
            .navigationTitle("Le programme").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        ForEach(axes.indices, id: \.self) { index in
                            Button(axes[index].title) { proxy.scrollTo(index, anchor: .top) }
                        }
                    } label: { Label("Sommaire", systemImage: "list.bullet") }
                    .disabled(axes.isEmpty)
                }
            }
        }
    }

    private func chapter(_ axis: PublicContent.Programme.Axis, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Image(systemName: symbols[index % symbols.count]).font(.title2)
                    .foregroundStyle(BiningaStyle.accent).padding(14)
                    .background(BiningaStyle.accent.opacity(0.08), in: RoundedRectangle(cornerRadius: 14))
                Spacer()
                Text("AXE \(index + 1)").font(.caption.weight(.semibold)).tracking(1).foregroundStyle(BiningaStyle.secondary)
            }
            Text(axis.title).font(.title.bold()).tracking(-0.4).fixedSize(horizontal: false, vertical: true).accessibilityAddTraits(.isHeader)
            if let text = axis.text { Text(text.editorialPlainText).font(.body).lineSpacing(6).textSelection(.enabled) }
            if let points = axis.points, !points.isEmpty {
                VStack(alignment: .leading, spacing: 16) {
                    ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "checkmark.circle").foregroundStyle(BiningaStyle.accent).accessibilityHidden(true)
                            Text(point.editorialPlainText).font(.body).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }.padding(18).frame(maxWidth: .infinity, alignment: .leading)
                    .background(BiningaStyle.surface, in: RoundedRectangle(cornerRadius: 16))
            }
            Divider().padding(.top, 8)
        }.padding(.top, 8)
    }
}
